#!/usr/bin/env python3
"""查询并执行劳动争议工作图转换，默认更新单一案件状态文件。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from case_state import read_json, validate_state, write_state


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH = ROOT / "workflow" / "graph.json"
STATUS_BY_EVENT = {
    "pass": "passed", "approved": "passed", "return": "returned",
    "pause": "paused", "escalate": "escalated", "blocked": "failed",
}


def fail(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def load(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], Path]:
    state_path = Path(args.state)
    state = read_json(state_path)
    errors = validate_state(state)
    if errors:
        fail("案件状态无效：\n" + "\n".join(errors))
    graph = read_json(Path(args.graph))
    return state, graph, state_path


def transitions_for(graph: dict[str, Any], node: str) -> list[dict[str, Any]]:
    return [item for item in graph.get("transitions", []) if item.get("from") == node]


def graph_nodes(graph: dict[str, Any]) -> set[str]:
    nodes = {str(graph.get("entry_node", "")), str(graph.get("terminal_node", ""))}
    for transition in graph.get("transitions", []):
        nodes.add(str(transition.get("from", "")))
        target = transition.get("to")
        if isinstance(target, list):
            nodes.update(str(item) for item in target)
        elif target:
            nodes.add(str(target))
    return {node for node in nodes if node}


def descendants(graph: dict[str, Any], start: str) -> set[str]:
    result: set[str] = set()
    pending = [start]
    while pending:
        node = pending.pop()
        for transition in transitions_for(graph, node):
            target = transition.get("to")
            targets = target if isinstance(target, list) else [target]
            for item in targets:
                if isinstance(item, str) and item not in result and item != start:
                    result.add(item)
                    pending.append(item)
    return result


def forward_descendants(graph: dict[str, Any], start: str) -> set[str]:
    """仅沿正常完成路径判断下游，避免 return 边形成反向环。"""
    result: set[str] = set()
    pending = [start]
    while pending:
        node = pending.pop()
        for transition in transitions_for(graph, node):
            if transition.get("on") not in {"pass", "approved"}:
                continue
            target = transition.get("to")
            targets = target if isinstance(target, list) else [target]
            for item in targets:
                if isinstance(item, str) and item not in result and item != start:
                    result.add(item)
                    pending.append(item)
    return result


def node_run_outcome(run: dict[str, Any]) -> str:
    value = str(run.get("status") or run.get("result") or "").casefold()
    if value.startswith("return"):
        return "returned"
    if value.startswith("fail") or value == "blocked":
        return "failed"
    if value.startswith("pause"):
        return "paused"
    if value.startswith("escalat"):
        return "escalated"
    if value.startswith("pass"):
        return "passed"
    return value


def task_context_errors(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    task = state.get("task_context")
    if not isinstance(task, dict):
        return ["缺少经用户确认的 task_context。"]
    if state.get("representation") not in {"employee", "employer"}:
        errors.append("代理立场未确认：必须明确为劳动者方或用人单位方。")
    if state.get("stage") in {None, "", "undetermined"}:
        errors.append("案件阶段未确认。")
    if not isinstance(task.get("user_request"), str) or not task.get("user_request", "").strip():
        errors.append("用户的本轮具体任务未确认。")
    if not task.get("confirmed_by") or not task.get("confirmed_at"):
        errors.append("任务上下文缺少用户确认记录。")
    return errors


def returned_nodes_with_rework_started(state: dict[str, Any]) -> set[str]:
    """返回已由工作图正式退回修复的节点。

    单纯在历史记录中写入 returned 仍应阻断下游；但通过
    workflow_transition 的 return 事件回到修复节点，是合法的返工路径，
    不能再被同一条 returned 记录锁死。
    """
    resolved: set[str] = set()
    for event in state.get("events", []):
        if not isinstance(event, dict) or event.get("event_type") != "workflow_transition":
            continue
        details = event.get("details")
        if not isinstance(details, dict) or details.get("event") != "return":
            continue
        node = details.get("from")
        if isinstance(node, str) and node:
            resolved.add(node)
    return resolved


def has_explicit_escalation_route(graph: dict[str, Any], node: str) -> bool:
    """节点若声明了升级去向，升级即为合法完成路径，由目标节点承接风险。"""
    return any(
        transition.get("on") == "escalate" and transition.get("to") != node
        for transition in transitions_for(graph, node)
    )


def workflow_blockers(state: dict[str, Any], graph: dict[str, Any]) -> list[str]:
    current = state.get("current_node")
    blockers: list[str] = []
    if current not in graph_nodes(graph):
        blockers.append(f"当前节点不存在于工作图：{current}。")
        return blockers
    if current != "task_intake":
        blockers.extend(task_context_errors(state))
    latest: dict[str, dict[str, Any]] = {}
    for run in state.get("node_runs", []):
        if isinstance(run, dict) and isinstance(run.get("node"), str):
            latest[run["node"]] = run
    resolved_returns = returned_nodes_with_rework_started(state)
    for node, run in latest.items():
        outcome = node_run_outcome(run)
        if outcome == "returned" and node in resolved_returns:
            continue
        if outcome == "escalated" and has_explicit_escalation_route(graph, node):
            continue
        if outcome in {"returned", "failed", "paused", "escalated"} and current != node and current in descendants(graph, node):
            blockers.append(f"上游节点 {node} 最新结果为 {outcome}，未修复前不得处理 {current}。")
    if current == "claims_procedure" and state.get("pending_nodes"):
        blockers.append("证据或法源分支尚未全部完成，不得进入金额程序节点。")
    blockers.extend(completed_node_requirement_errors(state, graph))
    return blockers


def latest_gate_approved(state: dict[str, Any], gate: str) -> bool:
    return any(item.get("gate") == gate and item.get("status") == "approved" for item in reversed(state["approvals"]))


def required_validation_kinds(state: dict[str, Any], graph: dict[str, Any]) -> list[str]:
    return graph.get("risk_routes", {}).get(state["risk_level"], {}).get("required_validations", [])


def passed_validation_kinds(state: dict[str, Any]) -> set[str]:
    latest: dict[str, dict[str, Any]] = {}
    for item in state["validations"]:
        if isinstance(item, dict) and isinstance(item.get("kind"), str):
            latest[item["kind"]] = item
    return {kind for kind, item in latest.items() if item.get("status") == "pass"}


def requirements_for(graph: dict[str, Any], node: str) -> list[dict[str, Any]]:
    requirements = graph.get("node_requirements", {}).get(node, [])
    return [item for item in requirements if isinstance(item, dict)]


def requirement_waived(state: dict[str, Any], node: str, requirement_id: str) -> bool:
    for waiver in reversed(state.get("node_requirement_waivers", [])):
        if not isinstance(waiver, dict):
            continue
        if (
            waiver.get("node") == node
            and waiver.get("requirement_id") == requirement_id
            and waiver.get("status") == "approved"
            and isinstance(waiver.get("reason"), str)
            and len(waiver["reason"].strip()) >= 8
            and waiver.get("confirmed_by")
            and waiver.get("confirmed_at")
        ):
            return True
    return False


def validation_report_is_valid(record: dict[str, Any]) -> bool:
    report_path = record.get("report_path")
    if not isinstance(report_path, str) or not report_path:
        return False
    path = Path(report_path).expanduser()
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(payload, dict)
        and payload.get("status") == record.get("status")
        and isinstance(payload.get("findings"), list)
    )


def requirement_is_met(
    state: dict[str, Any],
    graph: dict[str, Any],
    requirement: dict[str, Any],
    transition_output_artifact_ids: list[str],
) -> bool:
    requirement_type = requirement.get("type")
    if requirement_type == "non_empty_collection":
        collection = state.get(str(requirement.get("collection", "")))
        if not isinstance(collection, list) or not collection:
            return False
        id_key = requirement.get("id_key")
        if id_key:
            return all(
                isinstance(item, dict)
                and isinstance(item.get(str(id_key)), str)
                and bool(item[str(id_key)].strip())
                for item in collection
            )
        return True
    if requirement_type == "traceable_material":
        for material in state.get("materials", []):
            if not isinstance(material, dict):
                continue
            digest = str(material.get("source_sha256", ""))
            if (
                material.get("material_id")
                and material.get("source_path")
                and len(digest) == 64
                and all(character in "0123456789abcdefABCDEF" for character in digest)
            ):
                return True
        return False
    if requirement_type == "verified_authority":
        rules = state.get("rules", [])
        return bool(rules) and all(
            isinstance(rule, dict)
            and rule.get("rule_id")
            and rule.get("verification_status") == "verified"
            and rule.get("document_id")
            and rule.get("article_id")
            for rule in rules
        )
    if requirement_type == "claims_ready":
        claims = state.get("claims", [])
        return bool(claims) and all(
            isinstance(claim, dict)
            and claim.get("claim_id")
            and (claim.get("amount") is None or claim.get("calculation_id"))
            for claim in claims
        )
    if requirement_type == "transition_output_artifact":
        if not transition_output_artifact_ids:
            return False
        known = {
            item.get("artifact_id"): item
            for item in state.get("artifacts", [])
            if isinstance(item, dict) and item.get("artifact_id")
        }
        return all(
            artifact_id in known
            and Path(str(known[artifact_id].get("path", ""))).expanduser().is_file()
            for artifact_id in transition_output_artifact_ids
        )
    if requirement_type == "report_backed_validations":
        latest: dict[str, dict[str, Any]] = {}
        for item in state.get("validations", []):
            if isinstance(item, dict) and isinstance(item.get("kind"), str):
                latest[item["kind"]] = item
        return all(
            kind in latest
            and latest[kind].get("status") in {"pass", "escalate"}
            and validation_report_is_valid(latest[kind])
            for kind in required_validation_kinds(state, graph)
        )
    return False


def node_requirement_statuses(
    state: dict[str, Any],
    graph: dict[str, Any],
    node: str,
    transition_output_artifact_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    output_ids = transition_output_artifact_ids or []
    statuses = []
    for requirement in requirements_for(graph, node):
        requirement_id = str(requirement.get("id", ""))
        met = requirement_is_met(state, graph, requirement, output_ids)
        waived = (
            not met
            and bool(requirement.get("waiver_allowed"))
            and requirement_waived(state, node, requirement_id)
        )
        statuses.append({
            "id": requirement_id,
            "met": met,
            "waived": waived,
            "waiver_allowed": bool(requirement.get("waiver_allowed")),
            "message": requirement.get("message", "节点完成条件未满足。"),
        })
    return statuses


def completed_node_requirement_errors(state: dict[str, Any], graph: dict[str, Any]) -> list[str]:
    current = state.get("current_node")
    if not isinstance(current, str):
        return []
    latest_runs: dict[str, dict[str, Any]] = {}
    for run in state.get("node_runs", []):
        if isinstance(run, dict) and isinstance(run.get("node"), str):
            latest_runs[run["node"]] = run
    errors: list[str] = []
    for node in graph.get("node_requirements", {}):
        if node == current or current not in forward_descendants(graph, node):
            continue
        run = latest_runs.get(node, {})
        output_ids = run.get("output_artifact_ids", []) if isinstance(run, dict) else []
        if not isinstance(output_ids, list):
            output_ids = []
        for status in node_requirement_statuses(state, graph, node, output_ids):
            if not status["met"] and not status["waived"]:
                errors.append(
                    f"上游节点 {node} 的完成条件 {status['id']} 当前不成立：{status['message']}"
                )
    return errors


def gate_errors(
    state: dict[str, Any],
    graph: dict[str, Any],
    node: str,
    event: str,
    transition_output_artifact_ids: list[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    errors.extend(workflow_blockers(state, graph))
    if node == "task_intake" and event == "pass":
        errors.extend(task_context_errors(state))
    if node == "strategy_approval" and event == "approved" and not latest_gate_approved(state, "strategy_approval"):
        errors.append("缺少 strategy_approval 的律师批准记录。")
    if node == "validation" and event == "pass":
        missing = sorted(set(required_validation_kinds(state, graph)) - passed_validation_kinds(state))
        if missing:
            errors.append("缺少已通过的验证类型：" + "、".join(missing) + "。")
    if node == "lawyer_approval" and event == "approved" and not latest_gate_approved(state, "lawyer_approval"):
        errors.append("缺少 lawyer_approval 的律师批准记录。")
    completes_requirements = event == "pass" or (node == "validation" and event == "escalate")
    if completes_requirements:
        for status in node_requirement_statuses(
            state,
            graph,
            node,
            transition_output_artifact_ids,
        ):
            if not status["met"] and not status["waived"]:
                errors.append(f"节点完成条件 {status['id']} 未满足：{status['message']}")
    return errors


def command_route(args: argparse.Namespace) -> int:
    state, graph, _ = load(args)
    node = state["current_node"]
    blockers = workflow_blockers(state, graph)
    required_user_confirmations = task_context_errors(state) if node == "task_intake" else []
    result = {
        "status": "blocked" if blockers else "paused" if state["paused"] else "awaiting_user_input" if required_user_confirmations else "ready",
        "current_node": node,
        "pending_nodes": state["pending_nodes"],
        "risk_level": state["risk_level"],
        "allowed_transitions": [] if blockers else transitions_for(graph, node),
        "required_validations": required_validation_kinds(state, graph),
        "node_requirements": node_requirement_statuses(state, graph, node),
        "paused": state["paused"],
        "blockers": blockers,
        "required_user_confirmations": required_user_confirmations,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def resolve_target(state: dict[str, Any], target: Any, use_pending: bool = True) -> str:
    if isinstance(target, list):
        if not target:
            fail("工作图分支目标为空。")
        state["pending_nodes"] = list(target[1:]) + state["pending_nodes"]
        return target[0]
    if use_pending and state["pending_nodes"]:
        return state["pending_nodes"].pop(0)
    if not isinstance(target, str):
        fail("工作图目标节点无效。")
    return target


def command_transition(args: argparse.Namespace) -> int:
    state, graph, source = load(args)
    if state["paused"] and args.event != "resume":
        fail("案件已暂停；请先执行 resume。")
    if args.event == "resume":
        if not state["paused"]:
            fail("案件当前未暂停。")
        state["events"].append({
            "event_id": new_id("evt"), "event_type": "workflow_resumed", "actor": args.actor,
            "occurred_at": now_iso(), "details": {"checkpoint_id": state["paused"].get("checkpoint_id")}
        })
        state["paused"] = None
        output = Path(args.output) if args.output else source
        write_state(output, state, source=source, operation="workflow-resume")
        print(f"已从检查点恢复：{output}")
        return 0

    node = state["current_node"]
    matches = [item for item in transitions_for(graph, node) if item.get("on") == args.event]
    synthetic_escalation = False
    if not matches and args.event == "pause":
        matches = [{"from": node, "on": "pause", "to": node}]
    if not matches and args.event == "escalate":
        matches = [{"from": node, "on": "escalate", "to": node}]
        synthetic_escalation = True
    if len(matches) != 1:
        fail(f"节点 {node} 不存在唯一的 {args.event} 转换。")
    errors = gate_errors(state, graph, node, args.event, args.output_artifact)
    if errors:
        fail("门禁未通过：\n" + "\n".join(errors))

    completed_at = now_iso()
    state["node_runs"].append({
        "run_id": new_id("run"), "node": node, "status": STATUS_BY_EVENT.get(args.event, "passed"),
        "actor": args.actor, "started_at": args.started_at or completed_at, "completed_at": completed_at,
        "input_artifact_ids": args.input_artifact, "output_artifact_ids": args.output_artifact,
        "note": args.note,
    })
    if args.event == "pause" or synthetic_escalation:
        checkpoint_id = new_id("cp")
        checkpoint = {"checkpoint_id": checkpoint_id, "node": node, "created_at": completed_at, "reason": args.note}
        state["checkpoints"].append(checkpoint)
        default_reason = "等待律师处理升级事项" if synthetic_escalation else "等待补充信息"
        state["paused"] = {"reason": args.note or default_reason, "checkpoint_id": checkpoint_id, "paused_at": completed_at, "resume_condition": args.resume_condition}
        target = node
    else:
        if args.event != "pass":
            state["pending_nodes"] = []
        target = resolve_target(state, matches[0].get("to"), use_pending=args.event == "pass")
    state["current_node"] = target
    state["next_action"] = f"处理工作图节点：{target}"
    state["events"].append({
        "event_id": new_id("evt"), "event_type": "workflow_transition", "actor": args.actor,
        "occurred_at": completed_at, "details": {"from": node, "event": args.event, "to": target, "note": args.note}
    })
    output = Path(args.output) if args.output else source
    write_state(output, state, source=source, operation=f"transition-{node}-{args.event}")
    print(f"已更新工作图状态：{output}")
    return 0


def command_approve(args: argparse.Namespace) -> int:
    state, graph, source = load(args)
    if state["current_node"] != args.gate:
        fail(f"当前节点为 {state['current_node']}，不能记录 {args.gate} 审批。")
    required_scope = set(graph.get("approval_gates", {}).get(args.gate, []))
    missing_scope = sorted(required_scope - set(args.scope))
    if args.status == "approved" and missing_scope:
        fail("批准范围不完整，缺少：" + "、".join(missing_scope) + "。")
    state["approvals"].append({
        "approval_id": new_id("approval"), "gate": args.gate, "status": args.status,
        "approved_by": args.approved_by, "decided_at": now_iso(), "scope": args.scope, "note": args.note,
    })
    state["events"].append({
        "event_id": new_id("evt"), "event_type": "approval_recorded", "actor": args.approved_by,
        "occurred_at": now_iso(), "details": {"gate": args.gate, "status": args.status, "scope": args.scope}
    })
    output = Path(args.output) if args.output else source
    write_state(output, state, source=source, operation=f"approval-{args.gate}")
    print(f"已记录审批：{output}")
    return 0


def command_artifact(args: argparse.Namespace) -> int:
    state, _, source = load(args)
    artifact_path = Path(args.path).expanduser().resolve()
    if not artifact_path.is_file():
        fail(f"产物文件不存在：{artifact_path}")
    sha256 = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    artifact = {
        "artifact_id": args.artifact_id or new_id("artifact"), "kind": args.kind,
        "path": str(artifact_path), "version": args.version, "sha256": sha256,
        "created_by": args.created_by, "created_at": now_iso(), "derived_from": args.derived_from,
    }
    state["artifacts"].append(artifact)
    state["events"].append({
        "event_id": new_id("evt"), "event_type": "artifact_registered", "actor": args.created_by,
        "occurred_at": now_iso(), "details": {"artifact_id": artifact["artifact_id"], "sha256": sha256}
    })
    output = Path(args.output) if args.output else source
    write_state(output, state, source=source, operation="artifact-registered")
    print(json.dumps(artifact, ensure_ascii=False, indent=2))
    return 0


def command_record_validation(args: argparse.Namespace) -> int:
    state, _, source = load(args)
    findings: list[dict[str, Any]] = []
    report_path: str | None = None
    if args.report:
        report = Path(args.report).expanduser().resolve()
        if not report.is_file():
            fail(f"验证报告不存在：{report}")
        payload = read_json(report)
        if (
            not isinstance(payload, dict)
            or "status" not in payload
            or "findings" not in payload
            or not isinstance(payload.get("findings"), list)
        ):
            fail("验证报告必须是含 status 和 findings 数组的 JSON object。")
        findings = payload.get("findings", [])
        if args.status is None:
            args.status = payload.get("status")
        elif payload.get("status") and payload.get("status") != args.status:
            fail("--status 与验证报告中的 status 不一致。")
        report_path = str(report)
    if args.status not in {"pass", "return", "pause", "escalate", "blocked"}:
        fail("必须通过 --status 或报告提供合法验证状态。")
    if args.status in {"pass", "escalate"} and not report_path:
        fail("验证结论为 pass 或 escalate 时必须提供含 status 和 findings 的 JSON 报告。")
    record = {
        "validation_id": new_id("validation"), "kind": args.kind, "validator": args.validator,
        "status": args.status, "checked_at": now_iso(), "findings": findings,
        "artifact_ids": args.artifact_id, "report_path": report_path, "note": args.note,
    }
    state["validations"].append(record)
    state["events"].append({
        "event_id": new_id("evt"), "event_type": "validation_recorded", "actor": args.validator,
        "occurred_at": now_iso(), "details": {"validation_id": record["validation_id"], "kind": args.kind, "status": args.status}
    })
    output = Path(args.output) if args.output else source
    write_state(output, state, source=source, operation=f"validation-{args.kind}")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


def command_record_waiver(args: argparse.Namespace) -> int:
    state, graph, source = load(args)
    node = state["current_node"]
    requirements = {
        item.get("id"): item
        for item in requirements_for(graph, node)
        if item.get("id")
    }
    requirement = requirements.get(args.requirement)
    if not requirement:
        fail(f"当前节点 {node} 不存在完成条件 {args.requirement}。")
    if not requirement.get("waiver_allowed"):
        fail(f"完成条件 {args.requirement} 不允许豁免。")
    reason = args.reason.strip()
    if len(reason) < 8:
        fail("豁免理由不得为空泛，至少应说明无相应材料或记录的具体原因。")
    waiver = {
        "waiver_id": new_id("waiver"),
        "node": node,
        "requirement_id": args.requirement,
        "status": "approved",
        "reason": reason,
        "confirmed_by": args.confirmed_by,
        "confirmed_at": now_iso(),
    }
    state.setdefault("node_requirement_waivers", []).append(waiver)
    state["events"].append({
        "event_id": new_id("evt"),
        "event_type": "node_requirement_waiver_recorded",
        "actor": args.confirmed_by,
        "occurred_at": waiver["confirmed_at"],
        "details": {
            "waiver_id": waiver["waiver_id"],
            "node": node,
            "requirement_id": args.requirement,
        },
    })
    output = Path(args.output) if args.output else source
    write_state(output, state, source=source, operation=f"waiver-{node}-{args.requirement}")
    print(json.dumps(waiver, ensure_ascii=False, indent=2))
    return 0


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--state", required=True)
    parser.add_argument("--graph", default=str(DEFAULT_GRAPH))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="劳动争议办案工作图")
    sub = root.add_subparsers(dest="command", required=True)
    route = sub.add_parser("route")
    add_common(route)
    route.set_defaults(func=command_route)
    transition = sub.add_parser("transition")
    add_common(transition)
    transition.add_argument("--event", required=True, choices=["pass", "return", "pause", "escalate", "approved", "resume"])
    transition.add_argument("--actor", required=True)
    transition.add_argument("--started-at")
    transition.add_argument("--note")
    transition.add_argument("--resume-condition")
    transition.add_argument("--input-artifact", action="append", default=[])
    transition.add_argument("--output-artifact", action="append", default=[])
    transition.add_argument("--output", help="默认就地更新 --state，旧状态存入 .casework/history/")
    transition.set_defaults(func=command_transition)
    approve = sub.add_parser("approve")
    add_common(approve)
    approve.add_argument("--gate", required=True, choices=["strategy_approval", "lawyer_approval"])
    approve.add_argument("--status", required=True, choices=["approved", "returned", "rejected"])
    approve.add_argument("--approved-by", required=True)
    approve.add_argument("--scope", action="append", required=True)
    approve.add_argument("--note")
    approve.add_argument("--output", help="默认就地更新 --state，旧状态存入 .casework/history/")
    approve.set_defaults(func=command_approve)
    artifact = sub.add_parser("register-artifact")
    add_common(artifact)
    artifact.add_argument("--path", required=True)
    artifact.add_argument("--kind", required=True)
    artifact.add_argument("--version", required=True)
    artifact.add_argument("--created-by", required=True)
    artifact.add_argument("--artifact-id")
    artifact.add_argument("--derived-from", action="append", default=[])
    artifact.add_argument("--output", help="默认就地更新 --state，旧状态存入 .casework/history/")
    artifact.set_defaults(func=command_artifact)
    validation = sub.add_parser("record-validation")
    add_common(validation)
    validation.add_argument("--kind", required=True, choices=["deterministic", "adversarial", "authority_second_pass"])
    validation.add_argument("--validator", required=True)
    validation.add_argument("--status", choices=["pass", "return", "pause", "escalate", "blocked"])
    validation.add_argument("--report")
    validation.add_argument("--artifact-id", action="append", default=[])
    validation.add_argument("--note")
    validation.add_argument("--output", help="默认就地更新 --state，旧状态存入 .casework/history/")
    validation.set_defaults(func=command_record_validation)
    waiver = sub.add_parser("record-waiver")
    add_common(waiver)
    waiver.add_argument("--requirement", required=True)
    waiver.add_argument("--reason", required=True)
    waiver.add_argument("--confirmed-by", required=True)
    waiver.add_argument("--output", help="默认就地更新 --state，旧状态存入 .casework/history/")
    waiver.set_defaults(func=command_record_waiver)
    return root


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
