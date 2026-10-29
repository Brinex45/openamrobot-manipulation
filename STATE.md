# STATE

## Repository
- Type and lifecycle: interface / draft work; readiness unassessed (e0faeee).
- Owner role: common manipulation/Device Package work is owned by Om and Adnan (AGENTS.md at 095e6c7).
- Verification: `python3 -m unittest discover -s i2/tests -p 'test_*.py' -v`; 103/103 passed on the local working tree (2026-10-28). Hosted CI and commit-specific verification remain separate checks.
- Package validation: both example packages report VALID with pending values; strict freeze remains blocked by pending values; package validation ran before commit c3abb545 (2026-10-21).

## Current work
| Work package | Branch or PR | Status | Next step |
|---|---|---|---|
| A5/I2 Device Package | PR #20, pr-9 | Open, non-draft PR | Complete canonical I1 interface follow-up, obtain owner review, and resolve the gripper integration acceptance question. The latest recorded hosted CI pass was on PR head 279f8af; the later merge commit and documentation edits require fresh hosted verification. Runtime/device acceptance remains unverified. |

## Decisions this repository implements
- LIFT, ARM-MOUNT, CONFIG-IDS: see the [authoritative shared decision register](https://github.com/openAMRobot/.github/blob/main/decisions.yaml). Values and physical acceptance are not inferred here.

## Known gaps
- Contract owner Adnan accepted A3/I1 document Revision v2 / I1 API v1.0 and the decisions for `contact_detected_valid`, `object_detected_valid`, and CompliantHold rejection conditions in the PR #20 discussion. The corresponding canonical interface changes in the owning I1 contract repository remain outstanding.
- The latest uploaded snapshot changes both OpenArm `GripperActionController` entries to use the required singular `joint` parameter and adds a regression test against the selected controller type and actual parameters.
- Added I2 observation-validity conformance vectors and a regression that checks the accepted unavailable-versus-measured-negative cases. These vectors specify expected semantics; they do not exercise a runtime I1 implementation. These runtime observation fields must not be added to the device-package declaration schema.
- Hosted workflow run #41 passed both `repository-quality / quality/test` and `repository-quality` on PR head `279f8af`. This predates merge commit `b981425` and the documentation edits; fresh hosted verification is required after pushing. The schema/conformance suite and ROS/fake-hardware integration suite are separate checks.
- A clean local fake-hardware integration rerun passed all four suites. The four current xUnit XML files contain 37 test cases (15 fake-profile, 4 launch-guard, 11 fake-bringup, 7 MoveIt-planning). `colcon test-result --verbose` reported 41, which conflicts with the XML total and remains unexplained; do not report 41 as the verified case count.

## Not verified
- ROS/common-server/device end-to-end acceptance, hardware qualification of the pinned upstream acceleration limits, real hardware operation, physical-device acceptance, and safety qualification are not established by schema tests or fake hardware.
- Lift/arm transforms, physical workspace, payload/contact capabilities, and configuration acceptance are not validated by this PR (AGENTS.md at 095e6c7).
