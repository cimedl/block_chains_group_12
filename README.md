# Healthcare decentralized identity and data sharing

HealthRegistry, ConsentManager and ConsentReward work together on a local Hardhat
network. Patients register hashed identities and immutable record commitments, grant a
verified Doctor or Researcher access for 1-365 days, receive reward points, and revoke
their own grants. Every access request records an allowed or denied decision on-chain.
A Python service delivers the encrypted record off-chain only to a requester with valid
consent and a matching wallet signature.

## Project structure

| Path | Contents |
| --- | --- |
| `contracts/HealthRegistry.sol` | User registration (hashed identity + role), admin verification, record commitments |
| `contracts/ConsentManager.sol` | Consent grant/revoke, access requests and the `AccessDecision` audit events |
| `contracts/ConsentReward.sol` | Non-transferable reward points for granting consent |
| `contracts/interfaces/` | Shared interfaces between the contracts |
| `offchain/` | Hashing, encryption, signed-request verification and SQLite replay protection |
| `scripts/deploy.mjs` | Deploys and wires the three contracts on the local node |
| `scripts/hash_data.py` | Computes identity and record hashes |
| `scripts/p4_verify.py` | Runs all Solidity and Python tests and records outcomes and source hashes |
| `scripts/p4_benchmark.py` | Measures gas and timing for synthetic multi-user workloads |
| `scripts/p4_report.py` | Builds test, gas and scaling tables from matching verification and benchmark runs |
| `scripts/healthcare_demo.py` | Demonstrates registration, delivery, replay rejection and revocation |
| `test/*.t.sol` | Solidity unit tests, one file per contract |
| `test/test_*.py` | Python hashing tests and the end-to-end delivery integration test |
| `data/` | Synthetic (fake) identity and record fixtures; no real personal data |
| `results/` | Test, gas and scaling results used in the report |

## Setup and tests

Use a supported even-numbered Node.js release (at least 22.13) and Python 3.13.
Use the virtual environment's interpreter explicitly so a different default Python
installation does not load its native packages.

```powershell
npm ci
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm run compile
npm test
.\.venv\Scripts\python.exe -m unittest discover -s test -p "test_*.py" -v
.\.venv\Scripts\python.exe scripts/hash_data.py
```

`npm test` runs the Solidity unit tests. The Python command runs the hashing tests and
the delivery integration test, which starts and stops its own temporary Hardhat node.

To run all tests and regenerate measurement tables, run these commands in order:

```powershell
.\.venv\Scripts\python.exe scripts/p4_verify.py
.\.venv\Scripts\python.exe scripts/p4_benchmark.py --users 5 20 50 --repetitions 3
.\.venv\Scripts\python.exe scripts/p4_report.py
```

Verification and benchmarking start and stop their own temporary local nodes. Raw
results are saved under `results/p4-current/` and `results/p4-evaluation/`; each
directory's `latest.json` selects the most recent run. The report generator rejects
verification and measurements from different application sources, then writes a
Markdown report and three CSV tables under `results/p4-generated/`. Generated runs
are ignored by Git and do not replace the committed report evidence.

## Local deployment

Start the local blockchain in one terminal:

```sh
npm run node
```

In another terminal, deploy and configure the three contracts:

```sh
npm run deploy
```

The script deploys registry -> reward -> manager, sets the reward's authorized manager,
checks all dependency addresses, and writes addresses, ABIs and receipts to
`.local/deployment.json`. To use a different local port, pass its URL after `--`.
A stopped or reset local node invalidates that deployment; rerun deployment for a fresh node.

With that node still running, demonstrate the complete synthetic workflow:

```powershell
.\.venv\Scripts\python.exe scripts/healthcare_demo.py
```

## Results

| File | What it shows |
| --- | --- |
| `results/test-results-all-tests-with-why-critical.csv` | Pass/fail of every unit and integration test, and why each tested function matters |
| `results/solidity-unit-tests-output.txt` | Raw output of the Solidity unit tests |
| `results/python-hashing-and-integration-tests-output.txt` | Raw output of the Python hashing and delivery integration tests |
| `results/gas-deployment-and-function-costs.csv` | Deployment cost per contract and average gas per function |
| `results/scaling-time-and-cost-by-number-of-users.csv` | Total gas, transactions and time for 5, 20 and 50 patients (3 runs each) |

Gas and timing values are from a local auto-mining Hardhat node, not a public network.

## Rules

- IDs are registry-generated `uint256` values, not file hashes.
- `grantAccess(recordId, category, requester, durationDays)` emits the new grant ID
  in `ConsentGranted`. The category must exactly match the record's stored type.
  Repeated grants receive separate IDs. Revoking one grant does not revoke the others.
- Only the record owner can grant or revoke. Suspended patients may still revoke.
- Both patient and requester must be currently verified for permission to succeed.
  Requesters must be Doctors or Researchers. Identity updates clear verification.
- Permission is expired at `block.timestamp == endTime`.
- `requestAccess(recordId, grantId)` emits a contract-allocated request ID in
  `AccessDecision`. Ordinary denials do not revert, so failed attempts are logged too.
  `checkPermission` previews the same rules without creating an event.
- The reward policy is 10 non-transferable points per first record/requester pair.
  Renewal earns no repeat reward. Access and revocation do not move points.

## Off-chain delivery

Register each record's private file and key paths with `register_record_file`, then obtain
a message using `issue_delivery_challenge` and sign that exact message. Challenges expire
after five minutes and are consumed with the access receipt. Decryption requires an
existing key and uses the verified ciphertext bytes. A claimed request stays consumed
after a decryption failure; a new access request is needed to retry.

## Limits

The blockchain records permission decisions, not proof that a person downloaded or read a
file. Local SQLite delivery records can be changed and are not tamper-proof. Revocation
cannot erase copies already delivered. Admin verification is a manual flag, not proof of a
medical license or identity. Use only synthetic records.
