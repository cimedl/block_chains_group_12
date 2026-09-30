// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

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

    constructor(address _registry, address _reward) {
        require(_registry.code.length > 0, "Registry must be a contract");
        require(_reward.code.length > 0, "Reward must be a contract");
        healthRegistry = _registry;
        consentReward = _reward;
    }

    function grantAccess(
        uint256 recordId,
        string memory category,
        address requester,
        uint256 durationDays
        ) external returns (uint256) {
            IHealthRegistry.Record memory record = IHealthRegistry(healthRegistry).getRecord(recordId);
            address trueOwner = record.patient;

            require(msg.sender == trueOwner, "UNAUTHORIZED: Not the record owner");
            require(requester != address(0), "INVALID: Requester cannot be zero address");
            require(durationDays >= 1 && durationDays <= 365, "INVALID: Duration must be 1-365 days");

            require(IHealthRegistry(healthRegistry).isVerified(trueOwner, IHealthRegistry.Role.Patient), "Patient not verified");
            require(
                IHealthRegistry(healthRegistry).isVerified(requester, IHealthRegistry.Role.Doctor)
                    || IHealthRegistry(healthRegistry).isVerified(requester, IHealthRegistry.Role.Researcher),
                "Requester not verified"
            );
            require(keccak256(bytes(category)) == keccak256(bytes(record.recordType)), "INVALID: Record category mismatch");

            {
                ConsentRecord memory previous = consentGrants[latestGrantId[recordId][requester]];
                require(
                    previous.patient == address(0) || previous.revokedStatus || block.timestamp >= previous.endTime,
                    "INVALID: Consent already active"
                );
            }

            uint256 start = block.timestamp;
            uint256 end = start + (durationDays * 1 days);

            uint256 thisGrantId = currentGrantId;

            ConsentRecord memory newConsentRecord = ConsentRecord({
                patient: msg.sender,
                requester: requester,
                recordId: recordId,
                category: category,
                grantId: thisGrantId,
                startTime: start,
                endTime: end,
                revokedStatus: false
            });

            consentGrants[thisGrantId] = newConsentRecord;
            latestGrantId[recordId][requester] = thisGrantId;
            currentGrantId++;

            // Duplicate reward eligibility returns false; valid regrant still succeeds.
            // A reward error reverts the entire grant and its counters.
            IConsentReward(consentReward).rewardConsent(
                recordId,
                requester);

            emit ConsentGranted(
                thisGrantId,
                msg.sender,
                requester,
                recordId
            );
            return thisGrantId;
        }

    function revokeAccess(
        uint256 recordId,
        uint256 grantId
        ) external {
            ConsentRecord memory grant = consentGrants[grantId];
            require(grant.patient != address(0), "INVALID: Unknown grant");
            require(grant.recordId == recordId, "INVALID: Grant record mismatch");
            address trueOwner = IHealthRegistry(healthRegistry).getRecord(recordId).patient;
            require(msg.sender == trueOwner && msg.sender == grant.patient, "UNAUTHORIZED: Not the record owner");

            require(!grant.revokedStatus, "INVALID: Consent already revoked");

            // Suspended owners must still be able to withdraw consent.
            consentGrants[grantId].revokedStatus = true;
            emit ConsentRevoked(
                grantId,
                grant.patient,
                grant.requester,
                recordId
            );
    }


    function requestAccess(
        uint256 recordId,
        uint256 grantId
        ) external returns (uint256) {

        ConsentRecord memory grant = consentGrants[grantId];
        uint256 requestId = currentRequestId;
        currentRequestId++;

        if (!IHealthRegistry(healthRegistry).recordExists(recordId)) {
            emit AccessDecision(
                requestId,
                address(0),
                msg.sender,
                recordId,
                0,
                block.timestamp,
                false,
                ReasonCode.UNKNOWN_RECORD);
            return requestId;
        }

        IHealthRegistry.Record memory record = IHealthRegistry(healthRegistry).getRecord(recordId);
        uint256 matchingGrantId = 0;
        if (grant.patient == record.patient && grant.requester == msg.sender && grant.recordId == recordId) {
            matchingGrantId = grantId;
        }

        if (!IHealthRegistry(healthRegistry).isVerified(msg.sender, IHealthRegistry.Role.Doctor)
            && !IHealthRegistry(healthRegistry).isVerified(msg.sender, IHealthRegistry.Role.Researcher)) {
            emit AccessDecision(
                requestId,
                record.patient,
                msg.sender,
                recordId,
                matchingGrantId,
                block.timestamp,
                false,
                ReasonCode.UNREGISTERED_REQUESTER);
            return requestId;
        }

        if (!IHealthRegistry(healthRegistry).isVerified(record.patient, IHealthRegistry.Role.Patient)) {
            emit AccessDecision(
                requestId,
                record.patient,
                msg.sender,
                recordId,
                matchingGrantId,
                block.timestamp,
                false,
                ReasonCode.PATIENT_NOT_VERIFIED);
            return requestId;
        }

        if (grant.patient == address(0) || grant.patient != record.patient) {
            emit AccessDecision(
                requestId,
                record.patient,
                msg.sender,
                recordId,
                matchingGrantId,
                block.timestamp,
                false,
                ReasonCode.NO_CONSENT);
            return requestId;
        }

        if (grant.requester != msg.sender) {
            emit AccessDecision(
                requestId,
                record.patient,
                msg.sender,
                recordId,
                matchingGrantId,
                block.timestamp,
                false,
                ReasonCode.NO_CONSENT);
            return requestId;
        }

        if (grant.recordId != recordId) {
            emit AccessDecision(
                requestId,
                record.patient,
                msg.sender,
                recordId,
                matchingGrantId,
                block.timestamp,
                false,
                ReasonCode.NO_CONSENT);
            return requestId;
        }


        if (grant.revokedStatus == true) {
            emit AccessDecision(
                requestId,
                record.patient,
                msg.sender,
                recordId,
                matchingGrantId,
                block.timestamp,
                false,
                ReasonCode.REVOKED);
            return requestId;
        }

        if (block.timestamp >= grant.endTime) {
            emit AccessDecision(
                requestId,
                record.patient,
                msg.sender,
                recordId,
                matchingGrantId,
                block.timestamp,
                false,
                ReasonCode.EXPIRED);
            return requestId;
        }

        emit AccessDecision(
            requestId,
            record.patient,
            msg.sender,
            recordId,
            matchingGrantId,
            block.timestamp,
            true,
            ReasonCode.GRANTED);
        return requestId;
    }

    // Used to check if the patient hasn't revoked access while the request for access was being processed
    function checkPermission(
        uint256 grantId,
        address requester,
        uint256 recordId
    ) external view returns (bool) {
        ConsentRecord memory grant = consentGrants[grantId];

        if (!IHealthRegistry(healthRegistry).recordExists(recordId)) return false;
        IHealthRegistry.Record memory record = IHealthRegistry(healthRegistry).getRecord(recordId);
        if (!IHealthRegistry(healthRegistry).isVerified(record.patient, IHealthRegistry.Role.Patient)) return false;
        bool doctor = IHealthRegistry(healthRegistry).isVerified(requester, IHealthRegistry.Role.Doctor);
        bool researcher = IHealthRegistry(healthRegistry).isVerified(requester, IHealthRegistry.Role.Researcher);
        if (!doctor && !researcher) return false;
        if (grant.patient != record.patient) return false;

        if (grant.patient == address(0)) return false;
        if (grant.revokedStatus == true) return false;
        if (block.timestamp >= grant.endTime) return false;
        if (grant.requester != requester) return false;
        if (grant.recordId != recordId) return false;

        return true;
    }
}
