# Healthcare project — P1 first draft

This is just P1's part: identity registration, medical-record hashes and consent
reward points. The education project is still on the separate `plan-c` branch.

## Try it

Use Node.js 22.13+ on a supported even-numbered release, and Python 3.

```sh
npm ci
npm test
npm run test:hashes
npm run sample
```

The first Solidity compile needs an internet connection to download the compiler.
Python uses only the standard library. Tests run locally with Hardhat and do not
need a separate node, a wallet extension or real medical information.

## Start reading here

- `contracts/HealthRegistry.sol`: users, admin verification and record registration.
- `contracts/ConsentReward.sol`: ten reward points for each first record/requester grant.
- `contracts/interfaces/`: the functions other contracts need from P1.
- `test/HealthRegistry.t.sol` and `test/ConsentReward.t.sol`: component tests.
- `scripts/hash_data.py`: the identity and file hashing rules for P3.
- `data/`: fake identity and record examples, not real health information.
- `docs/P1-HANDOFF.md`: proposed interfaces and decisions to agree with teammates.
- `results/`: saved output from tests and the sample script.

## What this draft does

A user registers as a patient, doctor or researcher. The admin marks their role
verified after an off-chain check. A verified patient can register several records,
even of the same type. Each gets its own record ID, owner, file hash and type.
Files, names and storage locations are not stored in the contract.

Only the configured consent-manager contract can award points. A first grant for
a record/requester pair earns the record's patient ten points. Repeating it gives
no extra points. Points cannot be transferred, spent or used to gain access.

This is not the full application yet. Consent requests, expiry, revocation, access
logs, wallet login, encryption and file release belong to P2/P3. The reward tests
use a small caller stub, not a real consent manager. Admin verification is a
manual flag, not automatic identity or medical-license verification. A hash does
not prove a clinic issued a record. Wallets, roles, record types and events are
public; Solidity `private` does not make blockchain data secret.

No report or presentation is included. This draft is for local review before sharing.
