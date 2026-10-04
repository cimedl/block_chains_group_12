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
    bytes32 identityHash = sha256("identity and salt");
    bytes32 fileHash = sha256("fake stored file");

    event RecordRegistered(uint256 indexed recordId, address indexed patient, bytes32 recordHash, string recordType);
    event VerificationChanged(address indexed account, bool verified);

    function setUp() public {
        registry = new HealthRegistry(address(this));
        vm.prank(patient);
        registry.registerUser(identityHash,IHealthRegistry.Role.Patient);
    }

    function addRecord() internal returns (uint256) {
        registry.setVerification(patient, true);
        vm.prank(patient);
        return registry.registerRecord(fileHash, "Blood_Test_Panel");
    }

   function test_PatientRegistration() public {
    IHealthRegistry.User memory user = registry.getUser(patient);
    require(user.identityHash == identityHash, "identity hashes are not the same");
    require(user.role == IHealthRegistry.Role.Patient, "Roles do not match");
    require(user.verified == false , "new user should be unverified");
   }

   function test_AdminCanVerifyPatient() public {
    registry.setVerification(patient, true);

    IHealthRegistry.User memory user = registry.getUser(patient);

    require(user.verified == true, "new user should be verified");

    require(user.identityHash == identityHash, "identity hashes should be the same");

    require(user.role == IHealthRegistry.Role.Patient, "Roles should match");
   }

   function test_PatientCanRegisterRecord() public {

    registry.setVerification(patient,true);

    vm.prank(patient);

    uint256 recordId = registry.registerRecord(fileHash,"blood test panel");

    IHealthRegistry.Record memory record = registry.getRecord(recordId);

    require(recordId == 1, "record must correspond to the proper id ");

    require(record.patient == patient, "patient must match");
    require(record.recordHash == fileHash,"File hashes must match");

    require(keccak256(bytes(record.recordType)) == keccak256(bytes("blood test panel")), "types must match");

   }

   function test_UnverifiedPatientCannotRegisterRecord() public {
    uint256 recordId = registry.nextRecordId();

    vm.expectRevert(bytes("Verified patient required"));

    vm.prank(patient);

    registry.registerRecord(fileHash, "blood test panel");
    require(registry.nextRecordId() == recordId, "failed registration consumed a record ID");

   }

   function test_PatientCannotRegisterTwice() public {

    bytes32 diffIdHash = sha256("diffIdHash");

    vm.expectRevert(bytes("Already registered"));

    vm.prank(patient);

    registry.registerUser(diffIdHash, IHealthRegistry.Role.Patient);

    IHealthRegistry.User memory user = registry.getUser(patient);

    require(user.identityHash == identityHash, "og identity must remain ");

   }

   function test_PatientCanUpdateIdentity() public {

    registry.setVerification(patient,true);

    bytes32 diffIdHash = sha256("diffIdHash");

    vm.prank(patient);

    registry.updateIdentity(diffIdHash);

    IHealthRegistry.User memory user = registry.getUser(patient);

    require(user.identityHash == diffIdHash, "new identity hashes must match");

    require(user.role == IHealthRegistry.Role.Patient, "Roles should match");

    require(user.verified == false, "updated identity should be unverified");

   }

   function test_NonAdminCannotVerifyPatient() public {

    vm.expectRevert(bytes("Only admin"));

    vm.prank(patient);

    registry.setVerification(patient,true);

    IHealthRegistry.User memory user = registry.getUser(patient);

    require(user.verified == false, "patient should remain unverified");

    require(user.identityHash == identityHash, "identity hashes should be the same");

    require(user.role == IHealthRegistry.Role.Patient, "Roles should match");

   }

}
