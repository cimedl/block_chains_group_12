# Healthcare shared interfaces

These are the implemented interfaces on `integration/p1-p2` after integration fixes.

## Registry and rewards

Import `IHealthRegistry` and `IConsentReward` from `contracts/interfaces/`.
Record IDs are sequential `uint256` values starting at 1. A file commitment remains
a separate `bytes32` SHA-256 value. Records are immutable; changed files receive new IDs.

`getRecord(recordId)` returns patient, recordHash, recordType and reverts for unknown IDs.
`recordExists(recordId)` returns false for unknown IDs without reverting.
`isVerified(account, role)` checks the current verification flag and exact role.

`rewardConsent(recordId, requester)` is restricted to the configured manager, derives
the patient from the registry, and returns true for first payment or false for a
previously rewarded pair. A false return must not block valid renewal/regrant.
Reward eligibility is **record/requester**, with 10 integer points, no decimals,
no transfers and no access-time payout. It is not the earlier roadmap's proposed
patient/requester/category policy. Additional records/requesters can generate points;
this prototype does not establish anti-farming or real identity verification.

## ConsentManager methods

| Method | Result and rules |
| --- | --- |
| `grantAccess(uint256 recordId, string category, address requester, uint256 durationDays)` | Returns new uint256 grant ID. Owner-only; currently verified Patient and Doctor/Researcher; nonzero requester; exact category match; duration 1-365 days; equivalent active grant rejected. |
| `revokeAccess(uint256 recordId, uint256 grantId)` | Owner-only; existing grant must belong to that record and patient; repeated revocation rejected. Does not require current verification, so suspended owners can withdraw consent. |
| `requestAccess(uint256 recordId, uint256 grantId)` | Allocates and returns a uint256 request ID. Emits exactly one decision. An ordinary denial completes successfully. Requesters do not supply the request ID. |
| `checkPermission(uint256 grantId, address requester, uint256 recordId)` | Read-only bool using the same current checks as requestAccess; no request ID allocation or event. |
| `consentGrants(uint256 grantId)` | Returns patient, requester, recordId, category, grantId, startTime, endTime, revokedStatus. Missing IDs have default zero fields. |
| `latestGrantId(uint256 recordId, address requester)` | Latest allocated grant for this pair; it is not a claim that the grant is still active. |

Permission is valid only before endTime. Expiry or revocation permits a fresh grant ID;
it never makes old authorizations valid again. Reverification alone does not remove
revocation or extend expiry. State/counters/reward eligibility roll back if issuance reverts.

### Changes from the unmerged P2 draft

- All record ID inputs/events changed from bytes32 to uint256.
- `requestAccess(recordId, requestId, grantId)` became `requestAccess(recordId, grantId)`;
  use the returned ID or confirmed event rather than predicting an ID from a read call.
- The original six ReasonCode values retain their numeric positions; PATIENT_NOT_VERIFIED
  is appended as value 6.
- P2 no longer declares its own incompatible registry/reward interfaces.

## Events and denial precedence

`AccessDecision(requestId, patient, requester, recordId, grantId, timestamp, allowed, reason)`:

- requester is the transaction caller; patient is the requested record's actual owner.
- Unknown records have patient=zero. Existing records retain owner attribution even
  when no consent exists or a different patient's grant was supplied.
- grantId is the supplied grant only if its patient/requester/record match; otherwise 0.
- IDs are allocated once per request, globally within that manager deployment. Always
  bind them to chain ID and contract address; resets/new deployments can reuse numbers.
- Events describe decisions, not delivery. There is no category field in this event;
  derive the immutable category from the registry record.

| Check order | Reason | Value |
| --- | --- | --- |
| Requested record does not exist | UNKNOWN_RECORD | 3 |
| Requester is unknown, unverified, suspended, or wrong role | UNREGISTERED_REQUESTER | 4 |
| Patient is not currently verified | PATIENT_NOT_VERIFIED | 6 |
| Grant absent or patient/requester/record mismatch | NO_CONSENT | 0 |
| Matching grant revoked | REVOKED | 2 |
| Matching grant at/after endTime | EXPIRED | 1 |
| All checks succeed | GRANTED | 5 |

UNREGISTERED_REQUESTER covers every requester qualification failure, not only never-registered
wallets. `ConsentGranted` and `ConsentRevoked` contain grantId, patient, requester,
recordId, with the first three indexed. Original decision enum numbers are preserved.

## Deployment and P3 consumption

`npm run deploy` on a running local Hardhat node produces `.local/deployment.json`
with chainId, addresses, ABIs, deployment receipts and manager-wiring receipt.
Constructor code-presence checks do not prove arbitrary contracts implement the correct
interfaces; the script deploys actual artifacts and verifies dependency getters.

P3 must authenticate the wallet, fetch confirmed receipts itself, bind the exact chain,
manager, record, requester and grant, check current permission, verify stored file bytes,
and persist one-time redemption. The view accepts an address as a lookup parameter;
that parameter alone is not authentication. Receipt/current-check and transfer are not atomic.

These choices describe this branch; update the team specification and matrix before
claiming wider project acceptance.
