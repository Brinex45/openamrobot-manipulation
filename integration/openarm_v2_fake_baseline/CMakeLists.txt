# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.8)
project(openarm_v2_fake_baseline NONE)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

ament_python_install_package(${PROJECT_NAME})
install(DIRECTORY launch DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  find_package(ament_cmake_ros REQUIRED)

  # ament_add_pytest_test only warns when pytest is missing, which would leave
  # an empty suite that colcon reports as "0 failures". Refuse that instead.
  ament_has_pytest(_has_pytest QUIET)
  if(NOT _has_pytest)
    message(FATAL_ERROR
      "pytest not importable by ${Python3_EXECUTABLE}; tests would be silently empty")
  endif()

  # Every test runs on a unique ROS_DOMAIN_ID (domain_coordinator) and with
  # localhost-only discovery so it cannot talk to a live robot network.
  set(_isolation_env ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST)

  # Model/profile checks: xacro expansion only, no ROS graph.
  ament_add_pytest_test(test_fake_profile test/test_fake_profile.py
    ENV ${_isolation_env} TIMEOUT 120)
  # Launch guard: use_fake_hardware must be explicit and 'true'.
  ament_add_ros_isolated_pytest_test(test_launch_guard test/test_launch_guard.py
    ENV ${_isolation_env} TIMEOUT 120)
  # Running fake stack: controllers, endpoints, trajectories, grippers, negatives.
  ament_add_ros_isolated_pytest_test(test_fake_bringup test/test_fake_bringup.py
    ENV ${_isolation_env} TIMEOUT 300)
  # Headless MoveIt planning (reported separately from fake execution).
  ament_add_ros_isolated_pytest_test(test_moveit_planning test/test_moveit_planning.py
    ENV ${_isolation_env} TIMEOUT 300)
endif()

ament_package()
