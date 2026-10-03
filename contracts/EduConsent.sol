// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

// Students choose who can see their diploma, transcript or certificate.
contract EduConsent {
    // These are numbered 0, 1 and 2. The Python code uses the same numbers.
    enum DataType { Diploma, Transcript, Certificate }

    struct Identity {
        bytes32 attributesHash;
        bool registered;
    }

    struct Consent {
        uint64 expiresAt;
        bool active;
    }

    // Save each student's identity hash and the hashes of their files.
    mapping(address => Identity) public identities;
    mapping(address => mapping(DataType => bytes32)) public dataHashes;
    // Look up consent using: student -> requester -> type of file.
    mapping(address => mapping(address => mapping(DataType => Consent))) public consents;

    // Points are a reward for sharing. They cannot be sent to another account.
    mapping(address => uint256) public rewardBalance;
    mapping(address => mapping(address => mapping(DataType => bool))) public rewarded;

    event IdentityRegistered(address indexed student, bytes32 attributesHash);
    event IdentityUpdated(address indexed student, bytes32 attributesHash);
    event DataPublished(address indexed student, DataType indexed dataType, bytes32 dataHash);
    event ConsentGranted(
        address indexed student,
        address indexed requester,
        DataType indexed dataType,
        uint64 expiresAt
    );
    event ConsentRevoked(
        address indexed student,
        address indexed requester,
        DataType indexed dataType
    );
    event RewardEarned(address indexed student, uint256 amount);
    event AccessLogged(
        address indexed student,
        address indexed requester,
        DataType indexed dataType,
        bool allowed,
        uint256 timestamp,
        bytes32 dataHash
    );

    // Reuse this check in functions that need a registered student.
    modifier registeredStudent() {
        require(identities[msg.sender].registered, "Register first");
        _;
    }

    function register(bytes32 attributesHash) external {
        require(!identities[msg.sender].registered, "Already registered");
        require(attributesHash != bytes32(0), "Empty hash");
        // msg.sender is the account calling this function.
        identities[msg.sender] = Identity(attributesHash, true);
        emit IdentityRegistered(msg.sender, attributesHash);
    }

    function updateIdentity(bytes32 attributesHash) external registeredStudent {
        require(attributesHash != bytes32(0), "Empty hash");
        identities[msg.sender].attributesHash = attributesHash;
        emit IdentityUpdated(msg.sender, attributesHash);
    }

    function publishData(DataType dataType, bytes32 dataHash) external registeredStudent {
        require(dataHash != bytes32(0), "Empty hash");
        dataHashes[msg.sender][dataType] = dataHash;
        emit DataPublished(msg.sender, dataType, dataHash);
    }

    function grantConsent(address requester, DataType dataType, uint256 durationDays)
        external registeredStudent
    {
        require(requester != address(0) && requester != msg.sender, "Invalid requester");
        require(durationDays >= 1 && durationDays <= 365, "Use 1 to 365 days");
        require(dataHashes[msg.sender][dataType] != bytes32(0), "Publish data first");

        uint64 expiresAt = uint64(block.timestamp + durationDays * 1 days);
        consents[msg.sender][requester][dataType] = Consent(expiresAt, true);
        emit ConsentGranted(msg.sender, requester, dataType, expiresAt);

        // Only reward this permission once, even if it is granted again later.
        if (!rewarded[msg.sender][requester][dataType]) {
            rewarded[msg.sender][requester][dataType] = true;
            rewardBalance[msg.sender] += 10;
            emit RewardEarned(msg.sender, 10);
        }
    }

    function revokeConsent(address requester, DataType dataType) external registeredStudent {
        require(consents[msg.sender][requester][dataType].active, "No active consent");
        consents[msg.sender][requester][dataType].active = false;
        emit ConsentRevoked(msg.sender, requester, dataType);
    }

    function hasConsent(address student, address requester, DataType dataType)
        public view returns (bool)
    {
        Consent memory consent = consents[student][requester][dataType];

        if (!identities[student].registered) {
            return false;
        }
        if (dataHashes[student][dataType] == bytes32(0)) {
            return false;
        }
        if (!consent.active) {
            return false;
        }
        if (block.timestamp >= consent.expiresAt) {
            return false;
        }

        return true;
    }

    function requestAccess(address student, DataType dataType) external returns (bool) {
        bool allowed = hasConsent(student, msg.sender, dataType);
        // Log denied attempts too. A revert would remove this event.
        emit AccessLogged(
            student,
            msg.sender,
            dataType,
            allowed,
            block.timestamp,
            dataHashes[student][dataType]
        );
        return allowed;
    }
}
