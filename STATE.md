# STATE

## Repository
- Type and lifecycle: interface / draft work; readiness unassessed (e0faeee).
- Owner role: common manipulation/Device Package work is owned by Om and Adnan (AGENTS.md at 095e6c7).
- Latest reviewed PR source head verified by hosted run #52: `af8bbcea00c82f9e967598ee108becf49c5d56a5` on `pr-9`; PR #20 is open. The DCO sign-off was added locally in amended commit `6bbd52d8d4e83cbf0d26365056f0dc9b7b0e3d25`; fresh hosted verification of that amended commit is pending.
- Hosted verification: [GitHub Actions run #52](https://github.com/openAMRobot/openamrobot-manipulation/actions/runs/42646961863) completed successfully on source head `af8bbcea00c82f9e967598ee108becf49c5d56a5`; both `repository-quality` and `quality/test` passed. This run predates the DCO-only amend to `6bbd52d`; fresh hosted checks for the amended commit are pending.
- Schema/conformance: 113 tests passed in local validation on 2026-11-09; hosted `quality/test` passed in run #52 on source head `af8bbcea00c82f9e967598ee108becf49c5d56a5`.
- Fake-hardware integration: fresh local run on 2026-10-29 passed four suites containing 37 individual pytest cases (15 fake-profile, 4 launch-guard, 11 fake-bringup, 7 MoveIt-planning). Colcon's 41-entry summary includes four suite-level entries; it is not 41 individual pytest cases.
- Package validation: both example packages report VALID with pending values; strict freeze remains blocked by pending values; package validation ran before commit c3abb545 (2026-10-21).

## I2 v0.6 proposal status

- I2 v0.6 (`grippers[]` keyed by `manipulator_id`, replacing singular `gripper` and removing `ros2_control.gripper_joints`) is a **proposed breaking migration**, not a frozen or owner-adopted contract.
- Consumer migration and compatibility implications remain subject to owner review. Do not describe v0.6 as adopted until the contract owner records that decision.
- `ManipulatorSelector` numeric values (`UNKNOWN=0`, `MANIPULATOR=1`, `GROUP=2`) and string group identifiers remain provisional pending confirmation of the wire-format checklist in openAMRobot/openamrobot-interfaces#36.
- Tracking and owner decisions: issue #19 and interface PR #36.

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
- Hosted workflow run [#52](https://github.com/openAMRobot/openamrobot-manipulation/actions/runs/42646961863) passed both `repository-quality` and `quality/test` on source head `af8bbcea00c82f9e967598ee108becf49c5d56a5`. The DCO sign-off is present on local amended commit `6bbd52d`; fresh hosted verification of that commit is pending.
- The local fake-hardware integration rerun passed four suites with 37 individual pytest cases (15 fake-profile, 4 launch-guard, 11 fake-bringup, 7 MoveIt-planning). Colcon reports 41 total entries because it includes four suite-level entries; these are not additional pytest cases.
- Issue [#11](https://github.com/openAMRobot/openamrobot-manipulation/issues/11): owner acceptance of the fake MoveIt gripper-execution evidence remains open.
- Issue [#10](https://github.com/openAMRobot/openamrobot-manipulation/issues/10): upstream acceleration-limit owner acceptance remains open. The values are not physically qualified by this PR.
- Cross-repository upstream pin: this development fake-hardware profile uses `enactic/openarm_ros2` at `f0f6b639a65b4d05c1b3055825f4da0205e9330d`, while upper-body PR [#21](https://github.com/openAMRobot/openamr-upperbody-sw/pull/21) records `4e837e1d0dae692ff67b560b69d8d281d7a8d4ed`. The newer pin is three commits ahead and changes both v1.0 and v2.0 joint-limit files plus bringup/launch files. Combined-model validation on the newer pin is not established; model owners must adopt a common pin and rerun the coordinated checks.

## Not verified
- ROS/common-server/device end-to-end acceptance, hardware qualification of the pinned upstream acceleration limits, real hardware operation, physical-device acceptance, and safety qualification are not established by schema tests or fake hardware.
- Lift/arm transforms, physical workspace, payload/contact capabilities, and configuration acceptance are not validated by this PR (AGENTS.md at 095e6c7).
