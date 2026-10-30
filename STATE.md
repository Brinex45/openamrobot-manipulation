# STATE

## Repository
- Type and lifecycle: interface / draft work; readiness unassessed (e0faeee).
- Owner role: common manipulation/Device Package work is owned by Om and Adnan (AGENTS.md at 095e6c7).
- Latest PR head verified by hosted run #48: `f6457d0629ec5c993af0671ff979f83b27d01679` on `pr-9`; PR #20 is open.
- Hosted verification: [GitHub Actions run #48](https://github.com/openAMRobot/openamrobot-manipulation/actions/runs/41100746763) completed successfully on this exact head; both `repository-quality` and `quality/test` passed. DCO and CLA checks are green.
- Schema/conformance: 103 tests passed in the local validation recorded 2026-10-28; hosted `quality/test` passed on the current PR head.
- Fake-hardware integration: fresh local run on 2026-10-29 passed four suites containing 37 individual pytest cases (15 fake-profile, 4 launch-guard, 11 fake-bringup, 7 MoveIt-planning). Colcon's 41-entry summary includes four suite-level entries; it is not 41 individual pytest cases.
- Package validation: both example packages report VALID with pending values; strict freeze remains blocked by pending values; package validation ran before commit c3abb545 (2026-10-21).

## Current work
| Work package | Branch or PR | Status | Next step |
|---|---|---|---|
| A5/I2 Device Package | PR #20, pr-9 | Open, non-draft PR; current hosted quality checks pass | Complete canonical I1 interface alignment/follow-up; obtain owner acceptance for issue #11 evidence; resolve issue #10 separately. Runtime/device acceptance remains unverified. |

## Decisions this repository implements
- LIFT, ARM-MOUNT, CONFIG-IDS: see the [authoritative shared decision register](https://github.com/openAMRobot/.github/blob/main/decisions.yaml). Values and physical acceptance are not inferred here.

## Accepted A3/I1 decisions
- Adnan accepted A3/I1 Common Manipulation API v1.0, Revision v2, including the observation-validity and `CompliantHold` semantics, in [PR #20 discussion](https://github.com/openAMRobot/openamrobot-manipulation/pull/20#issuecomment-6334318786).
- These semantic decisions are **accepted, not pending**. False `contact_detected_valid` or `object_detected_valid` means the corresponding observation is unavailable/invalid, not a measured negative.
- `CompliantHold` is rejected with `ACTION_REJECTED` before device calls or motion unless `has_compliant_control` is true, `compliant_hold` is enabled, and `force_torque_sensing` is declared.
- The canonical cross-repository I1 interface changes/alignment remain outstanding. That implementation handoff is distinct from the already accepted semantic decisions.

## Known gaps

- The OpenArm `GripperActionController` entries use the required singular `joint` parameter, with regression coverage against the selected controller type and actual parameters.
- I2 observation-validity conformance vectors specify the accepted unavailable-versus-measured-negative cases. They do not exercise a runtime I1 implementation. Runtime observation fields must not be added to the Device Package declaration schema.
- Hosted workflow run [#48](https://github.com/openAMRobot/openamrobot-manipulation/actions/runs/41100746763) passed both `repository-quality` and `quality/test` on PR head `f6457d0629ec5c993af0671ff979f83b27d01679`. DCO and CLA checks are green.
- The local fake-hardware integration rerun passed four suites with 37 individual pytest cases (15 fake-profile, 4 launch-guard, 11 fake-bringup, 7 MoveIt-planning). Colcon reports 41 total entries because it includes four suite-level entries; these are not additional pytest cases.
- Issue [#11](https://github.com/openAMRobot/openamrobot-manipulation/issues/11): owner acceptance of the fake MoveIt gripper-execution evidence remains open.
- Issue [#10](https://github.com/openAMRobot/openamrobot-manipulation/issues/10): upstream acceleration-limit owner acceptance remains open. The values are not physically qualified by this PR.
- Cross-repository upstream pin: this development fake-hardware profile uses `enactic/openarm_ros2` at `f0f6b639a65b4d05c1b3055825f4da0205e9330d`, while upper-body PR [#21](https://github.com/openAMRobot/openamr-upperbody-sw/pull/21) records `4e837e1d0dae692ff67b560b69d8d281d7a8d4ed`. The newer pin is three commits ahead and changes both v1.0 and v2.0 joint-limit files plus bringup/launch files. Combined-model validation on the newer pin is not established; model owners must adopt a common pin and rerun the coordinated checks.

## Not verified
- ROS/common-server/device end-to-end acceptance, hardware qualification of the pinned upstream acceleration limits, real hardware operation, physical-device acceptance, and safety qualification are not established by schema tests or fake hardware.
- Lift/arm transforms, physical workspace, payload/contact capabilities, and configuration acceptance are not validated by this PR (AGENTS.md at 095e6c7).
