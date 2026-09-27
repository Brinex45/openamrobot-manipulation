# SPDX-License-Identifier: MIT
# Copyright (c) 2026 OpenAMRobot (Botshare LTD)
"""The fake launch must refuse anything but an explicit use_fake_hardware:=true."""

import pytest

from fake_stack import run_launch_to_exit

LAUNCHES = ['openarm_v2_fake.launch.py', 'openarm_v2_fake_moveit.launch.py']


def _assert_no_nodes_started(output):
    for executable in ('ros2_control_node', 'robot_state_publisher', 'move_group',
                       'spawner'):
        assert f'[{executable}-' not in output, output


@pytest.mark.parametrize('launch_file', LAUNCHES)
def test_rejects_use_fake_hardware_false(launch_file):
    code, output = run_launch_to_exit(launch_file, 'use_fake_hardware:=false')
    assert code not in (None, 0), output
    assert "use_fake_hardware must be 'true', got 'false'" in output, output
    _assert_no_nodes_started(output)


@pytest.mark.parametrize('launch_file', LAUNCHES)
def test_requires_explicit_use_fake_hardware(launch_file):
    code, output = run_launch_to_exit(launch_file)
    assert code not in (None, 0), output
    assert "missing required argument 'use_fake_hardware'" in output, output
    _assert_no_nodes_started(output)
