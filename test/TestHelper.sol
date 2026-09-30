// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

// Hardhat test helpers: change the caller and check errors or events.
interface Vm {
    function prank(address sender) external;
    function expectRevert(bytes calldata reason) external;
    function expectEmit(bool topic1, bool topic2, bool topic3, bool data) external;
}

abstract contract TestHelper {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));
}
