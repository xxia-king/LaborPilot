#!/usr/bin/env python3
"""初始化、验证、迁移并推进劳动争议案件状态。

用户侧始终只保留一份 case_state.json；就地更新前的状态自动进入
.casework/history/，以兼顾可回溯与目录可读性。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "2.0"
REPRESENTATIONS = {"employee", "employer", "undetermined"}
STAGES = ["undetermined", "intake", "pre_arbitration", "arbitration", "first_instance", "second_instance", "closure"]
FACT_STATUSES = {"supported", "client_statement", "opponent_allegation", "disputed", "to_verify"}
RISK_LEVELS = {"standard", "complex", "high"}
BUSINESS_ARRAYS = ["parties", "goals", "facts", "materials", "issues", "evidence", "rules", "claims", "deadlines", "decisions", "deliverables"]
GRAPH_ARRAYS = ["node_runs", "validations", "approvals", "checkpoints", "artifacts", "events"]


def fail(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"文件不存在：{path}")
    except json.JSONDecodeError as exc:
        fail(f"JSON 解析失败：{path}：{exc}")


def write_new(path: Path, payload: Any) -> None:
    if path.exists():
        fail(f"拒绝覆盖已有文件：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _snapshot_path(source: Path, operation: str) -> Path:
    internal = source.parent if source.parent.name == ".casework" else source.parent / ".casework"
    history = internal / "history"
    history.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    safe_operation = re.sub(r"[^a-zA-Z0-9_-]+", "-", operation).strip("-") or "update"
    return history / f"{timestamp}-{safe_operation}.json"


def write_state(path: Path, payload: Any, *, source: Path | None = None, operation: str = "update") -> None:
    """写入案件状态。

    当输入与输出是同一个文件时，先把旧状态保存到隐藏历史目录，再原子替换
    case_state.json。显式指定不同输出路径时保留旧版兼容行为，但仍拒绝覆盖。
    """
    source = source.resolve() if source is not None else None
    target = path.resolve()
    same_file = source is not None and source == target
    if same_file:
        if not source.exists():
            fail(f"源状态文件不存在：{source}")
        snapshot = _snapshot_path(source, operation)
        snapshot.write_bytes(source.read_bytes())
        if isinstance(payload, dict):
            payload["previous_state"] = str(snapshot.resolve())
        rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(rendered, encoding="utf-8")
        os.replace(temporary, target)
        return
    write_new(path, payload)


def valid_iso_date(value: Any) -> bool:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def check_unique_ids(items: Any, key: str, label: str, errors: list[str]) -> None:
    if not isinstance(items, list):
        return
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{label}[{index}] 必须是 object。")
            continue
        value = item.get(key)
        if not isinstance(value, str) or not value.strip() or value in seen:
            errors.append(f"{label}[{index}].{key} 缺失或重复。")
        else:
            seen.add(value)


def validate_state(state: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(state, dict):
        return ["顶层必须是 JSON object。"]
    if state.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version 必须为 {SCHEMA_VERSION}；1.0 状态请先执行 migrate。")
    if not isinstance(state.get("case_id"), str) or not state.get("case_id", "").strip():
        errors.append("case_id 不得为空。")
    if state.get("representation") not in REPRESENTATIONS:
        errors.append("representation 必须为 employee、employer 或 undetermined。")
    if state.get("stage") not in STAGES:
        errors.append(f"stage 必须为：{', '.join(STAGES)}。")
    if not isinstance(state.get("jurisdiction"), str) or not state.get("jurisdiction", "").strip():
        errors.append("jurisdiction 不得为空。")
    if not valid_iso_date(state.get("analysis_date")):
        errors.append("analysis_date 必须为合法 YYYY-MM-DD。")
    if state.get("risk_level") not in RISK_LEVELS:
        errors.append("risk_level 必须为 standard、complex 或 high。")
    if not isinstance(state.get("current_node"), str) or not state.get("current_node", "").strip():
        errors.append("current_node 不得为空。")
    if not isinstance(state.get("pending_nodes"), list) or not all(isinstance(node, str) and node for node in state.get("pending_nodes", [])):
        errors.append("pending_nodes 必须是字符串数组。")
    if state.get("paused") is not None and not isinstance(state.get("paused"), dict):
        errors.append("paused 必须为 null 或 object。")
    for key in BUSINESS_ARRAYS + GRAPH_ARRAYS:
        if not isinstance(state.get(key), list):
            errors.append(f"{key} 必须是数组。")
    if "next_action" not in state:
        errors.append("缺少 next_action。")
    task_context = state.get("task_context")
    if task_context is not None and not isinstance(task_context, dict):
        errors.append("task_context 必须为 object 或缺省。")

    for items, key, label in [
        (state.get("facts"), "fact_id", "facts"),
        (state.get("node_runs"), "run_id", "node_runs"),
        (state.get("validations"), "validation_id", "validations"),
        (state.get("approvals"), "approval_id", "approvals"),
        (state.get("checkpoints"), "checkpoint_id", "checkpoints"),
        (state.get("artifacts"), "artifact_id", "artifacts"),
        (state.get("events"), "event_id", "events"),
    ]:
        check_unique_ids(items, key, label, errors)

    for index, fact in enumerate(state.get("facts", []) if isinstance(state.get("facts"), list) else []):
        if not isinstance(fact, dict):
            continue
        if fact.get("status") not in FACT_STATUSES:
            errors.append(f"facts[{index}].status 无效。")
        if not isinstance(fact.get("sources"), list):
            errors.append(f"facts[{index}].sources 必须是数组。")
        if fact.get("status") == "supported" and not fact.get("sources"):
            errors.append(f"facts[{index}] 标记 supported 但没有材料来源。")
    for index, decision in enumerate(state.get("decisions", []) if isinstance(state.get("decisions"), list) else []):
        if not isinstance(decision, dict):
            continue
        for key in ("decision", "confirmed_on", "confirmed_by"):
            if not decision.get(key):
                errors.append(f"decisions[{index}] 缺少 {key}。")
    return errors


def initial_state(args: argparse.Namespace) -> dict[str, Any]:
    created_at = now_iso()
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": args.case_id or new_id("labor"),
        "representation": args.representation,
        "stage": args.stage,
        "jurisdiction": args.jurisdiction,
        "analysis_date": args.analysis_date or date.today().isoformat(),
        "previous_state": None,
        "risk_level": args.risk_level,
        "current_node": "task_intake",
        "pending_nodes": [],
        "paused": None,
        "task_context": {
            "user_request": None,
            "requested_outputs": [],
            "constraints": [],
            "confirmed_by": None,
            "confirmed_at": None,
        },
        "parties": [], "goals": [], "facts": [], "materials": [], "issues": [],
        "evidence": [], "rules": [], "claims": [], "deadlines": [], "decisions": [], "deliverables": [],
        "node_runs": [], "validations": [], "approvals": [], "checkpoints": [], "artifacts": [],
        "events": [{
            "event_id": new_id("evt"), "event_type": "state_initialized", "actor": args.actor,
            "occurred_at": created_at, "details": {"schema_version": SCHEMA_VERSION}
        }],
        "next_action": "询问并确认用户任务、代理立场和案件阶段；确认前不读取案件材料",
    }


def command_init(args: argparse.Namespace) -> int:
    state = initial_state(args)
    errors = validate_state(state)
    if errors:
        fail("\n".join(errors))
    write_new(Path(args.output), state)
    print(f"已创建案件图状态：{args.output}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    state = read_json(Path(args.input))
    errors = validate_state(state)
    print(json.dumps({
        "status": "valid" if not errors else "invalid",
        "schema_version": state.get("schema_version") if isinstance(state, dict) else None,
        "errors": errors,
    }, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def migrate_v1(state: dict[str, Any], actor: str) -> dict[str, Any]:
    if state.get("schema_version") != "1.0":
        fail("仅支持将 schema_version=1.0 迁移到 2.0。")
    migrated = deepcopy(state)
    migrated["schema_version"] = SCHEMA_VERSION
    migrated.setdefault("previous_state", None)
    migrated.update({"risk_level": "standard", "current_node": "task_intake", "pending_nodes": [], "paused": None})
    migrated["task_context"] = {
        "user_request": None, "requested_outputs": [], "constraints": [],
        "confirmed_by": None, "confirmed_at": None,
    }
    for key in GRAPH_ARRAYS:
        migrated[key] = []
    migrated["events"].append({
        "event_id": new_id("evt"), "event_type": "state_migrated", "actor": actor,
        "occurred_at": now_iso(), "details": {"from": "1.0", "to": SCHEMA_VERSION}
    })
    return migrated


def command_migrate(args: argparse.Namespace) -> int:
    source = Path(args.input)
    migrated = migrate_v1(read_json(source), args.actor)
    migrated["previous_state"] = str(source.resolve())
    errors = validate_state(migrated)
    if errors:
        fail("迁移后状态无效：\n" + "\n".join(errors))
    write_new(Path(args.output), migrated)
    print(f"已生成 2.0 案件状态：{args.output}")
    return 0


def command_advance(args: argparse.Namespace) -> int:
    source = Path(args.input)
    state = read_json(source)
    errors = validate_state(state)
    if errors:
        fail("源状态无效：\n" + "\n".join(errors))
    old_stage = state["stage"]
    if STAGES.index(args.stage) < STAGES.index(old_stage):
        fail(f"拒绝将阶段从 {old_stage} 回退到 {args.stage}。")
    state["stage"] = args.stage
    state["analysis_date"] = args.analysis_date or date.today().isoformat()
    state["events"].append({
        "event_id": new_id("evt"), "event_type": "stage_advanced", "actor": args.actor,
        "occurred_at": now_iso(), "details": {"from": old_stage, "to": args.stage}
    })
    output = Path(args.output) if args.output else source
    write_state(output, state, source=source, operation="stage-advance")
    print(f"已更新案件状态：{output}")
    return 0


def command_set_task(args: argparse.Namespace) -> int:
    source = Path(args.input)
    state = read_json(source)
    errors = validate_state(state)
    if errors:
        fail("源状态无效：\n" + "\n".join(errors))
    if state.get("current_node") not in {"task_intake", "material_ingestion", "intake"}:
        fail("仅允许在任务确认、材料接入或案件接入节点补录任务上下文。")
    confirmed_at = now_iso()
    state["representation"] = args.representation
    state["stage"] = args.stage
    state["jurisdiction"] = args.jurisdiction or state["jurisdiction"]
    state["task_context"] = {
        "user_request": args.user_request.strip(),
        "requested_outputs": list(args.requested_output),
        "constraints": list(args.constraint),
        "confirmed_by": args.confirmed_by,
        "confirmed_at": confirmed_at,
    }
    if args.user_request.strip() not in state["goals"]:
        state["goals"].append(args.user_request.strip())
    state["next_action"] = "通过 task_intake 门禁后进入材料接入"
    state["events"].append({
        "event_id": new_id("evt"), "event_type": "task_context_confirmed", "actor": args.confirmed_by,
        "occurred_at": confirmed_at,
        "details": {"representation": args.representation, "stage": args.stage, "jurisdiction": state["jurisdiction"]},
    })
    output = Path(args.output) if args.output else source
    write_state(output, state, source=source, operation="task-confirmed")
    print(f"已更新任务确认状态：{output}")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="劳动争议案件图状态工具")
    sub = root.add_subparsers(dest="command", required=True)
    init_parser = sub.add_parser("init")
    init_parser.add_argument("--representation", choices=sorted(REPRESENTATIONS), default="undetermined")
    init_parser.add_argument("--stage", choices=STAGES, default="undetermined")
    init_parser.add_argument("--jurisdiction", default="浙江省")
    init_parser.add_argument("--analysis-date")
    init_parser.add_argument("--risk-level", choices=sorted(RISK_LEVELS), default="standard")
    init_parser.add_argument("--actor", default="labor-dispute-casework")
    init_parser.add_argument("--case-id")
    init_parser.add_argument("--output", required=True)
    init_parser.set_defaults(func=command_init)
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--input", required=True)
    validate_parser.set_defaults(func=command_validate)
    migrate_parser = sub.add_parser("migrate")
    migrate_parser.add_argument("--input", required=True)
    migrate_parser.add_argument("--output", required=True)
    migrate_parser.add_argument("--actor", default="labor-dispute-casework")
    migrate_parser.set_defaults(func=command_migrate)
    advance_parser = sub.add_parser("advance")
    advance_parser.add_argument("--input", required=True)
    advance_parser.add_argument("--stage", choices=STAGES, required=True)
    advance_parser.add_argument("--analysis-date")
    advance_parser.add_argument("--actor", default="labor-dispute-casework")
    advance_parser.add_argument("--output", help="默认就地更新 --input，旧状态存入 .casework/history/")
    advance_parser.set_defaults(func=command_advance)
    task_parser = sub.add_parser("set-task")
    task_parser.add_argument("--input", required=True)
    task_parser.add_argument("--representation", choices=["employee", "employer"], required=True)
    task_parser.add_argument("--stage", choices=[item for item in STAGES if item != "undetermined"], required=True)
    task_parser.add_argument("--jurisdiction")
    task_parser.add_argument("--user-request", required=True)
    task_parser.add_argument("--requested-output", action="append", default=[])
    task_parser.add_argument("--constraint", action="append", default=[])
    task_parser.add_argument("--confirmed-by", default="user")
    task_parser.add_argument("--output", help="默认就地更新 --input，旧状态存入 .casework/history/")
    task_parser.set_defaults(func=command_set_task)
    return root


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
