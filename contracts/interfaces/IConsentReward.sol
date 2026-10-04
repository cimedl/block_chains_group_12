// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

interface IConsentReward {
    function rewardConsent(uint256 recordId, address requester) external returns (bool);
    function balanceOf(address patient) external view returns (uint256);
}
