#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 case_state 生成《案件研判报告》的输入脚手架。

预填可以从案件状态确定的内容：程序阶段、代理立场、分析基准日、已复核争点、
金额台账、时效截止日，以及已核验、已采用且适用的法条全文（进入附件）。
论证段落、可能结果和论点清单留下“【待撰写：……】”占位，由起草者填写；
占位未填时 report_lint.py 会阻断生成。结构见 references/case-report-contract.md。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


STAGES = {
    "intake": "接案", "pre_arbitration": "仲裁前", "arbitration": "仲裁",
    "first_instance": "一审", "second_instance": "二审", "closure": "结案",
}
REPRESENTATIONS = {"employee": "劳动者", "employer": "用人单位"}
VALIDITY = {
    "amended": "已修改", "repealed": "已废止", "expired": "已失效",
    "not_yet_effective": "尚未生效", "unknown": "效力待核",
}
CN_DIGITS = "零一二三四五六七八九"
PLACEHOLDER = {
    "结论": "【待撰写：结论在前并写明把握程度；只写在争点分析中有唯一出处的结论。】",
    "争点": "【待撰写：依次写结论及把握程度、规范依据、本案事实与证据现状、对方最强观点及回应、判断及会改变判断的条件。】",
    "一览": "【待撰写】",
    "策略": "【待撰写：调解、和解与后续程序安排。】",
}


def cn_number(value: int) -> str:
    """1—9999 的阿拉伯数字转中文数字，用于条号。"""
    if value < 10:
        return CN_DIGITS[value]
    units = [(1000, "千"), (100, "百"), (10, "十")]
    result, zero = "", False
    for unit, name in units:
        digit, value = divmod(value, unit)
        if digit:
            if zero:
                result += "零"
                zero = False
            result += ("" if unit == 10 and digit == 1 and not result else CN_DIGITS[digit]) + name
        elif result:
            zero = True
    if value:
        result += ("零" if zero else "") + CN_DIGITS[value]
    return result


def article_label(value: Any) -> str:
    """条号统一为中文数字：“39”“第39条”均写作“第三十九条”。"""
    text = str(value or "").strip()
    if re.fullmatch(r"\d+", text):
        return f"第{cn_number(int(text))}条"
    return re.sub(r"第(\d+)(条|款|项)", lambda m: f"第{cn_number(int(m.group(1)))}{m.group(2)}", text)


def readable_date(value: Any) -> str:
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", str(value or "").strip())
    if not match:
        return str(value or "")
    year, month, day = match.groups()
    return f"{year}年{int(month)}月{int(day)}日"


def book_title(value: Any) -> str:
    title = str(value or "").strip()
    return title if title.startswith("《") else f"《{title}》"


def reviewed_issues(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [issue for issue in state.get("issues") or [] if issue.get("analysis_status") == "reviewed"]


def adopted_rules(state: dict[str, Any]) -> list[dict[str, Any]]:
    """只取已核验、已采用且适用的法源；参考性或排除的法源不进入报告。"""
    return [
        rule for rule in state.get("rules") or []
        if rule.get("verification_status") == "verified"
        and rule.get("adoption_status") == "adopted"
        and rule.get("applicability_status") == "applicable"
        and str(rule.get("article_text") or "").strip()
    ]


def authority_entries(rules: list[dict[str, Any]]) -> list[dict[str, str]]:
    entries, seen = [], set()
    for rule in rules:
        key = (rule.get("document_title"), rule.get("article_number"))
        if key in seen:
            continue
        seen.add(key)
        article = article_label(rule.get("article_number"))
        status = VALIDITY.get(str(rule.get("validity_status") or ""))
        if status:
            article += f"（{status}）"
        entries.append({
            "名称": book_title(rule.get("document_title")),
            "条文": article,
            "原文": str(rule.get("article_text")).strip(),
        })
    return entries


def amount_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for calculation in state.get("calculations") or []:
        name = calculation.get("name") or calculation.get("calculation_id")
        if calculation.get("status") == "calculated" and calculation.get("amount") is not None:
            rows.append({"项目": name, "金额": calculation["amount"], "说明": calculation.get("expression") or ""})
        else:
            pending = "、".join(str(item) for item in calculation.get("pending_inputs") or []) or "计算输入"
            rows.append({"项目": name, "金额": "【待确认】", "说明": f"【待确认：{pending}】"})
    return rows


def deadline_paragraphs(state: dict[str, Any], titles: dict[str, str]) -> list[str]:
    paragraphs = []
    for assessment in state.get("procedural_assessments") or []:
        limitation = assessment.get("limitation") or {}
        deadline = limitation.get("deadline_date")
        if not deadline:
            continue
        title = titles.get(assessment.get("issue_id"), "该争点")
        paragraphs.append(f"关于{title}，时效截止日为{readable_date(deadline)}。")
    return paragraphs


def build_report_input(state: dict[str, Any], *, case_name: str | None = None) -> dict[str, Any]:
    issues = reviewed_issues(state)
    titles = {issue.get("issue_id"): str(issue.get("issue") or issue.get("issue_id")) for issue in issues}
    rules = adopted_rules(state)
    report: dict[str, Any] = {
        "案件名称": case_name or "【待确认：案件名称】",
        "程序阶段": STAGES.get(str(state.get("stage")), "【待确认：程序阶段】"),
        "代理立场": REPRESENTATIONS.get(str(state.get("representation")), "【待确认：代理立场】"),
        "分析基准日": state.get("analysis_date") or "【待确认：分析基准日】",
        "篇幅上限": 4000,
        "决策摘要": {"结论": [PLACEHOLDER["结论"]], "可能结果": [], "紧急事项": []},
        "争点": [],
        "金额": amount_rows(state),
        "期限": deadline_paragraphs(state, titles),
        "策略": [PLACEHOLDER["策略"]],
        "论点清单": [],
        "附件": {"法律依据": authority_entries(rules), "其他": []},
    }
    for issue in issues:
        issue_id = issue.get("issue_id")
        references = [
            f"{book_title(rule.get('document_title'))}{article_label(rule.get('article_number'))}"
            for rule in rules if rule.get("issue_id") == issue_id
        ]
        report["争点"].append({
            "id": issue_id,
            "标题": titles[issue_id],
            "一览": {key: PLACEHOLDER["一览"] for key in ("我方主要理由", "主要障碍", "评估")},
            "段落": [PLACEHOLDER["争点"]],
            "_写作参考": {
                "我方路径": issue.get("our_position"),
                "对方最强观点": issue.get("opponent_position"),
                "备选路径": issue.get("alternative_paths"),
                "失败后果": issue.get("failure_consequence"),
                "已核验法源": references,
            },
        })
    return {
        "_说明": (
            "本文件由 build_report_input.py 从 case_state 生成。金额、期限和附件法源来自已复核的案件状态，"
            "不得手工改写数值或条文；【待撰写】处由起草者按 references/case-report-contract.md 填写，"
            "并在论点清单中列出全部论点及其唯一位置。_写作参考 字段只供起草，不进入报告。"
        ),
        "case": {},
        "report": report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="从 case_state 生成《案件研判报告》输入脚手架")
    parser.add_argument("--state", required=True, help="<case-root>/.casework/case_state.json")
    parser.add_argument("--output", help="输出路径；默认 <case-root>/.casework/drafting/report_input.json")
    parser.add_argument("--case-name", help="报告中的案件名称")
    args = parser.parse_args()
    state_path = Path(args.state)
    output = Path(args.output) if args.output else state_path.parent / "drafting" / "report_input.json"
    if output.exists():
        parser.error(f"为避免覆盖既有输入，目标已存在：{output}")
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        parser.error(f"无法读取案件状态：{exc}")
    data = build_report_input(state, case_name=args.case_name)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = data["report"]
    print(f"已生成研判报告输入脚手架：{output}")
    print(f"  争点 {len(report['争点'])} 个，金额 {len(report['金额'])} 项，期限 {len(report['期限'])} 项，"
          f"附件法源 {len(report['附件']['法律依据'])} 条；【待撰写】处须由起草者填写。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
