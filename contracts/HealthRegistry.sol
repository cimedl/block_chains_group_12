// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {IHealthRegistry} from "./interfaces/IHealthRegistry.sol";

contract HealthRegistry is IHealthRegistry {
    address public immutable admin;
    uint256 public nextRecordId = 1;

    // private data stays off-chain
    mapping(address => User) private users;
    mapping(uint256 => Record) private records;

    event UserRegistered(address indexed account, Role role, bytes32 identityHash);
    event IdentityUpdated(address indexed account, bytes32 identityHash);
    event VerificationChanged(address indexed account, bool verified);
    event RecordRegistered(
        uint256 indexed recordId,
        address indexed patient,
        bytes32 recordHash,
        string recordType
    );

    modifier onlyAdmin() {
        require(msg.sender == admin, "Only admin");
        _;
    }

    constructor(address adminAddress) {
        require(adminAddress != address(0), "Invalid admin");
        admin = adminAddress;
    }

    function registerUser(bytes32 identityHash, Role role) external {
        require(users[msg.sender].role == Role.None, "Already registered");
        require(identityHash != bytes32(0), "Empty identity hash");
        require(role != Role.None, "Choose a role");

        users[msg.sender] = User(identityHash, role, false);
        emit UserRegistered(msg.sender, role, identityHash);
    }

    function updateIdentity(bytes32 identityHash) external {
        require(users[msg.sender].role != Role.None, "Register first");
        require(identityHash != bytes32(0), "Empty identity hash");

        users[msg.sender].identityHash = identityHash;
        // identity changes need verification again
        users[msg.sender].verified = false;
        emit IdentityUpdated(msg.sender, identityHash);
        emit VerificationChanged(msg.sender, false);
    }

    function setVerification(address account, bool verified) external onlyAdmin {
        require(users[account].role != Role.None, "Unknown user");
        users[account].verified = verified;
        emit VerificationChanged(account, verified);
    }

    function registerRecord(bytes32 recordHash, string calldata recordType)
        external returns (uint256)
    {
        require(isVerified(msg.sender, Role.Patient), "Verified patient required");
        require(recordHash != bytes32(0), "Empty record hash");
        require(bytes(recordType).length > 0, "Empty record type");
        require(bytes(recordType).length <= 64, "Record type too long");

        uint256 recordId =nextRecordId;
        nextRecordId += 1;
        records[recordId] = Record(msg.sender, recordHash, recordType);
        emit RecordRegistered(recordId, msg.sender, recordHash, recordType);
        return recordId;
    }

    function getUser(address account) external view override returns (User memory) {
        require(users[account].role != Role.None, "Unknown user");
        return users[account];
    }

    function getRecord(uint256 recordId) external view override returns (Record memory) {
        require(records[recordId].patient != address(0), "Unknown record");
        return records[recordId];
    }

    function recordExists(uint256 recordId) external view override returns (bool) {
        return records[recordId].patient != address(0);
    }

    function isVerified(address account, Role role) public view override returns (bool) {
        if (role == Role.None) {
            return false;
        }
        return users[account].role == role && users[account].verified;
    }

}
