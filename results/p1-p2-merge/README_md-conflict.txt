Original conflict snapshot (line-numbered; trailing whitespace omitted):
0001: <<<<<<< HEAD
0002: # Healthcare project — P1 first draft
0003:
0004: This is just P1's part: identity registration, medical-record hashes and consent
0005: reward points. The education project is still on the separate `plan-c` branch.
0006:
0007: ## Try it
0008:
0009: Use Node.js 22.13+ on a supported even-numbered release, and Python 3.
0010:
0011: ```sh
0012: npm ci
0013: npm test
0014: npm run test:hashes
0015: npm run sample
0016: ```
0017:
0018: The first Solidity compile needs an internet connection to download the compiler.
0019: Python uses only the standard library. Tests run locally with Hardhat and do not
0020: need a separate node, a wallet extension or real medical information.
0021:
0022: ## Start reading here
0023:
0024: - `contracts/HealthRegistry.sol`: users, admin verification and record registration.
0025: - `contracts/ConsentReward.sol`: ten reward points for each first record/requester grant.
0026: - `contracts/interfaces/`: the functions other contracts need from P1.
0027: - `test/HealthRegistry.t.sol` and `test/ConsentReward.t.sol`: component tests.
0028: - `scripts/hash_data.py`: the identity and file hashing rules for P3.
0029: - `data/`: fake identity and record examples, not real health information.
0030: - `docs/P1-HANDOFF.md`: proposed interfaces and decisions to agree with teammates.
0031: - `results/`: saved output from tests and the sample script.
0032:
0033: ## What this draft does
0034:
0035: A user registers as a patient, doctor or researcher. The admin marks their role
0036: verified after an off-chain check. A verified patient can register several records,
0037: even of the same type. Each gets its own record ID, owner, file hash and type.
0038: Files, names and storage locations are not stored in the contract.
0039:
0040: Only the configured consent-manager contract can award points. A first grant for
0041: a record/requester pair earns the record's patient ten points. Repeating it gives
0042: no extra points. Points cannot be transferred, spent or used to gain access.
0043:
0044: This is not the full application yet. Consent requests, expiry, revocation, access
0045: logs, wallet login, encryption and file release belong to P2/P3. The reward tests
0046: use a small caller stub, not a real consent manager. Admin verification is a
0047: manual flag, not automatic identity or medical-license verification. A hash does
0048: not prove a clinic issued a record. Wallets, roles, record types and events are
0049: public; Solidity `private` does not make blockchain data secret.
0050:
0051: No report or presentation is included. This draft is for local review before sharing.
0052: =======
0053: # EduConsent
0054:
0055: A small education project for sharing student diplomas, transcripts and certificates.
0056: Students keep their JSON records locally and use a Solidity contract to decide which
0057: employer can access each type of record and for how long.
0058:
0059: UML diagram: [view image](docs/uml.svg) · [diagram notes and Mermaid source](docs/UML.md).
0060:
0061: ## Files to read first
0062:
0063: - `contracts/EduConsent.sol`: registration, record hashes, consent, rewards and audit events.
0064: - `test/EduConsent.t.sol`: Solidity unit tests, including a randomized duration test.
0065: - `scripts/education.py`: simple Python helpers for local files and contract calls.
0066: - `scripts/demo.py`: the complete sharing example, with assertions.
0067: - `test/test_integration.py`: tests the contract and local file sharing together.
0068: - `scripts/benchmark.py`: records transaction gas and local confirmation times.
0069: - `results/`: captured test output, demo output and gas measurements.
0070:
0071: ## Install
0072:
0073: Use Node.js 22.13+ on a supported even-numbered release and Python 3.10+.
0074: Tested here with Node.js 26.8.1 and Python 3.14.7.
0075:
0076: ```sh
0077: npm ci
0078: python3 -m venv .venv
0079: .venv/bin/pip install -r requirements.txt
0080: npm run compile
0081: npm test
0082: ```
0083:
0084: The first compile downloads Solidity 0.8.28. Python and Node dependencies also
0085: need an internet connection during installation.
0086:
0087: ## Run the project
0088:
0089: Start the blockchain in one terminal and leave it running:
0090:
0091: ```sh
0092: npm run node
0093: ```
0094:
0095: In a second terminal, from this project directory:
0096:
0097: ```sh
0098: npm run demo
0099: npm run test:integration
0100: npm run benchmark
0101: ```
0102:
0103: The Python commands use `.venv/bin/python` (macOS/Linux). On Windows, use
0104: `.venv\Scripts\python` with the same Python script or unittest arguments.
0105: Each demo, test and benchmark deploys a fresh contract. The demo stores fictional
0106: records under `.local/records`. No wallet extension or public testnet is needed.
0107:
0108: ## What the demo shows
0109:
0110: 1. Register a fictional student and publish a diploma hash.
0111: 2. Try access before consent: denied, with an on-chain event.
0112: 3. Grant the employer one day of consent: access succeeds and the file hash matches.
0113: 4. Give the student 10 non-transferable reward points for the first grant.
0114: 5. Revoke consent: later access fails.
0115: 6. Grant again and advance the local blockchain clock: expired access fails.
0116: 7. Check the audit history and confirm repeat grants earned no extra rewards.
0117:
0118: `DataType` values are `0` for diploma, `1` for transcript and `2` for certificate.
0119: The same consent functions work for all three. Consent lasts 1–365 days and applies
0120: to the student's current record of the chosen type, including later replacements.
0121: Only the student can change their identity, record hash or consent; each function
0122: uses `msg.sender` as the owner. An employer does not need a student registration.
0123: There is no administrator with permission to override consent.
0124:
0125: ## Design notes
0126:
0127: Identity attributes are combined with a random salt and hashed as canonical JSON
0128: (sorted keys, compact separators). Only that hash goes on-chain. Education records
0129: also contain a random salt and are stored locally; their hashes go on-chain.
0130: No actual student data is used. Contract events record registration, updates,
0131: publication, grants, revocations, rewards and access decisions.
0132:
0133: Rewards are a simple balance of non-transferable points, not an ERC-20 currency.
0134: Access depends only on consent, never on holding points. The first grant for each
0135: student/requester/data-type combination earns 10 points. Repeating that grant
0136: cannot farm points, but creating new requester wallets can; this demo has no
0137: real-world identity checks and the points have no financial value.
0138:
0139: Denied access returns `false` instead of reverting so its audit event survives.
0140: The log records the permission decision, not proof that the requester downloaded
0141: or read the file. Python checks file availability, the current consent and the
0142: hash before returning the record. Record integrity does not prove a university
0143: issued a qualification: issuer signatures are outside this project's scope.
0144:
0145: This is a local teaching prototype. Hardhat accounts are unlocked, and the Python
0146: script acts as the student's trusted local sharing process. Do not expose the RPC
0147: port or turn these helpers into an unauthenticated public server. Someone with
0148: filesystem access can read the JSON directly. Revocation blocks future releases
0149: through this workflow; it cannot erase a copy already shared. The chain exposes
0150: addresses, data types and access metadata. Resetting the local development chain
0151: erases its history; the contract itself provides no event-deletion operation.
0152:
0153: ## Test and measurement output
0154:
0155: - `results/solidity-tests.txt`: Hardhat unit test output.
0156: - `results/integration-tests.txt`: Python integration test output.
0157: - `results/demo-output.txt`: the actual end-to-end demo output.
0158: - `results/demo-transactions.json`: receipts' gas measurements and transaction hashes.
0159: - `results/gas-summary.csv`: average gas and confirmation time per operation at 1, 5 and 10 students.
0160: - `results/gas-samples.json`: individual measurements behind the averages.
0161:
0162: The benchmark performs ten allowed accesses per student and measures all writing
0163: functions, including deployment, denied access and repeated consent. Getters use
0164: `eth_call`, so they have no transaction fee. Gas units are not a monetary price.
0165: Confirmation times include submission, auto-mining and receipt retrieval on one
0166: local machine; they are not a public-network performance estimate. The benchmark
0167: runs sequentially and is not a concurrent load test.
0168: >>>>>>> origin/p2
