# Healthcare P1 + P2 integration draft

This branch combines Thomas's registry/reward component with P2's ConsentManager.
The Git conflicts are resolved, but the supplied contracts are not yet compatible:
ConsentManager has a compile error and uses different registry/reward interfaces.
See [the complete merge report](docs/p1-p2-merge-report.md) for resolutions,
validation evidence, and outstanding issues. This is not a working end-to-end demo.

## Included components

- `contracts/HealthRegistry.sol`: user registration, admin verification, immutable medical-record metadata.
- `contracts/ConsentReward.sol`: ten non-transferable points per first record/requester pair.
- `contracts/ConsentManager.sol`: P2's grant, revoke, request, and permission-check draft, preserved as supplied.
- `contracts/interfaces/`: P1's shared interfaces; P2 currently declares incompatible local interfaces.
- `test/`: P1's Solidity component tests and Python hashing tests.
- `scripts/hash_data.py` and `data/`: SHA-256 helpers and synthetic fixture data.
- `docs/P1-HANDOFF.md`: P1's draft interface and deployment assumptions.

## Setup and checks

The source branches specify a supported even-numbered Node.js release at least
22.13 and Python 3. This merge was checked with the versions recorded in
`results/p1-p2-merge/validation.json`. The hashing helper uses only Python's standard
library. The npm Python scripts expect `python` to select Python 3; on systems that
only provide `python3`, run the equivalent Python commands directly.

```sh
npm ci
npm run test:hashes
npm run sample
npm run compile
npm test
```

At the reviewed merge state, Python checks run but both Hardhat commands fail at
`contracts/ConsentManager.sol:11` because an external string parameter lacks a
data location. Consequently none of the merged Solidity tests execute. Fixing
that syntax alone does not reconcile the P1/P2 interfaces.

`npm run node` starts a local Hardhat RPC node bound to localhost. No healthcare
deployment/demo or file-delivery script is included. Use the P1 handoff's deployment
order only after the interface issues in the merge report are resolved; configure
reward issuance with the real manager, not the unrestricted component-test stub.

## Historical material and evidence

`EduConsent.zip`, `docs/UML.md`, `docs/uml.*`, and `requirements.txt` arrived through
P2's education-project ancestry. They are retained as inherited material, not a
healthcare architecture, deployment package, or required Python dependency set.
The `demo`, `benchmark`, and old Python integration npm commands were removed from
the merged package because their referenced scripts do not exist in this tree.

P1's `results/hash-tests.txt`, `results/sample-output.txt`, and
`results/solidity-tests.txt` are historical component outputs from Thomas's branch.
They do not demonstrate that this merged source passes. Fresh merge evidence is
under `results/p1-p2-merge/`.

Only synthetic identities/records are included. Wallet control and admin verification
flags do not establish real identity, qualifications, or record truth. Permission
and reward code does not itself provide secure file delivery; P3 integration remains
outstanding. Review the draft rules and disclose actual contributions/AI assistance
in the course report.
