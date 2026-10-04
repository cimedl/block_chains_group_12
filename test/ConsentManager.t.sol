// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {HealthRegistry} from "../contracts/HealthRegistry.sol";
import {ConsentReward} from "../contracts/ConsentReward.sol";
import {ConsentManager} from "../contracts/ConsentManager.sol";
import {IHealthRegistry} from "../contracts/interfaces/IHealthRegistry.sol";
import {TestHelper} from "./TestHelper.sol";

contract ConsentManagerTest is TestHelper {
    HealthRegistry registry;
    ConsentReward reward;
    ConsentManager manager;
    address patient = address(0x101);
    address doctor = address(0x102);
    address otherDoctor = address(0x104);
    bytes32 identityHash = sha256("identity and salt");
    bytes32 fileHash = sha256("fake blood test panel");
    uint256 recordId;

    event ConsentGranted(uint256 indexed grantId, address indexed patient, address indexed requester, uint256 recordId);
    event ConsentRevoked(uint256 indexed grantId, address indexed patient, address indexed requester, uint256 recordId);
    event AccessDecision(uint256 indexed requestId, address indexed patient, address indexed requester,
        uint256 recordId, uint256 grantId, uint256 timestamp, bool allowed, ConsentManager.ReasonCode reason);

    function setUp() public {
        vm.warp(1000);

        registry = new HealthRegistry(address(this));
        reward = new ConsentReward(address(registry),address(this));
        manager = new ConsentManager(address(registry),address(reward));

        reward.setConsentManager(address(manager));

        vm.prank(patient);
        registry.registerUser(identityHash,IHealthRegistry.Role.Patient);
        registry.setVerification(patient, true);

        bytes32 doctorIdHash = sha256("doctor identity and salt");

        vm.prank(doctor);
        registry.registerUser(doctorIdHash, IHealthRegistry.Role.Doctor);
        registry.setVerification(doctor,true);

        bytes32 otherIdHash = sha256("other doctor identity and salt");

        vm.prank(otherDoctor);
        registry.registerUser(otherIdHash,IHealthRegistry.Role.Doctor);
        registry.setVerification(otherDoctor, true);

        vm.prank(patient);
        recordId = registry.registerRecord(fileHash,"blood test panel");
    }

   function test_PatientCanGrantAccess() public {

    uint256 startTime = block.timestamp;

    vm.expectEmit(true,true,true,true,address(manager));
    emit ConsentGranted(1,patient,doctor,recordId);

    vm.prank(patient);
    manager.grantAccess(recordId,"blood test panel",doctor,7);
    uint256 grantId = manager.currentGrantId() - 1;

    (address storedPatient, address requester, uint256 storedRecordId, string memory recordType,
        uint256 storedGrantId, uint256 storedStartTime, uint256 endTime, bool revokedStatus) = manager.consentGrants(grantId);

    require(grantId == 1, "grant must correspond to the proper id");
    require(storedGrantId == grantId, "stored grant ids must match");
    require(storedPatient == patient, "patient must match");
    require(requester == doctor, "doctor must match");

    require(storedRecordId == recordId, "record ids must match");

    require(keccak256(bytes(recordType)) == keccak256(bytes("blood test panel")), "types must match");

    require(storedStartTime == startTime, "start times must match");
    require(endTime == startTime + 7 days, "consent should last 7 days");
    require(revokedStatus == false , "new consent should not be revoked");

    require(manager.currentGrantId() == 2, "next grant id must be 2");
    require(manager.latestGrantId(recordId,doctor) == grantId, "latest grant ids must match");
    require(manager.checkPermission(grantId,doctor,recordId) == true, "doctor should have access");
    require(manager.checkPermission(grantId,otherDoctor,recordId) == false, "consent should only cover the chosen doctor");

    IHealthRegistry.Record memory record = registry.getRecord(recordId);

    require(record.patient == patient, "giving access should not change the record owner");

    require(reward.balanceOf(patient) == 10, "patient should get 10 points");
    require(reward.balanceOf(doctor) == 0 , "doctor should not get points");

   }

   function test_NonOwnerCannotGrantOrRevokeAccess() public {

    vm.expectRevert(bytes("UNAUTHORIZED: Not the record owner"));

    vm.prank(otherDoctor);

    manager.grantAccess(recordId,"blood test panel",doctor,7);

    require(manager.currentGrantId() == 1, "failed grant should not consume an id");
    require(manager.latestGrantId(recordId,doctor) == 0, "failed grant should not be stored");
    require(reward.balanceOf(patient) == 0, "failed grant should not give points");

    vm.prank(patient);

    manager.grantAccess(recordId,"blood test panel",doctor,7);
    uint256 grantId = manager.currentGrantId() - 1;

    vm.expectRevert(bytes("UNAUTHORIZED: Not the record owner"));

    vm.prank(otherDoctor);

    manager.revokeAccess(recordId, grantId);

    require(manager.checkPermission(grantId,doctor,recordId) == true, "failed revocation should not remove access");
    require(reward.balanceOf(patient) == 10, "failed revocation should not change points");

   }

   function test_ConsentDurationLimits() public {

    vm.expectRevert(bytes("INVALID: Duration must be 1=365 days"));

    vm.prank(patient);

    manager.grantAccess(recordId, "blood test panel",doctor,0);

    vm.expectRevert(bytes("INVALID: Duration must be 1=365 days"));

    vm.prank(patient);

    manager.grantAccess(recordId,"blood test panel",doctor, 366);

    require(manager.currentGrantId() == 1, "invalid duration should not consume an id");
    require(reward.balanceOf(patient) == 0, "invalid duration should not give points");

    uint256 startTime = block.timestamp;

    vm.prank(patient);

    manager.grantAccess(recordId,"blood test panel",doctor,1);
    uint256 grantId = manager.currentGrantId() - 1;

    (, , , , , , uint256 endTime, ) = manager.consentGrants(grantId);

    require(endTime == startTime + 1 days, "consent should last 1 day");
    require(manager.checkPermission(grantId,doctor,recordId) == true, "1 day consent should allow access");

    vm.prank(patient);

    manager.grantAccess(recordId, "blood test panel",otherDoctor,365);
    uint256 longGrantId = manager.currentGrantId() - 1;

    (, , , , , , uint256 longEndTime, ) = manager.consentGrants(longGrantId);

    require(longEndTime == startTime + 365 days, "consent should last 365 days");
    require(manager.checkPermission(longGrantId,otherDoctor,recordId) == true, "365 day consent should allow access");

   }

   function test_AccessRequestsAreLogged() public {

    require(manager.checkPermission(0,doctor,recordId) == false, "doctor should not have access without consent");

    vm.expectEmit(true,true,true,true,address(manager));
    emit AccessDecision(1,patient,doctor,recordId,0,block.timestamp,false,ConsentManager.ReasonCode.NO_CONSENT);

    vm.prank(doctor);
    manager.requestAccess(recordId, 0);
    uint256 deniedRequestId = manager.currentRequestId() - 1;

    require(deniedRequestId == 1, "first request id must be 1");
    require(reward.balanceOf(patient) == 0, "denied request should not give points");

    vm.prank(patient);

    manager.grantAccess(recordId,"blood test panel",doctor,7);
    uint256 grantId = manager.currentGrantId() - 1;

    require(manager.checkPermission(grantId,doctor,recordId) == true, "doctor should have access with consent");

    vm.expectEmit(true,true,true,true,address(manager));
    emit AccessDecision(2,patient,doctor,recordId,grantId,block.timestamp,true,ConsentManager.ReasonCode.GRANTED);

    vm.prank(doctor);

    manager.requestAccess(recordId,grantId);
    uint256 allowedRequestId = manager.currentRequestId() - 1;

    require(allowedRequestId == 2, "second request id must be 2");
    require(manager.currentRequestId() == 3, "next request id must be 3");

    require(reward.balanceOf(patient) == 10, "allowed request should not change patient points");
    require(reward.balanceOf(doctor) == 0, "doctor should not need points for access");

   }

   function test_RevokedAndExpiredConsentBlocksAccess() public {

    uint256 startTime = block.timestamp;

    vm.prank(patient);

    manager.grantAccess(recordId,"blood test panel",doctor,1);
    uint256 grantId = manager.currentGrantId() - 1;

    vm.warp(startTime + 1 days - 1);

    require(manager.checkPermission(grantId,doctor,recordId) == true, "consent should work before expiry");

    vm.warp(startTime + 1 days);

    require(manager.checkPermission(grantId,doctor,recordId) == false, "consent should stop at expiry");

    vm.expectEmit(true,true,true,true,address(manager));
    emit AccessDecision(1,patient,doctor,recordId,grantId,block.timestamp,false,ConsentManager.ReasonCode.EXPIRED);

    vm.prank(doctor);

    manager.requestAccess(recordId,grantId);
    uint256 expiredRequestId = manager.currentRequestId() - 1;

    require(expiredRequestId == 1, "expired request id must be 1");

    vm.prank(patient);

    manager.grantAccess(recordId,"blood test panel",doctor,1);
    uint256 renewedGrantId = manager.currentGrantId() - 1;

    require(manager.checkPermission(renewedGrantId,doctor,recordId) == true, "new consent should allow access");

    vm.expectEmit(true,true,true,true,address(manager));
    emit ConsentRevoked(renewedGrantId,patient,doctor,recordId);

    vm.prank(patient);

    manager.revokeAccess(recordId,renewedGrantId);

    require(manager.checkPermission(renewedGrantId,doctor,recordId) == false, "revoked consent should not allow access");
    require(manager.checkPermission(grantId,doctor,recordId) == false, "old expired consent should not allow access");

    vm.expectEmit(true,true,true,true,address(manager));
    emit AccessDecision(2,patient,doctor,recordId,renewedGrantId,block.timestamp,false,ConsentManager.ReasonCode.REVOKED);

    vm.prank(doctor);

    manager.requestAccess(recordId,renewedGrantId);
    uint256 revokedRequestId = manager.currentRequestId() - 1;

    require(revokedRequestId == 2, "revoked request id must be 2");
    require(reward.balanceOf(patient) == 10, "renewing consent should not give points twice");
    require(reward.balanceOf(doctor) == 0, "denied access should not change doctor points");

   }
}
