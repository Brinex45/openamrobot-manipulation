# openamrobot-manipulation

Shared arm-integration framework for the OpenAMRobot ecosystem. It provides the common manipulation layer used by OpenAMRobot mobile-manipulation systems while keeping vendor-specific arm integration behind a stable Device Package boundary.

> **Status:** OpenAMRobot 2.0 development / integration scaffold

The OpenAMRobot 2.0 cycle is focused on integrating a real bimanual manipulation stack around **OpenArm 2.0** while preserving an arm-agnostic common API. **LeRobot SO-101** is a secondary portability/API-validation fixture only.

## What lives here

- **Manipulation server:** one arm-agnostic API for named poses, plan/preview/execute, stop, gripper control, Cartesian motion, contact-aware primitives, readiness, recovery and capability discovery.
- **Device Package format:** a self-contained integration boundary for an arm/device: description, controllers, MoveIt configuration, capability manifest, diagnostics, UI/Blockly integration and LeRobot mapping.
- **Reference Device Packages:** **OpenArm 2.0** as the primary physical manipulation path; **SO-101** as portability/API-validation fixture.
- **Normalized execution semantics:** per-action timeout, typed failure results, constrained placement, bounded abort/retract behavior and controller-ownership handover.

Software and common integration logic live here. Physical upper-body structure, mast and arm mounting belong in `openamr-upperbody-hw`; upper-body hardware-specific integration belongs in the corresponding `openamr-upperbody-*` repositories.

## OpenAMRobot 2.0 scope

1. Implement a small, stable manipulation API over **MoveIt 2** and `ros2_control` / supported vendor interfaces.
2. Integrate **OpenArm 2.0** as the primary physical Device Package using upstream/vendor software wherever practical rather than reimplementing drivers, kinematics or planning.
3. Define the Device Package contract from the real OpenArm integration, then validate portability on **SO-101** without changing the common API.
4. Provide capability discovery so UI and higher-level applications do not hard-code vendor-specific arm behavior.
5. Provide explicit readiness and controller-ownership states. In OpenAMRobot 2.0, the mobile base and active arm joints/end effectors do **not** move at the same time.
6. Support the Embodied-AI workflow through a clean mapping to the project data/training layer, with **LeRobot** as the reference dataset and imitation-learning ecosystem.

## Integration principle

**Integration over invention.** Reuse maintained upstream packages and vendor-supported components first. OpenAMRobot-specific code should be limited to stable common interfaces, Device Packages, normalized capabilities/failures, readiness/ownership semantics, project-specific validation and thin adapters.

For deterministic manipulation, use **MoveIt 2** for robot model, kinematics, planning scene, collision checking, reachability, named poses and conventional trajectories. Learned policies may execute bounded task skills through declared interfaces, but do not replace the deterministic safety/control boundary.

## Contracts owned elsewhere

- Shared ROS 2 messages, services, actions and schemas live in `openamrobot-interfaces`.
- Device Package UI panels, Blockly blocks and operator surfaces are consumed by `openamrobot-ui`.
- Exact compatible component versions belong in `openamrobot-manifest` / release metadata.

## Design rules

- Arm-agnostic common API; vendor-specific code stays behind a Device Package.
- **OpenArm 2.0 is the primary physical arm for the current release cycle.**
- **SO-101 is a portability/API-validation fixture.**
- No vendor SDK calls from the UI.
- No custom replacement for MoveIt planning where existing MoveIt functionality satisfies the requirement.
- Base motion and active arm motion are mutually exclusive; readiness must be explicit and testable.
- Every material action has a timeout and a normalized result/failure state.
- Safety authority remains deterministic and independent of AI/LLM output.
- Simulation and learned-policy paths must use the same public platform contracts as physical execution wherever practical.

## Validation direction

The OpenArm 2.0 Device Package should be validated progressively through:

1. schema/static checks;
2. unit and contract tests;
3. fake-hardware / simulation bring-up;
4. MoveIt planning and named-pose execution;
5. capability discovery and unsupported-capability rejection;
6. controller-ownership and base/manipulation readiness tests;
7. supervised physical-arm integration and acceptance evidence.

A second Device Package should demonstrate that portability does not require edits to common manipulation code. If core files must be changed merely to add the second arm, treat that as a defect in the Device Package boundary rather than a vendor-specific workaround.

Part of the OpenAMRobot ecosystem: https://github.com/openAMRobot

## Ownership, licensing, and contributions

OpenAMRobot is a project initiated, operated, and controlled by **Botshare LTD** (Cyprus Company ID HE479056). Botshare LTD owns the transferable economic rights in original OpenAMRobot material created by or validly assigned to it. Third-party material remains subject to its respective ownership, licences, and notices.

Original OpenAMRobot software and firmware are licensed under MIT, documentation under CC BY 4.0, and hardware design source under CERN-OHL-P-2.0, as mapped in [`LICENSING.md`](LICENSING.md). Public distribution grants the permissions stated in the applicable licence; it does not transfer ownership of underlying copyright, trademarks, patents, or other intellectual property.

Accepted external contributions require DCO sign-off and an applicable Individual or Corporate Contributor Agreement. See the organization [IP Policy](https://github.com/openAMRobot/.github/blob/main/IP_POLICY.md), [Contribution Guide](https://github.com/openAMRobot/.github/blob/main/CONTRIBUTING.md), and [Contributor Agreement Process](https://github.com/openAMRobot/.github/blob/main/CLA.md).
