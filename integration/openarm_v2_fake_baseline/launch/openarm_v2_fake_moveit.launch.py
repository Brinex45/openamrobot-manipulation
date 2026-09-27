# SPDX-License-Identifier: MIT
# Copyright (c) 2026 OpenAMRobot (Botshare LTD)
"""Headless move_group on top of the fake-only OpenArm 2.0 bring-up.

Uses the pinned upstream openarm_bimanual_moveit_config v2.0 files unchanged
(SRDF, kinematics, joint limits, controllers) with the default OMPL pipeline,
the same way upstream demo.launch.py does, but without RViz.

Provenance: the MoveItConfigsBuilder call chain below follows upstream
enactic/openarm_ros2 openarm_bimanual_moveit_config/launch/demo.launch.py
(Apache-2.0, Copyright 2025 Enactic, Inc.) at the pinned commit.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription,
                            OpaqueFunction, SetEnvironmentVariable)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from moveit_configs_utils import MoveItConfigsBuilder

from openarm_v2_fake_baseline import fake_profile

CONFIG_DIR = 'config/openarm_v2.0'


def _move_group(context):
    fake_profile.require_fake_hardware(
        LaunchConfiguration('use_fake_hardware').perform(context))

    description_share = get_package_share_directory('openarm_description')
    moveit_config = (
        MoveItConfigsBuilder('openarm', package_name='openarm_bimanual_moveit_config')
        .robot_description(
            file_path=fake_profile.v20_xacro_path(description_share),
            mappings={'use_fake_hardware': 'true'})
        .robot_description_semantic(file_path=f'{CONFIG_DIR}/openarm_bimanual.srdf')
        .robot_description_kinematics(file_path=f'{CONFIG_DIR}/kinematics.yaml')
        .joint_limits(file_path=f'{CONFIG_DIR}/joint_limits.yaml')
        .trajectory_execution(file_path=f'{CONFIG_DIR}/moveit_controllers.yaml')
        .planning_pipelines(pipelines=['ompl'], default_planning_pipeline='ompl')
        .to_moveit_configs()
    )
    fake_profile.assert_mock_only(
        moveit_config.robot_description['robot_description'])

    return [Node(
        package='moveit_ros_move_group',
        executable='move_group',
        output='screen',
        parameters=[moveit_config.to_dict()],
    )]


def generate_launch_description():
    fake_launch = os.path.join(
        get_package_share_directory('openarm_v2_fake_baseline'),
        'launch', 'openarm_v2_fake.launch.py')
    return LaunchDescription([
        DeclareLaunchArgument(
            'use_fake_hardware',
            description="Required. Must be 'true'; any other value is rejected."),
        SetEnvironmentVariable('ROS_AUTOMATIC_DISCOVERY_RANGE', 'LOCALHOST'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(fake_launch),
            launch_arguments={
                'use_fake_hardware': LaunchConfiguration('use_fake_hardware'),
            }.items()),
        OpaqueFunction(function=_move_group),
    ])
