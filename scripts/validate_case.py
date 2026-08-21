#!/usr/bin/env python3
"""对案件图状态执行独立的确定性一致性检查。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from case_state import read_json, validate_state
from workflow_graph import DEFAULT_GRAPH, task_context_errors, workflow_blockers


def finding(code: str, severity: str, message: str, affected: list[str] | None = None) -> dict[str, Any]:
    return {"code": code, "severity": severity, "message": message, "affected_nodes": affected or []}


def ids(items: Any, key: str) -> set[str]:
    if not isinstance(items, list):
        return set()
    return {item.get(key) for item in items if isinstance(item, dict) and isinstance(item.get(key), str)}


def approved(state: dict[str, Any], gate: str) -> bool:
    return any(
        isinstance(item, dict)
        and item.get("gate") == gate
        and item.get("status") == "approved"
        for item in state.get("approvals", [])
    )


def validate_artifacts(state: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    for index, artifact in enumerate(state.get("artifacts", [])):
        if not isinstance(artifact, dict):
            findings.append(finding("ARTIFACT_OBJECT", "blocker", f"artifacts[{index}] 不是 object。"))
            continue
        path = Path(str(artifact.get("path", ""))).expanduser()
        if not path.is_file():
            findings.append(finding("ARTIFACT_MISSING", "high", f"产物文件不存在：{path}。", ["validation"]))
            continue
        expected = artifact.get("sha256")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if expected != actual:
            findings.append(finding("ARTIFACT_HASH", "high", f"产物哈希与登记值不一致：{path}。", ["validation"]))


def validate_links(state: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    fact_ids = ids(state.get("facts"), "fact_id")
    evidence_ids = ids(state.get("evidence"), "evidence_id")
    issue_ids = ids(state.get("issues"), "issue_id")
    rule_ids = ids(state.get("rules"), "rule_id") | ids(state.get("rules"), "article_id")
    for index, claim in enumerate(state.get("claims", [])):
        if not isinstance(claim, dict):
            continue
        for field, known, code in [
            ("fact_ids", fact_ids, "CLAIM_FACT_LINK"),
            ("evidence_ids", evidence_ids, "CLAIM_EVIDENCE_LINK"),
            ("issue_ids", issue_ids, "CLAIM_ISSUE_LINK"),
            ("rule_ids", rule_ids, "CLAIM_RULE_LINK"),
        ]:
            refs = claim.get(field, [])
            if refs is not None and not isinstance(refs, list):
                findings.append(finding(code, "high", f"claims[{index}].{field} 必须是数组。", ["issue_analysis"]))
                continue
            invalid = [ref for ref in refs or [] if not isinstance(ref, str)]
            if invalid:
                findings.append(finding(code, "high", f"claims[{index}].{field} 只能包含字符串 ID。", ["issue_analysis"]))
            missing = sorted({ref for ref in refs or [] if isinstance(ref, str)} - known)
            if missing:
                findings.append(finding(code, "high", f"claims[{index}].{field} 引用不存在的 ID：{', '.join(missing)}。", ["issue_analysis"]))
        if claim.get("amount") is not None and not claim.get("calculation_id"):
            findings.append(finding("CLAIM_CALCULATION", "high", f"claims[{index}] 含金额但缺少 calculation_id。", ["claims_procedure"]))


def validate_rules(state: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    for index, rule in enumerate(state.get("rules", [])):
        if not isinstance(rule, dict):
            continue
        if rule.get("verification_status") == "verified" and (not rule.get("document_id") or not rule.get("article_id")):
            findings.append(finding("RULE_ANCHOR", "high", f"rules[{index}] 标记已验证但缺少 document_id 或 article_id。", ["authority_research"]))
        if rule.get("validity_status") in {"已废止", "repealed"} and not rule.get("warning"):
            findings.append(finding("RULE_REPEALED", "blocker", f"rules[{index}] 使用已废止规则但未显式警示。", ["authority_research"]))


def validate_gates(state: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    node = state.get("current_node")
    after_strategy = {"drafting", "validation", "lawyer_approval", "stage_close"}
    if node in after_strategy and not approved(state, "strategy_approval"):
        findings.append(finding("STRATEGY_GATE", "blocker", "起草或后续节点缺少策略审批。", ["strategy_approval"]))
    if node == "stage_close" and not approved(state, "lawyer_approval"):
        findings.append(finding("LAWYER_GATE", "blocker", "阶段结案前缺少律师交付审批。", ["lawyer_approval"]))
    if node in {"lawyer_approval", "stage_close"} and not any(
        isinstance(item, dict) and item.get("status") == "pass"
        for item in state.get("validations", [])
    ):
        findings.append(finding("VALIDATION_GATE", "blocker", "交付审批前缺少已通过的独立验证。", ["validation"]))


def validate_material_traceability(state: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    for index, material in enumerate(state.get("materials", [])):
        if not isinstance(material, dict):
            continue
        if material.get("source_path") and not material.get("source_sha256"):
            findings.append(finding(
                "MATERIAL_HASH", "high",
                f"materials[{index}] 已登记原始路径但缺少 source_sha256。",
                ["material_ingestion"],
            ))
        if material.get("ocr_status") in {"partial", "completed"} and not material.get("derivative_path"):
            findings.append(finding(
                "OCR_DERIVATIVE", "high",
                f"materials[{index}] 已记录 OCR 结果但缺少 derivative_path。",
                ["material_ingestion"],
            ))


def validate_workflow_state(state: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    graph = read_json(DEFAULT_GRAPH)
    if state.get("current_node") == "task_intake":
        for message in task_context_errors(state):
            findings.append(finding("TASK_CONTEXT", "blocker", message, ["task_intake"]))
    for message in workflow_blockers(state, graph):
        findings.append(finding("WORKFLOW_REACHABILITY", "blocker", message, ["workflow"]))


def main() -> int:
    parser = argparse.ArgumentParser(description="劳动争议案件独立确定性验证")
    parser.add_argument("--state", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    state = read_json(Path(args.state))
    findings: list[dict[str, Any]] = []
    for message in validate_state(state):
        findings.append(finding("STATE_SCHEMA", "blocker", message))
    if isinstance(state, dict):
        validate_artifacts(state, findings)
        validate_links(state, findings)
        validate_rules(state, findings)
        validate_gates(state, findings)
        validate_material_traceability(state, findings)
        validate_workflow_state(state, findings)
    severities = {item["severity"] for item in findings}
    status = "blocked" if "blocker" in severities else "return" if "high" in severities else "pass"
    result = {"status": status, "validator": "deterministic", "findings": findings}
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = Path(args.output)
        if output.exists():
            raise SystemExit(f"拒绝覆盖已有文件：{output}")
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
