# P1 + P2 merge report

> Historical report for merge commit `9497375`. Compilation and integration issues described below were repaired afterwards; see [current fixes and verification](p1-p2-fixes.md). Original logs and findings are preserved.

- Date: 30 September 2026
- New local branch: `integration/p1-p2`
- Starting branch: `origin/thomas` at `b97799dfa2835cd8dd5dcdd6131294260ea6a80f`
- Merged branch: `origin/p2` at `12c4759868df2150492627f3fb1a28d6d10cd084`
- Common ancestor: `8c4767c68b07d06a17f7995a9e897e7b887a2b2a`

## Result and limits

The two histories are combined in a merge commit on `integration/p1-p2`. All four Git conflicts are resolved. This is a **source merge, not a working integrated application**: the combined Solidity build still fails on P2's existing interface syntax error, and the registry/reward calls do not match P1's APIs.

All five supplied contract/interface files retain their source-branch contents, apart from possible checkout line endings. Project configuration and documentation were reconciled; no new consent policy or contract fix was silently introduced. Provenance and checks are recorded in [validation.json](../results/p1-p2-merge/validation.json).

The existing `plan-A-P4` branch and its untracked P4 review documents/results were preserved. Only this merge's configuration, documentation, evidence, and incoming branch files belong to the new merge commit. The branch has not been pushed to origin.

This report lists every textual conflict Git reported and the integration issues identified by source comparison and the checks below. It is not a claim of exhaustive runtime/security coverage: compilation blocks Solidity execution, and no file service is included.

## 1. The four Git conflicts and their resolutions

The common ancestor contains no tracked files. Both histories independently added their project scaffolding, so Git classified the following as **add/add** conflicts, rather than one side merely editing the other's setup. The original [conflict index](../results/p1-p2-merge/conflict-index.txt) and conflicted file snapshots are retained as evidence.

| ID | File | Why it conflicted | Resolution | Status |
| --- | --- | --- | --- | --- |
| G01 | `.gitignore` | P1 ignored ZIP files; P2 added `dist/` and `.venv/`. The common ignores overlapped. | Keep the union: dependencies, artifacts, cache, dist, virtual environment, Python caches, local data, ZIP outputs. Already tracked `EduConsent.zip` remains tracked; ignore rules do not remove it. | Resolved |
| G02 | `README.md` | P1 describes a healthcare component draft; P2 inherited the education application's README with missing script/test references and historical claims. | Write a healthcare merge README that identifies all three components, actual commands, known build blockers, and historical material. Preserve the detailed P1 handoff. | Resolved |
| G03 | `package.json` | Different package names/versions, npm scripts, and Hardhat dependency placement. P2's demo/integration/benchmark scripts point to files absent from both merged source sets. | Use `healthcare-p1-p2-draft` version `0.1.0`; retain compile/test, P1 hash/sample commands, and P2's localhost node command. Keep Hardhat `3.18.0` as a dev dependency. Remove commands referencing absent scripts. Use `python` with a quoted test glob for Windows-compatible scripts; README explains Python 3 expectations. | Resolved |
| G04 | `package-lock.json` | Package identity/root dependency classification differed, including transitive `dev` metadata. | Start from P1's complete lockfile, align its root name with the merged manifest, and retain pinned dependency versions. Both parent locks had the same package-path/version mapping; no dependency upgrade was needed. `npm ci` validates the result. | Resolved |

Original snapshots: [.gitignore](../results/p1-p2-merge/_gitignore-conflict.txt), [README](../results/p1-p2-merge/README_md-conflict.txt), [package manifest](../results/p1-p2-merge/package_json-conflict.txt), and [lockfile](../results/p1-p2-merge/package-lock_json-conflict.txt). Conflict markers inside these `.txt` evidence files are historical evidence, not unresolved source conflicts.

`hardhat.config.ts` is identical across parents: Solidity 0.8.28, optimizer enabled, 200 runs. It merged without a conflict. P2's `^0.8.20` pragma permits the configured 0.8.28 compiler; the pragma difference is **not** the compiler failure.

## 2. Build and interface blockers

### I01 - P2's external string parameter has no data location

- **Owner:** P2. **Status:** Open; reproduced in the merged tree. **Priority:** Build blocker.
- **Location:** [ConsentManager.sol](../contracts/ConsentManager.sol), line 11, local `IConsentReward.issueReward` declaration.
- **Problem:** `string category` in an external interface function must specify a data location. The compiler rejects the file before any Solidity test executes.
- **Observed:** Both `npm run compile` and `npm test` exit 1 with the same TypeError. The separate missing-SPDX warning is nonfatal and did not cause this failure.
- **Next step:** Correct or replace this local interface declaration as part of agreeing the shared P1/P2 API. Adding a data location alone will not fix I02-I04.
- **Evidence:** [Compile log](../results/p1-p2-merge/compile.txt), [Solidity test-command log](../results/p1-p2-merge/solidity-tests.txt).

### I02 - Record identifiers have incompatible types

- **Owners:** P1 + P2; P3/P5 must consume the agreed representation. **Status:** Open; static comparison.
- **P1:** Registry-generated sequential `uint256` IDs starting at 1, used by both registry and reward.
- **P2:** `bytes32` IDs in grant storage, methods, and access/grant events.
- **Impact:** ABI signatures, encoders, service mappings, and test fixtures disagree. The fact that both occupy 32 bytes does not make their function signatures interchangeable.
- **Next step:** Choose one representation and update shared interfaces, manager, event consumers, and deployment fixtures consistently. Do not replace registered IDs with unrelated hashes.

### I03 - P2 calls a registry function P1 does not implement

- **Owners:** P1 + P2. **Status:** Open; static comparison.
- **P2:** Calls `getRecordOwner(bytes32)` in `grantAccess` and `revokeAccess`.
- **P1:** Exposes `getRecord(uint256)` returning `{patient, recordHash, recordType}`; there is no `getRecordOwner` method.
- **Impact:** Pointing P2 at the actual P1 registry does not satisfy P2's declared interface. Casting record IDs alone does not supply the missing method.
- **Next step:** Agree a shared lookup, import it from `contracts/interfaces`, and obtain the authoritative owner/type from the actual registry. Test a real grant using P1's deployed registry.

### I04 - P2 calls a reward function P1 does not implement

- **Owners:** P1 + P2. **Status:** Open; static comparison.
- **P2:** Calls `issueReward(patient, requester, category)` with no return value.
- **P1:** Exposes `rewardConsent(recordId, requester) returns (bool)`, derives the patient from registry ownership, and restricts calls to a configured consent manager.
- **Impact:** The real reward contract cannot service P2's current call. For P1's API, false means an already rewarded pair, not a failed valid renewal.
- **Next step:** Reconcile the call and inputs; do not require a duplicate's returned value to be true. Preserve all-or-nothing grant/reward behavior when a real reward call reverts.

### I05 - Reward eligibility is not agreed across the components and plan

- **Owners:** P1 + P2 + team. **Status:** Open policy decision, not an established assignment violation.
- **P1 implementation:** 10 points per first `(recordId, requester)`; different records can each earn points even for the same patient/requester/category.
- **P2 interface:** Sends patient/requester/category to a hypothetical reward API; it does not itself implement an eligibility ledger.
- **Earlier roadmap:** Proposed one reward per patient/requester/category.
- **Impact:** Two same-category records could yield 20 points under P1, but only 10 under the roadmap proposal. New record IDs can also be used to earn additional rewards; P1 documents that limitation.
- **Next step:** Agree and document the eligibility key and repeat-grant policy. Test same record, different record/same category, different requester, renewal, and revoke/regrant. The merge preserves P1's existing point policy rather than choosing a new one.

### I06 - Production deployment wiring and integrated tests are missing

- **Owners:** P5 + P1/P2; P4 verifies. **Status:** Open integration work.
- P1's reward manager can be configured once and must be a deployed contract. Deploy registry, reward, then the real manager; configure the manager afterwards as reward admin.
- P1's `RewardCallerStub` accepts arbitrary callers and deliberately omits consent checks. It is only a component-test helper, not a deployable access-control solution.
- There is no healthcare deployment script/address manifest or P2 Solidity suite in the supplied branches. The 45 P1 Solidity component tests exist but cannot run in the combined project until I01 is fixed; they also do not establish actual manager integration.
- **Next step:** After interfaces agree, test real registry -> manager -> reward interactions, authorized/unauthorized grants, duplicate reward=false, and full rollback when reward issuance fails.

## 3. Behavior issues discovered while reviewing the combined code

These findings are supported by unchanged source inspection. They were **not reproduced through transactions** because the merged source does not compile. Keep that distinction in team discussions and the results section.

### B01 - A patient can target another patient's grant during revocation

- **Owner:** P2. **Priority:** High ownership issue. **Status:** Open static finding.
- **Location:** `revokeAccess`, source lines 112-120.
- **Scenario:** Alice owns record A and grants Carol access under grant G. Bob owns record B. Bob calls `revokeAccess(B, G)`.
- **Problem:** P2 checks Bob owns B, then writes `consentGrants[G].revokedStatus = true` without checking that G belongs to B or Bob.
- **Expected:** Reject the mismatch and preserve Alice's grant.
- **Related issue:** The function also accepts a nonexistent grant ID after a valid ownership check and writes a revoked flag into an otherwise empty entry. A later grant allocation overwrites that slot; this should not be described as proven permanent future-grant revocation.
- **Next step:** Validate grant existence and its patient/record binding before mutation. Add cross-patient, same-patient/wrong-record, unknown-grant, and legitimate-revocation regression tests.

### B02 - P2 does not recheck current verified roles on access

- **Owners:** P1 + P2. **Status:** Open interface/behavior mismatch with P1's handoff.
- P1's handoff requires a currently verified patient and verified Doctor/Researcher, including at access time. Identity updates clear verification and the admin can suspend roles.
- P2's `requestAccess` and `checkPermission` inspect only stored consent fields; they do not query current verification. P2 also does not explicitly check roles on grant; P1 reward checks could cover that part only after reward integration is fixed.
- **Impact:** The source path would continue allowing an otherwise active grant after suspension or identity-update invalidation if no other component rechecks it.
- **Next step:** Agree the policy and consistently implement it in grant/request/current-permission checks. Test suspended patients/requesters, identity updates, reverification, and expired/revoked grants.

### B03 - Category is supplied freely without matching the record's type

- **Owners:** P1 + P2. **Status:** Open scope/policy issue.
- P1 stores an immutable `recordType`. P2 accepts any category string and neither checks it against that field nor consults it during access decisions.
- **Impact:** A grant can claim a category different from its record. If a future reward adapter uses that category as an eligibility key, misleading labels could also alter reward behavior.
- **Next step:** Use an agreed canonical category or validate against the registry's actual record type. Test empty/mismatched categories and different records in the same category. Exact record binding already exists in P2's access checks; it does not validate category metadata.

### B04 - Equivalent active grants are not rejected

- **Owner:** P2 + team. **Status:** Open policy decision.
- Each `grantAccess` call allocates a new ID. There is no active-duplicate lookup. The roadmap proposes rejecting an equivalent active grant, but that proposal has not been confirmed by these branches.
- **Impact:** Revoking one grant ID can leave another equivalent grant active. This matters when explaining whether revocation concerns one grant or all access for a record/requester pair.
- **Next step:** Agree duplicate/revocation semantics and test multiple live grants. Do not silently change a policy during a source merge.

### B05 - Access request IDs are caller-supplied and reusable

- **Owners:** P2 + P3. **Status:** Open identifier/protocol decision.
- `requestAccess` accepts `requestId` and emits it without allocating it or rejecting duplicates. The same or different wallets can reuse an ID across transactions.
- **Impact:** P3 cannot safely treat the raw request ID alone as a unique authorization. This is not proof of a replay exploit in a file service that does not yet exist here.
- **Next step:** Agree uniqueness scope and generation, or bind redemption to chain, contract, transaction, and log identity plus authenticated requester and current grant. Test repeated IDs and concurrent/restarted redemption at the service boundary.

### B06 - Denied audit events can misattribute patient and record

- **Owner:** P2; P3 consumes the schema. **Status:** Open static finding/schema issue.
- Missing grant: the event uses zero patient from the empty grant even if the requested record has a known owner.
- Wrong-record request: a grant belonging to Alice can be paired with Bob's requested record ID; the denied event then contains Alice as patient and Bob's record ID.
- **Impact:** Denial itself occurs, but the audit fields can be misleading or incomplete. Registry-change events from P1 do not substitute for these access-decision events.
- **Next step:** Define whether patient means requested-record owner or grant owner and represent both explicitly if necessary. Verify accurate fields for no-consent, wrong-record, and unknown-record cases. Confirm reason precedence: current P2 order is missing grant, revoked, expired, wrong requester, wrong record. Its `UNREGISTERED_REQUESTER` enum value is currently never emitted.

### B07 - Dependency addresses are accepted without deployment validation

- **Owner:** P2/P5. **Status:** Open deployment hardening decision.
- P2's constructor stores both addresses without verifying deployed code. This permits deployment with zero or wallet addresses; later operations can fail when making the external calls.
- P1 validates code presence for its registry and manager inputs, but code presence alone does not establish interface compatibility.
- **Next step:** Validate deployment configuration, agreed interfaces, and post-deployment smoke checks. Decide whether P2 should reject invalid dependencies at construction. Record any inability to change a bad configuration without redeployment.

## 4. Documentation, portability, and evidence issues

| ID | Issue | Explanation and disposition |
| --- | --- | --- |
| D01 | Education files arrive through P2 ancestry | `EduConsent.zip`, `docs/UML.md`, `docs/uml.*`, and `requirements.txt` are inherited from the older education project. Retained to preserve incoming files; README and UML text label them historical. The diagram is not a healthcare architecture, and the ZIP was not executed or used as implementation evidence. Team should decide whether to archive/remove them later. |
| D02 | Absent-script npm commands | P2 advertised `demo`, `test:integration`, and `benchmark`, but their referenced Python files are not present. Those commands were removed from merged package metadata; this does not implement replacements. P3/P5 still need actual healthcare workflows. |
| D03 | Python command portability | P1 used `python3` and single-quoted discovery patterns; P2 used Unix `.venv/bin/python` paths. Merged helper scripts use `python` and a double-quoted pattern, verified on this Windows machine. Systems with only `python3` should invoke equivalent commands explicitly. |
| D04 | Historical passing outputs can be mistaken for merged results | P1's committed `results/*.txt` remain historical. Fresh evidence under `results/p1-p2-merge/` reports build failure and five passing Python tests. No passing Solidity or end-to-end result is claimed for this merge. |
| D05 | Extra Python dependency file | The inherited `requirements.txt` pins `web3`, while current P1 hashing helpers/tests use only the standard library. It was retained but not installed as a requirement for those helpers. P3/P5 must publish their actual dependency set. |
| D06 | Scope of privacy/integrity remains incomplete | P1 proposes encrypted-file hashes but its sample hashes a plaintext fixture; P2 manages decisions, not file release. No encryption/authentication/receipt redemption/download implementation is supplied here. A successful hash sample does not demonstrate secure file delivery. |
| D07 | Source license warning | P2 has no SPDX identifier; the compiler emits a nonfatal warning. Ask the author/team to choose the correct identifier rather than inventing a license during merge resolution. |

## 5. Validation performed on the resolved tree

| Command/check | Result | Interpretation |
| --- | --- | --- |
| `npm ci --no-audit --no-fund` | Exit 0; 52 packages installed | Manifest and selected lockfile install. npm noted an unapproved esbuild install script; no approval settings changed. |
| `npm run compile` | Exit 1 | P2 interface data-location error, I01. |
| `npm test` | Exit 1 | Same compile error; **zero Solidity tests executed**, not a passing suite. |
| `npm run test:hashes` | Exit 0; 5 tests passed | P1's hashing/fixture tests work under the merged package command. |
| `npm run sample` | Exit 0 | Synthetic identity and plaintext fixture hashing works; no encryption or delivery demonstrated. |
| Source comparison | All five contract/interface files match source parents | No hidden contract rewrite or resolution-by-dropping-a-component. |
| Git conflict check | No unmerged index entries after resolution | Textual Git conflicts are resolved; semantic integration issues remain as listed above. |

Logs: [compile](../results/p1-p2-merge/compile.txt), [Solidity command](../results/p1-p2-merge/solidity-tests.txt), [Python tests](../results/p1-p2-merge/hash-tests.txt), [sample](../results/p1-p2-merge/sample.txt). [Metadata](../results/p1-p2-merge/validation.json) records runtime versions, hashes, commands, and timestamps.

## 6. Suggested owner handoff order

1. **P1/P2:** agree shared ID types, registry/reward methods, duplicate return semantics, and reward policy. P2 then repairs compilation against those interfaces.
2. **P2:** fix grant-bound revocation; confirm category, current-verification, duplicate-grant, and audit/request-ID semantics.
3. **P5:** deploy actual registry/reward/manager, configure issuer authority, and replace education documentation/commands with the real healthcare workflow.
4. **P4:** run component tests and add real cross-contract regressions, expiry boundaries, persistent denial events, and reward rollback; preserve actual evidence.
5. **P3/P5:** integrate authenticated file delivery and receipt/current-grant checks before claiming the complete workflow works.

No messages were sent to teammates. No remote branch was changed. This merge and report are AI-assisted; record the actual configuration/documentation/review contribution and distinguish it from the teammates' preserved source code.
