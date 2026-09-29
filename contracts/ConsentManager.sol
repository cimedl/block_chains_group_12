pragma solidity ^0.8.20;

interface IHealthRegistry {
    function getRecordOwner(bytes32 recordId) external view returns (address);
}

interface IConsentReward {
    function issueReward(
        address patient,
        address requester,
        string category
        ) external;
}


contract ConsentManager {
    enum ReasonCode {
        NO_CONSENT,
        EXPIRED,
        REVOKED,
        UNKNOWN_RECORD,
        UNREGISTERED_REQUESTER,
        GRANTED
    }

    struct ConsentRecord {
        address patient;
        address requester;
        bytes32 recordId;
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
        bytes32 recordId,
        uint256 grantId,
        uint256 timestamp,
        bool allowed,
        ReasonCode reason
    );

    event ConsentGranted(
        uint256 indexed grantId,
        address indexed patient,
        address indexed requester,
        bytes32 recordId
    );


    uint256 public currentGrantId = 1;
    mapping(uint256 => ConsentRecord) public consentGrants;


    address public healthRegistry;
    address public consentReward;

    constructor(address _registry, address _reward) {
        healthRegistry = _registry;
        consentReward = _reward;
    }

    function grantAccess(
        bytes32 recordId,
        string memory category,
        address requester,
        uint256 durationDays
        ) external {
            address trueOwner = IHealthRegistry(healthRegistry).getRecordOwner(recordId);
            
            require(msg.sender == trueOwner, "UNAUTHORIZED: Not the record owner");
            require(requester != address(0), "INVALID: Requester cannot be zero address");
            require(durationDays >= 1 && durationDays <= 365, "INVALID: Duration must be 1=365 days");

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
            currentGrantId++;

            IConsentReward(consentReward).issueReward(
                msg.sender, 
                requester, 
                category);

            emit ConsentGranted(
                thisGrantId,
                msg.sender,
                requester,
                recordId
            );
        }

    function revokeAccess(
        bytes32 recordId,
        uint256 grantId
        ) external {
            address trueOwner = IHealthRegistry(healthRegistry).getRecordOwner(recordId);
            require(msg.sender == trueOwner, "UNAUTHORIZED: Not the record owner");

            consentGrants[grantId].revokedStatus = true;
    }


    function requestAccess(
        bytes32 recordId,
        uint256 requestId,
        uint256 grantId
        ) external {

        ConsentRecord memory grant = consentGrants[grantId];

        if (grant.patient == address(0)) {
            emit AccessDecision(
                requestId, 
                grant.patient, 
                msg.sender, 
                recordId, 
                grantId, 
                block.timestamp, 
                false, 
                ReasonCode.NO_CONSENT);
            return;
        }

        if (grant.revokedStatus == true) {
            emit AccessDecision(
                requestId, 
                grant.patient, 
                msg.sender, 
                recordId, 
                grantId, 
                block.timestamp, 
                false, 
                ReasonCode.REVOKED);
            return;
        }

        if (block.timestamp >= grant.endTime) {
            emit AccessDecision(
                requestId, 
                grant.patient, 
                msg.sender, 
                recordId, 
                grantId, 
                block.timestamp, 
                false, 
                ReasonCode.EXPIRED);
            return;
        }

        if (grant.requester != msg.sender) {
            emit AccessDecision(
                requestId, 
                grant.patient, 
                msg.sender, 
                recordId, 
                grantId, 
                block.timestamp, 
                false, 
                ReasonCode.NO_CONSENT);
            return;
        }

        if (grant.recordId != recordId) {
            emit AccessDecision(
                requestId, 
                grant.patient, 
                msg.sender, 
                recordId, 
                grantId, 
                block.timestamp, 
                false, 
                ReasonCode.UNKNOWN_RECORD);
            return;
        }


        emit AccessDecision(
            requestId, 
            grant.patient, 
            msg.sender, 
            recordId, 
            grantId, 
            block.timestamp, 
            true, 
            ReasonCode.GRANTED);
    }

    // Used to check if the patient hasn't revoked access while the request for access was being processed
    function checkPermission(
        uint256 grantId,
        address requester,
        bytes32 recordId
    ) external view returns (bool) {
        ConsentRecord memory grant = consentGrants[grantId];

        if (grant.patient == address(0)) return false;
        if (grant.revokedStatus == true) return false;
        if (block.timestamp >= grant.endTime) return false;
        if (grant.requester != requester) return false;
        if (grant.recordId != recordId) return false;

        return true;
    }
}