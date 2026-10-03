# P3 merge: review before pushing
<!-- TODO: review this added checklist and every item before pushing. -->

Target: integration/p1-p2, originally 0bc5bbbc99369dcc32c44d33c30ace907b4eff53.
Source: origin/part3 at f14244498940bf3f2246c6ea0a659a6afa238c36.
This lists every incoming file, manual resolution, and local addition. Unchecked items require human review even when validation passes. No push is part of this change.

## Manual additions and conflict resolutions

- [ ] Review .gitignore: retained target exclusions; added .idea/, data/secret.key, data/*.enc, and *.db / *.db-journal / *.db-wal / *.db-shm. Omitted P3's blanket test/, docs/, results/, and data/ exclusions so future source/review files remain visible.
- [ ] Review package.json resolution: retained the target version and all compile/test/node/deploy/hash/sample commands. No npm commands or dependencies were added.
- [ ] Review README.md resolution: retained target paragraphs and appended only P3 service/dependency notes, a historical-state clarification, and the checklist link.
- [ ] Review offchain/offchain_service.py: added self.data_dir = data_dir so delivery uses the supplied directory.
- [ ] Review offchain/offchain_service.py: added request_id = str(int(request_id)) before authentication/replay checks. Leading-zero IDs previously replayed consumed receipts; normalization makes SQLite keys agree with receipt comparison.
- [ ] Review offchain/storage_db.py: create the parent directory only when one exists, fixing the service's bare default database filename.
- [ ] Review offchain/storage_db.py: added contextlib.closing around all three connection contexts, retaining explicit commits. The previous SQLite context did not close connections and left database files locked on Windows.
- [ ] Review requirements.txt: retained Web3 7.16.0 and P3's cryptography 44.0.0; changed eth-account 0.13.4 to 0.13.6, Web3's minimum supported version. Review the complete pinned set before distribution.
- [ ] Review this new docs/p3-merge-todo.md checklist and update it as review progresses.

## All incoming files

- [ ] Review offchain/crypto_utils.py, offchain/encrypt_record.py, offchain/offchain_service.py, and offchain/storage_db.py. Only the small corrections above were applied to incoming module bodies.
- [ ] Review removal of contracts/EduConsent.sol, scripts/education.py, scripts/demo.py, and scripts/benchmark.py. These inherited education files were outside the healthcare project.
- [ ] Review removal of results/benchmark-output.txt, results/demo-output.txt, results/demo-transactions.json, results/gas-samples.json, results/gas-summary.csv, and results/integration-tests.txt. These saved education outputs do not belong to this healthcare project.
- [ ] Review the full merge diff against the target parent and manual corrections against the P3 parent. Healthcare contracts/interfaces, existing tests, deployment script, and package lock were retained from the target.
- [ ] Decide separately whether to integrate the newer origin/integration/p1-p2-runtime commits. Only runtime history already present in part3 is included here.

## Remaining P3 issues and coverage

- [ ] Bind signed challenges to the chain, contract, record, request ID, transaction, and a server-issued nonce/expiry. Currently callers supply arbitrary signed text and the service only recovers the signer.
- [ ] Validate receipt event emitters explicitly, select the matching event instead of always events[0], and define finality/reorganization handling.
- [ ] Replace or retire check_consent(): it calls isConsentGranted(), which the merged ConsentManager does not implement. Delivery uses the correct checkPermission() API.
- [ ] Replace hard-coded fake-record.enc / secret.key with an agreed record-to-file/key mapping before multi-record delivery.
- [ ] Define failed-delivery and concurrent-redemption behavior: consumption is committed before reading the key/decrypting, so failed decryption prevents retry.
- [ ] Namespace replay IDs by chain/deployment, define database resets for redeployment, and handle uint256 record IDs larger than SQLite INTEGER.
- [ ] Agree on ciphertext versus plaintext commitments: P3 verifies ciphertext; the existing sample hashes its supplied fixture bytes.
- [ ] Add maintained automated healthcare delivery coverage for expiry, verification removal, multiple records/events, wrong event emitters, failed decryption, and concurrency. The smoke run covers only the flows listed below.
- [ ] Reconcile older README passages describing P3/requirements as historical or unimplemented when preparing final documentation; this merge appended clarification while preserving existing paragraphs.

## Validation and local additions

- [x] npm run compile passed (Solidity 0.8.28; incoming EduConsent compiled).
- [x] npm test: 88 existing Solidity tests passed.
- [x] .venv/Scripts/python.exe -m unittest discover -s test -p 'test_*.py' -v: 5 existing Python hash tests passed.
- [x] Corrected requirements installed successfully; python -m pip check reported no broken requirements.
- [x] Temporary local-blockchain smoke: startup with custom data directory/default bare database filename, nested database parent creation, real signature mismatch rejection, receipt-ID mismatch rejection, encrypted delivery/on-chain hash verification, replay rejection after restart, leading-zero replay rejection, ciphertext tampering rejection, revoked-grant rejection, and denied-receipt rejection. Ten checks passed.
- [ ] Review ignored local additions: .local/p3-merge-smoke.py, .local/p3-merge-validation.json, .local/p3-merge-node.log, and .local/p3-merge-node-error.log. Fresh contracts used port 18545 and synthetic temporary records; the node was stopped. Existing deployment files were not replaced. These diagnostics are excluded from the commit; review before promoting the smoke script into maintained tests.
- [ ] Review the local environment change: installed the corrected requirements in .venv (including eth-account 0.13.6, cryptography 44.0.0, and supporting dependencies). The virtual environment is excluded from Git.
- [ ] Review generated ignored artifacts/cache from compilation; these are excluded from Git.
- [ ] Rerun checks affected by later review edits, then push the chosen branch explicitly. Pre-existing untracked review documents/results are excluded from this merge commit.
- [x] All 24 pre-existing untracked files were verified byte-for-byte unchanged; no unresolved conflicts or conflict markers remain.
- [ ] Review inherited whitespace warnings from git diff --cached --check: trailing spaces/blank EOF lines in incoming offchain modules. The education gas-summary.csv was subsequently removed; remaining whitespace was retained to avoid unrelated edits.

<!-- TODO: review all annotation and push-guard additions below. -->
## Review comments and local push guard

- [ ] Review the added # TODO: review markers in all four offchain modules and .local/p3-merge-smoke.py. Markers cover whole imported/added files, individual definitions, and manual fixes. The annotated education scripts were later removed.
- [ ] Review removal of the annotated contracts/EduConsent.sol; this education contract is no longer compiled or part of the checkout.
- [ ] Review the added comments in .gitignore and requirements.txt and the HTML review comments and push-review instructions in README.md and docs/p3-merge-todo.md.
- [ ] Review .githooks/pre-push, the new local Git hook which runs the Node review checker.
- [ ] Review scripts/check-p3-review.mjs, the new checker: rejects unchecked committed checklist items, missing final sign-off, omitted file names, and uncommitted changes to the reviewed files.
- [ ] Review the local .git/config change: core.hooksPath is now .githooks. No existing custom hook path or pre-push hook was replaced. This local configuration is not committed or installed automatically in another clone.
- [ ] Review comment coverage for formats without comments: package.json and incoming JSON/CSV/results files remain syntactically unchanged and are covered by this checklist instead.
- [ ] Final review sign-off: I have personally checked every added or edited file, reviewed or explicitly accepted all remaining issues above, and approve pushing this change.
- [x] Review guard behavior checks passed: incomplete checklist, missing checklist/sign-off/file entry, and uncommitted changes block; a fully checked in-memory checklist passes. No human-review items were automatically checked.
- [x] Review annotations were verified to add comments only across all nine existing code files; tracked Python syntax trees are unchanged.
- [ ] Review .gitattributes: the added hook is forced to LF line endings so Windows checkouts preserve its executable shell header.

<!-- TODO: review the healthcare-only cleanup below. -->
## Education material removed

- [ ] Review removal of the older EduConsent.zip archive and docs/UML.md, docs/uml.dot, docs/uml.png, and docs/uml.svg education diagrams. Healthcare architecture documentation remains.
- [ ] Review the targeted README.md cleanup and scripts/check-p3-review.mjs changes. The guard continues to cover deleted paths and now also covers the removed archive/diagrams, so their removal or restoration requires review.
- [ ] Confirm that only the healthcare contracts/interfaces, P3 offchain service, healthcare deployment/hash scripts, and healthcare tests remain as current application code. Historical merge reports retain their original references as an audit record.
- [x] After education cleanup, a clean healthcare build passed all 88 Solidity tests and 5 Python hash tests; no EduConsent build artifacts remain.
- [x] The updated review guard passed all 6 behavior checks, including tracking removed education paths; human-review items remain unchecked.

<!-- TODO: review this completion audit before accepting its priorities or findings. -->
## Current completion audit (healthcare)

Assessed source revision: f3e6562. Scope: current code and the local healthcare acceptance matrix; the original grading PDFs referenced by that matrix were not independently reviewed. Passing component tests do not establish complete P3 acceptance.

- [ ] P0 - Make wallet proof specific and fresh. offchain/offchain_service.py accepts the same caller-supplied signed challenge repeatedly. Add a server-issued nonce, expiry, and binding to chain, contract, record/request and operation. Repeated acceptance was reproduced with a real signature.
- [ ] P0 - Validate receipt provenance. The installed Web3 decoder accepts a matching AccessDecision topic emitted by another contract; the service never checks event.address and selects events[0]. Require the configured manager address and select the matching record/request/requester/grant; agree confirmation/finality rules. This audit verified foreign-emitter decoding offline; current-grant checks still run separately.
- [ ] P0 - Decrypt the exact bytes whose hash was verified. offchain/offchain_service.py hashes a file, then encrypt_record.py opens it again. With mocked chain responses and real encryption/SQLite, changing the file between reads produced different delivered plaintext after the original commitment passed. Add regression coverage for this race.
- [ ] P1 - Define decryption failure and consumption outcomes. A missing key currently creates a new secret.key, fails decryption, and still consumes the receipt. This was reproduced with synthetic temporary data. Decryption must require an existing key; document whether failures require a fresh authorization and persist explicit outcomes.
- [ ] P1 - Support actual records and deployments. Replace the fixed fake-record.enc/secret.key pair with a private (chainId, registryAddress, recordId) file/key mapping. Scope replay keys to chain/manager deployment, handle concurrent claims cleanly, and replace or remove the unsupported check_consent() API.
- [ ] P1 - Provide a supported healthcare workflow command. Wire deployment manifest, patient/requester setup, encryption, ciphertext commitment registration, grant/reward, signature, request receipt, delivery and revoke/expiry checks together. Only an ignored local smoke script currently exercises P3. Newer origin/integration/p1-p2-runtime has candidate seed/demo scripts, but its separate plaintext service must be reconciled with P3 rather than imported as a second delivery design.
- [ ] P1 - Make P3 acceptance tests maintained and reproducible. Commit appropriate tests for the proof/emitter/file-race findings, expiry, role suspension, wrong/stale receipts, multiple records, replay after restart, concurrent redemption, and missing/corrupt keys. Map existing Solidity tests and new delivery tests to current acceptance cases without claiming old branch findings remain unresolved.
- [ ] P1 - Complete healthcare evaluation. Gather deployment/function gas and separately measured confirmation/authentication/permission/delivery timings using team-approved multi-user workloads, repetitions and reset rules. Preserve raw receipts, samples, environment/commit metadata, and traceable summaries. The removed education benchmarks are not healthcare evidence; 5/20/50 users are roadmap proposals, not a verified grading requirement.
- [ ] P1 - Finalize specification and documentation. Confirm per-record/requester rewards versus the older per-category proposal, ciphertext commitments, login lifetime, finality and failed-delivery policy. Update README.md and docs/healthcare-architecture.md (still says P3 pending and references removed UML); revise the untracked acceptance/verification documents for this branch and decide which belong in the submission.
- [ ] P1 - Prepare submission and independent reproduction. Assemble the course report/presentation if required by the original rubric, healthcare architecture, test/measurement evidence, limitations and contribution/AI-use record. Have a teammate rerun a clean setup and demo. Complete every review item and final sign-off before pushing.

Audit checks used real signatures/encryption/SQLite with synthetic temporary files and mocked blockchain responses, plus an offline Web3 event-decoding check. They are targeted reproductions, not a public-network security audit. Project application code was not changed by this assessment.

<!-- TODO: review these requirements verified against the supplied course PDFs. -->
## Verified assignment requirements and own-test plan

Sources read: C:/Users/kaloy/Downloads/Blockchains/Project Assignment.pdf (all six pages); Blockchains Coursebook 2026-2027.pdf (project/report/AI rules and Annex A); Blockchain_Lab_3-3 (1).pdf (test-running conventions). This supersedes uncertainty about the original rubric in the earlier completion audit.

- [ ] Write and review your own Solidity unit tests, with filenames matching the contracts verified; the assignment specifies no numeric minimum. Keep the ten scenario plan, but include 0/1/365/366-day grant boundaries and allowed/denied audit-event assertions. The student's separate test/p4/ files can be selected explicitly with Hardhat without running the older suites.
- [ ] Complete integration workflows including registration, consent grant, actual data access, and revocation; use only synthetic data. Python can exercise the offchain component, while required smart-contract unit tests remain Solidity.
- [ ] Produce tables of successfully performed tests, explain why every tested functionality matters, and collect deployment costs, average gas per key function, and multi-user time/cost scaling evidence. No fixed user count or repetition count is specified.
- [ ] Complete the required research/problem statement, roles/permissions and functional requirements; an onchain/offchain/hashed attribute table; consent/audit model and workflows; and healthcare architecture diagram.
- [ ] Complete a local Hardhat deployment and reproducible compile/deploy/test instructions. Public-testnet deployment and the frontend are optional; a frontend is listed for bonus points.
- [ ] Complete the required report and short presentation. Report sections: Introduction, Architecture, Implementation, Experimental Results, Discussion and Conclusion (discussion may be combined with conclusion). Maximum 10 pages excluding references/code; A4, 10-point Times New Roman, double spacing, 1-inch margins. Include consistent references, cover-page contributor names/IDs, individual contributions and AI-use acknowledgement. Exact presentation format is referenced to Week 6's Lab, which is not among the provided lab PDFs.
- [ ] Review these new factual checklist additions and the local PDF-reading dependency under ignored .local/pdf-reading-tools. It is an inspection tool, not a project dependency or test implementation.

The provided PDFs list project submission at 23:59 CEST on 4 October and presentation submission before 12:00 CEST on 5 October. These are document-stated deadlines; check Canvas for any subsequent change.

First own test: test/p4/HealthRegistry.t.sol, a HealthRegistry test contract with a public function named test_PatientRegistrationAndRecordCreation. Independently deploy a fresh registry; register synthetic identity data; inspect initial user state; verify the patient; register a synthetic commitment; inspect record owner/hash/type and record counter. Start with this positive unit scenario, then use separate actors for authorization tests. No student test implementation was generated by this requirements review.
