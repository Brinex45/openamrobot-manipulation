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
| `integration/openarm_v2_combined_model_inventory.md` | Handoff inventory for the combined base + mast + arms model owner |

## Pinned upstream

| Repository | Commit | Licence |
|---|---|---|
| [enactic/openarm_ros2](https://github.com/enactic/openarm_ros2/tree/4e837e1d0dae692ff67b560b69d8d281d7a8d4ed) | `4e837e1d0dae692ff67b560b69d8d281d7a8d4ed` (main, 2026-06-29; `0.9.2-5-g4e837e1`) | Apache-2.0 |
| [enactic/openarm_description](https://github.com/enactic/openarm_description/tree/14ff67b638ff1c738a1b9a6be8aaa5ce5ed2c831) | `14ff67b638ff1c738a1b9a6be8aaa5ce5ed2c831` (main, 2026-09-09; `1.0.4-22-g14ff67b`) | Apache-2.0 |

OpenArm 2.0 support exists only on upstream `main`: the model is under `assets/robot/openarm_v2.0`, and `openarm_ros2` gained it in 01b9f38 "Support OpenArm 2.0 (#91)". No release tag contains it, so the manifest pins commit SHAs. The build uses `openarm_description`, `openarm_bringup` and `openarm_bimanual_moveit_config`. `openarm_hardware` (the real CAN plugin) and the `openarm` meta-package are excluded with `COLCON_IGNORE`; `openarm_can` is not fetched. No upstream source is copied into this repository.

Verified with apt packages: `ros-jazzy-ros2-control` / `controller-manager` / `hardware-interface` 4.48.0, `joint-trajectory-controller` / `joint-state-broadcaster` 4.42.1, `moveit-*` 2.12.4, `xacro` 2.1.1, `robot-state-publisher` 3.3.4, `rclpy` 7.1.12, `rmw-fastrtps-cpp` 8.4.4 (default RMW).

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
| `test_fake_profile` (13) | v2.0 model is expanded (not v1.0), 18 unique movable joints (14 arm, 2 actuated fingers, 2 mimic fingers), only mock plugins, `ros2_control` joints match upstream controller YAML, targets stay inside URDF limits, guard rejects non-`true` values and a real-hardware expansion |
| `test_launch_guard` (4) | both launch files reject `use_fake_hardware:=false` and a missing argument, with no node started |
| `test_fake_bringup` (11) | runtime hardware is mock-only; JSB, both arm JTCs and both gripper JTCs active; `/joint_states` has the 16 actuated joints; 4 `follow_joint_trajectory` endpoints; a bounded trajectory on each arm and each gripper (targets derived from the URDF limits read back from `robot_state_publisher`) returns `SUCCESSFUL` and `/joint_states` reaches the target. Negative cases: a wrong endpoint name is not found; a deactivated right-arm controller shows as `inactive`, rejects the goal, and no joint moves |
| `test_moveit_planning` (5) | `move_group` loads the upstream v2.0 config and answers plan requests; root-cause check (below); planning for both arms and MoveIt execution for the left arm are **strict xfail** |

### Known upstream issue: MoveIt planning fails

At the pinned commit, `openarm_bimanual_moveit_config/config/openarm_v2.0/joint_limits.yaml` sets `has_acceleration_limits: false` for every joint. With MoveIt 2.12.4, the default OMPL pipeline's `AddTimeOptimalParameterization` adapter then rejects every plan: `No acceleration limit was defined for joint openarm_left_joint1!` → `FAILURE (99999)`. OMPL itself finds a path; only the time parameterization fails. In a scratch-only diagnostic (not committed), placeholder limits made both arms plan successfully. Those placeholder values are not proposed; real limits must come from upstream or the owners. The planning tests are strict xfails: they count as failures, not passes, and turn red once upstream changes. This package does not patch upstream configuration.

A second upstream mismatch: `moveit_controllers.yaml` (v2.0) declares the grippers as `GripperCommand` on `gripper_cmd`, but `openarm_bringup` runs them as `JointTrajectoryController` (`follow_joint_trajectory`). Gripper execution through MoveIt will therefore not work as configured. Only the direct JTC gripper path is tested here.

## Not validated by this baseline

Fake trajectory success only shows that mock hardware followed the commanded positions. It does not validate the real hardware plugin, CAN, gains, zeroing, gripper contact or grasp force, payload, dynamics, collisions during execution, safety, or physical acceptance. It is not integrated simulation and not release readiness.
