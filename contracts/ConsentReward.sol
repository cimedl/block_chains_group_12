// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {IHealthRegistry} from "./interfaces/IHealthRegistry.sol";
import {IConsentReward} from "./interfaces/IConsentReward.sol";

// Simple reward points. They cannot be transferred or used to buy access.
contract ConsentReward is IConsentReward {
    IHealthRegistry public immutable registry;
    address public immutable admin;
    address public consentManager;
    uint256 public constant REWARD_AMOUNT = 10;

    mapping(address => uint256) public override balanceOf;
    mapping(uint256 => mapping(address => bool)) public rewarded;

    event ConsentManagerSet(address indexed manager);
    event RewardGiven(
        address indexed patient,
        uint256 indexed recordId,
        address indexed requester,
        uint256 amount
    );

    constructor(address registryAddress, address adminAddress) {
        require(registryAddress.code.length > 0, "Registry must be a contract");
        require(adminAddress != address(0), "Invalid admin");
        registry = IHealthRegistry(registryAddress);
        admin = adminAddress;
    }

    // P5 calls this once after deploying P2's ConsentManager.
    function setConsentManager(address manager) external {
        require(msg.sender == admin, "Only admin");
        require(consentManager == address(0), "Manager already set");
        require(manager.code.length > 0, "Manager must be a contract");
        consentManager = manager;
        emit ConsentManagerSet(manager);
    }

    function rewardConsent(uint256 recordId, address requester)
        external override returns (bool)
    {
        require(msg.sender == consentManager, "Only consent manager");
        IHealthRegistry.Record memory record = registry.getRecord(recordId);
        address patient = record.patient;

        require(registry.isVerified(patient, IHealthRegistry.Role.Patient), "Patient not verified");
        bool doctor = registry.isVerified(requester, IHealthRegistry.Role.Doctor);
        bool researcher = registry.isVerified(requester, IHealthRegistry.Role.Researcher);
        require(doctor || researcher, "Requester not verified");

        // Renewing the same permission is allowed, but earns no extra points.
        if (rewarded[recordId][requester]) {
            return false;
        }

        rewarded[recordId][requester] = true;
        balanceOf[patient] += REWARD_AMOUNT;
        emit RewardGiven(patient, recordId, requester, REWARD_AMOUNT);
        return true;
    }
}
