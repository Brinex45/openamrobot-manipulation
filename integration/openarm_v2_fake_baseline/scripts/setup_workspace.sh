#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 OpenAMRobot (Botshare LTD)
#
# Create an isolated ROS 2 Jazzy workspace with the pinned upstream OpenArm 2.0
# packages and build the fake-only baseline. Fake profile only: the real
# openarm_hardware CAN plugin is excluded from the build.
#
# Usage: setup_workspace.sh [WORKSPACE_DIR]   (default: ~/openarm_v2_fake_ws)
set -euo pipefail

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS="${1:-${HOME}/openarm_v2_fake_ws}"
PY="${PYTHON3:-python3.12}"

if [[ "$("/usr/bin/python3" -c 'import sys; print("%d.%d" % sys.version_info[:2])')" != "3.12" ]]; then
  echo "ERROR: /usr/bin/python3 is not Python 3.12; ROS 2 Jazzy entry points" >&2
  echo "(ros2, xacro, spawner) use it. Fix the host/container Python first." >&2
  exit 1
fi

set +u
# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash
set -u

mkdir -p "${WS}/src"
vcs import --input "${PKG_DIR}/openarm_v2.dev.repos" "${WS}/src"
vcs export --exact "${WS}/src"

# Never build the real hardware plugin (or the meta-package that pulls it in).
touch "${WS}/src/openarm_ros2/openarm_hardware/COLCON_IGNORE"
touch "${WS}/src/openarm_ros2/openarm/COLCON_IGNORE"

ln -sfn "${PKG_DIR}" "${WS}/src/openarm_v2_fake_baseline"

rosdep install -y --rosdistro jazzy --ignore-src --from-paths "${WS}/src"

cd "${WS}"
"${PY}" -m colcon build --symlink-install \
  --packages-up-to openarm_v2_fake_baseline \
  --cmake-args "-DPython3_EXECUTABLE=$(command -v "${PY}")"

echo "Built. Next: source ${WS}/install/setup.bash"
