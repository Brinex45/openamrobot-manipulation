# SPDX-License-Identifier: MIT
# Copyright (c) 2026 OpenAMRobot (Botshare LTD)
"""Test helpers: run the fake launch in a subprocess and probe it with rclpy."""

import os
import signal
import subprocess
import tempfile
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from builtin_interfaces.msg import Duration
from control_msgs.action import FollowJointTrajectory
from controller_manager_msgs.srv import ListControllers, ListHardwareComponents
from controller_manager_msgs.srv import SwitchController
from rcl_interfaces.srv import GetParameters
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectoryPoint

PACKAGE = 'openarm_v2_fake_baseline'


class LaunchedStack:
    """`ros2 launch` in its own process group, always torn down."""

    def __init__(self, launch_file, *args):
        self.log = tempfile.NamedTemporaryFile(
            prefix=f'{launch_file}.', suffix='.log', delete=False)
        self.cmd = ['ros2', 'launch', PACKAGE, launch_file, *args]
        self.proc = subprocess.Popen(
            self.cmd, stdout=self.log, stderr=subprocess.STDOUT,
            start_new_session=True, env=dict(os.environ))

    def output(self):
        if not self.log.closed:
            self.log.flush()
        with open(self.log.name, encoding='utf-8', errors='replace') as f:
            return f.read()

    def stop(self, timeout=20.0):
        if self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGINT)
            try:
                self.proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait(timeout=5.0)
        self.log.close()


def run_launch_to_exit(launch_file, *args, timeout=20.0):
    """Run a launch that is expected to exit by itself; return (code, output)."""
    stack = LaunchedStack(launch_file, *args)
    try:
        stack.proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        pass
    code = stack.proc.poll()
    stack.stop()
    return code, stack.output()


class Probe(Node):

    def __init__(self):
        super().__init__('openarm_v2_fake_baseline_probe')
        self.last_joint_state = None
        self.create_subscription(JointState, '/joint_states', self._on_js, 10)
        self._actions = {}

    def _on_js(self, msg):
        self.last_joint_state = msg

    def spin_for(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.05)

    def _call(self, srv_type, name, request, timeout=10.0):
        client = self.create_client(srv_type, name)
        try:
            if not client.wait_for_service(timeout_sec=timeout):
                raise TimeoutError(f'service {name} not available')
            future = client.call_async(request)
            rclpy.spin_until_future_complete(self, future, timeout_sec=timeout)
            if not future.done():
                raise TimeoutError(f'service {name} did not answer')
            return future.result()
        finally:
            self.destroy_client(client)

    def controller_states(self):
        res = self._call(ListControllers, '/controller_manager/list_controllers',
                         ListControllers.Request())
        return {c.name: c.state for c in res.controller}

    def hardware_components(self):
        res = self._call(ListHardwareComponents,
                         '/controller_manager/list_hardware_components',
                         ListHardwareComponents.Request())
        return {c.name: (c.plugin_name, c.state.label) for c in res.component}

    def switch(self, activate=(), deactivate=()):
        req = SwitchController.Request()
        req.activate_controllers = list(activate)
        req.deactivate_controllers = list(deactivate)
        req.strictness = SwitchController.Request.STRICT
        req.timeout = Duration(sec=5)
        return self._call(SwitchController, '/controller_manager/switch_controller',
                          req).ok

    def robot_description(self):
        req = GetParameters.Request(names=['robot_description'])
        res = self._call(GetParameters, '/robot_state_publisher/get_parameters', req)
        return res.values[0].string_value

    def wait_for_controllers(self, names, timeout=90.0):
        end = time.monotonic() + timeout
        states = {}
        while time.monotonic() < end:
            try:
                states = self.controller_states()
            except TimeoutError:
                states = {}
            if all(states.get(n) == 'active' for n in names):
                return states
            self.spin_for(0.5)
        raise TimeoutError(f'controllers not active in {timeout}s: {states}')

    def action_server_available(self, name, timeout=5.0):
        client = self._action_client(name)
        return client.wait_for_server(timeout_sec=timeout)

    def _action_client(self, name):
        if name not in self._actions:
            self._actions[name] = ActionClient(self, FollowJointTrajectory, name)
        return self._actions[name]

    def joint_positions(self, timeout=5.0):
        self.last_joint_state = None
        end = time.monotonic() + timeout
        while self.last_joint_state is None and time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.05)
        if self.last_joint_state is None:
            raise TimeoutError('no /joint_states received')
        js = self.last_joint_state
        return dict(zip(js.name, js.position))

    def send_trajectory(self, action_name, joints, positions, seconds=2.0,
                        timeout=15.0):
        """Return (accepted, result_or_None). Never raises on rejection."""
        client = self._action_client(action_name)
        if not client.wait_for_server(timeout_sec=5.0):
            raise TimeoutError(f'action server {action_name} not available')
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = list(joints)
        point = JointTrajectoryPoint()
        point.positions = [float(p) for p in positions]
        point.time_from_start = Duration(sec=int(seconds),
                                         nanosec=int((seconds % 1) * 1e9))
        goal.trajectory.points = [point]
        send = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, send, timeout_sec=timeout)
        handle = send.result()
        if handle is None:
            raise TimeoutError(f'no goal response from {action_name}')
        if not handle.accepted:
            return False, None
        result = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result, timeout_sec=timeout)
        if not result.done():
            handle.cancel_goal_async()
            raise TimeoutError(f'no result from {action_name} in {timeout}s')
        return True, result.result().result
