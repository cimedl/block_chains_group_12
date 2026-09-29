// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {HealthRegistry} from "../contracts/HealthRegistry.sol";
import {ConsentReward} from "../contracts/ConsentReward.sol";
import {IHealthRegistry} from "../contracts/interfaces/IHealthRegistry.sol";
import {TestHelper} from "./TestHelper.sol";

// A test caller, not P2's consent implementation. It has no consent rules.
contract RewardCallerStub {
    ConsentReward reward;

    constructor(ConsentReward rewardContract) {
        reward = rewardContract;
    }

    function callReward(uint256 recordId, address requester) external returns (bool) {
        return reward.rewardConsent(recordId, requester);
    }
}

contract ConsentRewardTest is TestHelper {
    HealthRegistry registry;
    ConsentReward reward;
    RewardCallerStub manager;
    address patient = address(0x101);
    address doctor = address(0x102);
    address researcher = address(0x103);
    address other = address(0x104);
    uint256 recordId;
    bytes32 identityHash = sha256("fake identity");

    event RewardGiven(address indexed patient, uint256 indexed recordId, address indexed requester, uint256 amount);

    function setUp() public {
        registry = new HealthRegistry(address(this));
        reward = new ConsentReward(address(registry), address(this));
        manager = new RewardCallerStub(reward);
        reward.setConsentManager(address(manager));

        vm.prank(patient);
        registry.registerUser(identityHash, IHealthRegistry.Role.Patient);
        vm.prank(doctor);
        registry.registerUser(identityHash, IHealthRegistry.Role.Doctor);
        vm.prank(researcher);
        registry.registerUser(identityHash, IHealthRegistry.Role.Researcher);
        registry.setVerification(patient, true);
        registry.setVerification(doctor, true);
        registry.setVerification(researcher, true);
        bytes32 fileHash = sha256("fake file");
        vm.prank(patient);
        recordId = registry.registerRecord(fileHash, "Blood_Test_Panel");
    }

    function testAuthorizedRewardGoesToRecordOwner() public {
        require(manager.callReward(recordId, doctor), "Reward not given");
        require(reward.balanceOf(patient) == 10, "Patient should get ten points");
        require(reward.balanceOf(doctor) == 0, "Doctor should not get points");
        require(reward.rewarded(recordId, doctor), "Reward not remembered");
    }

    function testRepeatedPermissionGivesNoMorePoints() public {
        manager.callReward(recordId, doctor);
        require(!manager.callReward(recordId, doctor), "Duplicate reward");
        require(reward.balanceOf(patient) == 10, "Balance increased twice");
    }

    function testResearcherCanAlsoTriggerReward() public {
        manager.callReward(recordId, researcher);
        require(reward.balanceOf(patient) == 10, "Researcher grant not rewarded");
    }

    function testDifferentRequesterGetsSeparateReward() public {
        manager.callReward(recordId, doctor);
        manager.callReward(recordId, researcher);
        require(reward.balanceOf(patient) == 20, "Wrong total");
    }

    function testDifferentRecordGetsSeparateReward() public {
        manager.callReward(recordId, doctor);
        bytes32 nextHash = sha256("another file");
        vm.prank(patient);
        uint256 nextId = registry.registerRecord(nextHash, "Scan");
        manager.callReward(nextId, doctor);
        require(reward.balanceOf(patient) == 20, "Wrong total");
    }

    function testPatientCannotRewardThemselves() public {
        vm.expectRevert(bytes("Only consent manager"));
        vm.prank(patient);
        reward.rewardConsent(recordId, doctor);
    }

    function testAdminCannotIssueRewardsDirectly() public {
        vm.expectRevert(bytes("Only consent manager"));
        reward.rewardConsent(recordId, doctor);
    }

    function testUnknownRecordRejected() public {
        vm.expectRevert(bytes("Unknown record"));
        manager.callReward(999, doctor);
    }

    function testUnverifiedRequesterRejected() public {
        registry.setVerification(doctor, false);
        vm.expectRevert(bytes("Requester not verified"));
        manager.callReward(recordId, doctor);
        require(!reward.rewarded(recordId, doctor), "Failed call used the reward");
    }

    function testUnknownRequesterRejected() public {
        vm.expectRevert(bytes("Requester not verified"));
        manager.callReward(recordId, other);
    }

    function testPatientCannotBeRequesterForReward() public {
        vm.expectRevert(bytes("Requester not verified"));
        manager.callReward(recordId, patient);
    }

    function testUnverifiedPatientRejected() public {
        registry.setVerification(patient, false);
        vm.expectRevert(bytes("Patient not verified"));
        manager.callReward(recordId, doctor);
    }

    function testOnlyAdminCanSetManager() public {
        ConsentReward fresh = new ConsentReward(address(registry), address(this));
        vm.expectRevert(bytes("Only admin"));
        vm.prank(patient);
        fresh.setConsentManager(address(manager));
    }

    function testManagerCanOnlyBeSetOnce() public {
        vm.expectRevert(bytes("Manager already set"));
        reward.setConsentManager(address(manager));
    }

    function testWalletCannotBeManager() public {
        ConsentReward fresh = new ConsentReward(address(registry), address(this));
        vm.expectRevert(bytes("Manager must be a contract"));
        fresh.setConsentManager(doctor);
    }

    function testZeroManagerRejected() public {
        ConsentReward fresh = new ConsentReward(address(registry), address(this));
        vm.expectRevert(bytes("Manager must be a contract"));
        fresh.setConsentManager(address(0));
    }

    function testNoRewardBeforeManagerSetup() public {
        ConsentReward fresh = new ConsentReward(address(registry), address(this));
        vm.expectRevert(bytes("Only consent manager"));
        fresh.rewardConsent(recordId, doctor);
    }

    function testRegistryMustBeContract() public {
        vm.expectRevert(bytes("Registry must be a contract"));
        new ConsentReward(other, address(this));
    }

    function testZeroAdminRejected() public {
        vm.expectRevert(bytes("Invalid admin"));
        new ConsentReward(address(registry), address(0));
    }

    function testRewardEvent() public {
        vm.expectEmit(true, true, true, true);
        emit RewardGiven(patient, recordId, doctor, 10);
        manager.callReward(recordId, doctor);
    }
}
