// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {EduConsent} from "../contracts/EduConsent.sol";

// These helpers let tests change the caller, skip time and check errors.
// They only work in tests, not in the actual contract.
interface Vm {
    function prank(address sender) external;
    function warp(uint256 timestamp) external;
    function expectRevert(bytes calldata reason) external;
    function expectEmit(bool topic1, bool topic2, bool topic3, bool data) external;
}

contract EduConsentTest {
    // This is the standard address for the test helpers.
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));
    EduConsent platform;
    address student = address(0xA11CE);
    address employer = address(0xB0B);
    address stranger = address(0xCAFE);
    bytes32 identityHash = keccak256("fictional identity with a salt");
    bytes32 diplomaHash = keccak256("fictional diploma with a salt");
    EduConsent.DataType diploma = EduConsent.DataType.Diploma;

    event AccessLogged(address indexed student, address indexed requester, EduConsent.DataType indexed dataType, bool allowed, uint256 timestamp, bytes32 dataHash);

    // Start each test with a new contract and one student with a diploma.
    function setUp() public {
        platform = new EduConsent();
        vm.prank(student); // Make the next call as the student.
        platform.register(identityHash);
        vm.prank(student);
        platform.publishData(diploma, diplomaHash);
    }

    // Several tests need the same one-day permission.
    function grant() internal {
        vm.prank(student);
        platform.grantConsent(employer, diploma, 1);
    }

    function testRegistrationStoresHash() public view {
        (bytes32 saved, bool registered) = platform.identities(student);
        require(saved == identityHash && registered, "Identity missing");
    }

    function testDuplicateRegistrationRejected() public {
        vm.expectRevert(bytes("Already registered"));
        vm.prank(student);
        platform.register(identityHash);
    }

    function testEmptyIdentityRejected() public {
        vm.expectRevert(bytes("Empty hash"));
        vm.prank(stranger);
        platform.register(bytes32(0));
    }

    function testIdentityUpdate() public {
        bytes32 updated = keccak256("updated fictional identity");
        vm.prank(student);
        platform.updateIdentity(updated);
        (bytes32 saved,) = platform.identities(student);
        require(saved == updated, "Update failed");
    }

    function testUnregisteredCannotUpdate() public {
        vm.expectRevert(bytes("Register first"));
        vm.prank(stranger);
        platform.updateIdentity(identityHash);
    }

    function testUnregisteredCannotPublish() public {
        vm.expectRevert(bytes("Register first"));
        vm.prank(stranger);
        platform.publishData(diploma, diplomaHash);
    }

    function testEmptyDataRejected() public {
        vm.expectRevert(bytes("Empty hash"));
        vm.prank(student);
        platform.publishData(diploma, bytes32(0));
    }

    function testGrantEnablesOnlySelectedTypeAndRequester() public {
        grant();
        require(platform.hasConsent(student, employer, diploma), "Missing permission");
        require(!platform.hasConsent(student, stranger, diploma), "Wrong requester allowed");
        require(!platform.hasConsent(student, employer, EduConsent.DataType.Transcript), "Wrong type allowed");
    }

    function testZeroDaysRejected() public {
        vm.expectRevert(bytes("Use 1 to 365 days"));
        vm.prank(student);
        platform.grantConsent(employer, diploma, 0);
    }

    function test366DaysRejected() public {
        vm.expectRevert(bytes("Use 1 to 365 days"));
        vm.prank(student);
        platform.grantConsent(employer, diploma, 366);
    }

    function test365DaysAccepted() public {
        vm.prank(student);
        platform.grantConsent(employer, diploma, 365);
        (uint64 expiry,) = platform.consents(student, employer, diploma);
        require(expiry == block.timestamp + 365 days, "Wrong duration");
    }

    function testZeroRequesterRejected() public {
        vm.expectRevert(bytes("Invalid requester"));
        vm.prank(student);
        platform.grantConsent(address(0), diploma, 1);
    }

    function testSelfConsentRejected() public {
        vm.expectRevert(bytes("Invalid requester"));
        vm.prank(student);
        platform.grantConsent(student, diploma, 1);
    }

    function testMissingDataRejected() public {
        vm.expectRevert(bytes("Publish data first"));
        vm.prank(student);
        platform.grantConsent(employer, EduConsent.DataType.Transcript, 1);
    }

    function testUnregisteredCannotGrant() public {
        vm.expectRevert(bytes("Register first"));
        vm.prank(stranger);
        platform.grantConsent(employer, diploma, 1);
    }

    function testRewardsOnlyOncePerPermission() public {
        grant();
        vm.prank(student);
        platform.revokeConsent(employer, diploma);
        grant();
        require(platform.rewardBalance(student) == 10, "Repeated reward");
    }

    function testAccessDoesNotTransferRewards() public {
        grant();
        vm.prank(employer);
        require(platform.requestAccess(student, diploma), "Access denied");
        require(platform.rewardBalance(student) == 10, "Student reward changed");
        require(platform.rewardBalance(employer) == 0, "Requester received rewards");
    }

    function testRevokeStopsAccess() public {
        grant();
        vm.prank(student);
        platform.revokeConsent(employer, diploma);
        require(!platform.hasConsent(student, employer, diploma), "Revoke failed");
    }

    function testOtherStudentCannotRevokeOwnersConsent() public {
        grant();
        vm.prank(stranger);
        platform.register(identityHash);
        vm.expectRevert(bytes("No active consent"));
        vm.prank(stranger);
        platform.revokeConsent(employer, diploma);
        require(platform.hasConsent(student, employer, diploma), "Owner permission changed");
    }

    function testExactExpiryIsDenied() public {
        grant();
        (uint64 expiry,) = platform.consents(student, employer, diploma);
        vm.warp(expiry - 1);
        require(platform.hasConsent(student, employer, diploma), "Expired too soon");
        vm.warp(expiry);
        require(!platform.hasConsent(student, employer, diploma), "Expired permission allowed");
    }

    function testDeniedAccessEmitsAuditEvent() public {
        vm.expectEmit(true, true, true, true);
        emit AccessLogged(student, employer, diploma, false, block.timestamp, diplomaHash);
        vm.prank(employer);
        require(!platform.requestAccess(student, diploma), "Unexpected access");
    }

    function testAllowedAccessEmitsAuditEvent() public {
        grant();
        vm.expectEmit(true, true, true, true);
        emit AccessLogged(student, employer, diploma, true, block.timestamp, diplomaHash);
        vm.prank(employer);
        require(platform.requestAccess(student, diploma), "Unexpected denial");
    }

    function testUnknownStudentDenied() public {
        vm.prank(employer);
        require(!platform.requestAccess(stranger, diploma), "Unknown student allowed");
    }

    function testFuzzDuration(uint16 daysInput) public {
        // Keep the random input between 1 and 365 days.
        uint256 duration = uint256(daysInput) % 365 + 1;
        vm.prank(student);
        platform.grantConsent(employer, diploma, duration);
        (uint64 expiry,) = platform.consents(student, employer, diploma);
        require(expiry == block.timestamp + duration * 1 days, "Wrong fuzzed expiry");
    }
}
