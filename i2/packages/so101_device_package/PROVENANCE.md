# SO-101 Device Package Provenance

## Purpose

This package is a portability and API-validation fixture.
It is not evidence of validated physical-hardware operation.

## Upstream source

- Repository: https://github.com/adoodevv/so101_ros2
- Pinned revision: 0305e03ab54e64aae9263fcbf339622e654012f3

## Copied MoveIt configuration

The following files are copied from
`so101_moveit_config/config/so101/` at the pinned revision:

- `so101.srdf`
- `kinematics.yaml`
- `joint_limits.yaml`

## Limitations

- The local robot-description and ros2_control configuration files
  remain placeholders until the full description dependency tree
  and controller configuration are verified.
- The local simulation configuration remains a placeholder.
- Configuration copying does not establish successful MoveIt planning,
  trajectory execution, or physical-hardware compatibility.
- No force/contact sensing, object detection, or compliant-control
  capability is claimed.
- Gripper commands remain unvalidated against the common I1 API.

## Additional copied configuration

- `ros2_control/controllers.yaml` is copied from
  `so101_moveit_config/config/so101/ros2_controllers.yaml`.
- `moveit/moveit_controllers.yaml` is copied from
  `so101_moveit_config/config/so101/moveit_controllers.yaml`.
- `UPSTREAM_LICENSE` preserves the upstream description package license.

## Integration limitations

- The upstream launch scripts have not been adapted or validated for
  this Device Package layout.
- The upstream entry Xacro depends on the `so101_description` ROS package,
  other Xacro files, and mesh resources.
- Copying configuration files does not establish a working ROS launch,
  controller activation, simulation, or physical-hardware operation.

## Joint inventory

`description/upstream_joint_inventory.yaml` records the six joint names
extracted from `so101_description/urdf/so101_robot.urdf.xacro` at the
pinned upstream revision.

The inventory supports a CI consistency test. It does not validate the
full robot description, Xacro expansion, mesh resources, or launchability.
