"""工作图业务节点完成条件的反例与完整流程回归。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CASE_STATE = ROOT / "scripts" / "case_state.py"
WORKFLOW = ROOT / "scripts" / "workflow_graph.py"
VALIDATE = ROOT / "scripts" / "validate_case.py"


class WorkflowRequirementsTest(unittest.TestCase):
    def run_cli(self, script: Path, *arguments: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(script), *arguments],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            expected,
            f"命令退出码异常：{result.args}\nstdout={result.stdout}\nstderr={result.stderr}",
        )
        return result

    def initialize_confirmed_case(self, state_path: Path) -> None:
        self.run_cli(CASE_STATE, "init", "--output", str(state_path))
        self.run_cli(
            CASE_STATE,
            "set-task",
            "--input", str(state_path),
            "--representation", "employee",
            "--stage", "arbitration",
            "--user-request", "分析劳动争议并起草仲裁申请书",
            "--requested-output", "仲裁申请书",
            "--confirmed-by", "user",
        )
        self.run_cli(
            WORKFLOW,
            "transition",
            "--state", str(state_path),
            "--event", "pass",
            "--actor", "test",
        )

    def test_empty_business_state_is_blocked_but_confirmed_waiver_is_structured(self):
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "case_state.json"
            self.initialize_confirmed_case(state_path)

            blocked = self.run_cli(
                WORKFLOW,
                "transition",
                "--state", str(state_path),
                "--event", "pass",
                "--actor", "test",
                expected=2,
            )
            self.assertIn("traceable_material", blocked.stderr)

            self.run_cli(
                WORKFLOW,
                "record-waiver",
                "--state", str(state_path),
                "--requirement", "traceable_material",
                "--reason", "用户确认本轮仅基于对话文本分析，不提供文件材料。",
                "--confirmed-by", "user",
            )
            self.run_cli(
                WORKFLOW,
                "transition",
                "--state", str(state_path),
                "--event", "pass",
                "--actor", "test",
            )
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["current_node"], "intake")
            self.assertEqual(state["node_requirement_waivers"][0]["requirement_id"], "traceable_material")

    def test_manual_empty_stage_close_is_rejected_by_independent_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "case_state.json"
            self.initialize_confirmed_case(state_path)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["current_node"] = "stage_close"
            state["pending_nodes"] = []
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            result = self.run_cli(VALIDATE, "--state", str(state_path), expected=1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "blocked")
            messages = "\n".join(item["message"] for item in payload["findings"])
            self.assertIn("traceable_material", messages)
            self.assertIn("draft_artifact", messages)
            self.assertIn("report_backed_validations", messages)

    def test_valid_fixture_reaches_stage_close_and_validation_pass_requires_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            case_root = Path(temporary)
            state_path = case_root / "case_state.json"
            material_path = case_root / "material.txt"
            draft_path = case_root / "draft.md"
            material_path.write_text("劳动合同与解除通知", encoding="utf-8")
            draft_path.write_text("# 仲裁申请书初稿", encoding="utf-8")
            self.initialize_confirmed_case(state_path)

            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["materials"] = [{
                "material_id": "material-1",
                "source_path": str(material_path),
                "source_sha256": hashlib.sha256(material_path.read_bytes()).hexdigest(),
            }]
            state["facts"] = [{
                "fact_id": "fact-1",
                "statement": "劳动者陈述用人单位解除劳动合同。",
                "status": "client_statement",
                "sources": ["material-1"],
            }]
            state["issues"] = [{"issue_id": "issue-1", "issue": "解除是否合法"}]
            state["evidence"] = [{"evidence_id": "evidence-1", "name": "解除通知"}]
            state["rules"] = [{
                "rule_id": "rule-1",
                "verification_status": "verified",
                "validity_status": "现行有效",
                "document_id": "劳动合同法",
                "article_id": "第四十八条",
            }]
            state["claims"] = [{
                "claim_id": "claim-1",
                "description": "请求支付违法解除赔偿金",
                "amount": 100,
                "calculation_id": "calculation-1",
                "fact_ids": ["fact-1"],
                "evidence_ids": ["evidence-1"],
                "issue_ids": ["issue-1"],
                "rule_ids": ["rule-1"],
            }]
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            for expected_node in ("intake", "issue_analysis", "evidence_analysis", "authority_research", "claims_procedure"):
                self.run_cli(
                    WORKFLOW,
                    "transition",
                    "--state", str(state_path),
                    "--event", "pass",
                    "--actor", "test",
                )
                state = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertEqual(state["current_node"], expected_node)

            self.run_cli(
                WORKFLOW,
                "transition",
                "--state", str(state_path),
                "--event", "pass",
                "--actor", "test",
            )
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["current_node"], "strategy_approval")

            for gate, scopes in (
                (
                    "strategy_approval",
                    ["representation", "stage", "requested_document", "provisional_strategy"],
                ),
            ):
                arguments = [
                    "approve", "--state", str(state_path), "--gate", gate,
                    "--status", "approved", "--approved-by", "user",
                ]
                for scope in scopes:
                    arguments.extend(["--scope", scope])
                self.run_cli(WORKFLOW, *arguments)
            self.run_cli(
                WORKFLOW,
                "transition",
                "--state", str(state_path),
                "--event", "approved",
                "--actor", "test",
            )

            self.run_cli(
                WORKFLOW,
                "register-artifact",
                "--state", str(state_path),
                "--path", str(draft_path),
                "--kind", "legal_draft",
                "--version", "v1",
                "--created-by", "test",
                "--artifact-id", "draft-1",
            )
            self.run_cli(
                WORKFLOW,
                "transition",
                "--state", str(state_path),
                "--event", "pass",
                "--actor", "test",
                "--output-artifact", "draft-1",
            )

            missing_report = self.run_cli(
                WORKFLOW,
                "record-validation",
                "--state", str(state_path),
                "--kind", "deterministic",
                "--validator", "test",
                "--status", "pass",
                expected=2,
            )
            self.assertIn("必须提供", missing_report.stderr)

            missing_escalation_reports = self.run_cli(
                WORKFLOW,
                "transition",
                "--state", str(state_path),
                "--event", "escalate",
                "--actor", "test",
                expected=2,
            )
            self.assertIn("report_backed_validations", missing_escalation_reports.stderr)

            incomplete_report_path = case_root / "missing-status.json"
            incomplete_report_path.write_text(
                json.dumps({"findings": []}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            incomplete_report = self.run_cli(
                WORKFLOW,
                "record-validation",
                "--state", str(state_path),
                "--kind", "deterministic",
                "--validator", "test",
                "--status", "pass",
                "--report", str(incomplete_report_path),
                expected=2,
            )
            self.assertIn("status 和 findings", incomplete_report.stderr)

            for kind in ("deterministic", "adversarial"):
                report_path = case_root / f"{kind}.json"
                report_path.write_text(
                    json.dumps({"status": "pass", "findings": []}, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                self.run_cli(
                    WORKFLOW,
                    "record-validation",
                    "--state", str(state_path),
                    "--kind", kind,
                    "--validator", "test",
                    "--report", str(report_path),
                )
            self.run_cli(
                WORKFLOW,
                "transition",
                "--state", str(state_path),
                "--event", "pass",
                "--actor", "test",
            )

            arguments = [
                "approve", "--state", str(state_path), "--gate", "lawyer_approval",
                "--status", "approved", "--approved-by", "user",
            ]
            for scope in ("validated_draft", "residual_risks", "submission_decision"):
                arguments.extend(["--scope", scope])
            self.run_cli(WORKFLOW, *arguments)
            self.run_cli(
                WORKFLOW,
                "transition",
                "--state", str(state_path),
                "--event", "approved",
                "--actor", "test",
            )

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["current_node"], "stage_close")
            validation = self.run_cli(VALIDATE, "--state", str(state_path))
            self.assertEqual(json.loads(validation.stdout)["status"], "pass")

    def test_report_backed_validation_escalation_reaches_lawyer_approval(self):
        with tempfile.TemporaryDirectory() as temporary:
            case_root = Path(temporary)
            state_path = case_root / "case_state.json"
            draft_path = case_root / "draft.md"
            draft_path.write_text("# 律师复核初稿", encoding="utf-8")
            self.initialize_confirmed_case(state_path)

            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["current_node"] = "validation"
            state["materials"] = [{
                "material_id": "material-1",
                "source_path": str(case_root / "material.txt"),
                "source_sha256": "0" * 64,
            }]
            state["facts"] = [{
                "fact_id": "fact-1", "statement": "待律师复核的事实", "status": "to_verify", "sources": [],
            }]
            state["issues"] = [{"issue_id": "issue-1"}]
            state["evidence"] = [{"evidence_id": "evidence-1"}]
            state["rules"] = [{
                "rule_id": "rule-1", "verification_status": "verified",
                "document_id": "劳动合同法", "article_id": "第四十八条",
            }]
            state["claims"] = [{"claim_id": "claim-1", "amount": None}]
            state["approvals"] = [{
                "approval_id": "approval-strategy", "gate": "strategy_approval",
                "status": "approved", "approved_by": "user",
            }]
            state["artifacts"] = [{
                "artifact_id": "draft-1", "path": str(draft_path),
                "sha256": hashlib.sha256(draft_path.read_bytes()).hexdigest(),
            }]
            for node in (
                "material_ingestion", "intake", "issue_analysis", "evidence_analysis",
                "authority_research", "claims_procedure", "drafting",
            ):
                state["node_runs"].append({
                    "run_id": f"run-{node}", "node": node, "status": "passed",
                    "output_artifact_ids": ["draft-1"] if node == "drafting" else [],
                })
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            for kind, status in (("deterministic", "pass"), ("adversarial", "escalate")):
                report_path = case_root / f"{kind}.json"
                report_path.write_text(
                    json.dumps({"status": status, "findings": []}, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                self.run_cli(
                    WORKFLOW,
                    "record-validation",
                    "--state", str(state_path),
                    "--kind", kind,
                    "--validator", "test",
                    "--report", str(report_path),
                )

            self.run_cli(
                WORKFLOW,
                "transition",
                "--state", str(state_path),
                "--event", "escalate",
                "--actor", "test",
            )
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["current_node"], "lawyer_approval")
            route = self.run_cli(WORKFLOW, "route", "--state", str(state_path))
            self.assertEqual(json.loads(route.stdout)["status"], "ready")

            missing_approval = self.run_cli(
                WORKFLOW,
                "transition",
                "--state", str(state_path),
                "--event", "approved",
                "--actor", "test",
                expected=2,
            )
            self.assertIn("lawyer_approval", missing_approval.stderr)


if __name__ == "__main__":
    unittest.main()
