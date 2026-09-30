// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

// P2 and P3 can use this interface without copying the registry code.
interface IHealthRegistry {
    enum Role { None, Patient, Doctor, Researcher }

    struct User {
        bytes32 identityHash;
        Role role;
        bool verified;
    }

    struct Record {
        address patient;
        bytes32 recordHash;
        string recordType;
    }

    function getUser(address account) external view returns (User memory);
    function getRecord(uint256 recordId) external view returns (Record memory);
    function isVerified(address account, Role role) external view returns (bool);
}
