# STATE

## Repository
- Type and lifecycle: interface / draft work; readiness unassessed (e0faeee).
- Owner role: common manipulation/Device Package work is owned by Om and Adnan (AGENTS.md at 095e6c7).
- Verification: `python3 -m unittest discover -s i2/tests -p 'test_*.py'`; 91/91 passed with jsonschema 4.10.3 and with the fallback backend, on the working tree at e0faeee with the test-assertion changes subsequently applied; both backends passed before commit c3abb545 (2026-10-21).
- Package validation: both example packages report VALID with pending values; strict freeze remains blocked by pending values; package validation ran before commit c3abb545 (2026-10-21).

## Current work
| Work package | Branch or PR | Status | Next step |
|---|---|---|---|
| A5/I2 Device Package | PR #20, pr-9 | Draft | Refresh evidence and obtain owner review; exact I1 acceptance remains pending. |

## Decisions this repository implements
- LIFT, ARM-MOUNT, CONFIG-IDS: see the [authoritative shared decision register](https://github.com/openAMRobot/.github/blob/main/decisions.yaml). Values and physical acceptance are not inferred here.

## Known gaps
- Exact A3/I1 revision and acceptance record are pending contract-owner confirmation (PR #20 review, 2026-10-21).
- Unavailable gripper contact/object observation semantics and CompliantHold capability gating remain unresolved (PR #20 review, 2026-10-21).
- Hosted `repository-quality / quality/test` is skipped; hosted execution of local suites is unverified (run 39639693308, reviewed 2026-10-21).

## Not verified
- ROS/common-server/device end-to-end acceptance, MoveIt gripper execution, real hardware operation, physical-device acceptance, and safety qualification are not established by schema tests or fake hardware (PR #20 review, 2026-10-21).
- Lift/arm transforms, physical workspace, payload/contact capabilities, and configuration acceptance are not validated by this PR (AGENTS.md at 095e6c7).
