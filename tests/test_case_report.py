"""《案件研判报告》的固定骨架、写作校验与 JLS 版式。"""

from __future__ import annotations

import copy
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
GENERATOR = SCRIPTS / "generate_docs.py"
STYLE = SCRIPTS / "docx_style.py"
LINT = SCRIPTS / "report_lint.py"
FIXTURE = ROOT / "tests" / "fixtures" / "case-report.json"
REPORT_NAME = "01_案件研判报告_律师复核稿_v1"

sys.path.insert(0, str(SCRIPTS))
import build_report_input  # noqa: E402
import generate_docs  # noqa: E402
import report_lint  # noqa: E402


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def rules(result: dict, severity: str | None = None) -> set[str]:
    return {item["rule"] for item in result["findings"] if severity is None or item["severity"] == severity}


class CaseReportLintTest(unittest.TestCase):
    def test_clean_report_passes(self):
        result = report_lint.lint_report(load_fixture()["report"])
        self.assertEqual(result["status"], "pass", result["findings"])
        self.assertLess(result["body_chars"], result["body_limit"])

    def test_jargon_patches_symbols_and_claim_map_are_blocked(self):
        report = load_fixture()["report"]
        report["决策摘要"]["结论"].append("最高价值的结果是把2N打成0，这一点单独不足以翻盘。")
        report["争点"][0]["段落"].append("但必须清楚：依据解释一§44，单位负举证责任，见《劳动合同法》第39条。")
        report["论点清单"].append({"论点": "公示方式不限于显著位置", "位置": "I2"})
        report["论点清单"].append({"论点": "不存在的位置", "位置": "I9"})
        result = report_lint.lint_report(report)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue({"行话", "补丁句", "条文写法", "简称", "论点清单"} <= rules(result, "high"))
        messages = "\n".join(item["message"] for item in result["findings"])
        self.assertIn("二倍经济补偿标准的赔偿金", messages)
        self.assertIn("被重复登记", messages)
        self.assertIn("不存在", messages)

    def test_claim_map_is_required(self):
        report = load_fixture()["report"]
        del report["论点清单"]
        self.assertIn("论点清单", rules(report_lint.lint_report(report), "high"))

    def test_length_and_first_page_budget(self):
        report = load_fixture()["report"]
        filler = "测试用人单位应当就解除劳动合同的事实依据承担举证责任，本段用于测试篇幅上限。"
        report["争点"][0]["段落"].extend(f"第{index}段：{filler}" for index in range(120))
        report["决策摘要"]["结论"].append(filler * 30)
        result = report_lint.lint_report(report)
        self.assertTrue({"篇幅", "首页"} <= rules(result, "high"))
        relaxed = report_lint.lint_report(load_fixture()["report"], body_limit=500)
        self.assertIn("篇幅", rules(relaxed, "high"))

    def test_duplicated_reasoning_across_sections_is_reported(self):
        report = load_fixture()["report"]
        repeated = report["争点"][1]["段落"][0]
        report["策略"].append(repeated)
        result = report_lint.lint_report(report)
        self.assertIn("重复", rules(result, "medium"))

    def test_statute_citation_shared_with_appendix_is_not_duplication(self):
        result = report_lint.lint_report(load_fixture()["report"])
        self.assertNotIn("重复", rules(result))

    def test_full_titles_do_not_count_as_undeclared_abbreviations(self):
        report = load_fixture()["report"]
        report["策略"].append("《中华人民共和国劳动合同法实施条例》第二十五条规定赔偿金的计算年限自用工之日起计算。")
        self.assertNotIn("简称", rules(report_lint.lint_report(report)))

    def test_markdown_escaping_keeps_numbered_lines_as_plain_paragraphs(self):
        self.assertEqual(generate_docs.md_paragraph("1. 调取原件。"), "1\\. 调取原件。")
        self.assertEqual(generate_docs.md_paragraph("- 列表"), "\\- 列表")
        self.assertEqual(generate_docs.md_paragraph("**关键句。**"), "**关键句。**")


class CaseReportDocxTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(shutil.which("pandoc"), "研判报告 DOCX 测试需要安装 Pandoc。")

    @staticmethod
    def run_cli(script: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *arguments], cwd=ROOT,
            text=True, capture_output=True, check=False,
        )

    def generate(self, root: Path, content: dict, *extra: str) -> subprocess.CompletedProcess[str]:
        case_path = root / "case.json"
        case_path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.run_cli(
            GENERATOR, "--case", str(case_path), "--output", str(root),
            "--types", "研判报告", "--strict", *extra,
        )

    def test_report_renders_with_fixed_skeleton_page_numbers_and_outline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self.generate(root, load_fixture())
            self.assertEqual(result.returncode, 0, result.stderr)
            docx = root / "01_律师复核初稿" / f"{REPORT_NAME}.docx"
            self.assertTrue(docx.exists())

            style = json.loads(self.run_cli(
                STYLE, "check", "--input", str(docx), "--document-type", "研判报告",
            ).stdout)
            self.assertEqual(style["status"], "pass", style["findings"])

            work = root / ".casework" / "drafting"
            lint = json.loads((work / f"{REPORT_NAME}_写作校验.json").read_text(encoding="utf-8"))
            self.assertEqual(lint["status"], "pass")
            markdown = (work / f"{REPORT_NAME}.md").read_text(encoding="utf-8")
            positions = [markdown.index(heading) for heading in (
                "一、决策摘要", "二、争点分析", "三、金额与期限", "四、策略与建议", "\n附件\n",
            )]
            self.assertEqual(positions, sorted(positions))

            with ZipFile(docx) as archive:
                document = archive.read("word/document.xml").decode("utf-8")
                footer = archive.read("word/footer_laborpilot.xml").decode("utf-8")
            self.assertIn('w:outlineLvl w:val="0"', document)
            self.assertIn('w:outlineLvl w:val="1"', document)
            self.assertIn("tblHeader", document)
            self.assertIn("PAGE", footer)

            reread = json.loads(self.run_cli(LINT, "--docx", str(docx)).stdout)
            self.assertNotEqual(reread["status"], "blocked", reread["findings"])

    def test_generation_stops_before_docx_when_writing_check_blocks(self):
        content = load_fixture()
        content["report"]["策略"].append("宜作和解筹码，把2N压下来。")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self.generate(root, content)
            self.assertEqual(result.returncode, 1)
            self.assertIn("写作校验未通过", result.stderr)
            self.assertFalse(any((root / "01_律师复核初稿").glob("*.docx")))
            lint = json.loads(
                (root / ".casework" / "drafting" / f"{REPORT_NAME}_写作校验.json").read_text(encoding="utf-8")
            )
            self.assertEqual(lint["status"], "blocked")

    def test_report_is_internal_and_requires_report_object(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            final = self.generate(
                root, load_fixture(), "--delivery-status", "final_submission", "--approved-by", "测试律师",
            )
            self.assertEqual(final.returncode, 2)
            self.assertIn("内部工作文件", final.stderr)
            content = copy.deepcopy(load_fixture())
            del content["report"]
            missing = self.generate(root, content)
            self.assertEqual(missing.returncode, 2)
            self.assertIn("report 对象", missing.stderr)

    @staticmethod
    def docx_text(path: Path) -> str:
        with ZipFile(path) as archive:
            document = archive.read("word/document.xml").decode("utf-8")
        return "".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", document))

    def test_markdown_special_characters_survive_conversion(self):
        content = load_fixture()
        literal = "计算式为11554.86*17.5*2，期间为2008~2024年，金额在$100至$200之间，另见<附表>和^注^。"
        content["report"]["争点"][0]["段落"].append(literal)
        content["report"]["金额"][0]["说明"] = "10000*3.5*2"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self.generate(root, content)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = self.docx_text(root / "01_律师复核初稿" / f"{REPORT_NAME}.docx")
        unescaped = html.unescape(text)
        self.assertIn(literal, unescaped)
        self.assertIn("10000*3.5*2", unescaped)

    def test_arbitration_formula_and_facts_are_not_reinterpreted_as_markdown(self):
        case = {"申请人": "测试劳动者（虚构）", "事实与理由": "2020~2024年期间，<待核>工资按8000*12计算。"}
        claims = [{"事项": "违法解除劳动合同赔偿金", "金额": 1000.0, "计算式": "10000*3.5*2"}]
        markdown = generate_docs.generate_arbitration(case, claims)
        plain = subprocess.run(
            ["pandoc", "--from=markdown", "--to=plain", "--wrap=none"],
            input=markdown, text=True, capture_output=True, check=True,
        ).stdout
        self.assertIn("2020~2024年期间，<待核>工资按8000*12计算。", plain)
        self.assertIn("（10000*3.5*2）", plain)

    def test_ooxml_child_order_is_normalized_and_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(self.generate(root, load_fixture()).returncode, 0)
            docx = root / "01_律师复核初稿" / f"{REPORT_NAME}.docx"
            with ZipFile(docx) as archive:
                files = {name: archive.read(name) for name in archive.namelist()}
            document = files["word/document.xml"].decode("utf-8")
            ordered = re.search(r"<w:rPr><w:rFonts [^>]*/><w:b w:val=\"1\" /><w:bCs w:val=\"1\" />"
                                r"<w:sz w:val=\"\d+\" /><w:szCs w:val=\"\d+\" /></w:rPr>", document)
            self.assertIsNotNone(ordered, "加粗标记应排在字号之前")
            swapped = re.sub(
                r"(<w:b w:val=\"1\" /><w:bCs w:val=\"1\" />)(<w:sz w:val=\"\d+\" /><w:szCs w:val=\"\d+\" />)",
                r"\2\1", document, count=1,
            )
            files["word/document.xml"] = swapped.encode("utf-8")
            tampered = root / "tampered.docx"
            with ZipFile(tampered, "w") as archive:
                for name, content in files.items():
                    archive.writestr(name, content)
            result = json.loads(self.run_cli(
                STYLE, "check", "--input", str(tampered), "--document-type", "研判报告",
            ).stdout)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("<rPr> 的子元素顺序" in item for item in result["findings"]))

    def test_new_version_that_grows_is_flagged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(self.generate(root, load_fixture()).returncode, 0)
            longer = load_fixture()
            longer["report"]["策略"].append("测试用人单位还应当在二审开庭前完成证人出庭的准备工作。")
            result = self.generate(root, longer, "--version", "2")
            self.assertEqual(result.returncode, 0, result.stderr)
            lint = json.loads((
                root / ".casework" / "drafting" / "01_案件研判报告_律师复核稿_v2_写作校验.json"
            ).read_text(encoding="utf-8"))
        self.assertEqual(lint["previous_version"]["version"], 1)
        self.assertIn("篇幅增长", rules(lint, "medium"))
        self.assertEqual(lint["status"], "warn")

    def test_existing_docx_with_wide_table_and_shorthand_is_blocked(self):
        markdown = "\n".join([
            "案件研判报告", "",
            "一、结论", "",
            "现实预期：维持原判概率最高，最高价值的结果不是把2N打成0。", "",
            "| 争点 | 我方论点 | 对方反驳 | 依据 | 胜算 |",
            "|---|---|---|---|---|",
            "| 公示 | 无显著位置要件 | 无签收 | 劳动合同法§4④；解释一§44 | 中低 |",
            "",
        ])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "legacy.md"
            target = root / "legacy.docx"
            source.write_text(markdown, encoding="utf-8")
            subprocess.run(["pandoc", str(source), "-o", str(target)], check=True)
            result = self.run_cli(LINT, "--docx", str(target))
            self.assertEqual(result.returncode, 1)
            findings = json.loads(result.stdout)
            self.assertTrue({"表格", "行话", "条文写法", "简称"} <= rules(findings, "high"))
            self.assertIn("标签段首", rules(findings, "medium"))


def scaffold_state() -> dict:
    rule = {
        "issue_id": "I1", "document_title": "中华人民共和国劳动合同法", "article_number": "4",
        "article_text": "用人单位应当将直接涉及劳动者切身利益的规章制度和重大事项决定公示，或者告知劳动者。",
        "verification_status": "verified", "adoption_status": "adopted",
        "applicability_status": "applicable", "validity_status": "effective",
    }
    return {
        "stage": "second_instance", "representation": "employer", "analysis_date": "2026-10-16",
        "issues": [
            {"issue_id": "I1", "issue": "《员工手册》是否已向劳动者公示", "analysis_status": "reviewed",
             "our_position": "法律未要求置于显著位置", "opponent_position": "无签收记录",
             "failure_consequence": "解除被认定违法"},
            {"issue_id": "I9", "issue": "尚未复核的候选争点", "analysis_status": "to_review"},
        ],
        "rules": [
            dict(rule, rule_id="R1"),
            dict(rule, rule_id="R2"),
            dict(rule, rule_id="R3", article_number="第39条第2项", adoption_status="reference_only"),
            dict(rule, rule_id="R4", document_title="已废止的地方解答", article_number="11",
                 validity_status="repealed", adoption_status="adopted"),
        ],
        "calculations": [
            {"calculation_id": "C1", "name": "违法解除劳动合同赔偿金", "status": "calculated",
             "amount": 70000.0, "expression": "10,000元／月×3.5个月×2"},
            {"calculation_id": "C2", "name": "未休年休假工资", "status": "needs_confirmation",
             "pending_inputs": ["未休天数"]},
        ],
        "procedural_assessments": [{"issue_id": "I1", "limitation": {"deadline_date": "2027-04-08"}}],
    }


class ReportInputScaffoldTest(unittest.TestCase):
    def test_scaffold_prefills_state_and_leaves_reasoning_to_author(self):
        report = build_report_input.build_report_input(scaffold_state())["report"]
        self.assertEqual((report["程序阶段"], report["代理立场"]), ("二审", "用人单位"))
        self.assertEqual([issue["id"] for issue in report["争点"]], ["I1"])
        self.assertEqual(report["争点"][0]["_写作参考"]["已核验法源"][0], "《中华人民共和国劳动合同法》第四条")
        authorities = report["附件"]["法律依据"]
        self.assertEqual([item["条文"] for item in authorities], ["第四条", "第十一条（已废止）"])
        self.assertEqual(report["金额"][0]["金额"], 70000.0)
        self.assertIn("未休天数", report["金额"][1]["说明"])
        self.assertEqual(report["期限"], ["关于《员工手册》是否已向劳动者公示，时效截止日为2027年4月8日。"])
        self.assertEqual(build_report_input.article_label("第39条第2项"), "第三十九条第二项")
        self.assertEqual(build_report_input.cn_number(105), "一百零五")
        blocked = report_lint.lint_report(report)
        self.assertTrue({"占位未填", "论点清单"} <= rules(blocked, "high"))

    def test_scaffold_cli_does_not_overwrite_and_filled_input_generates(self):
        self.assertIsNotNone(shutil.which("pandoc"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / ".casework" / "case_state.json"
            state.parent.mkdir(parents=True)
            state.write_text(json.dumps(scaffold_state(), ensure_ascii=False), encoding="utf-8")
            command = [sys.executable, str(SCRIPTS / "build_report_input.py"), "--state", str(state),
                       "--case-name", "测试用人单位（虚构）与测试劳动者（虚构）劳动争议案"]
            first = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
            self.assertEqual(first.returncode, 0, first.stderr)
            again = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
            self.assertEqual(again.returncode, 2)
            self.assertIn("避免覆盖", again.stderr)

            path = root / ".casework" / "drafting" / "report_input.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            report = data["report"]
            report["决策摘要"]["结论"] = ["二审维持原判的可能性较大，测试用人单位应以补充证据推动调解。"]
            report["争点"][0]["段落"] = [
                "二审纠正一审关于公示方式的认定的可能性较高，但仅凭该项理由难以改变解除违法的结论。"
                "《中华人民共和国劳动合同法》第四条未限定公示的载体和位置，测试用人单位仍须证明已实际公示或者告知。"
            ]
            report["争点"][0]["一览"] = {"我方主要理由": "法律未要求置于显著位置", "主要障碍": "无签收记录",
                                     "评估": "单凭此项改判的可能性较低"}
            report["策略"] = ["建议以补充证据为基础推动二审调解。"]
            report["论点清单"] = [{"论点": "公示方式不限于显著位置", "位置": "I1"},
                               {"论点": "以补充证据推动调解", "位置": "策略与建议"}]
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(GENERATOR), "--case", str(path), "--output", str(root),
                 "--types", "研判报告", "--strict"],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / "01_律师复核初稿" / f"{REPORT_NAME}.docx").exists())


if __name__ == "__main__":
    unittest.main()
