# Integration: OpenArm 2.0 fake-hardware baseline

> **Status:** Owner-adopted development-only fake-hardware baseline.
> This draft is not an accepted contract or production implementation.
> Owners: Om Jagtap, Adnan Khalid. Reviewer: Mohamed Sayed.

A development-only, headless bring-up of the **upstream** OpenArm 2.0 bimanual model and controllers on `ros2_control` mock hardware, plus tests. It adds no manipulation API and no Device Package format. It adds no safety logic and never drives physical hardware.

## Workspace scope

`integration/` carries a `COLCON_IGNORE` marker, so the package is **not** built by the default OpenAMRobot workspace created from `openamrobot-manifest`: that workspace does not contain the pinned upstream OpenArm repositories, and `rosdep` would fail on their keys. The baseline is built and tested only in the isolated development workspace created by `scripts/setup_workspace.sh`, which symlinks the package directory itself (the marker in the parent directory does not apply there). Adding the upstream repositories to the release manifest is a separate decision tracked in openamrobot-manifest issue #8.

## Package paths

| Path | Purpose |
|---|---|
| `integration/openarm_v2_fake_baseline/` | ROS 2 package `openarm_v2_fake_baseline` (ament_cmake) |
| `…/openarm_v2.dev.repos` | **Development** dependency manifest: pinned upstream commits (vcstool) |
| `…/scripts/setup_workspace.sh` | Creates an isolated workspace, `rosdep install`, `colcon build` |
| `…/launch/openarm_v2_fake.launch.py` | Headless fake bring-up: `robot_state_publisher`, `ros2_control_node`, spawners |
| `…/launch/openarm_v2_fake_moveit.launch.py` | The above plus headless `move_group` (upstream v2.0 MoveIt config, OMPL) |
| `…/openarm_v2_fake_baseline/fake_profile.py` | Fake-only argument check, v2.0 xacro expansion, mock-plugin check, model parsing |
| `…/test/` | pytest suites run through `colcon test` |
| `integration/openarm_v2_combined_model_inventory.md` | Handoff inventory for the combined base + lift + arms model owner |

## Pinned upstream

| Repository | Commit | Licence |
|---|---|---|
| [enactic/openarm_ros2](https://github.com/enactic/openarm_ros2/tree/4e837e1d0dae692ff67b560b69d8d281d7a8d4ed) | `4e837e1d0dae692ff67b560b69d8d281d7a8d4ed` (main, 2026-06-29; `0.9.2-5-g4e837e1`) | Apache-2.0 |
| [enactic/openarm_description](https://github.com/enactic/openarm_description/tree/14ff67b638ff1c738a1b9a6be8aaa5ce5ed2c831) | `14ff67b638ff1c738a1b9a6be8aaa5ce5ed2c831` (main, 2026-09-09; `1.0.4-22-g14ff67b`) | Apache-2.0 |

OpenArm 2.0 support exists only on upstream `main`: the model is under `assets/robot/openarm_v2.0`, and `openarm_ros2` gained it in 01b9f38, "Support OpenArm 2.0 (#91)". No release tag contains it, so the manifest pins commit SHAs. The build uses `openarm_description`, `openarm_bringup` and `openarm_bimanual_moveit_config`. `openarm_hardware` (the real CAN plugin) and the `openarm` meta-package are excluded with `COLCON_IGNORE`; `openarm_can` is not fetched. No upstream source is copied into this repository.

Verified with apt packages: `ros-jazzy-ros2-control` / `controller-manager` / `hardware-interface` 4.48.0, `joint-trajectory-controller` / `joint-state-broadcaster` 4.42.1, `moveit-*` 2.12.4, `xacro` 2.1.1, `robot-state-publisher` 3.3.4, `rclpy` 7.1.12, `rmw-fastrtps-cpp` 8.4.4 (default RMW).

## Fake-profile acceleration overlay — pending review

The pinned upstream OpenArm v2.0 `joint_limits.yaml` remains unchanged by the integration overlay. Its disabled acceleration limits cause MoveIt's `AddTimeOptimalParameterization` adapter to reject plans in the pinned configuration.

The fake MoveIt launch can apply a separate synthetic acceleration overlay only after checking the explicit fake-hardware profile and mock-plugin configuration. The overlay is labelled **"planning placeholder, not hardware"**.

The overlay exists only to enable fake-profile planning and fake-controller execution tests. Its acceleration values are not approved, validated, or proposed for physical hardware. A regression test verifies that the overlay is rejected for non-fake profiles.

The new overlay is **pending review** and does not replace the upstream fix. Issue [#10](https://github.com/openAMRobot/openamrobot-manipulation/issues/10) remains open for the upstream acceleration-limit question. The original owner-adopted development-only fake-hardware baseline remains a separate record; the new overlay does not reset that adoption status.

## Commands

Prerequisites: Ubuntu 24.04, ROS 2 Jazzy in `/opt/ros/jazzy`, `colcon`, `rosdep` (initialised), `vcstool`, and `/usr/bin/python3` → Python 3.12. No GPU and no CAN device are needed.

```bash
# 1. Workspace (clones pinned upstream, installs declared deps, builds)
integration/openarm_v2_fake_baseline/scripts/setup_workspace.sh ~/openarm_v2_fake_ws

# 2. Tests
cd ~/openarm_v2_fake_ws
source /opt/ros/jazzy/setup.bash && source install/setup.bash
python3.12 -m colcon test --packages-select openarm_v2_fake_baseline
python3.12 -m colcon test-result --verbose --test-result-base build/openarm_v2_fake_baseline

# 3. Manual headless bring-up (use_fake_hardware is required and must be true)
ros2 launch openarm_v2_fake_baseline openarm_v2_fake.launch.py use_fake_hardware:=true
ros2 launch openarm_v2_fake_baseline openarm_v2_fake_moveit.launch.py use_fake_hardware:=true
```

`python3.12 -m colcon` is used because some images have a different default `python3` on `PATH`. The script passes `-DPython3_EXECUTABLE` for the same reason. If CMake finds no `pytest`, `CMakeLists.txt` stops with an error. It does not register an empty test suite.

## Fake-only guarantees (development profile, not a safety mechanism)

- `use_fake_hardware` has no default. Omitting it, or passing anything except `true`, aborts the launch before any node starts (tested).
- The wrapper expands the v2.0 xacro with `use_fake_hardware:=true` and passes no CAN interface names. It rejects the description unless every `ros2_control` system uses `mock_components/GenericSystem` (tested at expansion time and again at runtime through `list_hardware_components`).
- `openarm_hardware` is not built, so its plugin cannot be loaded.
- Launch and tests set `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`. `colcon test` also gives each test file a unique `ROS_DOMAIN_ID` through `ament_cmake_ros`.

## What the tests check

| Suite | Checks |
|---|---|
| `test_fake_profile` (17) | Fake-profile restrictions, application of the synthetic overlay to known joints, rejection of the overlay for non-fake profiles, and MoveIt controller/joint-name configuration mappings |
| `test_launch_guard` (4) | Both launch files reject `use_fake_hardware:=false` and a missing argument, with no node started |
| `test_fake_bringup` (11) | Runtime hardware is mock-only; JSB, both arm JTCs and both gripper JTCs active; `/joint_states` has the 16 actuated joints; four `follow_joint_trajectory` endpoints; bounded trajectories on both arms and both grippers return `SUCCESSFUL` and `/joint_states` reaches the target. Negative cases check wrong endpoint names and a deactivated right-arm controller |
| `test_moveit_planning` (5) | MoveIt loads the upstream v2.0 configuration and serves planning requests; root-cause check; planning to the upstream `hands_up` state for both arms and execution of a planned left-arm trajectory through the fake controller using the fake-only overlay |

The recorded local package validation is 17 passing fake-profile tests, five passing MoveIt planning tests, and 41 package tests with zero errors, failures or skipped tests. These are local results, not hosted CI results.

## Known upstream issue: MoveIt planning fails

At the pinned commit, `openarm_bimanual_moveit_config/config/openarm_v2.0/joint_limits.yaml` disables acceleration limits for the arm joints. With MoveIt 2.12.4, the default OMPL pipeline's `AddTimeOptimalParameterization` adapter rejects plans with an error such as:

```text
No acceleration limit was defined for joint openarm_left_joint1!
```

The planning service returns `FAILURE (99999)`. OMPL can find a geometric path, but time parameterization fails.

The fake-profile integration now uses a separate synthetic acceleration overlay labelled **"planning placeholder, not hardware"** to enable headless planning and fake-controller execution tests. The upstream configuration remains unchanged, and a regression test rejects the overlay for non-fake profiles. Passing tests establish fake-profile integration behaviour only; they do not establish approved acceleration limits or physical-hardware acceptance.

Issue [#10](https://github.com/openAMRobot/openamrobot-manipulation/issues/10) remains open for the upstream acceleration-limit question. The upstream fix must provide appropriate acceleration limits; this integration does not prescribe or qualify real-hardware values.

## MoveIt gripper execution gap — issue #11 remains open

At the pinned upstream v2.0 revision, `moveit_controllers.yaml` declares the grippers using `GripperCommand` on `gripper_cmd`, while `openarm_bringup` runs them as `JointTrajectoryController` controllers exposing `follow_joint_trajectory`.

The MoveIt controller configuration needs to use `FollowJointTrajectory` to match the controller setup. The integration checks the expected controller and joint-name mappings, but a configuration assertion does **not** prove that the gripper action executes successfully through MoveIt. Direct JTC gripper execution is separate evidence.

Issue [#11](https://github.com/openAMRobot/openamrobot-manipulation/issues/11) remains open for the actual MoveIt gripper execution gap until the MoveIt action path is validated. Do not treat the configuration mapping test as end-to-end gripper acceptance.

## Not validated by this baseline

Fake trajectory success only shows that mock hardware followed the commanded positions. It does not validate the real hardware plugin, CAN, gains, zeroing, gripper contact or grasp force, payload, dynamics, collisions during execution, safety, or physical acceptance. It is not integrated simulation and not release readiness.

## Current validation boundaries

- **Schema/conformance:** Local tests only; not hosted CI acceptance.
- **Fake-hardware integration:** Local build and tests only.
- **Synthetic acceleration values:** Planning placeholders only, not hardware-qualified.
- **MoveIt gripper action execution:** Not established by controller-configuration checks.
- **Physical hardware, real CAN operation, and device acceptance:** Not validated.
- **A3/I1 contract reference and acceptance record:** Exact revision and acceptance record still require confirmation from the contract owner.
- **Unresolved A3/I1 semantics:** Unavailable gripper contact/object data and `CompliantHold` / compliant-control capability gating remain open pending agreement with Adnan and the contract owners.
- **Hosted test gate:** The local test results above must not be presented as hosted Actions evidence. The skipped `repository-quality / quality/test` gate requires coordination with the repository maintainers.
