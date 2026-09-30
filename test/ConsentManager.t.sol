// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {HealthRegistry} from "../contracts/HealthRegistry.sol";
import {ConsentReward} from "../contracts/ConsentReward.sol";
import {ConsentManager} from "../contracts/ConsentManager.sol";
import {IHealthRegistry} from "../contracts/interfaces/IHealthRegistry.sol";
import {TestHelper, Vm} from "./TestHelper.sol";

// These tests use the real registry, manager and reward, not RewardCallerStub.
contract ConsentManagerTest is TestHelper {
    HealthRegistry registry;
    ConsentReward reward;
    ConsentManager manager;
    address alice = address(0x101);
    address bob = address(0x102);
    address carol = address(0x103);
    address david = address(0x104);
    address researcher = address(0x105);
    address unknown = address(0x106);
    uint256 lab;
    uint256 prescription;
    uint256 bobRecord;

    event AccessDecision(uint256 indexed requestId, address indexed patient, address indexed requester,
        uint256 recordId, uint256 grantId, uint256 timestamp, bool allowed, ConsentManager.ReasonCode reason);
    event ConsentGranted(uint256 indexed grantId, address indexed patient, address indexed requester, uint256 recordId);
    event ConsentRevoked(uint256 indexed grantId, address indexed patient, address indexed requester, uint256 recordId);

    function setUp() public {
        vm.warp(1000);
        registry = new HealthRegistry(address(this));
        reward = new ConsentReward(address(registry), address(this));
        manager = new ConsentManager(address(registry), address(reward));
        reward.setConsentManager(address(manager));
        register(alice, IHealthRegistry.Role.Patient);
        register(bob, IHealthRegistry.Role.Patient);
        register(carol, IHealthRegistry.Role.Doctor);
        register(david, IHealthRegistry.Role.Doctor);
        register(researcher, IHealthRegistry.Role.Researcher);
        bytes32 labHash = sha256("fake laboratory file");
        bytes32 prescriptionHash = sha256("fake prescription file");
        bytes32 bobHash = sha256("Bob's fake laboratory file");
        vm.prank(alice);
        lab = registry.registerRecord(labHash, "Blood_Test_Panel");
        vm.prank(alice);
        prescription = registry.registerRecord(prescriptionHash, "Prescription");
        vm.prank(bob);
        bobRecord = registry.registerRecord(bobHash, "Blood_Test_Panel");
    }

    function register(address account, IHealthRegistry.Role role) internal {
        bytes32 identityHash = sha256("synthetic identity");
        vm.prank(account);
        registry.registerUser(identityHash, role);
        registry.setVerification(account, true);
    }

    function grantCarol() internal returns (uint256) {
        vm.prank(alice);
        return manager.grantAccess(lab, "Blood_Test_Panel", carol, 7);
    }

    function endTime(uint256 grantId) internal view returns (uint256) {
        (, , , , , , uint256 end, ) = manager.consentGrants(grantId);
        return end;
    }

    function expectDecision(address requester, address patient, uint256 recordId, uint256 suppliedGrant,
        uint256 matchingGrant, bool allowed, ConsentManager.ReasonCode reason) internal
    {
        uint256 requestId = manager.currentRequestId();
        vm.expectEmit(true, true, true, true, address(manager));
        emit AccessDecision(requestId, patient, requester, recordId, matchingGrant, block.timestamp, allowed, reason);
        vm.prank(requester);
        require(manager.requestAccess(recordId, suppliedGrant) == requestId, "Wrong allocated request ID");
    }

    function testRealGrantStoresFieldsAndRewardsOwner() public {
        uint256 start = block.timestamp;
        vm.expectEmit(true, true, true, true, address(manager));
        emit ConsentGranted(1, alice, carol, lab);
        uint256 grantId = grantCarol();
        (address patient, address requester, uint256 recordId, string memory category,
            uint256 storedId, uint256 storedStart, uint256 end, bool revoked) = manager.consentGrants(grantId);
        require(grantId == 1 && storedId == 1, "Wrong grant ID");
        require(patient == alice && requester == carol && recordId == lab, "Wrong scope");
        require(keccak256(bytes(category)) == keccak256("Blood_Test_Panel"), "Wrong category");
        require(storedStart == start && end == start + 7 days && !revoked, "Wrong duration/state");
        require(manager.currentGrantId() == 2 && manager.latestGrantId(lab, carol) == 1, "Wrong counters");
        require(reward.balanceOf(alice) == 10 && reward.balanceOf(carol) == 0, "Wrong reward recipient");
        require(manager.checkPermission(grantId, carol, lab), "Valid grant denied");
    }

    function testAnotherPatientCannotGrant() public {
        vm.expectRevert(bytes("UNAUTHORIZED: Not the record owner"));
        vm.prank(bob);
        manager.grantAccess(lab, "Blood_Test_Panel", carol, 7);
        require(manager.currentGrantId() == 1 && reward.balanceOf(alice) == 0, "Partial grant");
    }

    function testDeployerCannotGrantForPatient() public {
        vm.expectRevert(bytes("UNAUTHORIZED: Not the record owner"));
        manager.grantAccess(lab, "Blood_Test_Panel", carol, 7);
    }

    function testZeroRequesterRejected() public {
        vm.expectRevert(bytes("INVALID: Requester cannot be zero address"));
        vm.prank(alice);
        manager.grantAccess(lab, "Blood_Test_Panel", address(0), 7);
    }

    function testZeroDaysRejected() public {
        vm.expectRevert(bytes("INVALID: Duration must be 1-365 days"));
        vm.prank(alice);
        manager.grantAccess(lab, "Blood_Test_Panel", carol, 0);
        require(manager.currentGrantId() == 1 && reward.balanceOf(alice) == 0, "Invalid grant changed state");
    }

    function test366DaysRejected() public {
        vm.expectRevert(bytes("INVALID: Duration must be 1-365 days"));
        vm.prank(alice);
        manager.grantAccess(lab, "Blood_Test_Panel", carol, 366);
    }

    function testOneDayAccepted() public {
        uint256 start = block.timestamp;
        vm.prank(alice);
        uint256 id = manager.grantAccess(lab, "Blood_Test_Panel", carol, 1);
        require(endTime(id) == start + 1 days, "Wrong minimum expiry");
    }

    function test365DaysAccepted() public {
        uint256 start = block.timestamp;
        vm.prank(alice);
        uint256 id = manager.grantAccess(lab, "Blood_Test_Panel", carol, 365);
        require(endTime(id) == start + 365 days, "Wrong maximum expiry");
    }

    function testCategoryMismatchRejected() public {
        vm.expectRevert(bytes("INVALID: Record category mismatch"));
        vm.prank(alice);
        manager.grantAccess(lab, "Prescription", carol, 7);
        require(manager.currentGrantId() == 1 && !reward.rewarded(lab, carol), "Mismatch consumed eligibility");
    }

    function testEmptyCategoryRejected() public {
        vm.expectRevert(bytes("INVALID: Record category mismatch"));
        vm.prank(alice);
        manager.grantAccess(lab, "", carol, 7);
    }

    function testUnverifiedRequesterCannotReceiveGrant() public {
        registry.setVerification(carol, false);
        vm.expectRevert(bytes("Requester not verified"));
        vm.prank(alice);
        manager.grantAccess(lab, "Blood_Test_Panel", carol, 7);
    }

    function testPatientRoleCannotReceiveGrant() public {
        vm.expectRevert(bytes("Requester not verified"));
        vm.prank(alice);
        manager.grantAccess(lab, "Blood_Test_Panel", bob, 7);
    }

    function testUnverifiedOwnerCannotGrant() public {
        registry.setVerification(alice, false);
        vm.expectRevert(bytes("Patient not verified"));
        vm.prank(alice);
        manager.grantAccess(lab, "Blood_Test_Panel", carol, 7);
    }

    function testUnknownRecordCannotBeGranted() public {
        vm.expectRevert(bytes("Unknown record"));
        vm.prank(alice);
        manager.grantAccess(999, "Blood_Test_Panel", carol, 7);
    }

    function testActiveDuplicateRejectedWithoutReward() public {
        uint256 id = grantCarol();
        vm.expectRevert(bytes("INVALID: Consent already active"));
        vm.prank(alice);
        manager.grantAccess(lab, "Blood_Test_Panel", carol, 7);
        require(manager.currentGrantId() == 2 && manager.latestGrantId(lab, carol) == id, "Duplicate changed grants");
        require(reward.balanceOf(alice) == 10, "Duplicate paid twice");
    }

    function testCannotRevokeOtherPatientGrantUsingOwnRecord() public {
        uint256 id = grantCarol();
        vm.expectRevert(bytes("INVALID: Grant record mismatch"));
        vm.prank(bob);
        manager.revokeAccess(bobRecord, id);
        require(manager.checkPermission(id, carol, lab), "Bob revoked Alice's grant");
    }

    function testCannotRevokeGrantUsingAnotherOwnedRecord() public {
        uint256 id = grantCarol();
        vm.expectRevert(bytes("INVALID: Grant record mismatch"));
        vm.prank(alice);
        manager.revokeAccess(prescription, id);
        require(manager.checkPermission(id, carol, lab), "Wrong record revoked grant");
    }

    function testAnotherPatientCannotRevokeCorrectRecord() public {
        uint256 id = grantCarol();
        vm.expectRevert(bytes("UNAUTHORIZED: Not the record owner"));
        vm.prank(bob);
        manager.revokeAccess(lab, id);
        require(manager.checkPermission(id, carol, lab), "Unauthorized revoke changed grant");
    }

    function testUnknownGrantCannotBeRevoked() public {
        vm.expectRevert(bytes("INVALID: Unknown grant"));
        vm.prank(alice);
        manager.revokeAccess(lab, 99);
        (address patient, , , , , , , bool revoked) = manager.consentGrants(99);
        require(patient == address(0) && !revoked, "Created revoked placeholder");
    }

    function testOwnerRevocationEmitsEventAndDeniesAccess() public {
        uint256 id = grantCarol();
        vm.expectEmit(true, true, true, true, address(manager));
        emit ConsentRevoked(id, alice, carol, lab);
        vm.prank(alice);
        manager.revokeAccess(lab, id);
        require(!manager.checkPermission(id, carol, lab), "Revoked consent allowed");
        expectDecision(carol, alice, lab, id, id, false, ConsentManager.ReasonCode.REVOKED);
        require(reward.balanceOf(alice) == 10, "Revocation changed points");
    }

    function testSuspendedOwnerCanStillRevoke() public {
        uint256 id = grantCarol();
        registry.setVerification(alice, false);
        vm.prank(alice);
        manager.revokeAccess(lab, id);
        registry.setVerification(alice, true);
        require(!manager.checkPermission(id, carol, lab), "Reverification restored revoked grant");
    }

    function testRegrantHasNewIdAndNoRepeatedReward() public {
        uint256 oldId = grantCarol();
        vm.prank(alice);
        manager.revokeAccess(lab, oldId);
        uint256 newId = grantCarol();
        require(newId == oldId + 1 && manager.latestGrantId(lab, carol) == newId, "Not a fresh grant");
        require(!manager.checkPermission(oldId, carol, lab) && manager.checkPermission(newId, carol, lab), "Old grant revived");
        require(reward.balanceOf(alice) == 10, "Regrant paid twice");
        expectDecision(carol, alice, lab, oldId, oldId, false, ConsentManager.ReasonCode.REVOKED);
    }

    function testRegrantAtExpiryPreservesExpiredOldGrant() public {
        uint256 oldId = grantCarol();
        vm.warp(endTime(oldId));
        uint256 newId = grantCarol();
        require(newId != oldId && !manager.checkPermission(oldId, carol, lab), "Old grant renewed in place");
        require(manager.checkPermission(newId, carol, lab) && reward.balanceOf(alice) == 10, "Renewal failed or paid twice");
    }

    function testAllowedRequestRecordsDecision() public {
        uint256 id = grantCarol();
        expectDecision(carol, alice, lab, id, id, true, ConsentManager.ReasonCode.GRANTED);
        require(reward.balanceOf(alice) == 10 && reward.balanceOf(carol) == 0, "Access moved points");
    }

    function testBeforeExpiryAllowed() public {
        uint256 id = grantCarol();
        vm.warp(endTime(id) - 1);
        require(manager.checkPermission(id, carol, lab), "Expired too early");
        expectDecision(carol, alice, lab, id, id, true, ConsentManager.ReasonCode.GRANTED);
    }

    function testExactlyAtExpiryDenied() public {
        uint256 id = grantCarol();
        vm.warp(endTime(id));
        require(!manager.checkPermission(id, carol, lab), "Equality allowed");
        expectDecision(carol, alice, lab, id, id, false, ConsentManager.ReasonCode.EXPIRED);
    }

    function testAfterExpiryDenied() public {
        uint256 id = grantCarol();
        vm.warp(endTime(id) + 1);
        require(!manager.checkPermission(id, carol, lab), "Expired consent allowed");
        expectDecision(carol, alice, lab, id, id, false, ConsentManager.ReasonCode.EXPIRED);
    }

    function testWrongRequesterDenied() public {
        uint256 id = grantCarol();
        require(!manager.checkPermission(id, david, lab), "Wrong requester allowed");
        expectDecision(david, alice, lab, id, 0, false, ConsentManager.ReasonCode.NO_CONSENT);
    }

    function testWrongRecordDeniedWithActualOwner() public {
        uint256 id = grantCarol();
        require(!manager.checkPermission(id, carol, bobRecord), "Bob's record allowed");
        expectDecision(carol, bob, bobRecord, id, 0, false, ConsentManager.ReasonCode.NO_CONSENT);
        expectDecision(carol, alice, prescription, id, 0, false, ConsentManager.ReasonCode.NO_CONSENT);
    }

    function testMissingGrantDenialStillIdentifiesPatient() public {
        expectDecision(carol, alice, lab, 0, 0, false, ConsentManager.ReasonCode.NO_CONSENT);
        require(!manager.checkPermission(0, carol, lab), "Missing grant allowed");
    }

    function testUnknownRecordDenial() public {
        expectDecision(carol, address(0), 999, 0, 0, false, ConsentManager.ReasonCode.UNKNOWN_RECORD);
        require(!manager.checkPermission(0, carol, 999), "Unknown record allowed");
    }

    function testUnregisteredRequesterDenial() public {
        expectDecision(unknown, alice, lab, 0, 0, false, ConsentManager.ReasonCode.UNREGISTERED_REQUESTER);
    }

    function testRequesterSuspensionImmediatelyBlocksAccess() public {
        uint256 id = grantCarol();
        registry.setVerification(carol, false);
        require(!manager.checkPermission(id, carol, lab), "Suspended requester allowed");
        expectDecision(carol, alice, lab, id, id, false, ConsentManager.ReasonCode.UNREGISTERED_REQUESTER);
        registry.setVerification(carol, true);
        require(manager.checkPermission(id, carol, lab), "Valid reverified requester denied");
    }

    function testPatientSuspensionImmediatelyBlocksAccess() public {
        uint256 id = grantCarol();
        registry.setVerification(alice, false);
        require(!manager.checkPermission(id, carol, lab), "Suspended patient allowed");
        expectDecision(carol, alice, lab, id, id, false, ConsentManager.ReasonCode.PATIENT_NOT_VERIFIED);
    }

    function testIdentityChangesRequireReverificationForAccess() public {
        uint256 id = grantCarol();
        bytes32 doctorHash = sha256("changed synthetic doctor identity");
        bytes32 patientHash = sha256("changed synthetic patient identity");
        vm.prank(carol);
        registry.updateIdentity(doctorHash);
        require(!manager.checkPermission(id, carol, lab), "Identity update did not block access");
        registry.setVerification(carol, true);
        vm.prank(alice);
        registry.updateIdentity(patientHash);
        require(!manager.checkPermission(id, carol, lab), "Patient identity update ignored");
        registry.setVerification(alice, true);
        require(manager.checkPermission(id, carol, lab), "Valid reverified consent denied");
    }

    function testResearcherAndOtherPatientRewardsRemainIndependent() public {
        grantCarol();
        vm.prank(alice);
        uint256 researchId = manager.grantAccess(lab, "Blood_Test_Panel", researcher, 7);
        vm.prank(bob);
        uint256 bobId = manager.grantAccess(bobRecord, "Blood_Test_Panel", carol, 7);
        require(manager.checkPermission(researchId, researcher, lab), "Researcher denied");
        require(manager.checkPermission(bobId, carol, bobRecord), "Bob's valid grant denied");
        require(reward.balanceOf(alice) == 20 && reward.balanceOf(bob) == 10, "Rewards crossed patients");
    }

    function testSameCategoryNewRecordKeepsP1RewardPolicy() public {
        grantCarol();
        bytes32 newHash = sha256("another synthetic lab");
        vm.prank(alice);
        uint256 newRecord = registry.registerRecord(newHash, "Blood_Test_Panel");
        vm.prank(alice);
        manager.grantAccess(newRecord, "Blood_Test_Panel", carol, 7);
        require(reward.balanceOf(alice) == 20, "Per-record policy changed");
    }

    function testRewardFailureRollsBackEntireGrantThenRetryWorks() public {
        ConsentReward freshReward = new ConsentReward(address(registry), address(this));
        ConsentManager freshManager = new ConsentManager(address(registry), address(freshReward));
        vm.recordLogs();
        vm.expectRevert(bytes("Only consent manager"));
        vm.prank(alice);
        freshManager.grantAccess(lab, "Blood_Test_Panel", carol, 7);
        Vm.Log[] memory logs = vm.getRecordedLogs();
        require(logs.length == 0, "Failed grant emitted audit/reward logs");
        require(freshManager.currentGrantId() == 1 && freshManager.latestGrantId(lab, carol) == 0, "Partial grant counters");
        (address patient, , , , , , , ) = freshManager.consentGrants(1);
        require(patient == address(0), "Partial grant saved");
        require(freshReward.balanceOf(alice) == 0 && !freshReward.rewarded(lab, carol), "Eligibility consumed");
        freshReward.setConsentManager(address(freshManager));
        vm.prank(alice);
        require(freshManager.grantAccess(lab, "Blood_Test_Panel", carol, 7) == 1, "Retry lost grant ID");
        require(freshReward.balanceOf(alice) == 10, "Retry not rewarded");
    }

    function testDeniedLogsPersistAndRequestIdsAreUniqueAcrossWallets() public {
        uint256 id = grantCarol();
        vm.recordLogs();
        vm.prank(david);
        uint256 first = manager.requestAccess(lab, id);
        vm.prank(carol);
        uint256 second = manager.requestAccess(lab, id);
        Vm.Log[] memory logs = vm.getRecordedLogs();
        require(first == 1 && second == 2 && manager.currentRequestId() == 3, "Request ID reused");
        require(logs.length == 2 && logs[0].emitter == address(manager) && logs[1].emitter == address(manager), "Missing decisions");
        require(uint256(logs[0].topics[1]) == first && uint256(logs[1].topics[1]) == second, "Wrong event IDs");
        (, , , bool deniedAllowed, uint8 deniedReason) = abi.decode(logs[0].data, (uint256, uint256, uint256, bool, uint8));
        require(!deniedAllowed && deniedReason == uint8(ConsentManager.ReasonCode.NO_CONSENT), "Denial not persisted");
        require(reward.balanceOf(alice) == 10 && reward.balanceOf(david) == 0, "Requests moved points");
    }

    function testRevokedReasonPrecedesExpiryForMatchingGrant() public {
        uint256 id = grantCarol();
        vm.prank(alice);
        manager.revokeAccess(lab, id);
        vm.warp(endTime(id) + 1);
        expectDecision(carol, alice, lab, id, id, false, ConsentManager.ReasonCode.REVOKED);
    }

    function testViewDoesNotConsumeRequestId() public {
        uint256 id = grantCarol();
        manager.checkPermission(id, carol, lab);
        manager.checkPermission(id, david, lab);
        require(manager.currentRequestId() == 1, "Preview consumed request");
    }

    function testInvalidDependencyAddressesRejected() public {
        vm.expectRevert(bytes("Registry must be a contract"));
        new ConsentManager(address(0), address(reward));
        vm.expectRevert(bytes("Registry must be a contract"));
        new ConsentManager(alice, address(reward));
        vm.expectRevert(bytes("Reward must be a contract"));
        new ConsentManager(address(registry), address(0));
        vm.expectRevert(bytes("Reward must be a contract"));
        new ConsentManager(address(registry), carol);
    }
}
