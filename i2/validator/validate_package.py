#!/usr/bin/env python3
"""I2 Device Package validator (draft v0.5).

One JSON Schema pair + this checker is run unchanged for every device package.

Usage:
    python validate_package.py <package_dir> [<package_dir> ...] [--strict]

Exit codes:
    0  valid (pending values may still exist; they are listed)
    1  invalid
    2  valid but --strict (freeze gate) and unresolved/pending values remain

Pending model
-------------
Unresolved values are never silently accepted as validated:
  * the literal string "PENDING" (only where the schema allows it), and
  * entries in the manifest's top-level `pending:` registry (JSON-pointer + reason)
    for placeholders that are not sentinels (e.g. placeholder UUIDs, empty pose lists)
  * action entries with `validation.state: PENDING`
are all collected and reported. `--strict` turns any of them into a failure.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import yaml

try:  # use the real library in CI when it is installed
    import jsonschema as _jsonschema  # type: ignore
except ImportError:  # pragma: no cover - fallback path is what runs in the sandbox
    _jsonschema = None

PENDING = "PENDING"
VALIDATOR_SCHEMA_VERSION = (0, 5)   # I2 contract (major, minor) this validator implements
VALIDATOR_I1_VERSION = (1, 0)       # I1 API version this validator implements
SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"

ACTIONS = [
    "named_pose_move", "plan", "plan_preview", "execute", "gripper_command",
    "cartesian_motion", "move_until_contact", "compliant_hold", "abort_task",
]
# Provided by the common server for every device; never declared by a package.
COMMON_SERVER_ACTIONS = ["stop", "capability_query", "controller_ownership"]
CONTACT_ACTIONS = ("move_until_contact", "compliant_hold")
E2E_EVIDENCE = ("SIM_FAKE_E2E", "HARDWARE_E2E")

DIAG_VOCAB = {
    "device_health": {"UNKNOWN", "OK", "DEGRADED", "FAULT"},
    "driver_status": {"UNKNOWN", "OK", "DEGRADED", "FAULT"},
    "connection_status": {"UNKNOWN", "CONNECTED", "DISCONNECTED"},
}
DIAG_FIELDS = ["device_health", "driver_status", "connection_status", "fault_reporting", "device_ready"]


# --------------------------------------------------------------------------- #
# Minimal JSON-Schema subset validator (used only if `jsonschema` is missing)
# --------------------------------------------------------------------------- #
class _MiniSchema:
    """Supports exactly the keywords our two schemas use."""

    def __init__(self, root: dict):
        self.root = root

    def errors(self, instance) -> list[str]:
        out: list[str] = []
        self._check(instance, self.root, "", out)
        return out

    def _ref(self, ref: str) -> dict:
        assert ref.startswith("#/"), ref
        node = self.root
        for part in ref[2:].split("/"):
            node = node[part]
        return node

    @staticmethod
    def _is(t: str, v) -> bool:
        if t == "object":
            return isinstance(v, dict)
        if t == "array":
            return isinstance(v, list)
        if t == "string":
            return isinstance(v, str)
        if t == "boolean":
            return isinstance(v, bool)
        if t == "integer":
            return isinstance(v, int) and not isinstance(v, bool)
        if t == "number":
            return isinstance(v, (int, float)) and not isinstance(v, bool)
        return False

    def _check(self, v, s: dict, p: str, out: list[str]) -> None:
        loc = p or "/"
        if "$ref" in s:
            return self._check(v, self._ref(s["$ref"]), p, out)
        if "anyOf" in s:
            if not any(not self._sub(v, b, p) for b in s["anyOf"]):
                out.append(f"{loc}: value {v!r} does not match any allowed form")
            return
        if "oneOf" in s:
            n = sum(1 for b in s["oneOf"] if not self._sub(v, b, p))
            if n != 1:
                out.append(f"{loc}: must match exactly one allowed form (matched {n})")
            return
        if "const" in s and v != s["const"]:
            out.append(f"{loc}: must be {s['const']!r}, got {v!r}")
            return
        if "enum" in s and v not in s["enum"]:
            out.append(f"{loc}: {v!r} is not one of {s['enum']}")
            return
        if "type" in s and not self._is(s["type"], v):
            out.append(f"{loc}: expected {s['type']}, got {type(v).__name__}")
            return
        if isinstance(v, str):
            if len(v) < s.get("minLength", 0):
                out.append(f"{loc}: string is empty")
            if "pattern" in s and not re.search(s["pattern"], v):
                out.append(f"{loc}: {v!r} does not match pattern {s['pattern']}")
        if self._is("number", v):
            if "minimum" in s and v < s["minimum"]:
                out.append(f"{loc}: {v} < minimum {s['minimum']}")
            if "exclusiveMinimum" in s and v <= s["exclusiveMinimum"]:
                out.append(f"{loc}: {v} must be > {s['exclusiveMinimum']}")
        if isinstance(v, list):
            if len(v) < s.get("minItems", 0):
                out.append(f"{loc}: needs at least {s['minItems']} item(s)")
            if "maxItems" in s and len(v) > s["maxItems"]:
                out.append(f"{loc}: at most {s['maxItems']} item(s)")
            if s.get("uniqueItems") and len({json.dumps(i, sort_keys=True) for i in v}) != len(v):
                out.append(f"{loc}: items must be unique")
            if "items" in s:
                for i, item in enumerate(v):
                    self._check(item, s["items"], f"{p}/{i}", out)
        if isinstance(v, dict):
            for r in s.get("required", []):
                if r not in v:
                    out.append(f"{loc}: missing required key '{r}'")
            props = s.get("properties", {})
            pat = s.get("patternProperties", {})
            for k, val in v.items():
                if k in props:
                    self._check(val, props[k], f"{p}/{k}", out)
                    continue
                matched = [sub for rx, sub in pat.items() if re.search(rx, k)]
                if matched:
                    for sub in matched:
                        self._check(val, sub, f"{p}/{k}", out)
                    continue
                ap = s.get("additionalProperties", True)
                if ap is False:
                    out.append(f"{loc}: unknown key '{k}'")
                elif isinstance(ap, dict):
                    self._check(val, ap, f"{p}/{k}", out)

    def _sub(self, v, s, p) -> list[str]:
        tmp: list[str] = []
        self._check(v, s, p, tmp)
        return tmp


def _schema_errors(instance, schema_file: str) -> list[str]:
    schema = json.loads((SCHEMA_DIR / schema_file).read_text())
    if _jsonschema is not None:
        v = _jsonschema.Draft202012Validator(schema)
        return [
            f"/{'/'.join(str(x) for x in e.absolute_path)}: {e.message}"
            for e in sorted(v.iter_errors(instance), key=lambda e: list(map(str, e.absolute_path)))
        ]
    return _MiniSchema(schema).errors(instance)


def schema_fingerprint() -> str:
    """Hash of both schema files: proves two packages were checked by the same schema."""
    h = hashlib.sha256()
    for name in ("device_package.schema.json", "capabilities.schema.json"):
        h.update((SCHEMA_DIR / name).read_bytes())
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
@dataclass
class Report:
    package: str
    errors: list[str] = field(default_factory=list)
    pending: list[tuple[str, str]] = field(default_factory=list)  # (json pointer, reason)
    strict: bool = False
    schema_hash: str = ""

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def freeze_ready(self) -> bool:
        return self.valid and not self.pending

    @property
    def exit_code(self) -> int:
        if self.errors:
            return 1
        if self.strict and self.pending:
            return 2
        return 0

    def err(self, msg: str) -> None:
        self.errors.append(msg)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _load_yaml(path: Path):
    with path.open() as f:
        return yaml.safe_load(f)


def _parse_version(s: str) -> tuple[int, int]:
    parts = s.split(".")
    return int(parts[0]), int(parts[1])


def _norm_action(entry) -> dict:
    """Shorthand `plan: supported` -> {'status': 'supported'}."""
    return {"status": entry} if isinstance(entry, str) else entry


def _walk(node, pointer=""):
    yield pointer, node
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk(v, f"{pointer}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{pointer}/{i}")


def _resolve_pointer(doc, pointer: str):
    node = doc
    for part in pointer.split("/")[1:]:
        if isinstance(node, list):
            node = node[int(part)]
        else:
            node = node[part]
    return node


def _check_path(root: Path, value: str, pointer: str, rep: Report) -> None:
    if not isinstance(value, str) or not value:
        return
    if value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", value) or PurePosixPath(value).is_absolute():
        rep.err(f"{pointer}: absolute path not permitted: {value!r}")
        return
    target = (root / value).resolve()
    if root.resolve() not in target.parents and target != root.resolve():
        rep.err(f"{pointer}: path escapes the package root: {value!r}")
        return
    if not target.exists():
        rep.err(f"{pointer}: referenced file does not exist in package: {value!r}")


# --------------------------------------------------------------------------- #
# Derived behaviour (also the reference oracle for common-server tests)
# --------------------------------------------------------------------------- #
def derive_supported_actions(caps: dict) -> list[str]:
    """supported_actions is derived only from capabilities.actions (status == supported)."""
    actions = caps["capabilities"]["actions"]
    listed = [a for a in ACTIONS if _norm_action(actions[a])["status"] == "supported"]
    return listed + COMMON_SERVER_ACTIONS


def resolve_request(manifest: dict, caps: dict, action: str, *,
                    gripper_command: str | None = None, dev_test_enabled: bool = False) -> dict:
    """Reference for A5 section 13: what the common server does with a request.

    Unsupported -> ACTION_REJECTED, message names the capability, device never invoked,
    no motion. (Jonathan's UNSUPPORTED_CAPABILITY is not an I1 code; it surfaces as this.)
    """
    if action in COMMON_SERVER_ACTIONS:
        return {"result": None, "dispatch": True, "device_invoked": True, "motion": None}
    if action not in ACTIONS:
        raise ValueError(f"unknown capability name: {action!r}")

    c = caps["capabilities"]
    entry = _norm_action(c["actions"][action])
    status = entry["status"]

    def reject(msg: str) -> dict:
        return {"result": "ACTION_REJECTED", "message": f"{action}: {msg}",
                "device_invoked": False, "motion": False}

    if status in ("planned", "unsupported"):
        return reject(f"{status}: {entry.get('reason', 'no reason declared')}")
    if status == "experimental" and not dev_test_enabled:
        return reject("experimental: development/test enablement required")
    if action in CONTACT_ACTIONS and c["force_torque_sensing"] in ("UNKNOWN", PENDING):
        return reject("force_torque_sensing is not available on this device")
    if action == "gripper_command":
        if not manifest["gripper"]["has_gripper"]:
            return reject("device has no gripper")
        if gripper_command not in manifest["gripper"].get("supported_commands", []):
            return reject(f"gripper command {gripper_command!r} not in supported_commands")
    return {"result": None, "dispatch": True, "device_invoked": True, "motion": None}


def validate_status_report(report: dict) -> list[str]:
    """Section 10.1: runtime diagnostic status values must use the fixed vocabulary."""
    errs = []
    for f, allowed in DIAG_VOCAB.items():
        if f in report and report[f] not in allowed:
            errs.append(f"{f}: {report[f]!r} not in {sorted(allowed)}")
    if "device_ready" in report and not isinstance(report["device_ready"], bool):
        errs.append("device_ready: must be boolean")
    for i, fault in enumerate(report.get("fault_reporting", [])):
        if fault.get("severity") not in ("WARNING", "ERROR"):
            errs.append(f"fault_reporting/{i}/severity: must be WARNING or ERROR")
        if not fault.get("source") or not fault.get("code"):
            errs.append(f"fault_reporting/{i}: source and code are required")
    return errs


# --------------------------------------------------------------------------- #
# Main entry
# --------------------------------------------------------------------------- #
def validate_package(root: str | Path, strict: bool = False) -> Report:
    root = Path(root)
    rep = Report(package=str(root), strict=strict, schema_hash=schema_fingerprint())

    manifest_path = root / "device_package.yaml"
    if not manifest_path.is_file():
        rep.err("device_package.yaml not found at package root")
        return rep
    try:
        manifest = _load_yaml(manifest_path)
    except yaml.YAMLError as e:
        rep.err(f"device_package.yaml is not valid YAML: {e}")
        return rep
    if not isinstance(manifest, dict):
        rep.err("device_package.yaml must be a mapping")
        return rep

    if "supported_actions" in manifest:
        rep.err("supported_actions must not be declared; it is derived from capabilities.actions")

    # 1. Versions first: an incompatible package is rejected, never partially loaded.
    for key, mine, label in (("schema_version", VALIDATOR_SCHEMA_VERSION, "I2 schema_version"),
                             ("i1_api_version", VALIDATOR_I1_VERSION, "I1 api version")):
        val = manifest.get(key)
        if not isinstance(val, str) or not re.match(r"^\d+\.\d+(\.\d+)?$", val):
            rep.err(f"{key}: missing or malformed ({val!r})")
            continue
        major, minor = _parse_version(val)
        if major != mine[0] or minor > mine[1]:
            rep.err(f"{label} incompatible: expected {mine[0]}.{mine[1]} (same major, minor not newer), found {val}")
    if rep.errors:
        return rep

    # 2. Schema
    serrs = _schema_errors(manifest, "device_package.schema.json")
    for e in serrs:
        rep.err(f"schema {e}")
    if serrs:
        return rep

    # 3. File references (package-relative, must exist)
    d = manifest
    path_fields = {
        "/driver/config": d["driver"]["config"],
        "/ros2_control/controllers/config": d["ros2_control"]["controllers"]["config"],
        "/moveit/config_ref": d["moveit"]["config_ref"],
        "/moveit/kinematics": d["moveit"]["kinematics"],
        "/moveit/joint_limits": d["moveit"]["joint_limits"],
        "/capabilities/config": d["capabilities"]["config"],
        "/lerobot/config": d["lerobot"]["config"],
    }
    if "error_codes" in d["diagnostics"]:
        path_fields["/diagnostics/error_codes"] = d["diagnostics"]["error_codes"]
    sim = d["simulation"]
    if sim["supported"]:
        for k in ("description_ref", "config"):
            if k in sim:
                path_fields[f"/simulation/{k}"] = sim[k]
    for ptr, val in path_fields.items():
        _check_path(root, val, ptr, rep)

    # 4. Capabilities file
    caps = None
    caps_rel = d["capabilities"]["config"]
    caps_path = root / caps_rel
    if caps_path.is_file():
        try:
            caps = _load_yaml(caps_path)
        except yaml.YAMLError as e:
            rep.err(f"{caps_rel}: not valid YAML: {e}")
    if isinstance(caps, dict):
        if "supported_actions" in caps or "supported_actions" in caps.get("capabilities", {}):
            rep.err(f"{caps_rel}: supported_actions must not be declared; it is derived from capabilities.actions")
        cerrs = _schema_errors(caps, "capabilities.schema.json")
        for e in cerrs:
            rep.err(f"capabilities schema {e}")
        if cerrs:
            caps = None
    else:
        caps = None

    _cross_checks(manifest, caps, rep)
    _collect_pending(manifest, caps, rep)
    if strict and rep.pending:
        pass  # exit_code handles it; the list is the explanation
    return rep


def _cross_checks(m: dict, caps: dict | None, rep: Report) -> None:
    dev, rc, mv, grip, sim = m["device"], m["ros2_control"], m["moveit"], m["gripper"], m["simulation"]

    # --- manipulators and groups -------------------------------------------
    ids = [x["manipulator_id"] for x in dev["manipulators"]]
    for i in ids:
        try:
            uuid.UUID(i)
        except ValueError:
            rep.err(f"manipulator_id {i!r} is not a valid UUID")
    if len(set(ids)) != len(ids):
        rep.err("duplicate manipulator_id in device.manipulators")
    id_set = set(ids)

    group_ids = []
    for g in dev.get("groups", []):
        gid, members = g["group_id"], g["members"]
        group_ids.append(gid)
        if len(set(members)) != len(members):
            rep.err(f"group {gid}: duplicate members")
        for mem in members:
            if mem not in id_set:
                rep.err(f"group {gid}: member {mem} is not a declared manipulator")
        if gid == "BIMANUAL" and len(members) != 2:
            rep.err("group BIMANUAL must contain exactly two manipulators")
    if len(set(group_ids)) != len(group_ids):
        rep.err("duplicate group_id in device.groups")
    selectors = id_set | set(group_ids)

    # --- joints -------------------------------------------------------------
    joints = rc["joints"]
    mj = rc["manipulator_joints"]
    gj = rc.get("gripper_joints", [])
    if set(mj) != id_set:
        rep.err("ros2_control.manipulator_joints keys must be exactly the declared manipulator_ids")
    seen_arm: dict[str, str] = {}
    for x in dev["manipulators"]:
        lst = mj.get(x["manipulator_id"], [])
        if len(lst) != x["arm_dof"]:
            rep.err(f"manipulator {x['name']}: {len(lst)} arm joints listed but arm_dof is {x['arm_dof']}")
        for j in lst:
            if j in seen_arm:
                rep.err(f"arm joint {j!r} belongs to more than one manipulator")
            seen_arm[j] = x["manipulator_id"]
            if j not in joints:
                rep.err(f"arm joint {j!r} missing from ros2_control.joints")
    for j in gj:
        if j not in joints:
            rep.err(f"gripper joint {j!r} missing from ros2_control.joints")
        if j in seen_arm:
            rep.err(f"gripper joint {j!r} must not appear in manipulator_joints")
    for j in joints:
        if j not in seen_arm and j not in gj:
            rep.err(f"joint {j!r} is neither an arm joint nor a gripper joint")

    # --- gripper ------------------------------------------------------------
    has_g = grip["has_gripper"]
    other = [k for k in grip if k != "has_gripper"]
    if has_g:
        need = ["gripper_type", "gripper_id", "joint_count", "command_interfaces", "state_interfaces",
                "supported_commands", "reports_effort", "contact_detection", "object_detection"]
        for k in need:
            if k not in grip:
                rep.err(f"gripper.{k} is required when has_gripper is true")
        if "joint_count" in grip and grip["joint_count"] != len(gj):
            rep.err(f"gripper.joint_count ({grip['joint_count']}) must equal len(ros2_control.gripper_joints) ({len(gj)})")
        if "end_effectors" not in mv:
            rep.err("moveit.end_effectors is required when a gripper is present")
    else:
        if other:
            rep.err(f"has_gripper is false: other gripper fields must be omitted ({', '.join(other)})")
        if gj:
            rep.err("has_gripper is false: ros2_control.gripper_joints must be empty or absent")

    # --- moveit ---------------------------------------------------------------
    pg_names = [g["name"] for g in mv["planning_groups"]]
    if len(set(pg_names)) != len(pg_names):
        rep.err("duplicate MoveIt planning group names")
    arm_cover: set[str] = set()
    members_by_group = {g["group_id"]: set(g["members"]) for g in dev.get("groups", [])}
    for g in mv["planning_groups"]:
        mt = g["maps_to"]
        if "manipulator_id" in mt:
            if mt["manipulator_id"] not in id_set:
                rep.err(f"planning group {g['name']}: unknown manipulator_id")
            elif g["role"] == "ARM":
                arm_cover.add(mt["manipulator_id"])
        else:
            if mt["group_id"] not in members_by_group:
                rep.err(f"planning group {g['name']}: group_id {mt['group_id']} not declared in device.groups")
            elif g["role"] == "ARM":
                arm_cover |= members_by_group[mt["group_id"]]
    named: dict[str, set[str]] = {}
    for np_ in mv["named_poses"]:
        if np_["selector"] not in selectors:
            rep.err(f"named_poses: unknown selector {np_['selector']!r}")
        named.setdefault(np_["selector"], set()).update(np_["poses"])
    for sel, pose in mv.get("stow_pose", {}).items():
        if sel not in selectors:
            rep.err(f"stow_pose: unknown selector {sel!r}")
        elif pose not in named.get(sel, set()):
            rep.err(f"stow_pose for {sel}: pose {pose!r} is not in named_poses for that selector")
    ee = mv.get("end_effectors")
    if isinstance(ee, list):
        for e in ee:
            if e["parent_group"] not in pg_names:
                rep.err(f"end_effector {e['name']}: parent_group {e['parent_group']!r} is not a declared planning group")

    # --- simulation -----------------------------------------------------------
    if sim["supported"]:
        for k in ("backend", "description_ref", "fake_hardware", "config", "selection"):
            if k not in sim:
                rep.err(f"simulation.{k} is required when simulation.supported is true")
        if sim.get("fake_hardware") is True and rc["fake_hardware"] is not True:
            rep.err("simulation.fake_hardware is true but ros2_control.fake_hardware does not match")
        if sim.get("fake_hardware") is False and "hardware_mode" not in sim:
            rep.err("simulation.hardware_mode must be declared when simulation.fake_hardware is false")

    # --- diagnostics ----------------------------------------------------------
    missing = [f for f in DIAG_FIELDS if f not in m["diagnostics"]["reports"]]
    if missing:
        rep.err(f"diagnostics.reports must include {', '.join(missing)}")

    if caps is None:
        return
    c = caps["capabilities"]
    acts = {a: _norm_action(c["actions"][a]) for a in ACTIONS}
    ft = c["force_torque_sensing"]

    # --- abort modes ------------------------------------------------------------
    def check_modes(label: str, modes: list[str], sels: set[str]) -> None:
        if "STOP_ONLY" not in modes:
            rep.err(f"{label}: abort modes must include STOP_ONLY")
        if "STOW" in modes:
            for s in sorted(sels):
                if s not in mv.get("stow_pose", {}):
                    rep.err(f"{label}: STOW requires a stow_pose for selector {s}")

    by_sel = c.get("abort_modes_by_selector", {})
    for k in by_sel:
        if k not in selectors:
            rep.err(f"abort_modes_by_selector: unknown selector {k!r}")
    check_modes("abort_modes", c["abort_modes"], selectors - set(by_sel))
    for k, modes in by_sel.items():
        if k in selectors:
            check_modes(f"abort_modes_by_selector[{k}]", modes, {k})

    # --- statuses, reasons, gates, evidence ----------------------------------
    for name, e in acts.items():
        st = e["status"]
        if st != "supported" and not e.get("reason"):
            rep.err(f"actions.{name}: status {st} requires a reason")
        if st == "supported":
            val = e.get("validation")
            if not val or val.get("state") != "VALIDATED":
                rep.err(f"actions.{name}: supported requires validation.state VALIDATED "
                        f"(config/sim presence alone is not evidence)")
            elif not any(ev["kind"] in E2E_EVIDENCE for ev in val.get("evidence", [])):
                rep.err(f"actions.{name}: supported requires end-to-end evidence "
                        f"({' or '.join(E2E_EVIDENCE)}); CONFIG_ONLY is not enough")
        if st in ("supported", "experimental"):
            _gate(name, st, acts, c, m, id_set, arm_cover, named, rep)

    if not has_g and acts["gripper_command"]["status"] != "unsupported":
        rep.err("has_gripper is false: gripper_command must be declared unsupported with a reason")


def _gate(name, st, acts, c, m, id_set, arm_cover, named, rep) -> None:
    ft = c["force_torque_sensing"]
    plan_ok = {"supported"} if st == "supported" else {"supported", "experimental"}
    if name == "named_pose_move" and not any(named.values()):
        rep.err(f"actions.{name}: {st} requires at least one named pose in moveit.named_poses")
    elif name in ("plan_preview", "execute") and acts["plan"]["status"] not in plan_ok:
        rep.err(f"actions.{name}: {st} requires plan to be {' or '.join(sorted(plan_ok))}")
    elif name == "gripper_command":
        g = m["gripper"]
        if not g["has_gripper"] or not g.get("supported_commands"):
            rep.err(f"actions.{name}: {st} requires has_gripper true and non-empty supported_commands")
    elif name == "cartesian_motion":
        uncovered = id_set - arm_cover
        if uncovered:
            rep.err(f"actions.{name}: {st} requires an ARM MoveIt planning group for every manipulator "
                    f"(missing: {sorted(uncovered)})")
    elif name in CONTACT_ACTIONS and ft in ("UNKNOWN", PENDING):
        rep.err(f"actions.{name}: {st} requires force_torque_sensing other than UNKNOWN/PENDING (found {ft})")


def _collect_pending(manifest: dict, caps: dict | None, rep: Report) -> None:
    reasons = {}
    for item in manifest.get("pending", []):
        ptr = item["path"]
        try:
            _resolve_pointer(manifest, ptr)
        except (KeyError, IndexError, ValueError, TypeError):
            rep.err(f"pending registry: path {ptr} does not exist in the manifest")
            continue
        reasons[ptr] = item["reason"]
    found: dict[str, str] = {}
    for ptr, node in _walk(manifest):
        if node == PENDING and not ptr.startswith("/pending"):
            found[ptr] = reasons.get(ptr, "unresolved value")
    for ptr, reason in reasons.items():
        found.setdefault(ptr, reason)
    if caps:
        for ptr, node in _walk(caps["capabilities"], "/capabilities"):
            if node == PENDING and not ptr.endswith("/validation/state"):
                found[ptr] = "unresolved value"
        for name, entry in caps["capabilities"]["actions"].items():
            e = _norm_action(entry)
            if e.get("validation", {}).get("state") == "PENDING":
                found[f"/capabilities/actions/{name}/validation"] = e["validation"].get("note", "validation pending")
    rep.pending = sorted(found.items())


# --------------------------------------------------------------------------- #
def main(argv: list[str]) -> int:
    strict = "--strict" in argv
    pkgs = [a for a in argv if not a.startswith("--")]
    if not pkgs:
        print(__doc__)
        return 1
    worst = 0
    for p in pkgs:
        rep = validate_package(p, strict=strict)
        print(f"== {rep.package}  (schema {rep.schema_hash})")
        for e in rep.errors:
            print(f"  ERROR   {e}")
        for ptr, why in rep.pending:
            print(f"  PENDING {ptr}  -- {why}")
        status = "INVALID" if rep.errors else ("PENDING-BLOCKS-FREEZE" if (strict and rep.pending) else
                                                ("VALID (with pending values)" if rep.pending else "VALID"))
        print(f"  => {status}")
        worst = max(worst, rep.exit_code)
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
