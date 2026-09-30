// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {HealthRegistry} from "../contracts/HealthRegistry.sol";
import {IHealthRegistry} from "../contracts/interfaces/IHealthRegistry.sol";
import {TestHelper} from "./TestHelper.sol";

contract HealthRegistryTest is TestHelper {
    HealthRegistry registry;
    address patient = address(0x101);
    address doctor = address(0x102);
    address researcher = address(0x103);
    address other = address(0x104);
    bytes32 identityHash = sha256("fake identity and salt");
    bytes32 fileHash = sha256("fake stored file");

    event RecordRegistered(uint256 indexed recordId, address indexed patient, bytes32 recordHash, string recordType);
    event VerificationChanged(address indexed account, bool verified);

    function setUp() public {
        registry = new HealthRegistry(address(this));
        vm.prank(patient);
        registry.registerUser(identityHash, IHealthRegistry.Role.Patient);
    }

    function addRecord() internal returns (uint256) {
        registry.setVerification(patient, true);
        vm.prank(patient);
        return registry.registerRecord(fileHash, "Blood_Test_Panel");
    }

    function testRegistrationStartsUnverified() public view {
        IHealthRegistry.User memory user = registry.getUser(patient);
        require(user.identityHash == identityHash, "Wrong hash");
        require(user.role == IHealthRegistry.Role.Patient, "Wrong role");
        require(!user.verified, "Should need verification");
    }

    function testDoctorAndResearcherCanRegister() public {
        vm.prank(doctor);
        registry.registerUser(identityHash, IHealthRegistry.Role.Doctor);
        vm.prank(researcher);
        registry.registerUser(identityHash, IHealthRegistry.Role.Researcher);
        require(registry.getUser(doctor).role == IHealthRegistry.Role.Doctor, "Wrong doctor role");
        require(registry.getUser(researcher).role == IHealthRegistry.Role.Researcher, "Wrong researcher role");
    }

    function testCannotRegisterTwiceOrChangeRole() public {
        vm.expectRevert(bytes("Already registered"));
        vm.prank(patient);
        registry.registerUser(identityHash, IHealthRegistry.Role.Doctor);
    }

    function testEmptyIdentityRejected() public {
        vm.expectRevert(bytes("Empty identity hash"));
        vm.prank(other);
        registry.registerUser(bytes32(0), IHealthRegistry.Role.Patient);
    }

    function testNoneRoleRejected() public {
        vm.expectRevert(bytes("Choose a role"));
        vm.prank(other);
        registry.registerUser(identityHash, IHealthRegistry.Role.None);
    }

    function testAdminCanVerifyAndRemoveVerification() public {
        registry.setVerification(patient, true);
        require(registry.isVerified(patient, IHealthRegistry.Role.Patient), "Not verified");
        require(!registry.isVerified(patient, IHealthRegistry.Role.Doctor), "Wrong role accepted");
        registry.setVerification(patient, false);
        require(!registry.isVerified(patient, IHealthRegistry.Role.Patient), "Still verified");
    }

    function testPatientCannotVerifyThemselves() public {
        vm.expectRevert(bytes("Only admin"));
        vm.prank(patient);
        registry.setVerification(patient, true);
    }

    function testCannotVerifyUnknownUser() public {
        vm.expectRevert(bytes("Unknown user"));
        registry.setVerification(other, true);
    }

    function testIdentityChangeNeedsVerificationAgain() public {
        registry.setVerification(patient, true);
        bytes32 newHash = sha256("changed fake identity");
        vm.prank(patient);
        registry.updateIdentity(newHash);
        IHealthRegistry.User memory user = registry.getUser(patient);
        require(user.identityHash == newHash, "Hash not changed");
        require(!user.verified, "Must verify again");
    }

    function testIdentityChangeDoesNotChangeAnotherUser() public {
        vm.prank(other);
        registry.registerUser(identityHash, IHealthRegistry.Role.Patient);
        bytes32 otherHash = sha256("other identity");
        vm.prank(other);
        registry.updateIdentity(otherHash);
        require(registry.getUser(patient).identityHash == identityHash, "Changed someone else");
    }

    function testUnregisteredCannotUpdateIdentity() public {
        vm.expectRevert(bytes("Register first"));
        vm.prank(other);
        registry.updateIdentity(identityHash);
    }

    function testEmptyIdentityUpdateRejected() public {
        vm.expectRevert(bytes("Empty identity hash"));
        vm.prank(patient);
        registry.updateIdentity(bytes32(0));
    }

    function testVerifiedPatientCanRegisterRecord() public {
        uint256 id = addRecord();
        IHealthRegistry.Record memory record = registry.getRecord(id);
        require(id == 1, "IDs start at one");
        require(record.patient == patient, "Wrong owner");
        require(record.recordHash == fileHash, "Wrong file hash");
        require(keccak256(bytes(record.recordType)) == keccak256("Blood_Test_Panel"), "Wrong type");
    }

    function testMultipleRecordsOfSameTypeHaveSeparateIds() public {
        uint256 first = addRecord();
        bytes32 secondHash = sha256("second file");
        vm.prank(patient);
        uint256 second = registry.registerRecord(secondHash, "Blood_Test_Panel");
        require(second == first + 1, "IDs should differ");
        require(registry.getRecord(first).recordHash == fileHash, "Old record overwritten");
    }

    function testUnverifiedPatientCannotRegisterRecord() public {
        vm.expectRevert(bytes("Verified patient required"));
        vm.prank(patient);
        registry.registerRecord(fileHash, "Blood_Test_Panel");
    }

    function testVerifiedDoctorCannotRegisterPatientRecord() public {
        vm.prank(doctor);
        registry.registerUser(identityHash, IHealthRegistry.Role.Doctor);
        registry.setVerification(doctor, true);
        vm.expectRevert(bytes("Verified patient required"));
        vm.prank(doctor);
        registry.registerRecord(fileHash, "Blood_Test_Panel");
    }

    function testEmptyRecordHashRejected() public {
        registry.setVerification(patient, true);
        vm.expectRevert(bytes("Empty record hash"));
        vm.prank(patient);
        registry.registerRecord(bytes32(0), "Blood_Test_Panel");
    }

    function testEmptyRecordTypeRejected() public {
        registry.setVerification(patient, true);
        vm.expectRevert(bytes("Empty record type"));
        vm.prank(patient);
        registry.registerRecord(fileHash, "");
    }

    function testLongRecordTypeRejected() public {
        registry.setVerification(patient, true);
        vm.expectRevert(bytes("Record type too long"));
        vm.prank(patient);
        registry.registerRecord(fileHash, string(new bytes(65)));
    }

    function testUnknownRecordRejected() public {
        vm.expectRevert(bytes("Unknown record"));
        registry.getRecord(0);
    }

    function testUnknownUserRejected() public {
        vm.expectRevert(bytes("Unknown user"));
        registry.getUser(other);
    }

    function testUnknownUserIsNotVerified() public view {
        require(!registry.isVerified(other, IHealthRegistry.Role.Patient), "Unknown user verified");
        require(!registry.isVerified(other, IHealthRegistry.Role.None), "None role verified");
    }

    function testRecordEventIncludesOwnerAndHash() public {
        registry.setVerification(patient, true);
        vm.expectEmit(true, true, false, true);
        emit RecordRegistered(1, patient, fileHash, "Blood_Test_Panel");
        vm.prank(patient);
        registry.registerRecord(fileHash, "Blood_Test_Panel");
    }

    function testVerificationEvent() public {
        vm.expectEmit(true, false, false, true);
        emit VerificationChanged(patient, true);
        registry.setVerification(patient, true);
    }

    function testZeroAdminRejected() public {
        vm.expectRevert(bytes("Invalid admin"));
        new HealthRegistry(address(0));
    }
}
