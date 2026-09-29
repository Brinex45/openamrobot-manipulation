# OpenArm 2.0 inventory for the combined-model owner

> **Status:** Founder-authorized Sunday preparation; owner alignment pending Monday review.
> This draft is not an accepted contract or production implementation.
> Recipient: `openamr-upperbody-sw` owner (Tushar), who owns the combined base + fixed mast + arms model.
> This is an inventory only. It selects no mast position, invents no transforms and makes no payload, contact or stability claims.

All values below come from the pinned upstream sources. They were read from the URDF expanded with the default preset and `use_fake_hardware:=true`. They have not been validated on hardware.

## 1. Model revision

| Item | Value |
|---|---|
| Description | [enactic/openarm_description @ `14ff67b`](https://github.com/enactic/openarm_description/tree/14ff67b638ff1c738a1b9a6be8aaa5ce5ed2c831/assets/robot/openarm_v2.0) (Apache-2.0) |
| Entry xacro | [`assets/robot/openarm_v2.0/urdf/openarm_v20.urdf.xacro`](https://github.com/enactic/openarm_description/blob/14ff67b638ff1c738a1b9a6be8aaa5ce5ed2c831/assets/robot/openarm_v2.0/urdf/openarm_v20.urdf.xacro), robot name `openarm_v20` |
| xacro args | `robot_preset` (default `default_bimanual`), `collapse_internal_empty_links` (`true`), `emit_grasp_frame` (`false`), `use_fake_hardware` (`true`) |
| Presets | [`config/robot_presets/`](https://github.com/enactic/openarm_description/tree/14ff67b638ff1c738a1b9a6be8aaa5ce5ed2c831/assets/robot/openarm_v2.0/config/robot_presets): `default_bimanual`, `left_arm`, `right_arm`, `left_arm_with_pinch_gripper`, `right_arm_with_pinch_gripper` |
| End effector | `pinch_gripper` ([assets](https://github.com/enactic/openarm_description/tree/14ff67b638ff1c738a1b9a6be8aaa5ce5ed2c831/assets/end_effector/pinch_gripper)) |
| Controllers / MoveIt | [enactic/openarm_ros2 @ `4e837e1`](https://github.com/enactic/openarm_ros2/tree/4e837e1d0dae692ff67b560b69d8d281d7a8d4ed): `openarm_bringup/config/controllers/*.yaml`, `openarm_bimanual_moveit_config/config/openarm_v2.0/` |

## 2. Frames and mounting (upstream default bimanual preset)

```
world
└─ openarm_body_link0                (fixed, origin 0 0 0)          ← upstream OpenArm body, not the OpenAMRobot mast
   ├─ openarm_left_base_link          (fixed, xyz 0  0.031 0.698, rpy 0 0 0)   from body left_arm_mount_point
   │  └─ link1 … link6 → openarm_left_ee_base_link → ee_link1 / ee_link2
   └─ openarm_right_base_link         (fixed, xyz 0 -0.031 0.698, rpy 0 0 0)   from body right_arm_mount_point
      └─ link1 … link6 → openarm_right_ee_base_link → ee_link1 / ee_link2
```

Mount points: [`config/body/struct/reference_points.yaml`](https://github.com/enactic/openarm_description/blob/14ff67b638ff1c738a1b9a6be8aaa5ce5ed2c831/assets/robot/openarm_v2.0/config/body/struct/reference_points.yaml). The left arm is a Y-reflected copy (`reflect.y: -1` in `default_bimanual.yaml`), which is why the left and right joint1/joint2 limits are mirrored.

## 3. Joints (unique; 18 movable, 4 fixed)

| Joint | Parent → child | Origin xyz (m) | Limits (rad) |
|---|---|---|---|
| `openarm_left_joint1` | left_base_link → left_link1 | 0 0.0625 0 | −3.4907 … 1.3963 |
| `openarm_left_joint2` | left_link1 → left_link2 | 0 0.06 0 | −3.3161 … 0.17453 |
| `openarm_left_joint3` | left_link2 → left_link3 | 0 0 −0.06625 | −1.5708 … 1.5708 |
| `openarm_left_joint4` | left_link3 → left_link4 | 0 0 −0.15375 | 0 … 2.4435 |
| `openarm_left_joint5` | left_link4 → left_link5 | 0 0 −0.0955 | −1.5708 … 1.5708 |
| `openarm_left_joint6` | left_link5 → left_link6 | 0 0 −0.1205 | −0.7854 … 0.7854 |
| `openarm_left_joint7` | left_link6 → left_ee_base_link | 0 0 0 | −1.5708 … 1.5708 |
| `openarm_left_finger_joint1` | left_ee_base_link → left_ee_link1 | −0.00143 −0.018 −0.068 | 0 … 0.7854 |
| `openarm_left_finger_joint2` | mimic of finger_joint1 (×1) | −0.00143 0.018 −0.068 | 0 … 0.7854 |
| `openarm_right_joint1` | right_base_link → right_link1 | 0 −0.0625 0 | −1.3963 … 3.4907 |
| `openarm_right_joint2` | right_link1 → right_link2 | 0 −0.06 0 | −0.17453 … 3.3161 |
| `openarm_right_joint3`–`joint7` | as left | as left | as left |
| `openarm_right_finger_joint1` | right_ee_base_link → right_ee_link1 | −0.00143 0.018 −0.068 | −0.7854 … 0 |
| `openarm_right_finger_joint2` | mimic of finger_joint1 (×1) | −0.00143 −0.018 −0.068 | −0.7854 … 0 |

Fixed joints: `openarm_body_link0_mount_joint`, `openarm_{left,right}_base_link_mount_joint` (plus `openarm_{left,right}_grasp_frame_joint` when `emit_grasp_frame:=true`). The `ros2_control` systems are `openarm_left_hardware_interface` and `openarm_right_hardware_interface`. Each exposes joint1–7 and finger_joint1 with position/velocity/effort interfaces.

## 4. TCP / end-effector frames

- The SRDF end effectors are `left_ee` and `right_ee`, with parent links `openarm_{left,right}_ee_base_link` (groups `left_gripper`, `right_gripper`).
- There is no TCP frame by default. Upstream can emit `openarm_{side}_grasp_frame` with `emit_grasp_frame:=true`: parent `openarm_{side}_ee_base_link`, xyz `-0.00143 0 -0.138`, rpy `0 1.5708 0` (from [`pinch_gripper/config/struct/reference_points.yaml`](https://github.com/enactic/openarm_description/blob/14ff67b638ff1c738a1b9a6be8aaa5ce5ed2c831/assets/end_effector/pinch_gripper/config/struct/reference_points.yaml) after upstream base-frame shift). It is not validated as an OpenAMRobot TCP.

## 5. Collision / visual / inertial assets

All 21 non-world links have a visual, a collision mesh and an upstream "nominal" inertial.

- Arm: `assets/robot/openarm_v2.0/meshes/arm/{visual/*.dae, collision/*.stl}` (base_link, link1–link6)
- Body: `assets/robot/openarm_v2.0/meshes/body/{visual/body_link0.dae, collision/body_link0_symp.stl}`
- Gripper: `assets/end_effector/pinch_gripper/meshes/{visual/*.dae, collision/*.stl}` (ee_base_link, finger_inner, finger_outer)

Upstream nominal inertials are not measured values for the OpenAMRobot build.

## 6. Mast configuration context (not a selection)

| Configuration ID | Status |
|---|---|
| `mast_1350` | Installed shoulder-axis height, 1350 mm (P-03 Decision Addendum revision 18.2, 28 September 2026) |
| `mast_1300`, `mast_1400`, `mast_1450` | Indexed positions available for assessment; not installed without a recorded decision |

The mast top is 1500 mm above the floor and the maximum assembled height is 1700 mm; positions above 1450 mm are not provided by the 2.0 mast. None of the four positions is validated by this work. The fixed mast is the 2.0 configuration; the lift is deferred to OpenAMRobot 3.0.

## 7. Missing inputs (no values guessed)

1. **Shoulder-axis datum:** which OpenArm frame the "shoulder-axis height" refers to (`openarm_*_base_link` origin, the joint1 axis at +0.0625 m in Y, or the joint2 axis). This is needed before any mast ID can become a transform.
2. **Base → mast → arm-mount transforms** for each `mast_*` ID: xyz/rpy of each arm base link relative to the mobile-base frame, including lateral spacing and mount orientation. The upstream value (±0.031 m, z 0.698 m on `openarm_body_link0`) describes Enactic's body, not the OpenAMRobot mast.
3. **Body usage:** whether the combined model keeps `openarm_body_link0` or mounts the arms directly on the mast. Upstream single-arm presets exist, but none is chosen here.
4. **Mast and base collision geometry**, and the allowed-collision matrix between mast, base and arms.
5. **TCP definition** for OpenAMRobot tools, and whether the upstream grasp frame is adopted.
6. **Measured mass/inertia** of the as-built arms, grippers and any tool; payload is not claimed.
7. **Mounted-pose calibration** procedure and data.
8. **MoveIt acceleration limits:** upstream v2.0 `joint_limits.yaml` has none, so MoveIt 2.12 time parameterization fails (see `integration/README.md`).
9. **Gripper interface choice:** the upstream MoveIt config expects `GripperCommand`, but bring-up provides `JointTrajectoryController`.

## 8. Documentation discrepancies (reported, not edited here)

- [`openamr-upperbody-sw` README @ `d090ec5`](https://github.com/openAMRobot/openamr-upperbody-sw/blob/d090ec545f4450e4c94335dded6e2f001cf494d6/README.md) still describes an actuated lift ("Lift control", "base + lift + arm", "arm + lift" planning groups). This is stale for 2.0: the mast is fixed and the lift is deferred.
- This repository's `README.md` (main @ `6198d48`) still names **ReBot** as the secondary portability target. The current secondary fixture is **SO-101**.
