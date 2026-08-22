"""LaborPilot 八个公开领域场景的争点召回回归测试。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
ROUTER_PATH = ROOT / "scripts" / "issue_router.py"
EVALS_PATH = ROOT / "evals" / "evals.json"
SPEC = importlib.util.spec_from_file_location("laborpilot_domain_eval_router", ROUTER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"无法加载知识路由脚本：{ROUTER_PATH}")
ROUTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ROUTER)


class DomainEvalsTest(unittest.TestCase):
    def test_all_domain_prompts_recall_their_core_issues(self):
        payload = json.loads(EVALS_PATH.read_text(encoding="utf-8"))

        for case in payload["evals"]:
            with self.subTest(eval_id=case["id"]):
                results = ROUTER.query_knowledge(case["prompt"])
                issue_text = "\n".join(item["issue"] for item in results)
                self.assertTrue(results, "领域场景没有召回任何争点")
                for term in case["expected_issue_terms"]:
                    self.assertIn(term, issue_text)


if __name__ == "__main__":
    unittest.main()
