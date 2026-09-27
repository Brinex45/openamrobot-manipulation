# SPDX-License-Identifier: MIT
# Copyright (c) 2026 OpenAMRobot (Botshare LTD)
"""Headless, fake-only OpenArm 2.0 bimanual bring-up.

Wraps the pinned upstream enactic/openarm_description v2.0 model and the
enactic/openarm_ros2 openarm_bringup controller configuration. Upstream
openarm.bimanual.launch.py always starts RViz and passes CAN interface names;
this wrapper does neither.

use_fake_hardware has no default: it must be passed explicitly and must be
'true'. Any other value aborts before a node is started.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from openarm_v2_fake_baseline import fake_profile

CONTROLLER_FILES = (
    'openarm_bimanual_moveit_controllers.yaml',
    'openarm_bimanual_controllers.yaml',
)


def _bring_up(context):
    fake_profile.require_fake_hardware(
        LaunchConfiguration('use_fake_hardware').perform(context))

    robot_description = fake_profile.expand_fake_description(
        get_package_share_directory('openarm_description'))
    fake_profile.assert_mock_only(robot_description)

    controllers_file = os.path.join(
        get_package_share_directory('openarm_bringup'), 'config', 'controllers',
        LaunchConfiguration('controllers_file').perform(context))
    description_param = {'robot_description': robot_description}

    arm_and_gripper_controllers = [
        fake_profile.ARM_CONTROLLERS['left'],
        fake_profile.ARM_CONTROLLERS['right'],
        fake_profile.GRIPPER_CONTROLLERS['left'],
        fake_profile.GRIPPER_CONTROLLERS['right'],
    ]

    return [
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            output='screen',
            parameters=[description_param],
        ),
        Node(
            package='controller_manager',
            executable='ros2_control_node',
            output='screen',
            parameters=[description_param, controllers_file],
        ),
        Node(
            package='controller_manager',
            executable='spawner',
            output='screen',
            arguments=['joint_state_broadcaster',
                       '--controller-manager', '/controller_manager',
                       '--controller-manager-timeout', '60'],
        ),
        Node(
            package='controller_manager',
            executable='spawner',
            output='screen',
            arguments=arm_and_gripper_controllers + [
                '--controller-manager', '/controller_manager',
                '--controller-manager-timeout', '60'],
        ),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'use_fake_hardware',
            description="Required. Must be 'true'; any other value is rejected."),
        DeclareLaunchArgument(
            'controllers_file',
            default_value=CONTROLLER_FILES[0],
            choices=list(CONTROLLER_FILES),
            description='Upstream openarm_bringup controller file to load.'),
        # Keep DDS discovery on this host so the fake stack cannot reach a
        # live robot network.
        SetEnvironmentVariable('ROS_AUTOMATIC_DISCOVERY_RANGE', 'LOCALHOST'),
        OpaqueFunction(function=_bring_up),
    ])
