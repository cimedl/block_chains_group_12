// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {IHealthRegistry} from "./interfaces/IHealthRegistry.sol";
import {IConsentReward} from "./interfaces/IConsentReward.sol";

contract ConsentManager {
    enum ReasonCode {
        NO_CONSENT,
        EXPIRED,
        REVOKED,
        UNKNOWN_RECORD,
        UNREGISTERED_REQUESTER,
        GRANTED,
        PATIENT_NOT_VERIFIED
    }

    struct ConsentRecord {
        address patient;
        address requester;
        uint256 recordId;
        string category;
        uint256 grantId;
        uint256 startTime;
        uint256 endTime;
        bool revokedStatus;
    }

    event AccessDecision(
        uint256 indexed requestId,
        address indexed patient,
        address indexed requester,
        uint256 recordId,
        uint256 grantId,
        uint256 timestamp,
        bool allowed,
        ReasonCode reason
    );

    event ConsentGranted(
        uint256 indexed grantId,
        address indexed patient,
        address indexed requester,
        uint256 recordId
    );

    event ConsentRevoked(
        uint256 indexed grantId,
        address indexed patient,
        address indexed requester,
        uint256 recordId
    );

    uint256 public currentGrantId = 1;
    uint256 public currentRequestId = 1;
    mapping(uint256 => ConsentRecord) public consentGrants;
    mapping(uint256 => mapping(address => uint256)) public latestGrantId;

    address public immutable healthRegistry;
    address public immutable consentReward;

    constructor(address registryAddress, address rewardAddress) {
        require(registryAddress.code.length > 0, "Registry must be a contract");
        require(rewardAddress.code.length > 0, "Reward must be a contract");
        healthRegistry = registryAddress;
        consentReward = rewardAddress;
    }

    function grantAccess(
        uint256 recordId,
        string memory category,
        address requester,
        uint256 durationDays
    ) external returns (uint256) {
        IHealthRegistry registry = IHealthRegistry(healthRegistry);
        IHealthRegistry.Record memory record = registry.getRecord(recordId);

        require(msg.sender == record.patient, "UNAUTHORIZED: Not the record owner");
        require(requester != address(0), "INVALID: Requester cannot be zero address");
        require(durationDays >= 1 && durationDays <= 365, "INVALID: Duration must be 1-365 days");
        require(registry.isVerified(record.patient, IHealthRegistry.Role.Patient), "Patient not verified");
        require(isVerifiedRequester(requester), "Requester not verified");
        require(keccak256(bytes(category)) == keccak256(bytes(record.recordType)), "INVALID: Record category mismatch");

        ConsentRecord memory previous = consentGrants[latestGrantId[recordId][requester]];
        require(
            previous.patient == address(0) || previous.revokedStatus || block.timestamp >= previous.endTime,
            "INVALID: Consent already active"
        );

        uint256 thisGrantId = currentGrantId;
        consentGrants[thisGrantId] = ConsentRecord({
            patient: msg.sender,
            requester: requester,
            recordId: recordId,
            category: category,
            grantId: thisGrantId,
            startTime: block.timestamp,
            endTime: block.timestamp + (durationDays * 1 days),
            revokedStatus: false
        });
        latestGrantId[recordId][requester] = thisGrantId;
        currentGrantId++;

        // A duplicate reward returns false, but a valid regrant still succeeds.
        // If issuance reverts, the entire grant and its counters roll back.
        IConsentReward(consentReward).rewardConsent(recordId, requester);
        emit ConsentGranted(thisGrantId, msg.sender, requester, recordId);
        return thisGrantId;
    }

    function revokeAccess(uint256 recordId, uint256 grantId) external {
        ConsentRecord storage grant = consentGrants[grantId];
        require(grant.patient != address(0), "INVALID: Unknown grant");
        require(grant.recordId == recordId, "INVALID: Grant record mismatch");
        IHealthRegistry.Record memory record = IHealthRegistry(healthRegistry).getRecord(recordId);
        require(msg.sender == record.patient && msg.sender == grant.patient, "UNAUTHORIZED: Not the record owner");
        require(!grant.revokedStatus, "INVALID: Consent already revoked");

        // Owners may withdraw consent even while their verification is suspended.
        grant.revokedStatus = true;
        emit ConsentRevoked(grantId, grant.patient, grant.requester, recordId);
    }

    // IDs are allocated here, rather than trusted from a requester.
    // Ordinary denied decisions complete successfully so their audit logs survive.
    function requestAccess(uint256 recordId, uint256 grantId) external returns (uint256) {
        (address patient, uint256 matchingGrantId, ReasonCode reason) = permissionDecision(grantId, msg.sender, recordId);
        uint256 requestId = currentRequestId;
        currentRequestId++;
        emit AccessDecision(
            requestId,
            patient,
            msg.sender,
            recordId,
            matchingGrantId,
            block.timestamp,
            reason == ReasonCode.GRANTED,
            reason
        );
        return requestId;
    }

    // P3 must also bind its receipt to this same grant and authenticated requester.
    function checkPermission(uint256 grantId, address requester, uint256 recordId) external view returns (bool) {
        (, , ReasonCode reason) = permissionDecision(grantId, requester, recordId);
        return reason == ReasonCode.GRANTED;
    }

    function isVerifiedRequester(address requester) internal view returns (bool) {
        IHealthRegistry registry = IHealthRegistry(healthRegistry);
        return registry.isVerified(requester, IHealthRegistry.Role.Doctor)
            || registry.isVerified(requester, IHealthRegistry.Role.Researcher);
    }

    function permissionDecision(uint256 grantId, address requester, uint256 recordId)
        internal view returns (address patient, uint256 matchingGrantId, ReasonCode reason)
    {
        IHealthRegistry registry = IHealthRegistry(healthRegistry);
        if (!registry.recordExists(recordId)) {
            return (address(0), 0, ReasonCode.UNKNOWN_RECORD);
        }
        IHealthRegistry.Record memory record = registry.getRecord(recordId);
        patient = record.patient;
        ConsentRecord memory grant = consentGrants[grantId];
        bool matches = grant.patient == patient && grant.requester == requester && grant.recordId == recordId;
        if (matches) {
            matchingGrantId = grant.grantId;
        }

        if (!isVerifiedRequester(requester)) {
            return (patient, matchingGrantId, ReasonCode.UNREGISTERED_REQUESTER);
        }
        if (!registry.isVerified(patient, IHealthRegistry.Role.Patient)) {
            return (patient, matchingGrantId, ReasonCode.PATIENT_NOT_VERIFIED);
        }
        if (!matches) {
            return (patient, 0, ReasonCode.NO_CONSENT);
        }
        if (grant.revokedStatus) {
            return (patient, matchingGrantId, ReasonCode.REVOKED);
        }
        if (block.timestamp >= grant.endTime) {
            return (patient, matchingGrantId, ReasonCode.EXPIRED);
        }
        return (patient, matchingGrantId, ReasonCode.GRANTED);
    }
}
