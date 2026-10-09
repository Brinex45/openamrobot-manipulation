# SPDX-License-Identifier: MIT
# Copyright (c) 2026 OpenAMRobot (Botshare LTD)
"""Headless move_group tests using the pinned upstream v2.0 MoveIt config.

Planning and fake execution are tested separately.

The pinned upstream joint_limits.yaml lacks acceleration limits. The fake
profile applies a synthetic acceleration overlay labelled
"planning placeholder, not hardware" so headless planning and fake execution
can be tested. The pinned upstream configuration remains unchanged, and the
overlay must never be treated as validated hardware limits.
"""

import os
import time
import xml.etree.ElementTree as ET

from ament_index_python.packages import get_package_share_directory
import pytest
import yaml
import rclpy
from rclpy.action import ActionClient

from moveit_msgs.action import ExecuteTrajectory
from moveit_msgs.msg import Constraints, JointConstraint, MoveItErrorCodes
from moveit_msgs.srv import GetMotionPlan

from fake_stack import LaunchedStack, Probe
from openarm_v2_fake_baseline import fake_profile as fp

NAMED_STATE = 'hands_up'  # Upstream SRDF group_state, not an OpenAMRobot pose.
MOVEIT_V20 = os.path.join(get_package_share_directory('openarm_bimanual_moveit_config'),
                          'config', 'openarm_v2.0')
SRDF = os.path.join(MOVEIT_V20, 'openarm_bimanual.srdf')


def _named_state(group):
    root = ET.parse(SRDF).getroot()
    for gs in root.findall('group_state'):
        if gs.get('name') == NAMED_STATE and gs.get('group') == group:
            return {j.get('name'): float(j.get('value')) for j in gs.findall('joint')}
    raise LookupError(f'{NAMED_STATE} not defined for {group} in {SRDF}')


def test_root_cause_upstream_joint_limits_lack_acceleration():
    """Pins the root cause of the xfails above; fails once upstream changes it."""
    with open(os.path.join(MOVEIT_V20, 'joint_limits.yaml')) as f:
        limits = yaml.safe_load(f)['joint_limits']
    arm_joints = [j for s in fp.ARM_SIDES for j in fp.ARM_JOINTS[s]]
    assert set(arm_joints) <= set(limits)
    assert not any(limits[j].get('has_acceleration_limits') for j in arm_joints)


def test_move_group_plan_service_is_up(probe):
    """move_group loaded the upstream config and serves planning requests."""
    res = _plan(probe, 'left_arm', _named_state('left_arm')).motion_plan_response
    assert res.planning_time > 0.0
    assert res.trajectory_start.joint_state.name, 'no start state from move_group'


@pytest.fixture(scope='module')
def probe():
    stack = LaunchedStack('openarm_v2_fake_moveit.launch.py', 'use_fake_hardware:=true')
    rclpy.init()
    node = Probe()
    try:
        try:
            node.wait_for_controllers(
                [fp.ARM_CONTROLLERS[s] for s in fp.ARM_SIDES])
            client = node.create_client(GetMotionPlan, '/plan_kinematic_path')
            if not client.wait_for_service(timeout_sec=90.0):
                raise TimeoutError('move_group /plan_kinematic_path not available')
            node.destroy_client(client)
        except TimeoutError as exc:
            pytest.fail(f'{exc}\n--- launch output ---\n{stack.output()}')
        yield node
    finally:
        node.destroy_node()
        rclpy.shutdown()
        stack.stop()


def _plan(probe, group, goal):
    req = GetMotionPlan.Request()
    mpr = req.motion_plan_request
    mpr.group_name = group
    mpr.pipeline_id = 'ompl'
    mpr.num_planning_attempts = 1
    mpr.allowed_planning_time = 5.0
    mpr.max_velocity_scaling_factor = 0.1
    mpr.max_acceleration_scaling_factor = 0.1
    mpr.start_state.is_diff = True
    mpr.goal_constraints = [Constraints(joint_constraints=[
        JointConstraint(joint_name=j, position=v, tolerance_above=1e-3,
                        tolerance_below=1e-3, weight=1.0)
        for j, v in goal.items()])]
    return probe._call(GetMotionPlan, '/plan_kinematic_path', req, timeout=30.0)


@pytest.mark.parametrize('side', fp.ARM_SIDES)
def test_plan_to_upstream_named_state(probe, side):
    group = f'{side}_arm'
    goal = _named_state(group)
    res = _plan(probe, group, goal).motion_plan_response
    assert res.error_code.val == MoveItErrorCodes.SUCCESS, res.error_code.val
    traj = res.trajectory.joint_trajectory
    assert sorted(traj.joint_names) == sorted(fp.ARM_JOINTS[side])
    assert len(traj.points) >= 2
    final = dict(zip(traj.joint_names, traj.points[-1].positions))
    for j, v in goal.items():
        assert abs(final[j] - v) < 1e-2, (j, final[j], v)


def test_execute_planned_left_arm_on_fake_controller(probe):
    """Fake execution of a MoveIt plan (separate result from planning)."""
    goal = _named_state('left_arm')
    res = _plan(probe, 'left_arm', goal).motion_plan_response
    assert res.error_code.val == MoveItErrorCodes.SUCCESS
    client = ActionClient(probe, ExecuteTrajectory, '/execute_trajectory')
    assert client.wait_for_server(timeout_sec=10.0)
    send = client.send_goal_async(ExecuteTrajectory.Goal(trajectory=res.trajectory))
    rclpy.spin_until_future_complete(probe, send, timeout_sec=10.0)
    handle = send.result()
    assert handle is not None and handle.accepted
    result = handle.get_result_async()
    rclpy.spin_until_future_complete(probe, result, timeout_sec=60.0)
    assert result.done(), 'execute_trajectory timed out'
    assert result.result().result.error_code.val == MoveItErrorCodes.SUCCESS
    deadline = time.monotonic() + 5.0
    while True:
        pos = probe.joint_positions()
        if all(abs(pos[j] - v) < 1e-2 for j, v in goal.items()):
            break
        assert time.monotonic() < deadline, pos
        probe.spin_for(0.2)
