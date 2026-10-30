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
| [enactic/openarm_ros2](https://github.com/enactic/openarm_ros2/tree/f0f6b639a65b4d05c1b3055825f4da0205e9330d) | `f0f6b639a65b4d05c1b3055825f4da0205e9330d` (upstream MoveIt acceleration-limit fix, PR #96) | Apache-2.0 |
| [enactic/openarm_description](https://github.com/enactic/openarm_description/tree/14ff67b638ff1c738a1b9a6be8aaa5ce5ed2c831) | `14ff67b638ff1c738a1b9a6be8aaa5ce5ed2c831` (main, 2026-09-09; `1.0.4-22-g14ff67b`) | Apache-2.0 |

OpenArm 2.0 support exists only on upstream `main`: the model is under `assets/robot/openarm_v2.0`, and `openarm_ros2` gained it in 01b9f38, "Support OpenArm 2.0 (#91)". No release tag contains it, so the manifest pins commit SHAs. The build uses `openarm_description`, `openarm_bringup` and `openarm_bimanual_moveit_config`. `openarm_hardware` (the real CAN plugin) and the `openarm` meta-package are excluded with `COLCON_IGNORE`; `openarm_can` is not fetched. No upstream source is copied into this repository.

Verified with apt packages: `ros-jazzy-ros2-control` / `controller-manager` / `hardware-interface` 4.48.0, `joint-trajectory-controller` / `joint-state-broadcaster` 4.42.1, `moveit-*` 2.12.4, `xacro` 2.1.1, `robot-state-publisher` 3.3.4, `rclpy` 7.1.12, `rmw-fastrtps-cpp` 8.4.4 (default RMW).

## Upstream MoveIt acceleration-limit fix

The development manifest pins `enactic/openarm_ros2` to `f0f6b639a65b4d05c1b3055825f4da0205e9330d`, the upstream merge commit for MoveIt acceleration limits (upstream PR #96). The former local synthetic acceleration overlay has been removed; the fake baseline now tests the pinned upstream configuration directly.

The integration suite includes `test_upstream_joint_limits_enable_acceleration` and headless MoveIt planning and fake-controller execution checks. Passing these tests demonstrates fake-profile planning behaviour only. It does not establish that the acceleration values are appropriate or qualified for physical hardware.

Issue [#10](https://github.com/openAMRobot/openamrobot-manipulation/issues/10) remains open pending the project's owner-level acceptance and closure decision. The upstream fix and fake-profile tests do not, by themselves, establish physical-device acceptance.

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
| `test_fake_profile` (15) | Fake-profile restrictions, v2.0 model and joint checks, bounded targets, mock-only hardware, and MoveIt controller/joint-name configuration mappings |
| `test_launch_guard` (4) | Both launch files reject `use_fake_hardware:=false` and a missing argument, with no node started |
| `test_fake_bringup` (11) | Runtime hardware is mock-only; JSB, both arm JTCs and both gripper JTCs active; `/joint_states` has the 16 actuated joints; four `follow_joint_trajectory` endpoints; bounded trajectories on both arms and both grippers return `SUCCESSFUL` and `/joint_states` reaches the target. Negative cases check wrong endpoint names and a deactivated right-arm controller |
| `test_moveit_planning` (7) | Checks acceleration limits in the pinned upstream configuration, MoveIt planning-service availability, planning to the upstream `hands_up` state for both arms, execution of a planned left-arm trajectory, and plan-and-execute tests for both grippers through fake controllers |

The fresh local rerun on 2026-10-29 passed all four integration suites. The four xUnit XML files contain 37 individual pytest cases: 15 fake-profile, four launch-guard, 11 fake-bringup, and seven MoveIt-planning cases. Colcon reports 41 total entries because its summary also counts four suite-level entries from `Testing/20261029-1829/Test.xml`; these are not four additional pytest cases. All four suites passed with zero errors, failures, or skipped tests. These are contributor-local results, not hosted CI results.

## MoveIt acceleration-limit verification

The development dependency manifest now pins `enactic/openarm_ros2` at `f0f6b639a65b4d05c1b3055825f4da0205e9330d`, the upstream merge commit for acceleration limits (PR #96). The integration no longer applies a local synthetic acceleration overlay. The test `test_upstream_joint_limits_enable_acceleration` checks the pinned configuration, and the suite verifies headless planning and fake-controller execution against it.

These checks establish behaviour in the isolated fake-hardware profile only. They do not qualify the upstream acceleration values for a physical robot, nor do they establish physical-device or safety acceptance. Issue [#10](https://github.com/openAMRobot/openamrobot-manipulation/issues/10) remains open pending the project's owner-level acceptance and closure decision.

## MoveIt gripper execution gap — issue #11 remains open

At the pinned upstream v2.0 revision, `moveit_controllers.yaml` declares the grippers using `GripperCommand` on `gripper_cmd`, while `openarm_bringup` runs them as `JointTrajectoryController` controllers exposing `follow_joint_trajectory`.

The MoveIt controller configuration needs to use `FollowJointTrajectory` to match the controller setup. The fake-profile suite now plans and executes gripper trajectories through MoveIt for both arms, sends the planned trajectory through the fake execution path, and checks that mock joint state reaches the target. This is local fake-hardware evidence only; it does not prove that the unchanged upstream configuration works, or that real hardware executes gripper actions correctly.

Issue [#11](https://github.com/openAMRobot/openamrobot-manipulation/issues/11) remains open pending owner review of the fake-profile execution evidence and confirmation of the issue's acceptance criteria. The fake-profile tests do not establish upstream configuration correctness or physical-device acceptance.

## Not validated by this baseline

Fake trajectory success only shows that mock hardware followed the commanded positions. It does not validate the real hardware plugin, CAN, gains, zeroing, gripper contact or grasp force, payload, dynamics, collisions during execution, safety, or physical acceptance. It is not integrated simulation and not release readiness.

## Current validation boundaries

- **Hosted schema/conformance:** GitHub Actions Repository quality run [#48](https://github.com/openAMRobot/openamrobot-manipulation/actions/runs/41100746763) completed successfully on PR head `f6457d0629ec5c993af0671ff979f83b27d01679`; both `repository-quality` and `quality/test` passed. The schema/conformance gate contains 103 tests. This workflow does not run the separate ROS/fake-hardware integration suite.
- **DCO / CLA:** Both checks passed on the submitted PR head.
- **Fake-hardware integration:** The fresh local run on 2026-10-29 passed all four suites with zero errors, failures, or skipped tests. The four xUnit XML files contain 37 individual pytest cases (15 fake-profile, 4 launch-guard, 11 fake-bringup, 7 MoveIt-planning). Colcon reports 41 total entries because it also counts four suite-level entries in `Testing/20261029-1829/Test.xml`; these are not additional pytest cases. This is contributor-local evidence, not hosted CI evidence.
- **MoveIt acceleration limits:** Uses the pinned upstream fix; no synthetic local acceleration overlay remains. Fake-profile planning success does not qualify the limits for physical hardware. Issue [#10](https://github.com/openAMRobot/openamrobot-manipulation/issues/10) remains open pending owner-level acceptance.
- **Cross-repository upstream pin:** The development fake-hardware profile uses `enactic/openarm_ros2` at `f0f6b639a65b4d05c1b3055825f4da0205e9330d`, while upper-body PR [#21](https://github.com/openAMRobot/openamr-upperbody-sw/pull/21) records `4e837e1d0dae692ff67b560b69d8d281d7a8d4ed`. The newer pin is three commits ahead and changes both v1.0 and v2.0 joint-limit files plus bringup/launch files. PR #21's successful checks on the older pin do not validate the combined model against the newer acceleration limits. The model owners must adopt a common pin and rerun coordinated combined-model checks.
- **MoveIt gripper action execution:** Both grippers have local fake-profile plan-and-execute test coverage; issue [#11](https://github.com/openAMRobot/openamrobot-manipulation/issues/11) remains open pending owner review. Physical-device acceptance remains unverified.
- **A3/I1 contract:** Adnan accepted A3/I1 document Revision v2 / I1 API v1.0 and the observation-validity and `CompliantHold` decisions in [PR conversation](https://github.com/openAMRobot/openamrobot-manipulation/pull/20#issuecomment-6334318786). These semantic decisions are accepted, not pending. Canonical I1 interface changes and cross-repository alignment remain outstanding.
- **Physical hardware, real CAN operation, and device acceptance:** Not validated.
