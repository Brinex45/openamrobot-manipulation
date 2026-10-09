# SPDX-License-Identifier: MIT
# Copyright (c) 2026 OpenAMRobot (Botshare LTD)
"""Model-expansion checks for the pinned OpenArm 2.0 description (no ROS graph)."""

import os

from ament_index_python.packages import get_package_share_directory
import pytest
import xacro
import yaml

from openarm_v2_fake_baseline import fake_profile as fp

DESCRIPTION_SHARE = get_package_share_directory('openarm_description')


@pytest.fixture(scope='module')
def fake_urdf():
    return fp.expand_fake_description(DESCRIPTION_SHARE)


def test_expands_v20_model_not_v10(fake_urdf):
    assert os.path.isfile(fp.v20_xacro_path(DESCRIPTION_SHARE))
    assert '<robot name="openarm_v20"' in fake_urdf
    assert 'openarm_v2.0/meshes' in fake_urdf
    assert 'openarm_v1.0' not in fake_urdf


def test_only_mock_hardware_plugins(fake_urdf):
    plugins = fp.assert_mock_only(fake_urdf)
    assert sorted(n for n, _ in plugins) == [
        'openarm_left_hardware_interface', 'openarm_right_hardware_interface']
    assert all(p == fp.MOCK_PLUGIN for _, p in plugins)
    assert 'openarm_hardware/OpenArmHW' not in fake_urdf
    assert 'can_interface' not in fake_urdf


def test_joint_names_unique_and_expected(fake_urdf):
    joints = fp.model_joints(fake_urdf)
    movable = sorted(n for n, j in joints.items() if j['type'] != 'fixed')
    expected = sorted(
        fp.ARM_JOINTS['left'] + fp.ARM_JOINTS['right']
        + fp.GRIPPER_JOINTS['left'] + fp.GRIPPER_JOINTS['right']
        + ['openarm_left_finger_joint2', 'openarm_right_finger_joint2'])
    assert movable == expected
    for side in fp.ARM_SIDES:
        assert joints[f'openarm_{side}_finger_joint2']['mimic'] == \
            f'openarm_{side}_finger_joint1'
    for name in movable:
        assert joints[name]['lower'] < joints[name]['upper'], name


def test_ros2_control_joints_match_upstream_controllers(fake_urdf):
    rc_joints = fp.ros2_control_joints(fake_urdf)
    assert len(rc_joints) == len(set(rc_joints)) == 16
    path = os.path.join(get_package_share_directory('openarm_bringup'), 'config',
                        'controllers', 'openarm_bimanual_moveit_controllers.yaml')
    with open(path) as f:
        cfg = yaml.safe_load(f)
    for side in fp.ARM_SIDES:
        arm = cfg[fp.ARM_CONTROLLERS[side]]['ros__parameters']['joints']
        grip = cfg[fp.GRIPPER_CONTROLLERS[side]]['ros__parameters']['joints']
        assert arm == fp.ARM_JOINTS[side]
        assert grip == fp.GRIPPER_JOINTS[side]
        assert set(arm + grip) <= set(rc_joints)


def test_bounded_targets_stay_inside_model_limits(fake_urdf):
    joints = fp.model_joints(fake_urdf)
    for side in fp.ARM_SIDES:
        for name in fp.ARM_JOINTS[side] + fp.GRIPPER_JOINTS[side]:
            lo, hi = joints[name]['lower'], joints[name]['upper']
            target = fp.bounded_target(lo, hi)
            assert lo < target < hi, (name, lo, hi, target)
            assert target != 0.0, name


@pytest.mark.parametrize('value', ['false', 'False', '0', '', 'yes', 'real'])
def test_require_fake_hardware_rejects_non_true(value):
    with pytest.raises(fp.FakeProfileError, match="must be 'true'"):
        fp.require_fake_hardware(value)


def test_require_fake_hardware_accepts_true():
    fp.require_fake_hardware('true')


def test_guard_detects_real_hardware_description():
    """Deliberate fault: a real-hardware expansion must be rejected by the guard.

    The URDF is only generated as text here; nothing loads the plugin.
    """
    real_urdf = xacro.process_file(
        fp.v20_xacro_path(DESCRIPTION_SHARE),
        mappings={'use_fake_hardware': 'false'}).toxml()
    assert 'openarm_hardware/OpenArmHW' in real_urdf
    with pytest.raises(fp.FakeProfileError, match='non-mock hardware plugin'):
        fp.assert_mock_only(real_urdf)


def test_fake_acceleration_overlay_rejects_real_profile():
    base = {
        'joint_limits': {
            'openarm_left_joint1': {
                'has_acceleration_limits': False,
                'max_acceleration': 0.0,
            },
        },
    }
    overlay = {
        'joint_limits': {
            'openarm_left_joint1': {
                'has_acceleration_limits': True,
                'max_acceleration': 20.0,
            },
        },
    }
    with pytest.raises(fp.FakeProfileError, match='real profiles must reject it'):
        fp.merge_fake_acceleration_overlay(base, overlay, profile='real')


def test_fake_acceleration_overlay_merges_only_known_joints():
    base = {
        'joint_limits': {
            'openarm_left_joint1': {
                'has_acceleration_limits': False,
                'max_acceleration': 0.0,
                'max_velocity': 16.754666,
            },
        },
    }
    overlay = {
        'joint_limits': {
            'openarm_left_joint1': {
                'has_acceleration_limits': True,
                'max_acceleration': 20.0,
            },
        },
    }
    merged = fp.merge_fake_acceleration_overlay(base, overlay, profile='fake')
    joint = merged['joint_limits']['openarm_left_joint1']
    assert joint['has_acceleration_limits'] is True
    assert joint['max_acceleration'] == 20.0
    assert joint['max_velocity'] == 16.754666
    assert base['joint_limits']['openarm_left_joint1']['has_acceleration_limits'] is False


def test_fake_acceleration_overlay_rejects_unknown_joint():
    base = {'joint_limits': {'openarm_left_joint1': {}}}
    overlay = {
        'joint_limits': {
            'openarm_left_joint99': {
                'has_acceleration_limits': True,
                'max_acceleration': 20.0,
            },
        },
    }
    with pytest.raises(fp.FakeProfileError, match='unknown joint'):
        fp.merge_fake_acceleration_overlay(base, overlay, profile='fake')


def test_moveit_controller_mapping_matches_upstream_names():
    share = get_package_share_directory('openarm_bimanual_moveit_config')
    path = os.path.join(share, 'config', 'openarm_v2.0', 'moveit_controllers.yaml')
    with open(path) as stream:
        cfg = yaml.safe_load(stream)

    manager = cfg['moveit_simple_controller_manager']
    assert cfg['moveit_controller_manager'] == (
        'moveit_simple_controller_manager/MoveItSimpleControllerManager')

    for side in fp.ARM_SIDES:
        name = fp.ARM_CONTROLLERS[side]
        controller = manager[name]
        assert name in manager['controller_names']
        assert controller['type'] == 'FollowJointTrajectory'
        assert controller['action_ns'] == 'follow_joint_trajectory'
        assert controller['joints'] == fp.ARM_JOINTS[side]

        gripper_name = fp.GRIPPER_CONTROLLERS[side]
        gripper = manager[gripper_name]
        assert gripper_name in manager['controller_names']
        assert gripper['type'] == 'GripperCommand'
        assert gripper['joints'] == fp.GRIPPER_JOINTS[side]
