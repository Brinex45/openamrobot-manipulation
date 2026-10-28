# STATE

## Repository
- Type and lifecycle: interface / draft work; readiness unassessed (e0faeee).
- Owner role: common manipulation/Device Package work is owned by Om and Adnan (AGENTS.md at 095e6c7).
- Verification: `python3 -m unittest discover -s i2/tests -p 'test_*.py' -v`; 103/103 passed on the local working tree (2026-10-28). Hosted CI and commit-specific verification remain separate checks.
- Package validation: both example packages report VALID with pending values; strict freeze remains blocked by pending values; package validation ran before commit c3abb545 (2026-10-21).

## Current work
| Work package | Branch or PR | Status | Next step |
|---|---|---|---|
| A5/I2 Device Package | PR #20, pr-9 | Open, non-draft PR | Complete canonical I1 interface follow-up; hosted quality/test and DCO/CLA are green on reviewed head 878b3ca. Obtain owner review. Runtime/device acceptance remains unverified. |

## Decisions this repository implements
- LIFT, ARM-MOUNT, CONFIG-IDS: see the [authoritative shared decision register](https://github.com/openAMRobot/.github/blob/main/decisions.yaml). Values and physical acceptance are not inferred here.

## Known gaps
- Contract owner Adnan accepted A3/I1 document Revision v2 / I1 API v1.0 and the decisions for `contact_detected_valid`, `object_detected_valid`, and CompliantHold rejection conditions in the PR #20 discussion. The corresponding canonical interface changes in the owning I1 contract repository remain outstanding.
- The latest uploaded snapshot changes both OpenArm `GripperActionController` entries to use the required singular `joint` parameter and adds a regression test against the selected controller type and actual parameters.
- Added I2 observation-validity conformance vectors and a regression that checks the accepted unavailable-versus-measured-negative cases. These vectors specify expected semantics; they do not exercise a runtime I1 implementation. These runtime observation fields must not be added to the device-package declaration schema.
- Hosted `repository-quality / quality/test` passed on reviewed head 878b3ca (run #40658921655, job #122716742748; 103 tests). DCO and CLA are green on that reviewed head. The hosted schema suite does not run the separate 40-test ROS/fake-hardware integration suite.

## Not verified
- ROS/common-server/device end-to-end acceptance, upstream MoveIt configuration correctness, real hardware operation, physical-device acceptance, and safety qualification are not established by schema tests or fake hardware (PR #20 review, 2026-10-21).
- Lift/arm transforms, physical workspace, payload/contact capabilities, and configuration acceptance are not validated by this PR (AGENTS.md at 095e6c7).
