"""Run: python -m unittest discover -s tests -v   (pytest also works)

Every rejection test copies a real package to a temp dir, applies ONE mutation,
and asserts the shared validator reports the expected error.
"""
import copy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "validator"))
import validate_package as vp  # noqa: E402

PKGS = {
    "so101": ROOT / "packages" / "so101_device_package",
    "openarm": ROOT / "packages" / "openarm_v2_device_package",
}


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def copy_pkg(self, key):
        dst = Path(self._tmp.name) / key
        shutil.copytree(PKGS[key], dst)
        return dst

    def mutate(self, key, manifest_fn=None, caps_fn=None):
        root = self.copy_pkg(key)
        if manifest_fn:
            p = root / "device_package.yaml"
            m = yaml.safe_load(p.read_text())
            manifest_fn(m)
            p.write_text(yaml.safe_dump(m, sort_keys=False))
        if caps_fn:
            p = root / "capabilities" / "capabilities.yaml"
            c = yaml.safe_load(p.read_text())
            caps_fn(c["capabilities"])
            p.write_text(yaml.safe_dump(c, sort_keys=False))
        return vp.validate_package(root)

    def assertRejects(self, rep, fragment):
        self.assertFalse(rep.valid, "expected INVALID but package validated")
        self.assertTrue(any(fragment in e for e in rep.errors),
                        f"no error containing {fragment!r}; got:\n" + "\n".join(rep.errors))


def validated(reason_ref="test:e2e", kind="SIM_FAKE_E2E"):
    return {"state": "VALIDATED", "evidence": [{"kind": kind, "ref": reason_ref}]}


# ------------------------------------------------------------------ positive
class TestBothPackages(Base):
    def test_both_pass_same_validator_and_schema(self):
        reps = {k: vp.validate_package(v) for k, v in PKGS.items()}
        for k, r in reps.items():
            self.assertTrue(r.valid, f"{k}: {r.errors}")
        self.assertEqual(reps["so101"].schema_hash, reps["openarm"].schema_hash)

    def test_pending_is_reported_not_validated(self):
        for k, v in PKGS.items():
            r = vp.validate_package(v)
            self.assertTrue(r.pending, k)
            self.assertFalse(r.freeze_ready, k)

    def test_strict_blocks_freeze_while_pending(self):
        for k, v in PKGS.items():
            self.assertEqual(vp.validate_package(v, strict=True).exit_code, 2, k)

    def test_no_action_is_supported_without_e2e_validation(self):
        for k, v in PKGS.items():
            caps = yaml.safe_load((v / "capabilities/capabilities.yaml").read_text())
            self.assertEqual(vp.derive_supported_actions(caps), vp.COMMON_SERVER_ACTIONS, k)

    def test_so101_cartesian_stays_non_supported_with_config_evidence(self):
        caps = yaml.safe_load((PKGS["so101"] / "capabilities/capabilities.yaml").read_text())
        c = caps["capabilities"]["actions"]["cartesian_motion"]
        self.assertNotEqual(c["status"], "supported")
        self.assertEqual(c["validation"]["state"], "PENDING")
        self.assertEqual({e["kind"] for e in c["validation"]["evidence"]}, {"CONFIG_ONLY"})

    def test_launch_identifier_is_not_checked_as_a_path(self):
        m = yaml.safe_load((PKGS["openarm"] / "device_package.yaml").read_text())
        self.assertEqual(m["driver"]["launch"], "openarm_driver")
        self.assertFalse((PKGS["openarm"] / "driver" / "openarm_driver").exists())
        self.assertTrue(vp.validate_package(PKGS["openarm"]).valid)

    def test_experimental_not_in_supported_actions(self):
        def f(c):
            c["actions"]["plan"] = {"status": "experimental", "reason": "unstable"}
        root = self.copy_pkg("so101")
        p = root / "capabilities/capabilities.yaml"
        c = yaml.safe_load(p.read_text())
        f(c["capabilities"])
        self.assertNotIn("plan", vp.derive_supported_actions(c))

    def test_validated_supported_is_listed(self):
        def f(c):
            c["actions"]["plan"] = {"status": "supported", "validation": validated()}
        rep = self.mutate("so101", caps_fn=f)
        self.assertTrue(rep.valid, rep.errors)

    def test_status_report_vocabulary(self):
        ok = {"device_health": "OK", "driver_status": "DEGRADED", "connection_status": "CONNECTED",
              "fault_reporting": [{"source": "j1", "severity": "WARNING", "code": "E1"}], "device_ready": True}
        self.assertEqual(vp.validate_status_report(ok), [])
        self.assertTrue(vp.validate_status_report({"device_health": "healthy"}))
        self.assertTrue(vp.validate_status_report({"connection_status": "OK"}))
        self.assertTrue(vp.validate_status_report({"device_ready": "yes"}))


# ------------------------------------------------------------- reject: manifest
class TestManifestRejections(Base):
    def test_missing_required_section(self):
        self.assertRejects(self.mutate("so101", lambda m: m.pop("gripper")), "'gripper' is a required property")

    def test_missing_maintainer(self):
        self.assertRejects(self.mutate("so101", lambda m: m["device"].pop("maintainer")), "maintainer")

    def test_supported_actions_in_manifest(self):
        self.assertRejects(self.mutate("so101", lambda m: m.update(supported_actions=["plan"])), "supported_actions")

    def test_supported_actions_in_capabilities(self):
        self.assertRejects(self.mutate("so101", caps_fn=lambda c: c.update(supported_actions=["plan"])), "supported_actions")

    def test_unknown_top_level_key(self):
        self.assertRejects(self.mutate("so101", lambda m: m.update(extra=1)), "Additional properties are not allowed")

    def test_version_major_mismatch(self):
        self.assertRejects(self.mutate("so101", lambda m: m.update(schema_version="1.0")), "incompatible")

    def test_version_minor_newer(self):
        self.assertRejects(self.mutate("so101", lambda m: m.update(schema_version="0.6")), "expected 0.5")

    def test_i1_major_mismatch(self):
        self.assertRejects(self.mutate("so101", lambda m: m.update(i1_api_version="2.0")), "I1 api version incompatible")

    def test_version_error_names_expected_and_found(self):
        rep = self.mutate("so101", lambda m: m.update(i1_api_version="2.0"))
        self.assertTrue(any("expected 1.0" in e and "found 2.0" in e for e in rep.errors))

    def test_bad_uuid(self):
        def f(m):
            m["device"]["manipulators"][0]["manipulator_id"] = "not-a-uuid"
        self.assertRejects(self.mutate("so101", f), "manipulator_id")

    def test_bad_group_id(self):
        def f(m):
            m["device"]["groups"][0]["group_id"] = "MIDDLE"
        self.assertRejects(self.mutate("openarm", f), "group_id")

    def test_bimanual_needs_two(self):
        def f(m):
            g = m["device"]["groups"][2]
            g["members"] = g["members"][:1]
        self.assertRejects(self.mutate("openarm", f), "BIMANUAL must contain exactly two")

    def test_duplicate_group_members(self):
        def f(m):
            g = m["device"]["groups"][2]
            g["members"] = [g["members"][0], g["members"][0]]
        self.assertRejects(self.mutate("openarm", f), "duplicate members")

    def test_group_unknown_member(self):
        def f(m):
            m["device"]["groups"][0]["members"] = ["11111111-1111-4111-8111-111111111111"]
        self.assertRejects(self.mutate("openarm", f), "not a declared manipulator")

    def test_workspace_type_unknown(self):
        def f(m):
            m["device"]["workspace_envelope"] = {"type": "UNKNOWN"}
        self.assertRejects(self.mutate("so101", f), "workspace_envelope")

    def test_bounding_box_missing_corner(self):
        def f(m):
            m["device"]["workspace_envelope"] = {"type": "BOUNDING_BOX", "min_corner": [0, 0, 0]}
        self.assertRejects(self.mutate("so101", f), "workspace_envelope")

    def test_configuration_must_be_structured(self):
        def f(m):
            m["device"]["configuration"] = "fixed, base_link"
        self.assertRejects(self.mutate("so101", f), "configuration")

    def test_configuration_unknown_mounting(self):
        def f(m):
            m["device"]["configuration"]["mounting"] = "hovering"
        self.assertRejects(self.mutate("so101", f), "mounting")


# ------------------------------------------------------------------ reject: paths
class TestPathRejections(Base):
    def test_absolute_path(self):
        def f(m):
            m["driver"]["config"] = "/etc/driver.yaml"
        self.assertRejects(self.mutate("so101", f), "absolute path")

    def test_windows_absolute_path(self):
        def f(m):
            m["driver"]["config"] = "C:\\robots\\driver.yaml"
        self.assertRejects(self.mutate("so101", f), "absolute path")

    def test_path_escape(self):
        def f(m):
            m["driver"]["config"] = "../outside.yaml"
        self.assertRejects(self.mutate("so101", f), "escapes the package root")

    def test_missing_file(self):
        def f(m):
            m["moveit"]["kinematics"] = "moveit/nope.yaml"
        self.assertRejects(self.mutate("so101", f), "does not exist")

    def test_pending_is_not_a_valid_path(self):
        def f(m):
            m["driver"]["config"] = "PENDING"
        self.assertRejects(self.mutate("so101", f), "does not exist")


# --------------------------------------------------------------- reject: joints
class TestJointRejections(Base):
    def test_arm_dof_mismatch(self):
        def f(m):
            m["device"]["manipulators"][0]["arm_dof"] = 6
        self.assertRejects(self.mutate("so101", f), "arm_dof is 6")

    def test_joint_in_two_manipulators(self):
        def f(m):
            ids = [x["manipulator_id"] for x in m["device"]["manipulators"]]
            m["ros2_control"]["manipulator_joints"][ids[1]][0] = m["ros2_control"]["manipulator_joints"][ids[0]][0]
        self.assertRejects(self.mutate("openarm", f), "more than one manipulator")

    def test_unclassified_joint(self):
        def f(m):
            m["ros2_control"]["joints"].append("mystery_joint")
        self.assertRejects(self.mutate("so101", f), "neither an arm joint nor a gripper joint")

    def test_gripper_joint_inside_arm_list(self):
        def f(m):
            mid = m["device"]["manipulators"][0]["manipulator_id"]
            m["ros2_control"]["manipulator_joints"][mid][-1] = "gripper"
            m["device"]["manipulators"][0]["arm_dof"] = 5
        self.assertRejects(self.mutate("so101", f), "must not appear in manipulator_joints")

    def test_arm_joint_missing_from_joints(self):
        def f(m):
            m["ros2_control"]["joints"].remove("wrist_roll")
        self.assertRejects(self.mutate("so101", f), "missing from ros2_control.joints")

    def test_gripper_joint_count_mismatch(self):
        def f(m):
            m["gripper"]["joint_count"] = 2
        self.assertRejects(self.mutate("so101", f), "joint_count")

    def test_no_gripper_but_gripper_joints(self):
        def f(m):
            m["gripper"] = {"has_gripper": False}
        self.assertRejects(self.mutate("so101", f), "gripper_joints must be empty or absent")

    def test_no_gripper_other_fields_must_be_omitted(self):
        def f(m):
            m["gripper"]["has_gripper"] = False
        self.assertRejects(self.mutate("so101", f), "other gripper fields must be omitted")

    def test_unknown_interface_name(self):
        def f(m):
            m["ros2_control"]["command_interfaces"] = ["position", "torque"]
        self.assertRejects(self.mutate("so101", f), "command_interfaces")


# ------------------------------------------------------------- reject: gripper
class TestGripperRejections(Base):
    def test_unknown_gripper_command(self):
        def f(m):
            m["gripper"]["supported_commands"] = ["OPEN", "UNKNOWN"]
        self.assertRejects(self.mutate("so101", f), "supported_commands")

    def test_lowercase_gripper_command(self):
        def f(m):
            m["gripper"]["supported_commands"] = ["open"]
        self.assertRejects(self.mutate("so101", f), "supported_commands")

    def test_gripper_command_supported_without_gripper(self):
        def f(m):
            m["gripper"] = {"has_gripper": False}
            m["ros2_control"].pop("gripper_joints")
            m["ros2_control"]["joints"].remove("gripper")
            m["moveit"].pop("end_effectors")
        def g(c):
            c["actions"]["gripper_command"] = {"status": "supported", "validation": validated()}
        rep = self.mutate("so101", f, g)
        self.assertRejects(rep, "gripper_command")

    def test_no_gripper_requires_unsupported_declaration(self):
        def f(m):
            m["gripper"] = {"has_gripper": False}
            m["ros2_control"].pop("gripper_joints")
            m["ros2_control"]["joints"].remove("gripper")
            m["moveit"].pop("end_effectors")
        # gripper_command is still "planned" -> must be explicitly unsupported
        self.assertRejects(self.mutate("so101", f), "gripper_command must be declared unsupported")

    def test_no_gripper_with_unsupported_declaration_is_valid(self):
        def f(m):
            m["gripper"] = {"has_gripper": False}
            m["pending"] = [p for p in m["pending"] if not p["path"].startswith("/gripper")]
            m["ros2_control"].pop("gripper_joints")
            m["ros2_control"]["joints"].remove("gripper")
            m["moveit"].pop("end_effectors")
        def g(c):
            c["actions"]["gripper_command"] = {"status": "unsupported", "reason": "no gripper"}
        rep = self.mutate("so101", f, g)
        self.assertTrue(rep.valid, rep.errors)

    def test_gripper_required_fields(self):
        def f(m):
            m["gripper"].pop("gripper_id")
        self.assertRejects(self.mutate("so101", f), "gripper.gripper_id is required")


# ------------------------------------------------------ reject: capabilities
class TestCapabilityRejections(Base):
    def test_typo_action_name(self):
        def g(c):
            c["actions"]["cartesian_moton"] = c["actions"].pop("cartesian_motion")
        self.assertRejects(self.mutate("so101", caps_fn=g), "cartesian_moton")

    def test_missing_canonical_action(self):
        def g(c):
            c["actions"].pop("compliant_hold")
        self.assertRejects(self.mutate("so101", caps_fn=g), "compliant_hold")

    def test_unsupported_requires_reason(self):
        def g(c):
            c["actions"]["move_until_contact"] = {"status": "unsupported"}
        self.assertRejects(self.mutate("so101", caps_fn=g), "requires a reason")

    def test_planned_requires_reason(self):
        def g(c):
            c["actions"]["plan"] = {"status": "planned"}
        self.assertRejects(self.mutate("so101", caps_fn=g), "requires a reason")

    def test_shorthand_unsupported_has_no_reason(self):
        def g(c):
            c["actions"]["compliant_hold"] = "unsupported"
        self.assertRejects(self.mutate("so101", caps_fn=g), "requires a reason")

    def test_bad_status(self):
        def g(c):
            c["actions"]["plan"] = {"status": "maybe", "reason": "x"}
        self.assertRejects(self.mutate("so101", caps_fn=g), "is not valid under any of the given schemas")

    def test_ft_invalid_enum(self):
        def g(c):
            c["force_torque_sensing"] = "SOME_FT"
        self.assertRejects(self.mutate("so101", caps_fn=g), "force_torque_sensing")

    # --- supported needs end-to-end evidence (the Cartesian point) ---------
    def test_supported_shorthand_has_no_evidence(self):
        def g(c):
            c["actions"]["plan"] = "supported"
        self.assertRejects(self.mutate("so101", caps_fn=g), "requires validation.state VALIDATED")

    def test_supported_with_pending_validation(self):
        def g(c):
            c["actions"]["plan"] = {"status": "supported", "validation": {"state": "PENDING"}}
        self.assertRejects(self.mutate("so101", caps_fn=g), "requires validation.state VALIDATED")

    def test_cartesian_supported_on_planning_group_alone_is_rejected(self):
        def g(c):
            c["actions"]["cartesian_motion"] = {
                "status": "supported",
                "validation": validated("sim/fake fixture: MoveIt planning group 'arm'", kind="CONFIG_ONLY"),
            }
        self.assertRejects(self.mutate("so101", caps_fn=g), "CONFIG_ONLY is not enough")

    def test_cartesian_supported_with_e2e_evidence_is_accepted(self):
        def g(c):
            c["actions"]["cartesian_motion"] = {"status": "supported", "validation": validated()}
        rep = self.mutate("so101", caps_fn=g)
        self.assertTrue(rep.valid, rep.errors)

    def test_cartesian_needs_arm_group_for_every_manipulator(self):
        def f(m):
            m["moveit"]["planning_groups"] = [g for g in m["moveit"]["planning_groups"] if g["name"] != "arm"]
        def g(c):
            c["actions"]["cartesian_motion"] = {"status": "supported", "validation": validated()}
        self.assertRejects(self.mutate("so101", f, g), "requires an ARM MoveIt planning group")

    def test_cartesian_end_effector_group_does_not_count_as_arm_group(self):
        def f(m):
            for grp in m["moveit"]["planning_groups"]:
                if grp["name"] == "arm":
                    grp["role"] = "END_EFFECTOR"
        def g(c):
            c["actions"]["cartesian_motion"] = {"status": "supported", "validation": validated()}
        self.assertRejects(self.mutate("so101", f, g), "requires an ARM MoveIt planning group")

    # --- gates --------------------------------------------------------------
    def test_contact_supported_with_ft_unknown(self):
        def g(c):
            c["actions"]["move_until_contact"] = {"status": "supported", "validation": validated()}
        self.assertRejects(self.mutate("so101", caps_fn=g), "force_torque_sensing")

    def test_compliant_hold_supported_with_ft_unknown(self):
        def g(c):
            c["actions"]["compliant_hold"] = {"status": "supported", "validation": validated()}
        self.assertRejects(self.mutate("so101", caps_fn=g), "force_torque_sensing")

    def test_contact_supported_with_ft_pending(self):
        def g(c):
            c["actions"]["move_until_contact"] = {"status": "supported", "validation": validated()}
        self.assertRejects(self.mutate("openarm", caps_fn=g), "force_torque_sensing")

    def test_contact_supported_with_ft_estimate_is_accepted(self):
        def g(c):
            c["force_torque_sensing"] = "ACTUATOR_ESTIMATE"
            c["actions"]["move_until_contact"] = {"status": "supported", "validation": validated()}
        rep = self.mutate("openarm", caps_fn=g)
        self.assertTrue(rep.valid, rep.errors)

    def test_execute_supported_requires_plan_supported(self):
        def g(c):
            c["actions"]["execute"] = {"status": "supported", "validation": validated()}
        self.assertRejects(self.mutate("so101", caps_fn=g), "requires plan")

    def test_plan_preview_supported_requires_plan_supported(self):
        def g(c):
            c["actions"]["plan_preview"] = {"status": "supported", "validation": validated()}
        self.assertRejects(self.mutate("so101", caps_fn=g), "requires plan")

    def test_named_pose_move_requires_a_named_pose(self):
        def g(c):
            c["actions"]["named_pose_move"] = {"status": "supported", "validation": validated()}
        self.assertRejects(self.mutate("openarm", caps_fn=g), "named pose")

    # --- abort modes --------------------------------------------------------
    def test_abort_modes_must_include_stop_only(self):
        def g(c):
            c["abort_modes"] = ["RETRACT"]
        self.assertRejects(self.mutate("so101", caps_fn=g), "must include STOP_ONLY")

    def test_abort_mode_unknown_value(self):
        def g(c):
            c["abort_modes"] = ["STOP_ONLY", "UNKNOWN"]
        self.assertRejects(self.mutate("so101", caps_fn=g), "abort_modes")

    def test_stow_requires_stow_pose(self):
        def g(c):
            c["abort_modes"] = ["STOP_ONLY", "STOW"]
        self.assertRejects(self.mutate("so101", caps_fn=g), "STOW requires a stow_pose")

    def test_stow_with_stow_pose_is_accepted(self):
        def f(m):
            mid = m["device"]["manipulators"][0]["manipulator_id"]
            m["moveit"]["stow_pose"] = {mid: "home"}
        def g(c):
            c["abort_modes"] = ["STOP_ONLY", "STOW"]
        rep = self.mutate("so101", f, g)
        self.assertTrue(rep.valid, rep.errors)

    def test_stow_pose_must_be_a_named_pose(self):
        def f(m):
            mid = m["device"]["manipulators"][0]["manipulator_id"]
            m["moveit"]["stow_pose"] = {mid: "nonexistent"}
        self.assertRejects(self.mutate("so101", f), "not in named_poses")

    def test_abort_selector_unknown_key(self):
        def g(c):
            c["abort_modes_by_selector"] = {"LEFT": ["STOP_ONLY"]}
        self.assertRejects(self.mutate("so101", caps_fn=g), "unknown selector")

    def test_abort_selector_must_include_stop_only(self):
        def g(c):
            c["abort_modes_by_selector"] = {"LEFT": ["RETRACT"]}
        self.assertRejects(self.mutate("openarm", caps_fn=g), "must include STOP_ONLY")


# ------------------------------------------------------- reject: sim / pending
class TestSimAndPendingRejections(Base):
    def test_sim_fake_hardware_mismatch(self):
        def f(m):
            m["ros2_control"]["fake_hardware"] = False
        self.assertRejects(self.mutate("so101", f), "does not match")

    def test_sim_fake_false_needs_hardware_mode(self):
        def f(m):
            m["simulation"]["fake_hardware"] = False
        self.assertRejects(self.mutate("so101", f), "hardware_mode")

    def test_sim_unsupported_needs_no_sim_fields(self):
        def f(m):
            m["simulation"] = {"supported": False}
        rep = self.mutate("so101", f)
        self.assertTrue(rep.valid, rep.errors)

    def test_diagnostics_must_report_all_fields(self):
        def f(m):
            m["diagnostics"]["reports"].remove("device_ready")
        self.assertRejects(self.mutate("so101", f), "device_ready")

    def test_pending_registry_path_must_exist(self):
        def f(m):
            m["pending"].append({"path": "/gripper/no_such_field", "reason": "x"})
        self.assertRejects(self.mutate("so101", f), "does not exist in the manifest")

    def test_pending_sentinel_not_allowed_in_identity_fields(self):
        def f(m):
            m["device"]["version"] = "PENDING"
        self.assertRejects(self.mutate("so101", f), "version")

    def test_pending_sentinel_not_allowed_for_uuid(self):
        def f(m):
            m["device"]["manipulators"][0]["manipulator_id"] = "PENDING"
        self.assertRejects(self.mutate("so101", f), "manipulator_id")

    def test_resolved_package_is_freeze_ready(self):
        """A fully resolved SO-101 (no PENDING anywhere) passes --strict."""
        def f(m):
            def fix(node):
                if isinstance(node, dict):
                    return {k: fix(v) for k, v in node.items()}
                if isinstance(node, list):
                    return [fix(v) for v in node]
                return "resolved" if node == "PENDING" else node
            fixed = fix(m)
            m.clear()
            m.update(fixed)
            m["device"]["configuration"]["mounting"] = "fixed"
            m["device"]["workspace_envelope"] = {"type": "REACH_RADIUS", "reach_radius": 0.4}
            m["gripper"].update(command_interfaces=["position"], state_interfaces=["position"],
                                reports_effort=False, contact_detection=False, object_detection=False)
            m.pop("pending")

        def g(c):
            for a in vp.ACTIONS:
                if c["actions"][a]["status"] == "planned":
                    c["actions"][a] = {"status": "unsupported", "reason": "descoped for this test"}
        root = self.copy_pkg("so101")
        p = root / "device_package.yaml"
        m = yaml.safe_load(p.read_text()); f(m); p.write_text(yaml.safe_dump(m, sort_keys=False))
        cp = root / "capabilities/capabilities.yaml"
        c = yaml.safe_load(cp.read_text()); g(c["capabilities"]); cp.write_text(yaml.safe_dump(c, sort_keys=False))
        rep = vp.validate_package(root, strict=True)
        self.assertTrue(rep.valid, rep.errors)
        self.assertEqual(rep.pending, [], rep.pending)
        self.assertEqual(rep.exit_code, 0)


# --------------------------------------------- runtime rejection (ACTION_REJECTED)
class TestActionRejected(Base):
    def load(self, key):
        v = PKGS[key]
        return (yaml.safe_load((v / "device_package.yaml").read_text()),
                yaml.safe_load((v / "capabilities/capabilities.yaml").read_text()))

    def assertRejectedNoMotion(self, res, capability):
        self.assertEqual(res["result"], "ACTION_REJECTED")
        self.assertIn(capability, res["message"])        # message names the capability
        self.assertIs(res["device_invoked"], False)      # never calls into the device
        self.assertIs(res["motion"], False)              # no motion attempted

    def test_unsupported_contact_actions_rejected_on_so101(self):
        m, c = self.load("so101")
        for a in ("move_until_contact", "compliant_hold"):
            self.assertRejectedNoMotion(vp.resolve_request(m, c, a), a)

    def test_pending_cartesian_is_rejected_on_so101(self):
        m, c = self.load("so101")
        self.assertRejectedNoMotion(vp.resolve_request(m, c, "cartesian_motion"), "cartesian_motion")

    def test_every_non_supported_action_is_rejected_on_both_devices(self):
        for key in PKGS:
            m, c = self.load(key)
            for a in vp.ACTIONS:
                self.assertRejectedNoMotion(vp.resolve_request(m, c, a), a)

    def test_experimental_rejected_unless_dev_test_enabled(self):
        m, c = self.load("so101")
        c["capabilities"]["actions"]["plan"] = {"status": "experimental", "reason": "unstable"}
        self.assertRejectedNoMotion(vp.resolve_request(m, c, "plan"), "plan")
        self.assertTrue(vp.resolve_request(m, c, "plan", dev_test_enabled=True)["dispatch"])

    def test_gripper_command_outside_supported_commands_rejected(self):
        m, c = self.load("so101")
        c["capabilities"]["actions"]["gripper_command"] = {"status": "supported", "validation": validated()}
        self.assertRejectedNoMotion(
            vp.resolve_request(m, c, "gripper_command", gripper_command="FORCE_LIMITED_CLOSE"), "gripper_command")
        self.assertTrue(vp.resolve_request(m, c, "gripper_command", gripper_command="OPEN")["dispatch"])

    def test_no_gripper_rejects_any_gripper_command(self):
        m, c = self.load("so101")
        m["gripper"] = {"has_gripper": False}
        c["capabilities"]["actions"]["gripper_command"] = {"status": "supported", "validation": validated()}
        self.assertRejectedNoMotion(vp.resolve_request(m, c, "gripper_command", gripper_command="OPEN"), "gripper_command")

    def test_contact_rejected_when_ft_unknown_even_if_declared_supported(self):
        m, c = self.load("so101")
        c["capabilities"]["actions"]["move_until_contact"] = {"status": "supported", "validation": validated()}
        res = vp.resolve_request(m, c, "move_until_contact")
        self.assertRejectedNoMotion(res, "move_until_contact")
        self.assertIn("force_torque_sensing", res["message"])

    def test_stop_capability_query_ownership_are_never_package_rejectable(self):
        m, c = self.load("so101")
        for a in vp.COMMON_SERVER_ACTIONS:
            self.assertTrue(vp.resolve_request(m, c, a)["dispatch"])

    def test_unknown_capability_name_is_an_error_not_a_silent_noop(self):
        m, c = self.load("so101")
        with self.assertRaises(ValueError):
            vp.resolve_request(m, c, "UNSUPPORTED_CAPABILITY")
        with self.assertRaises(ValueError):
            vp.resolve_request(m, c, "cartesian_moton")


if __name__ == "__main__":
    unittest.main()
