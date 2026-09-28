# EduConsent

A small education project for sharing student diplomas, transcripts and certificates.
Students keep their JSON records locally and use a Solidity contract to decide which
employer can access each type of record and for how long.

UML diagram: [view image](docs/uml.svg) · [diagram notes and Mermaid source](docs/UML.md).

## Files to read first

- `contracts/EduConsent.sol`: registration, record hashes, consent, rewards and audit events.
- `test/EduConsent.t.sol`: Solidity unit tests, including a randomized duration test.
- `scripts/education.py`: simple Python helpers for local files and contract calls.
- `scripts/demo.py`: the complete sharing example, with assertions.
- `test/test_integration.py`: tests the contract and local file sharing together.
- `scripts/benchmark.py`: records transaction gas and local confirmation times.
- `results/`: captured test output, demo output and gas measurements.

## Install

Use Node.js 22.13+ on a supported even-numbered release and Python 3.10+.
Tested here with Node.js 26.8.1 and Python 3.14.7.

```sh
npm ci
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm run compile
npm test
```

The first compile downloads Solidity 0.8.28. Python and Node dependencies also
need an internet connection during installation.

## Run the project

Start the blockchain in one terminal and leave it running:

```sh
npm run node
```

In a second terminal, from this project directory:

```sh
npm run demo
npm run test:integration
npm run benchmark
```

The Python commands use `.venv/bin/python` (macOS/Linux). On Windows, use
`.venv\Scripts\python` with the same Python script or unittest arguments.
Each demo, test and benchmark deploys a fresh contract. The demo stores fictional
records under `.local/records`. No wallet extension or public testnet is needed.

## What the demo shows

1. Register a fictional student and publish a diploma hash.
2. Try access before consent: denied, with an on-chain event.
3. Grant the employer one day of consent: access succeeds and the file hash matches.
4. Give the student 10 non-transferable reward points for the first grant.
5. Revoke consent: later access fails.
6. Grant again and advance the local blockchain clock: expired access fails.
7. Check the audit history and confirm repeat grants earned no extra rewards.

`DataType` values are `0` for diploma, `1` for transcript and `2` for certificate.
The same consent functions work for all three. Consent lasts 1–365 days and applies
to the student's current record of the chosen type, including later replacements.
Only the student can change their identity, record hash or consent; each function
uses `msg.sender` as the owner. An employer does not need a student registration.
There is no administrator with permission to override consent.

## Design notes

Identity attributes are combined with a random salt and hashed as canonical JSON
(sorted keys, compact separators). Only that hash goes on-chain. Education records
also contain a random salt and are stored locally; their hashes go on-chain.
No actual student data is used. Contract events record registration, updates,
publication, grants, revocations, rewards and access decisions.

Rewards are a simple balance of non-transferable points, not an ERC-20 currency.
Access depends only on consent, never on holding points. The first grant for each
student/requester/data-type combination earns 10 points. Repeating that grant
cannot farm points, but creating new requester wallets can; this demo has no
real-world identity checks and the points have no financial value.

Denied access returns `false` instead of reverting so its audit event survives.
The log records the permission decision, not proof that the requester downloaded
or read the file. Python checks file availability, the current consent and the
hash before returning the record. Record integrity does not prove a university
issued a qualification: issuer signatures are outside this project's scope.

This is a local teaching prototype. Hardhat accounts are unlocked, and the Python
script acts as the student's trusted local sharing process. Do not expose the RPC
port or turn these helpers into an unauthenticated public server. Someone with
filesystem access can read the JSON directly. Revocation blocks future releases
through this workflow; it cannot erase a copy already shared. The chain exposes
addresses, data types and access metadata. Resetting the local development chain
erases its history; the contract itself provides no event-deletion operation.

## Test and measurement output

- `results/solidity-tests.txt`: Hardhat unit test output.
- `results/integration-tests.txt`: Python integration test output.
- `results/demo-output.txt`: the actual end-to-end demo output.
- `results/demo-transactions.json`: receipts' gas measurements and transaction hashes.
- `results/gas-summary.csv`: average gas and confirmation time per operation at 1, 5 and 10 students.
- `results/gas-samples.json`: individual measurements behind the averages.

The benchmark performs ten allowed accesses per student and measures all writing
functions, including deployment, denied access and repeated consent. Getters use
`eth_call`, so they have no transaction fee. Gas units are not a monetary price.
Confirmation times include submission, auto-mining and receipt retrieval on one
local machine; they are not a public-network performance estimate. The benchmark
runs sequentially and is not a concurrent load test.
