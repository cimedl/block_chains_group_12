// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

// P2 calls rewardConsent only after the patient has granted valid consent.
interface IConsentReward {
    function rewardConsent(uint256 recordId, address requester) external returns (bool);
    function balanceOf(address patient) external view returns (uint256);
}
