# Healthcare P1 + P2 integration

HealthRegistry, ConsentManager and ConsentReward now compile and work together.
Patients register immutable record commitments, grant a verified Doctor or Researcher
access for 1-365 days, receive eligible reward points, and revoke their own grants.
Access requests record allowed and denied decisions. A Python file service is still
needed to authenticate users and deliver private files.

## Setup and tests

Use a supported even-numbered Node.js release at least 22.13 and Python 3.
Python hashing helpers use only the standard library. The scripts expect `python`
to select Python 3; if your system only provides `python3`, run the equivalent
unittest/hash commands with that executable.

```sh
npm ci
npm run compile
npm test
npm run test:hashes
npm run sample
```

Verified on the environment recorded in `results/p1-p2-fixes/validation.json`:
88 Solidity tests and 5 Python hashing tests pass. Solidity tests instantiate the
real registry, manager and reward contracts; no separate blockchain node is needed
for those tests. The sample hashes a synthetic plaintext fixture; it does not encrypt
or deliver a medical record.

## Local deployment

Start the local blockchain in one terminal:

```sh
npm run node
```

In another terminal, deploy and configure the three contracts:

```sh
npm run deploy
```

The script uses Node's built-in modules and the local unlocked deployment account.
It deploys registry -> reward -> manager, sets the reward's authorized manager, checks
all dependency addresses, and writes addresses, ABIs and receipts to
`.local/deployment.json`. To use a different local port, pass its URL after `--`.
A stopped/reset local node invalidates that deployment; rerun deployment for a fresh
node. The recorded smoke check used a temporary node, which was stopped afterwards.
The script deploys/configures contracts; it does not seed users or run file delivery.

## Rules and interfaces

- IDs are registry-generated `uint256` values, not file hashes.
- `grantAccess(recordId, category, requester, durationDays)` returns a new grant ID.
  The category must exactly match the record's stored type. Equivalent active grants
  are rejected. After revocation or expiry, regrant gets a fresh ID.
- Only the record owner can grant or revoke. Suspended patients may still revoke.
- Both patient and requester must be currently verified for permission to succeed.
  Requesters must be Doctors or Researchers. Identity updates clear verification.
- Permission is expired at `block.timestamp == endTime`.
- `requestAccess(recordId, grantId)` returns a contract-allocated request ID and emits
  `AccessDecision`. Ordinary denials do not revert. `checkPermission` previews the same
  rules without creating an event or consuming an ID.
- P1's reward policy remains 10 non-transferable points per first record/requester
  pair. Renewal/regrant earns no repeat reward; new records can earn separate rewards.
  Access and revocation do not move points. This differs from the earlier roadmap's
  per-category proposal; team report/test expectations must use the actual policy.

Read [shared interfaces](docs/interfaces.md), [healthcare architecture](docs/healthcare-architecture.md),
[fixes and evidence](docs/p1-p2-fixes.md), and the [P1 handoff](docs/P1-HANDOFF.md).
The [original merge report](docs/p1-p2-merge-report.md) describes the historical merge
state before these repairs. Old `results/*.txt` and `results/p1-p2-merge/` logs remain
historical evidence, not the current test outcome.

## Limits and historical material

The blockchain records permission decisions, not proof a person downloaded/read a
file. P3 must implement authenticated receipt redemption, current-grant checks,
integrity verification, replay protection and private file delivery. Use only
synthetic records. Admin verification is a manual demo flag, not proof of a medical
license or identity; hashes do not prove a clinic issued a record.

`EduConsent.zip`, `docs/UML.md`, `docs/uml.*` and `requirements.txt` are historical
education-project material. They are not the healthcare architecture or the required
dependency set for these standard-library helpers. Review and understand the changes,
record individual contributions, and disclose AI assistance in the course report.
