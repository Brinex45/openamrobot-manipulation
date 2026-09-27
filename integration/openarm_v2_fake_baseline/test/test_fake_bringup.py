# SPDX-License-Identifier: MIT
# Copyright (c) 2026 OpenAMRobot (Botshare LTD)
"""Run the fake-only bring-up and exercise both arms and both grippers.

Fake trajectory success only shows that upstream mock_components followed the
commanded positions. It does not validate contact, load, dynamics or safety.
"""

import pytest
import rclpy

from control_msgs.action import FollowJointTrajectory

from fake_stack import LaunchedStack, Probe
from openarm_v2_fake_baseline import fake_profile as fp

SUCCESSFUL = FollowJointTrajectory.Result.SUCCESSFUL
TOLERANCE = 1e-3
ALL_CONTROLLERS = (['joint_state_broadcaster']
                   + [fp.ARM_CONTROLLERS[s] for s in fp.ARM_SIDES]
                   + [fp.GRIPPER_CONTROLLERS[s] for s in fp.ARM_SIDES])


@pytest.fixture(scope='module')
def probe():
    stack = LaunchedStack('openarm_v2_fake.launch.py', 'use_fake_hardware:=true')
    rclpy.init()
    node = Probe()
    try:
        try:
            node.wait_for_controllers(ALL_CONTROLLERS)
        except TimeoutError as exc:
            pytest.fail(f'{exc}\n--- launch output ---\n{stack.output()}')
        yield node
    finally:
        node.destroy_node()
        rclpy.shutdown()
        stack.stop()


@pytest.fixture(scope='module')
def model(probe):
    urdf = probe.robot_description()
    fp.assert_mock_only(urdf)
    return fp.model_joints(urdf)


def _move_and_check(probe, model, controller, joints):
    start = probe.joint_positions()
    targets = [fp.bounded_target(model[j]['lower'], model[j]['upper'], start[j])
               for j in joints]
    accepted, result = probe.send_trajectory(
        fp.FOLLOW_JOINT_TRAJECTORY.format(controller), joints, targets)
    assert accepted, f'{controller} rejected an in-limit goal'
    assert result.error_code == SUCCESSFUL, (result.error_code, result.error_string)
    probe.spin_for(0.3)
    end = probe.joint_positions()
    for j, t in zip(joints, targets):
        assert abs(end[j] - start[j]) > 0.05, f'{j} did not move'
        assert abs(end[j] - t) < TOLERANCE, (j, end[j], t)
    return start


def test_runtime_hardware_is_mock_only(probe):
    components = probe.hardware_components()
    assert set(components) == {'openarm_left_hardware_interface',
                               'openarm_right_hardware_interface'}, components
    for name, (plugin, state) in components.items():
        assert plugin == fp.MOCK_PLUGIN, (name, plugin)
        assert state == 'active', (name, state)


def test_expected_controllers_active(probe):
    states = probe.controller_states()
    for name in ALL_CONTROLLERS:
        assert states.get(name) == 'active', states


def test_joint_states_cover_all_actuated_joints(probe):
    probe.joint_positions()
    names = list(probe.last_joint_state.name)
    expected = [j for s in fp.ARM_SIDES
                for j in fp.ARM_JOINTS[s] + fp.GRIPPER_JOINTS[s]]
    assert len(names) == len(set(names))
    assert sorted(names) == sorted(expected)


@pytest.mark.parametrize('side', fp.ARM_SIDES)
def test_arm_and_gripper_action_endpoints(probe, side):
    for controller in (fp.ARM_CONTROLLERS[side], fp.GRIPPER_CONTROLLERS[side]):
        name = fp.FOLLOW_JOINT_TRAJECTORY.format(controller)
        assert probe.action_server_available(name), name


@pytest.mark.parametrize('side', fp.ARM_SIDES)
def test_arm_trajectory_executes(probe, model, side):
    joints = fp.ARM_JOINTS[side]
    start = _move_and_check(probe, model, fp.ARM_CONTROLLERS[side], joints)
    # Return to where we started so later tests see a known state.
    accepted, result = probe.send_trajectory(
        fp.FOLLOW_JOINT_TRAJECTORY.format(fp.ARM_CONTROLLERS[side]), joints,
        [start[j] for j in joints])
    assert accepted and result.error_code == SUCCESSFUL


@pytest.mark.parametrize('side', fp.ARM_SIDES)
def test_gripper_fake_position_trajectory(probe, model, side):
    """Position-only mock gripper; says nothing about grasp or contact."""
    _move_and_check(probe, model, fp.GRIPPER_CONTROLLERS[side],
                    fp.GRIPPER_JOINTS[side])


def test_wrong_endpoint_is_detected(probe):
    """Negative: an endpoint name that does not exist must not look available."""
    assert not probe.action_server_available(
        '/left_arm_controller/follow_joint_trajectory', timeout=3.0)


def test_missing_controller_is_detected(probe, model):
    """Negative: with the right arm controller deactivated, the checks must fail.

    The action server object still exists while the controller is inactive, so
    the controller state and goal rejection are what must catch it.
    """
    controller = fp.ARM_CONTROLLERS['right']
    joints = fp.ARM_JOINTS['right']
    assert probe.switch(deactivate=[controller])
    try:
        assert probe.controller_states()[controller] == 'inactive'
        before = probe.joint_positions()
        targets = [fp.bounded_target(model[j]['lower'], model[j]['upper'], before[j])
                   for j in joints]
        accepted, _ = probe.send_trajectory(
            fp.FOLLOW_JOINT_TRAJECTORY.format(controller), joints, targets,
            timeout=10.0)
        assert not accepted, 'inactive controller accepted a goal'
        probe.spin_for(0.5)
        after = probe.joint_positions()
        assert all(abs(after[j] - before[j]) < TOLERANCE for j in joints)
    finally:
        assert probe.switch(activate=[controller])
    assert probe.controller_states()[controller] == 'active'
