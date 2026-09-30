# P1 handoff — draft interfaces

This is a proposed first version, not a team-approved interface yet.

## HealthRegistry

Deploy with `new HealthRegistry(adminAddress)`.
Roles are `None=0`, `Patient=1`, `Doctor=2`, `Researcher=3`.
Each address has one role; it cannot change roles after registration.

- `registerUser(bytes32 identityHash, Role role)`: the caller registers unverified.
- `updateIdentity(bytes32 identityHash)`: changes the caller's hash and clears verification.
- `setVerification(address account, bool verified)`: admin only; also supports suspension.
- `registerRecord(bytes32 recordHash, string recordType) -> uint256`: verified patients only.
- `getUser(address account) -> User`: returns `(identityHash, role, verified)`.
- `getRecord(uint256 recordId) -> Record`: returns `(patient, recordHash, recordType)`.
- `isVerified(address account, Role role) -> bool`: false for unknown users and None.

Unknown users/records make getUser/getRecord revert. IDs start at 1. Record types
are 1–64 UTF-8 bytes; use short generic labels such as `Blood_Test_Panel`.
Record ownership comes from the caller, not a user-supplied patient address.
Records cannot be edited or deleted in v1. A corrected file gets a new ID and must
receive new consent through P2. P3 keeps a private `(chainId, registryAddress,
recordId) -> encrypted file location` lookup. No storage URI goes on-chain.

Events: UserRegistered, IdentityUpdated, VerificationChanged, RecordRegistered.
These are registry changes, not P2's data-access audit events.

## P2: consent and rewards

Import IHealthRegistry and IConsentReward from `contracts/interfaces`.
When granting consent, check that the patient is the record owner and currently
verified, and that the requester is a verified Doctor or Researcher. P2 must also
check requests, durations, expiry and revocation. Role checks must be repeated at
access time: verification can be removed after a grant.

After successfully creating consent, in the same transaction call:

```solidity
bool paid = reward.rewardConsent(recordId, requester);
```

Only the configured ConsentManager may call this. The reward contract independently
checks the record and roles, derives the patient from the record owner, and awards
10 points once per `(recordId, requester)`. A duplicate returns false without
reverting, so renewals can still succeed. P2 should not require `paid == true`.
Calls with invalid records/roles or by unauthorized callers revert. Do not catch
those errors and silently continue a grant unless the team explicitly changes
this atomic grant/reward policy.

The reward contract trusts ConsentManager to enforce patient approval. It does not
prove consent exists by itself. Never configure RewardCallerStub from the test file
as the application's manager: it deliberately skips consent for component tests.
Points do not get spent on access, and revoke/expiry does not claw points back.

Reward policy is a simple non-transferable balance, NOT an ERC-20. One requester
can earn a separate patient reward for each record. New record IDs or new verified
requesters can generate more points, so this is not complete anti-farming protection.
Points have no monetary value. Confirm this model with the team before integration.

## P3: proposed identity and record schema

`data/fake-identity.json` shows the identity fields. All values are strings:
name, email, personal_id, date_of_birth (YYYY-MM-DD), salt (64 lowercase hex digits).
For actual generated test identities, use a fresh `secrets.token_hex(32)` salt.
Fixed salts in the committed files are only reproducible fake test fixtures.

Identity hash = SHA-256 of UTF-8 JSON using Python `json.dumps(identity,
sort_keys=True, separators=(",", ":"), ensure_ascii=True)`. Send the 32-byte hash
as a `0x`-prefixed hexadecimal string. Use this exact encoding across components.
Do not substitute Ethereum keccak256: this draft uses SHA-256.

`data/fake-record.json` proposes the plaintext schema: schema_version, record_type,
issued_at, issuer, salt and a results list of `{test, value, unit}`. Values are
strings to avoid floating-point formatting differences. P3 should validate the
schema and encrypt the record, including its salt, before storing it.

Record hash = SHA-256 of the exact stored encrypted file bytes. P3 owns the encryption
format and key handling. The sample script hashes the plaintext fixture only to
demonstrate the helper; it does not encrypt or create a production-ready record.
After integration, verify encrypted bytes against getRecord(recordId).recordHash
before decrypting/releasing. Plaintext and encrypted-file hashes are different.
Wallet authentication, receipt checks, current consent checks and one-time receipt
redemption remain P3's work. This component does not promise researcher anonymity.

## P5: deployment order

1. Deploy HealthRegistry with the chosen admin.
2. Deploy ConsentReward(registryAddress, adminAddress).
3. Deploy P2's ConsentManager with registry/reward addresses (constructor agreed with P2).
4. As reward admin, call setConsentManager(managerAddress) once.
5. Seed fake users, verify them, then register fake record hashes.

The reward manager must be a deployed contract and can be set only once. Do not
call setConsentManager in ConsentManager's constructor: its runtime code will not
exist yet. Redeploy ConsentReward if the wrong manager was selected in local testing.
Admins are immutable in v1. P5 should use the same intended admin for both contracts.

## Validation boundary

P1 tests check registration, verification permissions, identity changes, record
ownership/IDs, reward authorization and duplicate prevention. They do not establish
that P2 consent rules or P3 file-release security work. P4 needs real cross-component
tests after integration, including revoked/expired access and suspended roles.

## Integrated ConsentManager on integration/p1-p2

P2 now imports the shared P1 interfaces and uses uint256 record IDs. Registry adds
recordExists(recordId), a non-reverting existence lookup for ordinary denied requests.

- grantAccess(recordId, category, requester, durationDays) returns grantId.
- revokeAccess(recordId, grantId) binds both patient and record before mutation.
- requestAccess(recordId, grantId) allocates and returns a unique requestId.
- checkPermission(grantId, requester, recordId) previews the current decision.

Patient/requester verification is checked at grant and access time. Category must
exactly match the registry recordType. Duplicate active grants are rejected; revoked
or expired grants can be replaced with a new ID. Reward=false on a valid duplicate
eligibility key is accepted. Expiry equality is denied. Read docs/interfaces.md for
event semantics and reason precedence, and docs/p1-p2-fixes.md for actual evidence.
These branch integration choices and the retained per-record reward policy must be
reflected in the team's agreed specification and final report.
