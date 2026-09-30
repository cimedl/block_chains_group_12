# P1 + P2 integration fixes and verification

Date: 30 September 2026. Branch: `integration/p1-p2`.
Baseline: merge commit `94973757ef4448e82b2fac8d460701b1ed671d31`.

The three real contracts now compile and work together. The original merge failures
are preserved in `results/p1-p2-merge/`; this report describes the repaired state.
The changes retain the authors' structs, mappings, explicit require messages, simple
events, and shared-interface style. No new token library or contract framework was added.

## Repairs against the original merge report

| Original issue | Repair / disposition | Verification |
| --- | --- | --- |
| I01: compiler error | Removed P2's incompatible local interfaces and imported the shared P1 declarations; matched compiler pragma and license style. | Solidity compile and full suite pass. |
| I02/I03: ID and registry mismatch | Manager uses uint256 IDs and getRecord. Registry adds non-reverting recordExists for denied requests. | Real grant fields, ownership isolation, existence, and unknown-record tests. |
| I04: reward API mismatch | Manager calls rewardConsent(recordId, requester). Duplicate=false is allowed; errors revert the whole grant. | Actual P1 reward payment, regrant without repeat payout, rollback and retry tests. |
| I05: competing reward policies | Retained P1's implemented 10 points per first record/requester pair; documented the difference from the earlier per-category proposal. | Same-category/new-record test explicitly earns 20 total points. Team report must use this actual policy or authorize a later change. |
| I06: deployment/wiring | Added npm deploy command and standard-library Node script. Deploys registry/reward/manager, configures issuer, verifies getters, writes address/ABI/receipt manifest. | Temporary-node smoke check and saved receipts; actual manager used. |
| B01: revocation ownership | Require existing grant, exact record match, and both stored/current record owner before mutation. Missing grants cannot create revoked placeholders. | Cross-patient attack, wrong owned record, unauthorized caller, unknown grant, correct revocation tests. |
| B02: current verified roles | Check currently verified Patient and Doctor/Researcher on both grant and permission evaluation. Suspended owners may still revoke. | Suspension, identity-update, researcher, reverification, and suspended-owner revocation tests. |
| B03: category scope | Category must exactly match immutable registry recordType at grant. | Empty/mismatched category rejected; stored category verified. |
| B04: active duplicates | Track latest grant by record/requester. Reject duplicates while unrevoked and before expiry; replacement receives a new ID. | Active duplicate, revoke/regrant and expiry/regrant tests; old grants remain invalid. |
| B05: request IDs | Manager allocates sequential request IDs; caller no longer supplies them. IDs are unique within a deployment, not across chain resets/deployments. | Actual recorded denial/allow logs from different wallets have distinct IDs; view consumes none. |
| B06: audit attribution | Patient comes from requested record. Nonmatching grant produces grantId=0. Same permission evaluator drives view and transaction; ordinary denials return normally. | Exact event fields/emitter, known owner with missing grant, wrong-record actual owner, unknown record and recorded denied logs. |
| B07: dependency addresses | Reject zero or wallet addresses at construction; deployment script verifies actual cross-contract addresses. | Invalid dependency cases and four deployed getter checks. |
| D01/D05: education artifacts | Keep historical artifacts labelled; add a separate current healthcare architecture. Current deploy/helper commands need no third-party JS/Python libraries beyond Hardhat. | README and healthcare diagram align with implementation. Inherited web3 requirements are not installed for these helpers. |
| D02/D03: commands and portability | Existing usable scripts retained; new deploy command added. Python hashing commands use python with quoted discovery pattern. | Five Python tests pass; deployment command executes. |
| D04: old results | Keep original failure/pass logs historical and store new evidence separately. | Current evidence includes runtime/configuration and source hashes. |
| D06: file delivery | P3 authentication/encryption/receipt redemption/private delivery remains outside these P1/P2 components. | No file-delivery or public-network performance claim. |
| D07: SPDX warning | ConsentManager uses the same MIT identifier as P1's supplied contracts. | Compilation emits no earlier missing-license warning. |

## Implemented branch choices

- Reward policy stays per record/requester, with integer points and no access-time token movement.
- Equivalent active grants are rejected; regrant replaces neither the old grant's fields nor its ID.
- Category is the exact registry type string, not a new fixed category enumeration.
- Denial precedence is unknown record, invalid requester role/verification, unverified patient,
  missing/mismatched grant, revoked, expired, granted.
- Original six reason values retain their numeric positions; PATIENT_NOT_VERIFIED is appended.
- Access IDs are contract-generated; requestAccess now takes recordId and grantId only.
- Owners can revoke while suspended. Reverification restores only otherwise active consent;
  it never overrides revocation or expiry.

These are concrete choices for this branch. P1/P2/P3/P5 must use the [updated interfaces](interfaces.md)
and actual reward policy in their integrations and report. The earlier matrix/proposals
are not automatically converted into passing project acceptance cases.

## Actual validation

- **88 Solidity tests pass:** 26 registry, 20 reward, 42 real-manager integration tests.
- **5 Python hashing/fixture tests pass.**
- Local deployment on temporary Hardhat chain 31337 succeeded for all three contracts;
  manager authorization and all four dependency getters were verified.
- The temporary node was stopped after the check. Its recorded addresses are evidence
  from that run, not an active service. Start a node and rerun npm run deploy for new work.

Evidence is under `results/p1-p2-fixes/`: [validation metadata](../results/p1-p2-fixes/validation.json),
[Solidity test output](../results/p1-p2-fixes/solidity-tests.txt),
[Python test output](../results/p1-p2-fixes/hash-tests.txt),
[deployment output](../results/p1-p2-fixes/deployment-smoke.txt), and
[deployment receipts](../results/p1-p2-fixes/deployment-receipts.json).

The new Solidity suite uses the actual registry, reward and manager. It verifies expiry
at T-1/T/T+1, revocation isolation, distinct grant/request IDs, reward atomicity, current
roles, event persistence and absence of access-time reward movement. One setup mistake
was corrected before the passing run: SHA-256 calculations were moved before vm.prank,
so precompile calls do not consume the intended simulated caller.

## Reproduction

```sh
npm ci
npm run compile
npm test
npm run test:hashes
```

For deployment, start npm run node in one terminal and npm run deploy in another.
The deployment script writes `.local/deployment.json`; no private keys are needed in
source because local Hardhat accounts are unlocked.

## Contribution, limitations and AI use

This is AI-assisted debugging, integration, regression testing and documentation.
Students must review, understand and explain the changes and record the actual use in
the course contribution/disclosure statement. Solidity integration is verified locally;
P3's authenticated file service, multi-user experiments, final report and presentation
still require their own implementation and evidence. A decision event does not prove
delivery or reading; revocation cannot delete existing copies; filesystem operator trust
and the final-check/transfer race remain part of the system's limits.
