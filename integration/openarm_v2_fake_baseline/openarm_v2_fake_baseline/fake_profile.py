# SPDX-License-Identifier: MIT
# Copyright (c) 2026 OpenAMRobot (Botshare LTD)
"""Fake-only profile helpers for the pinned OpenArm 2.0 bimanual description.

This module only expands and inspects the upstream enactic/openarm_description
v2.0 model. It never loads a hardware plugin and never opens a CAN device.
It is not a safety mechanism: it only keeps this development profile on
upstream mock hardware.
"""

import os
import xml.etree.ElementTree as ET

MOCK_PLUGIN = 'mock_components/GenericSystem'
REAL_PLUGIN_MARKER = 'openarm_hardware'
EXPECTED_ROBOT_NAME = 'openarm_v20'
V20_XACRO_RELPATH = os.path.join(
    'assets', 'robot', 'openarm_v2.0', 'urdf', 'openarm_v20.urdf.xacro')

ARM_SIDES = ('left', 'right')
ARM_JOINTS = {
    side: [f'openarm_{side}_joint{i}' for i in range(1, 8)] for side in ARM_SIDES
}
GRIPPER_JOINTS = {side: [f'openarm_{side}_finger_joint1'] for side in ARM_SIDES}
ARM_CONTROLLERS = {side: f'{side}_joint_trajectory_controller' for side in ARM_SIDES}
GRIPPER_CONTROLLERS = {side: f'{side}_gripper_controller' for side in ARM_SIDES}
FOLLOW_JOINT_TRAJECTORY = '/{}/follow_joint_trajectory'


class FakeProfileError(RuntimeError):
    """Raised when the fake-only profile would not be fake-only."""


def require_fake_hardware(value):
    """Accept only an explicit 'true'; reject 'false' and anything else."""
    if str(value).strip().lower() != 'true':
        raise FakeProfileError(
            'openarm_v2_fake_baseline is a fake-only profile: '
            f"use_fake_hardware must be 'true', got '{value}'. "
            'Real OpenArm hardware bring-up is out of scope for this package.')


def v20_xacro_path(description_share):
    return os.path.join(description_share, V20_XACRO_RELPATH)


def expand_fake_description(description_share):
    """Expand the pinned v2.0 xacro with use_fake_hardware:=true only.

    No CAN interface mapping is passed on purpose.
    """
    import xacro  # Imported lazily so pure-XML checks do not need ROS.
    doc = xacro.process_file(
        v20_xacro_path(description_share),
        mappings={'use_fake_hardware': 'true'})
    return doc.toprettyxml(indent='  ')


def hardware_plugins(urdf_xml):
    root = ET.fromstring(urdf_xml)
    return [
        (rc.get('name'), (rc.findtext('hardware/plugin') or '').strip())
        for rc in root.findall('ros2_control')
    ]


def assert_mock_only(urdf_xml):
    """Fail unless every ros2_control system uses the upstream mock plugin."""
    root = ET.fromstring(urdf_xml)
    if root.get('name') != EXPECTED_ROBOT_NAME:
        raise FakeProfileError(
            f"expected robot '{EXPECTED_ROBOT_NAME}', got '{root.get('name')}'")
    plugins = hardware_plugins(urdf_xml)
    if not plugins:
        raise FakeProfileError('no ros2_control system found in description')
    bad = [(n, p) for n, p in plugins
           if p != MOCK_PLUGIN or REAL_PLUGIN_MARKER in p]
    if bad:
        raise FakeProfileError(f'non-mock hardware plugin(s) in description: {bad}')
    if 'can_interface' in urdf_xml:
        raise FakeProfileError('description carries a can_interface parameter')
    return plugins


def model_joints(urdf_xml):
    """Return {joint_name: dict(type, lower, upper, mimic)} for the URDF."""
    root = ET.fromstring(urdf_xml)
    joints = {}
    names = [j.get('name') for j in root.findall('joint')]
    if len(names) != len(set(names)):
        raise FakeProfileError('duplicate joint names in description')
    for j in root.findall('joint'):
        limit = j.find('limit')
        mimic = j.find('mimic')
        joints[j.get('name')] = {
            'type': j.get('type'),
            'lower': float(limit.get('lower')) if limit is not None else None,
            'upper': float(limit.get('upper')) if limit is not None else None,
            'mimic': mimic.get('joint') if mimic is not None else None,
        }
    return joints


def ros2_control_joints(urdf_xml):
    root = ET.fromstring(urdf_xml)
    return [j.get('name') for rc in root.findall('ros2_control')
            for j in rc.findall('joint')]


def bounded_target(lower, upper, current=0.0, step=0.2, fraction=0.25):
    """Small in-limit target moving from current towards the joint mid-range."""
    span = upper - lower
    delta = min(step, fraction * span)
    mid = 0.5 * (lower + upper)
    direction = 1.0 if mid >= current else -1.0
    target = current + direction * delta
    margin = 0.05 * span
    return min(max(target, lower + margin), upper - margin)


def merge_fake_acceleration_overlay(joint_limits_config, overlay, profile):
    """Merge synthetic planning limits only for the explicit fake profile.

    The overlay is not a source of validated hardware limits.
    """
    if profile != 'fake':
        raise FakeProfileError(
            "planning placeholder, not hardware: overlay is restricted "
            "to the fake profile; real profiles must reject it")
    if not isinstance(joint_limits_config, dict):
        raise FakeProfileError('invalid MoveIt joint limits configuration')
    if not isinstance(overlay, dict) or not isinstance(
            overlay.get('joint_limits'), dict):
        raise FakeProfileError('invalid acceleration overlay schema')

    merged = {
        key: (dict(value) if isinstance(value, dict) else value)
        for key, value in joint_limits_config.items()
    }
    base_joints = dict(merged.get('joint_limits', {}))
    for name, limits in overlay['joint_limits'].items():
        if name not in base_joints:
            raise FakeProfileError(
                f'overlay references unknown joint: {name}')
        if not isinstance(limits, dict):
            raise FakeProfileError(f'invalid overlay entry for {name}')
        if limits.get('has_acceleration_limits') is not True:
            raise FakeProfileError(
                f'overlay must explicitly enable acceleration limits for {name}')
        value = limits.get('max_acceleration')
        if not isinstance(value, (int, float)) or value <= 0:
            raise FakeProfileError(
                f'overlay acceleration must be positive for {name}')
        base_joints[name] = {**base_joints[name], **limits}

    merged['joint_limits'] = base_joints
    return merged
