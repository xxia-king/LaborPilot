#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《案件研判报告》书面写作校验：篇幅、推理结构、语体与表格。

规则来源见 references/case-report-contract.md 与 references/writing-style.md。
只使用标准库；既可校验生成器的结构化输入（--input），也可直接校验已有
DOCX（--docx）。输出 JSON：status 为 pass、warn 或 blocked。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import sys
from typing import Any
from zipfile import BadZipFile, ZipFile

from xml_safe import UnsafeXMLError, fromstring as safe_fromstring


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DEFAULT_BODY_LIMIT = 4000
DEFAULT_SUMMARY_LIMIT = 900
TABLE_MAX_COLUMNS = 4
TABLE_CELL_MAX_CHARS = 40
DUPLICATE_WINDOW = 20
TOPIC_SPREAD_LIMIT = 3
FULL_BOLD_LIMIT = 3
SECTION_KEYS = ("决策摘要", "金额与期限", "策略与建议")
CN_DIGITS = "一二三四五六七八九十"
HEADING_PATTERN = re.compile(rf"^[{CN_DIGITS}]+、")
SUBHEADING_PATTERN = re.compile(rf"^（[{CN_DIGITS}]+）")
APPENDIX_PATTERN = re.compile(r"附件|附录")
CITATION_PATTERN = re.compile(
    r"《[^》]{1,60}》(?:（[^）]{1,30}）)?(?:第[一二三四五六七八九十百零]+[条款项]|第（[一二三四五六七八九十]+）项)*"
)

# 行话：明确的口语和自造缩写阻断生成；语义上偶有正当用法的只作提示。
JARGON_HIGH = (
    (r"(?<![A-Za-z0-9])2N(?![A-Za-z0-9])", "二倍经济补偿标准的赔偿金"),
    (r"(?<![A-Za-z0-9])N\+1(?![A-Za-z0-9])", "经济补偿及额外支付的一个月工资"),
    (r"(?<![A-Za-z0-9+])N(?![A-Za-z0-9+])", "经济补偿"),
    (r"翻盘", "改判／推翻原审结论"),
    (r"抓手", "依据／理由"),
    (r"讲透", "充分阐明"),
    (r"打成[0零]", "改判为无需支付"),
    (r"零认定", "未作认定"),
    (r"筹码", "协商条件"),
    (r"主攻", "主要理由"),
    (r"站得住", "成立／依据充分"),
    (r"对向风险", "对方上诉的风险"),
    (r"硬伤", "明显缺陷"),
    (r"坐实", "证实"),
    (r"撬动", "改用具体动词"),
    (r"打法", "策略"),
)
JARGON_MEDIUM = (
    (r"拉回|推回", "使……重新成为审理对象"),
    (r"真空期", "新规定出台前的适用问题"),
    (r"增量", "新增"),
    (r"胜算", "胜诉可能性"),
    (r"(?<!约)定价", "确定金额"),
    (r"突破口", "主要理由"),
)
# 未经“以下简称”声明不得使用的简称。
ABBREVIATIONS = (
    "解释一", "解释（一）", "解释二", "解释（二）", "民诉法解释", "民诉法",
    "实施条例", "解答（三）", "解答（五）", "解答三", "解答五",
)
# 首次出现须写全称（或先声明简称）的法律名称。
STATUTE_FULL_NAMES = {
    "劳动合同法": "中华人民共和国劳动合同法",
    "劳动法": "中华人民共和国劳动法",
    "民事诉讼法": "中华人民共和国民事诉讼法",
    "民法典": "中华人民共和国民法典",
    "劳动争议调解仲裁法": "中华人民共和国劳动争议调解仲裁法",
    "社会保险法": "中华人民共和国社会保险法",
}
# 复核意见以补丁段追加的典型句式。
PATCH_PHRASES = (
    "但必须清楚", "必须清楚：", "需如实指出", "另需评估", "另有一处", "另需指出",
    "需要说明的是", "值得注意的是", "补充说明", "更须冷静看待",
)
WORKLOG_PATTERNS = (
    r"版本[:：]\s*v\d", r"对抗性复核", r"复核修正", r"未能抓取", r"本次检索", r"本次未能",
)
LABEL_ALLOWED = ("附件", "注")
SCAFFOLD_MARKER = "【待撰写"
SENTENCE_END = "。！？；：”’）》】"


@dataclass
class Paragraph:
    text: str
    fully_bold: bool = False


@dataclass
class Section:
    key: str
    title: str
    paragraphs: list[Paragraph] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)
    appendix: bool = False
    front: bool = False

    def text(self, *, with_tables: bool = True) -> str:
        parts = [paragraph.text for paragraph in self.paragraphs]
        if with_tables:
            for table in self.tables:
                parts.extend(cell for row in table for cell in row)
        return "\n".join(parts)


def char_count(text: str) -> int:
    return sum(1 for char in text if not char.isspace())


def strip_bold(text: str) -> tuple[str, bool]:
    stripped = text.strip()
    fully = stripped.startswith("**") and stripped.endswith("**") and len(stripped) > 4
    return stripped.replace("**", ""), fully


def paragraphs_from(values: Any) -> list[Paragraph]:
    if isinstance(values, str):
        values = [values]
    result = []
    for value in values or []:
        text, fully = strip_bold(str(value))
        if text:
            result.append(Paragraph(text, fully))
    return result


def urgent_lines(items: list[dict[str, Any]]) -> list[str]:
    lines = []
    for index, item in enumerate(items or [], 1):
        action = str(item.get("事项", "")).strip().rstrip("。；")
        deadline = str(item.get("期限", "")).strip()
        line = f"{index}. {action}"
        if deadline:
            line += f"（期限：{deadline}）"
        lines.append(line + "。")
    return lines


def money(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:,.2f}"
    return str(value or "")


def sections_from_report(report: dict[str, Any]) -> list[Section]:
    """把生成器的结构化输入还原为与渲染结果同序的章节。"""
    sections: list[Section] = []
    summary = report.get("决策摘要", {}) or {}
    first = Section("决策摘要", "决策摘要", paragraphs_from(summary.get("结论")))
    outcomes = summary.get("可能结果") or []
    if outcomes:
        first.tables.append([["可能结果", "可能性", "金额影响"]] + [
            [str(item.get("结果", "")), str(item.get("可能性", "")), str(item.get("金额影响", ""))]
            for item in outcomes
        ])
    urgent = urgent_lines(summary.get("紧急事项") or [])
    if urgent:
        first.paragraphs.append(Paragraph("需要立即办理的事项如下。"))
        first.paragraphs.extend(Paragraph(line) for line in urgent)
    sections.append(first)

    issues = report.get("争点") or []
    overview = [issue.get("一览") for issue in issues]
    if issues and all(isinstance(item, dict) for item in overview):
        sections.append(Section("争点一览", "争点一览", tables=[[["争点", "我方主要理由", "主要障碍", "评估"]] + [
            [str(issue.get("标题", "")), str(item.get("我方主要理由", "")),
             str(item.get("主要障碍", "")), str(item.get("评估", ""))]
            for issue, item in zip(issues, overview)
        ]]))
    for issue in issues:
        sections.append(Section(
            f"争点:{issue.get('id', '')}", str(issue.get("标题", "")),
            [Paragraph(str(issue.get("标题", "")))] + paragraphs_from(issue.get("段落")),
        ))

    amounts = report.get("金额") or []
    deadlines = paragraphs_from(report.get("期限"))
    if amounts or deadlines:
        section = Section("金额与期限", "金额与期限", deadlines)
        if amounts:
            section.tables.append([["项目", "金额（元）", "说明"]] + [
                [str(item.get("项目", "")), money(item.get("金额")), str(item.get("说明", ""))]
                for item in amounts
            ])
        sections.append(section)
    strategy = paragraphs_from(report.get("策略"))
    if strategy:
        sections.append(Section("策略与建议", "策略与建议", strategy))

    appendix = report.get("附件") or {}
    texts: list[Paragraph] = []
    for item in appendix.get("法律依据") or []:
        texts.append(Paragraph(f"{item.get('名称', '')}{item.get('条文', '')}：“{item.get('原文', '')}”"))
    for item in appendix.get("其他") or []:
        texts.extend(paragraphs_from(item.get("段落")))
    if texts:
        sections.append(Section("附件", "附件", texts, appendix=True))
    return sections


def w(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def docx_paragraph(element) -> Paragraph:
    runs = [run for run in element.iter(w("r")) if "".join(t.text or "" for t in run.iter(w("t"))).strip()]
    text = "".join(node.text or "" for node in element.iter(w("t"))).strip()

    def bold(run) -> bool:
        rpr = run.find(w("rPr"))
        node = rpr.find(w("b")) if rpr is not None else None
        return node is not None and node.get(w("val"), "1") not in {"0", "false"}

    return Paragraph(text, bool(runs) and all(bold(run) for run in runs))


def sections_from_docx(path: Path) -> list[Section]:
    """按一级、二级标题把既有 DOCX 切分为可比较的章节单元。"""
    with ZipFile(path) as archive:
        document = safe_fromstring(archive.read("word/document.xml"))
    body = document.find(w("body"))
    sections = [Section("卷首", "卷首", front=True)]
    current_level1 = "卷首"
    appendix = False
    for child in list(body) if body is not None else []:
        if child.tag == w("p"):
            paragraph = docx_paragraph(child)
            if not paragraph.text:
                continue
            if HEADING_PATTERN.match(paragraph.text) or (
                current_level1 != "卷首" and APPENDIX_PATTERN.match(paragraph.text) and len(paragraph.text) <= 20
            ):
                appendix = appendix or bool(APPENDIX_PATTERN.search(paragraph.text))
                current_level1 = paragraph.text
                sections.append(Section(paragraph.text, paragraph.text, appendix=appendix))
                continue
            if SUBHEADING_PATTERN.match(paragraph.text) and not sections[-1].front:
                key = f"{current_level1}/{paragraph.text}"
                sections.append(Section(key, paragraph.text, [paragraph], appendix=appendix))
                continue
            sections[-1].paragraphs.append(paragraph)
        elif child.tag == w("tbl"):
            rows = []
            for row in child.findall(w("tr")):
                rows.append([
                    "".join(node.text or "" for node in cell.iter(w("t"))).strip()
                    for cell in row.findall(w("tc"))
                ])
            sections[-1].tables.append(rows)
    return [section for section in sections if section.paragraphs or section.tables]


class Linter:
    def __init__(self, sections: list[Section], *, body_limit: int, summary_limit: int,
                 claims: list[dict[str, Any]] | None, require_claims: bool):
        self.sections = sections
        self.body_limit = body_limit
        self.summary_limit = summary_limit
        self.claims = claims
        self.require_claims = require_claims
        self.findings: list[dict[str, Any]] = []

    def add(self, rule: str, severity: str, message: str, location: str = "", excerpt: str = "") -> None:
        self.findings.append({
            "id": f"R{len(self.findings) + 1:03d}",
            "rule": rule,
            "severity": severity,
            "location": location,
            "message": message,
            "excerpt": excerpt[:80],
        })

    @property
    def body_sections(self) -> list[Section]:
        return [section for section in self.sections if not section.front and not section.appendix]

    def run(self) -> list[dict[str, Any]]:
        self.check_length()
        self.check_language()
        self.check_abbreviations()
        self.check_paragraphs()
        self.check_tables()
        self.check_duplicates()
        self.check_topic_spread()
        self.check_claims()
        return self.findings

    def check_length(self) -> None:
        body = sum(char_count(section.text()) for section in self.body_sections)
        if body > self.body_limit:
            self.add("篇幅", "high", f"正文 {body} 字，超过上限 {self.body_limit} 字；附件不计入。"
                     "应删去重复论述，把法条原文、判决复述和工作记录移入附件或内部工作稿。")
        body_sections = self.body_sections
        if body_sections:
            first = body_sections[0]
            count = char_count(first.text())
            if count > self.summary_limit:
                self.add("首页", "high", f"决策摘要 {count} 字，超过首页上限 {self.summary_limit} 字。"
                         "首页只写结论、可能结果及金额、需要立即办理的事项。", first.title)

    def iter_body_texts(self, *, with_tables: bool = True):
        for section in self.body_sections:
            for paragraph in section.paragraphs:
                yield section, paragraph.text
            if with_tables:
                for table in section.tables:
                    for row in table:
                        for cell in row:
                            yield section, cell

    def check_language(self) -> None:
        for section, text in self.iter_body_texts():
            if "§" in text or re.search(r"[\d条款项][①-⑳]", text):
                self.add("条文写法", "high", "条文引用使用了 § 或圈码，应写法律全称加中文条款项序号。",
                         section.title, text)
            match = re.search(r"第\d+(?:条|款|项)", text)
            if match:
                self.add("条文写法", "high", f"条文序号“{match.group()}”使用阿拉伯数字，应写中文数字。",
                         section.title, text)
            for pattern, suggestion in JARGON_HIGH:
                match = re.search(pattern, text)
                if match:
                    self.add("行话", "high", f"“{match.group()}”属于行话或自造缩写，建议改为“{suggestion}”等规范表述。",
                             section.title, text)
            for pattern, suggestion in JARGON_MEDIUM:
                match = re.search(pattern, text)
                if match:
                    self.add("行话", "medium", f"“{match.group()}”偏口语，建议改为“{suggestion}”等规范表述。",
                             section.title, text)
            if SCAFFOLD_MARKER in text:
                self.add("占位未填", "high", "仍有脚手架占位“【待撰写】”，应由起草者写完后再生成。", section.title, text)
            for phrase in PATCH_PHRASES:
                if phrase in text:
                    self.add("补丁句", "high", f"“{phrase}”是复核意见追加成段的痕迹，应改进原段落，不另起补丁段。",
                             section.title, text)
            for pattern in WORKLOG_PATTERNS:
                if re.search(pattern, text):
                    self.add("工作记录", "medium", "版本说明、检索与复核过程属于工作记录，应移入 .casework 或文档属性。",
                             section.title, text)
            if re.search(r"[一-鿿][,;:?!()]|[,;:?!()][一-鿿]", text):
                self.add("标点", "medium", "中文语句中使用了半角标点，应改为全角。", section.title, text)

    def check_abbreviations(self) -> None:
        ordered = "\n".join(section.text() for section in self.sections if not section.front)
        for alias in ABBREVIATIONS:
            # 全称《……的解释（一）》《……法实施条例》中的同形字样不算简称。
            usage = re.search(rf"(?<![的之法]){re.escape(alias)}", ordered)
            if usage is None:
                continue
            first = usage.start()
            declared = re.search(rf"(?:以下简称|下称|简称)[“《]*[^》”）]{{0,10}}{re.escape(alias)}", ordered)
            if declared is None or declared.start() > first:
                self.add("简称", "high", f"简称“{alias}”未在首次使用时以“以下简称”声明，应先写全称。",
                         "", ordered[max(0, first - 20):first + 20])
        for short, full in STATUTE_FULL_NAMES.items():
            first = ordered.find(f"《{short}》")
            if first < 0:
                continue
            full_at = ordered.find(f"《{full}》")
            declared = re.search(rf"(?:以下简称|下称|简称)《{re.escape(short)}》", ordered)
            if (full_at < 0 or full_at > first) and (declared is None or declared.start() > first):
                self.add("简称", "high", f"《{short}》首次出现应写全称《{full}》，或在全称后声明简称。",
                         "", ordered[max(0, first - 20):first + 20])

    def check_paragraphs(self) -> None:
        bold_paragraphs = 0
        for section in self.body_sections:
            for paragraph in section.paragraphs:
                text = paragraph.text
                if HEADING_PATTERN.match(text) or SUBHEADING_PATTERN.match(text) or text == section.title:
                    continue
                if paragraph.fully_bold:
                    bold_paragraphs += 1
                label = re.match(r"^([一-鿿]{2,8})：", text)
                if label and not label.group(1).startswith(LABEL_ALLOWED):
                    self.add("标签段首", "medium", f"段首“{label.group()}”是标签加冒号的写法，应直接写成完整句子。",
                             section.title, text)
                if text[-1] not in SENTENCE_END:
                    self.add("半句", "medium", "段落未以句末标点结束，可能是不完整的句子。", section.title, text)
        if bold_paragraphs > FULL_BOLD_LIMIT:
            self.add("加粗", "medium", f"整段加粗 {bold_paragraphs} 处，超过 {FULL_BOLD_LIMIT} 处；加粗只用于关键句。")

    def check_tables(self) -> None:
        for section in self.body_sections:
            for index, table in enumerate(section.tables, 1):
                columns = max((len(row) for row in table), default=0)
                if columns > TABLE_MAX_COLUMNS:
                    self.add("表格", "high", f"表格有 {columns} 列，超过 {TABLE_MAX_COLUMNS} 列；一张表只回答一个问题，论证放正文。",
                             f"{section.title} 表{index}")
                for row in table[1:]:
                    for cell in row:
                        if char_count(cell) > TABLE_CELL_MAX_CHARS:
                            self.add("表格", "medium", f"单元格 {char_count(cell)} 字，超过 {TABLE_CELL_MAX_CHARS} 字；表格只写规范短语，理由放正文。",
                                     f"{section.title} 表{index}", cell)
                        if re.match(r"^(?:败|胜)(?:[，,；]|$)|^(?:中低|中高)(?:[，,；]|$)", cell):
                            self.add("表格", "medium", "单元格是需要读者猜测的标签，应写成规范短语，例如“我方败诉，涉及金额较小”。",
                                     f"{section.title} 表{index}", cell)

    @staticmethod
    def comparable(section: Section) -> str:
        """去空白，并把“《名称》第×条”式引用折叠成占位符；正文与附件互引同一条文不算重复。"""
        text = re.sub(r"\s+", "", "".join(paragraph.text for paragraph in section.paragraphs))
        return CITATION_PATTERN.sub("□", text)

    def check_duplicates(self) -> None:
        units = [section for section in self.sections if not section.front]
        owners: dict[str, set[str]] = {}
        for section in units:
            text = self.comparable(section)
            for start in range(0, max(0, len(text) - DUPLICATE_WINDOW + 1)):
                owners.setdefault(text[start:start + DUPLICATE_WINDOW], set()).add(section.key)
        reported: list[str] = []
        for section in units:
            text = self.comparable(section)
            start = 0
            while start <= len(text) - DUPLICATE_WINDOW:
                gram = text[start:start + DUPLICATE_WINDOW]
                others = owners.get(gram, set()) - {section.key}
                if not others:
                    start += 1
                    continue
                end = start + DUPLICATE_WINDOW
                while end < len(text) and owners.get(text[end - DUPLICATE_WINDOW + 1:end + 1], set()) - {section.key}:
                    end += 1
                span = text[start:end]
                if not any(span in item or item in span for item in reported):
                    reported.append(span)
                    where = "、".join(sorted({section.title} | {
                        item.title for item in units if item.key in others
                    }))
                    self.add("重复", "medium", f"同一段文字在多个部分重复出现（{where}）；同一论点只在一处完整论述，别处只引结论。",
                             section.title, span)
                start = end
                if len(reported) >= 10:
                    return

    def check_topic_spread(self) -> None:
        owners: dict[str, set[str]] = {}
        for section in self.body_sections:
            for match in re.finditer(r"第[一二三四五六七八九十百零]+条", section.text(with_tables=False)):
                owners.setdefault(match.group(), set()).add(section.title)
        for article, titles in sorted(owners.items()):
            if len(titles) >= TOPIC_SPREAD_LIMIT:
                self.add("论点分散", "medium", f"{article}在正文 {len(titles)} 个部分出现，检查是否同一论点被分散多处论述。",
                         "、".join(sorted(titles)))

    def check_claims(self) -> None:
        if self.claims is None:
            if self.require_claims:
                self.add("论点清单", "high", "缺少论点清单；动笔前应列出全部论点，并为每个论点指定唯一位置。")
            return
        if not self.claims and self.require_claims:
            self.add("论点清单", "high", "论点清单为空；动笔前应列出全部论点，并为每个论点指定唯一位置。")
            return
        valid = {section.key.split(":", 1)[-1] for section in self.sections} | set(SECTION_KEYS)
        seen: dict[str, str] = {}
        for index, item in enumerate(self.claims, 1):
            claim = str(item.get("论点", "")).strip()
            location = str(item.get("位置", "")).strip()
            if not claim or not location:
                self.add("论点清单", "high", f"论点清单第 {index} 项缺少论点或位置。")
                continue
            if location not in valid:
                self.add("论点清单", "high", f"论点“{claim[:20]}”指定的位置“{location}”不存在。")
            if claim in seen:
                self.add("论点清单", "high", f"论点“{claim[:20]}”被重复登记（{seen[claim]}、{location}）；每个论点只能有一个位置。")
            seen[claim] = location


def lint_sections(sections: list[Section], *, body_limit: int = DEFAULT_BODY_LIMIT,
                  summary_limit: int = DEFAULT_SUMMARY_LIMIT,
                  claims: list[dict[str, Any]] | None = None,
                  require_claims: bool = False) -> dict[str, Any]:
    findings = Linter(sections, body_limit=body_limit, summary_limit=summary_limit,
                      claims=claims, require_claims=require_claims).run()
    body = sum(char_count(section.text()) for section in sections if not section.front and not section.appendix)
    if any(item["severity"] == "high" for item in findings):
        status = "blocked"
    elif findings:
        status = "warn"
    else:
        status = "pass"
    return {
        "status": status,
        "validator": "laborpilot-report-lint",
        "body_chars": body,
        "body_limit": body_limit,
        "summary_limit": summary_limit,
        "findings": findings,
    }


def lint_report(report: dict[str, Any], *, body_limit: int | None = None) -> dict[str, Any]:
    """校验生成器输入中的 report 对象；论点清单为必填项。"""
    limit = body_limit or int(report.get("篇幅上限") or DEFAULT_BODY_LIMIT)
    summary_limit = int(report.get("首页上限") or DEFAULT_SUMMARY_LIMIT)
    claims = report.get("论点清单")
    return lint_sections(
        sections_from_report(report), body_limit=limit, summary_limit=summary_limit,
        claims=claims if isinstance(claims, list) else None, require_claims=True,
    )


def lint_docx(path: Path, *, body_limit: int = DEFAULT_BODY_LIMIT,
              summary_limit: int = DEFAULT_SUMMARY_LIMIT) -> dict[str, Any]:
    """校验既有 DOCX；无法取得论点清单时只做文本层检查。"""
    return lint_sections(sections_from_docx(path), body_limit=body_limit, summary_limit=summary_limit)


def main() -> int:
    parser = argparse.ArgumentParser(description="校验《案件研判报告》的篇幅、推理结构、语体与表格")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", help="生成器输入 JSON（读取其中的 report 对象）")
    source.add_argument("--docx", help="既有研判报告 DOCX")
    parser.add_argument("--body-limit", type=int, help=f"正文字数上限，默认 {DEFAULT_BODY_LIMIT}")
    parser.add_argument("--output", help="把结果另存为 JSON 文件")
    args = parser.parse_args()
    try:
        if args.input:
            data = json.loads(Path(args.input).read_text(encoding="utf-8"))
            report = data.get("report", data)
            result = lint_report(report, body_limit=args.body_limit)
        else:
            result = lint_docx(Path(args.docx), body_limit=args.body_limit or DEFAULT_BODY_LIMIT)
    except (OSError, ValueError, KeyError, BadZipFile, UnsafeXMLError) as exc:
        result = {"status": "blocked", "validator": "laborpilot-report-lint",
                  "findings": [{"id": "R001", "rule": "输入", "severity": "high", "location": "",
                                "message": f"无法读取输入：{exc}", "excerpt": ""}]}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 1 if result["status"] == "blocked" else 0


if __name__ == "__main__":
    sys.exit(main())
