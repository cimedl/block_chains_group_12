// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {HealthRegistry} from "../contracts/HealthRegistry.sol";
import {ConsentReward} from "../contracts/ConsentReward.sol";
import {IHealthRegistry} from "../contracts/interfaces/IHealthRegistry.sol";
import {TestHelper} from "./TestHelper.sol";

contract RewardCallerStub {
    ConsentReward reward;

    constructor(ConsentReward rewardContract) {
        reward = rewardContract;
    }

    function callReward(uint256 recordId, address requester) external returns (bool) {
        return reward.rewardConsent(recordId,requester);
    }
}


contract ConsentRewardTest is TestHelper {
    HealthRegistry registry;
    ConsentReward reward;
    RewardCallerStub manager;
    address patient = address(0x101);
    address doctor = address(0x102);
    address researcher = address(0x103);
    bytes32 identityHash = sha256("identity and salt");
    bytes32 fileHash = sha256("fake blood test panel");
    uint256 recordId;

    event RewardGiven(address indexed patient, uint256 indexed recordId, address indexed requester, uint256 amount);
    event ConsentManagerSet(address indexed manager);


    function setUp() public {
        registry = new HealthRegistry(address(this));
        reward = new ConsentReward(address(registry),address(this));
        manager = new RewardCallerStub(reward);

        reward.setConsentManager(address(manager));

        vm.prank(patient);
        registry.registerUser(identityHash,IHealthRegistry.Role.Patient);
        registry.setVerification(patient, true);

        bytes32 doctorIdHash = sha256("doctor identity and salt");

        vm.prank(doctor);
        registry.registerUser(doctorIdHash, IHealthRegistry.Role.Doctor);
        registry.setVerification(doctor,true);

        bytes32 researcherIdHash = sha256("researcher identity and salt");

        vm.prank(researcher);
        registry.registerUser(researcherIdHash,IHealthRegistry.Role.Researcher);
        registry.setVerification(researcher, true);

        vm.prank(patient);
        recordId = registry.registerRecord(fileHash,"blood test panel");
    }


   function test_OnlyAdminCanSetManagerAndOnlyManagerCanReward() public{

    ConsentReward newReward = new ConsentReward(address(registry),address(this));
    RewardCallerStub newManager = new RewardCallerStub(newReward);

    vm.expectRevert(bytes("Only consent manager"));
    newReward.rewardConsent(recordId,doctor);

    vm.expectRevert(bytes("Only admin"));

    vm.prank(patient);
    newReward.setConsentManager(address(newManager));

    require(newReward.consentManager() == address(0), "patient should not be able to set the manager");

    vm.expectRevert(bytes("Manager must be a contract"));
    newReward.setConsentManager(doctor);

    vm.expectRevert(bytes("Manager must be a contract"));
    newReward.setConsentManager(address(0));

    vm.expectEmit(true,false,false,true,address(newReward));
    emit ConsentManagerSet(address(newManager));

    newReward.setConsentManager(address(newManager));

    require(newReward.consentManager() == address(newManager), "manager addresses must match");

    vm.expectRevert(bytes("Manager already set"));
    newReward.setConsentManager(address(manager));

    require(newReward.consentManager() == address(newManager), "og manager must remain");

    vm.expectRevert(bytes("Only consent manager"));
    vm.prank(patient);

    newReward.rewardConsent(recordId,doctor);

    vm.expectRevert(bytes("Only consent manager"));
    newReward.rewardConsent(recordId, doctor);

    require(newReward.balanceOf(patient) == 0, "rejected calls should not give points");
    require(newReward.rewarded(recordId,doctor) == false , "rejected calls should not use the reward");

    vm.expectEmit(true,true,true,true,address(newReward));
    emit RewardGiven(patient,recordId,doctor,10);

    bool given = newManager.callReward(recordId,doctor);

    require(given == true, "manager should be able to give the reward");
    require(newReward.balanceOf(patient) == 10, "patient should get 10 points");

    require(newReward.balanceOf(doctor) == 0, "doctor should not get points");
    require(newReward.rewarded(recordId,doctor) == true, "reward should be remembered");

   }

   // Sharing the same blood panel with the same doctor should earn points only once.
   function test_PatientCannotGetRewardTwice() public {

    bool given = manager.callReward(recordId, doctor);

    require(given == true, "first reward should be given");
    require(reward.balanceOf(patient) == 10, "patient should get 10 points");

    bool givenAgain = manager.callReward(recordId,doctor);

    require(givenAgain == false, "same permission should not give points twice");
    require(reward.balanceOf(patient) == 10, "points should stay the same");
    require(reward.rewarded(recordId,doctor) == true, "og reward should still be remembered");

    // Sharing with a researcher is a separate permission and can earn its own points.
    require(reward.rewarded(recordId,researcher) == false, "researcher reward should not be used yet");

    bool researcherGiven = manager.callReward(recordId, researcher);

    require(researcherGiven == true, "different requester should get a separate reward");
    require(reward.balanceOf(patient) == 20, "patient should get points for both permissions");

    require(reward.balanceOf(doctor) == 0 , "doctor should not get points");
    require(reward.balanceOf(researcher) == 0, "researcher should not get points");

   }
}
