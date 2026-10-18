#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文书生成器 v3：生成并校验 JLS 版式的律师复核初稿或最终提交版。

参考模板：assets/template-仲裁申请书.docx / template-证据清单.docx。
Pandoc 完成内容转换后，由标准库 OOXML 修正器确定性应用并校验 JLS 版式。
《案件研判报告》按 references/case-report-contract.md 的固定骨架渲染，
转换前先通过 report_lint.py 的写作校验。

用法：python3 generate_docs.py --case case.json --output 案件根目录 --types 仲裁申请书 --strict
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from zipfile import BadZipFile

from docx_style import INTERNAL_DOCUMENT_TYPES, PROFILE_ID, apply_jls_style, validate_jls_docx
from report_lint import DEFAULT_BODY_LIMIT, lint_report, money, urgent_lines

SKILL_DIR = Path(__file__).parent.parent
ASSETS = SKILL_DIR / "assets"
DELIVERY_DIRS = {
    "lawyer_review_draft": "01_律师复核初稿",
    "final_submission": "02_最终提交版",
}
DELIVERY_LABELS = {
    "lawyer_review_draft": "律师复核初稿",
    "final_submission": "最终提交版",
}
DOC_PREFIXES = {"研判报告": "01", "仲裁申请书": "02", "证据清单": "03", "行动清单": "04"}
DOC_DISPLAY_NAMES = {
    "研判报告": "案件研判报告", "仲裁申请书": "劳动仲裁申请书",
    "证据清单": "证据目录", "行动清单": "待补材料与行动清单",
}
CN_ORDINALS = "一二三四五六七八九十"

# 中文数字日期
CN_NUM = {"0":"〇","1":"一","2":"二","3":"三","4":"四","5":"五","6":"六","7":"七","8":"八","9":"九"}

def cn_date(d=None):
    """2026-08-21 → 二〇二六年八月二十一日"""
    if d is None:
        d = date.today()
    y = "".join(CN_NUM[c] for c in str(d.year))
    m = d.month
    if m < 10:
        mon = CN_NUM[str(m)]
    elif m == 10:
        mon = "十"
    else:
        mon = "十" + CN_NUM[str(m % 10)]
    day = d.day
    if day < 10:
        dd = CN_NUM[str(day)]
    elif day == 10:
        dd = "十"
    elif day < 20:
        dd = "十" + CN_NUM[str(day % 10)]
    elif day == 20:
        dd = "二十"
    elif day < 30:
        dd = "二十" + CN_NUM[str(day % 10)]
    elif day == 30:
        dd = "三十"
    else:
        dd = "三十" + CN_NUM[str(day % 10)]
    return f"{y}年{mon}月{dd}日"


def compact_prose(value):
    """把事实与理由整理为连续正文，不保留 Markdown 分点。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


# Pandoc Markdown 的行内语法字符：不转义时，“*”会变成斜体、“~”“^”变成上下标、“<…>”被当作 HTML 丢弃。
MD_SPECIAL = set("\\`*_{}[]<>#~^$|@")


def md_escape(value, *, keep_bold=False):
    """转义行内语法字符，使作者文字原样进入 DOCX；keep_bold 时保留成对的 **加粗** 标记。"""
    text = str(value or "")
    if keep_bold:
        return "**".join(md_escape(part) for part in text.split("**"))
    return "".join("\\" + char if char in MD_SPECIAL else char for char in text)


def table_cell(value):
    """表格单元格合并为单行并转义全部行内语法字符（含列分隔符“|”）。"""
    return md_escape(re.sub(r"\s+", " ", str(value or "")).strip())


def output_stem(doc_type, delivery_status, version):
    label = DELIVERY_LABELS[delivery_status]
    if doc_type in INTERNAL_DOCUMENT_TYPES:
        label = "律师复核稿"
    return f"{DOC_PREFIXES[doc_type]}_{DOC_DISPLAY_NAMES[doc_type]}_{label}_v{version}"


PANDOC_MISSING = (
    "未找到 Pandoc，无法生成 .docx。请先安装：https://pandoc.org\n"
    "macOS: brew install pandoc\n"
    "Debian/Ubuntu: apt install pandoc"
)


def md_to_docx(md_file: Path, docx_file: Path, ref_doc: Path = None):
    """pandoc md→docx,可指定参考样式文档。"""
    cmd = ["pandoc", str(md_file), "-o", str(docx_file),
           "--from=markdown", "--to=docx", "-V", "lang=zh-CN"]
    if ref_doc and ref_doc.exists():
        cmd.extend(["--reference-doc", str(ref_doc)])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        return False, PANDOC_MISSING
    return r.returncode == 0, r.stderr


def generate_arbitration(case, claims):
    """仲裁申请书——严格按律师定稿格式。"""
    lines = []
    # 标题
    lines.append("劳动仲裁申请书")
    lines.append("")
    # 当事人信息仅保留文书必要要素；示例和模板不要求身份证号、个人住址。
    lines.append(f"申请人：{case.get('申请人','【申请人姓名】')}，{case.get('性别','【性别】')}，"
                f"{case.get('出生年月','【年月日】')}出生，{case.get('民族','汉族')}。"
                f"联系电话：{case.get('电话','【电话】')}。")
    lines.append("")
    lines.append(f"被申请人：{case.get('被申请人','【公司名称】')}，"
                f"住所地：{case.get('被申请人地址','【注册地址】')}。"
                + (f"统一社会信用代码：{case.get('统一社会信用代码')}。" if case.get('统一社会信用代码') else ""))
    lines.append("")
    # 仲裁请求(律师格式:一、二、三中文编号)
    cn = ["一","二","三","四","五","六","七","八","九","十",
          "十一","十二","十三","十四","十五","十六","十七","十八","十九","二十"]
    lines.append("仲裁请求：")
    lines.append("")
    for i, c in enumerate(claims):
        if c.get("金额"):
            item = f"请求裁决被申请人支付申请人{c['事项']}{c['金额']:,.2f}元"
            if c.get("计算式"):
                item += f"（{c['计算式']}）"
            item += "；"
        else:
            item = f"请求裁决被申请人{c['事项']}；"
        num = cn[i] if i < len(cn) else str(i + 1)
        lines.append(f"{num}、{item}")
    lines.append("")
    # 事实与理由(律师格式:段落体,不用markdown标题)
    lines.append("事实与理由：")
    lines.append("")
    lines.append(compact_prose(case.get("事实与理由", case.get("事实概要", "【按时间轴组织，不添加未确认事实】"))))
    lines.append("")
    # 落款(律师格式:中文数字日期)
    lines.append("此致")
    lines.append("")
    lines.append(f"{case.get('仲裁委','【劳动人事争议仲裁委员会】')}")
    lines.append("")
    lines.append(f"申请人：{case.get('申请人','【申请人签名】')}")
    lines.append("")
    lines.append(cn_date())
    return "\n".join(md_escape(line) for line in lines)


def generate_evidence_list(case, evidence_items):
    """证据清单——严格按律师定稿格式。"""
    lines = []
    # 标题(含案件信息)
    applicant = case.get("申请人", "【申请人】")
    respondent = case.get("被申请人", "【被申请人】")
    cause = case.get("案由", "【案由】")
    lines.append(md_escape(f"{applicant}与{respondent}{cause}一案"))
    lines.append("")
    lines.append("证据目录")
    lines.append("")
    # 表格(律师格式:5列,不用争点卡列)
    lines.append("| 序号 | 证据名称 | 来源 | 页码 | 证明目的 |")
    lines.append("|---:|---|---|---|---|")
    for i, e in enumerate(evidence_items, 1):
        lines.append(f"| {i} | {table_cell(e.get('名称'))} | {table_cell(e.get('来源'))} | "
                    f"{table_cell(e.get('页码'))} | {table_cell(e.get('证明目的'))} |")
    lines.append("")
    # 落款
    lines.append(md_escape(f"提交人：{case.get('申请人','【申请人签名】')}"))
    lines.append("")
    lines.append(f"提交时间：{cn_date()}")
    return "\n".join(lines)


def generate_action_list(case, actions):
    """行动清单——律师内部工作文件。"""
    lines = []
    lines.append("待补材料与行动清单")
    lines.append("")
    lines.append("一、需向当事人核实的事实")
    lines.append("")
    lines.append("| 优先级 | 问题 | 影响的请求 | 状态 |")
    lines.append("|---|---|---|---|")
    for a in actions.get("核实", []):
        lines.append(f"| {table_cell(a.get('优先级'))} | {table_cell(a.get('问题'))} | {table_cell(a.get('影响'))} | 待核实 |")
    lines.append("")
    lines.append("二、待补证据")
    lines.append("")
    lines.append("| 优先级 | 材料 | 持有人 | 证明目的 | 状态 |")
    lines.append("|---|---|---|---|---|")
    for a in actions.get("证据", []):
        lines.append(f"| {table_cell(a.get('优先级'))} | {table_cell(a.get('材料'))} | {table_cell(a.get('持有人'))} | {table_cell(a.get('证明目的'))} | 待收集 |")
    lines.append("")
    lines.append("三、金额与程序核对")
    lines.append("")
    lines.append("| 事项 | 当前口径 | 风险／后果 | 状态 |")
    lines.append("|---|---|---|---|")
    for a in actions.get("核对", []):
        lines.append(f"| {table_cell(a.get('事项'))} | {table_cell(a.get('口径'))} | {table_cell(a.get('风险'))} | 待核对 |")
    lines.append("")
    return "\n".join(lines)


def md_paragraph(value):
    """把作者段落转为 Markdown 正文段，避免被 Pandoc 误识别为列表、标题或引用。"""
    text = md_escape(compact_prose(value), keep_bold=True)
    if re.match(r"^\d+[.)]\s", text):
        text = re.sub(r"^(\d+)([.)])", r"\1\\\2", text, count=1)
    elif text[:1] in {"#", "-", "+", ">"} or (text.startswith("*") and not text.startswith("**")):
        text = "\\" + text
    return text


def md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for row in rows:
        lines.append("| " + " | ".join(table_cell(cell) for cell in row) + " |")
    return lines


def analysis_date(value):
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", str(value or "").strip())
    if match:
        year, month, day = match.groups()
        return f"{year}年{int(month)}月{int(day)}日"
    return str(value or "【待确认：分析基准日】")


def generate_case_report(case, report):
    """《案件研判报告》——按读者要做的决定组织，每个论点只在一处论述。"""
    lines = ["案件研判报告", ""]
    title = report.get("案件名称") or case.get("案由") or "【待确认：案件名称】"
    lines.extend([md_escape(compact_prose(title)), ""])
    caption = [report.get("程序阶段"), f"代理{report['代理立场']}" if report.get("代理立场") else None,
               f"分析基准日：{analysis_date(report.get('分析基准日'))}", "律师复核稿"]
    lines.extend([md_escape("　".join(item for item in caption if item)), ""])

    sections = []
    summary = report.get("决策摘要", {}) or {}
    body = [md_paragraph(item) for item in summary.get("结论") or []]
    outcomes = summary.get("可能结果") or []
    if outcomes:
        body.append("\n".join(md_table(["可能结果", "可能性", "金额影响"], [
            [item.get("结果", ""), item.get("可能性", ""), item.get("金额影响", "")] for item in outcomes
        ])))
    urgent = urgent_lines(summary.get("紧急事项") or [])
    if urgent:
        body.append("需要立即办理的事项如下。")
        body.extend(md_paragraph(item) for item in urgent)
    sections.append(("决策摘要", body))

    issues = report.get("争点") or []
    if issues:
        body = []
        overview = [issue.get("一览") for issue in issues]
        if all(isinstance(item, dict) for item in overview):
            body.append("\n".join(md_table(["争点", "我方主要理由", "主要障碍", "评估"], [
                [issue.get("标题", ""), item.get("我方主要理由", ""), item.get("主要障碍", ""), item.get("评估", "")]
                for issue, item in zip(issues, overview)
            ])))
        for index, issue in enumerate(issues):
            ordinal = CN_ORDINALS[index] if index < len(CN_ORDINALS) else str(index + 1)
            body.append(f"（{ordinal}）{md_escape(compact_prose(issue.get('标题', '')))}")
            body.extend(md_paragraph(item) for item in issue.get("段落") or [])
        sections.append(("争点分析", body))

    amounts = report.get("金额") or []
    deadlines = report.get("期限") or []
    if amounts or deadlines:
        body = []
        if amounts:
            body.append("\n".join(md_table(["项目", "金额（元）", "说明"], [
                [item.get("项目", ""), money(item.get("金额")), item.get("说明", "")] for item in amounts
            ])))
        body.extend(md_paragraph(item) for item in deadlines)
        sections.append(("金额与期限", body))
    strategy = report.get("策略") or []
    if strategy:
        sections.append(("策略与建议", [md_paragraph(item) for item in strategy]))

    for index, (heading, body) in enumerate(sections):
        lines.extend([f"{CN_ORDINALS[index]}、{heading}", ""])
        for block in body:
            lines.extend([block, ""])

    appendix = report.get("附件") or {}
    authorities = appendix.get("法律依据") or []
    others = appendix.get("其他") or []
    if authorities or others:
        lines.extend(["附件", ""])
        groups = []
        if authorities:
            groups.append(("法律依据", [
                md_paragraph(f"{item.get('名称', '')}{item.get('条文', '')}：“{item.get('原文', '')}”")
                for item in authorities
            ]))
        groups.extend((item.get("标题", ""), [md_paragraph(text) for text in item.get("段落") or []]) for item in others)
        for index, (heading, body) in enumerate(groups):
            lines.extend([f"（{CN_ORDINALS[index]}）{md_escape(compact_prose(heading))}", ""])
            for block in body:
                lines.extend([block, ""])
    return "\n".join(lines).rstrip() + "\n"


def note_report_growth(lint, work_dir, delivery_status, version):
    """与最近一个旧版本的写作校验比较正文字数；变长时提示，防止复核只增不减。"""
    for earlier in range(version - 1, 0, -1):
        path = work_dir / f"{output_stem('研判报告', delivery_status, earlier)}_写作校验.json"
        if not path.exists():
            continue
        try:
            previous = json.loads(path.read_text(encoding="utf-8")).get("body_chars")
        except (OSError, ValueError, AttributeError):
            return
        if not isinstance(previous, int):
            return
        lint["previous_version"] = {"version": earlier, "body_chars": previous}
        growth = lint["body_chars"] - previous
        if growth > 0:
            lint["findings"].append({
                "id": f"R{len(lint['findings']) + 1:03d}",
                "rule": "篇幅增长",
                "severity": "medium",
                "location": "",
                "message": f"正文比 v{earlier} 增加 {growth} 字。复核意见应改进原段落；确需新增的，在 .casework/drafting/ 记录新增内容及理由。",
                "excerpt": "",
            })
            if lint["status"] == "pass":
                lint["status"] = "warn"
        return


# 文档类型 → 生成函数 + 参考样式
DOC_REGISTRY = {}

def _register():
    ref_arb = ASSETS / "template-仲裁申请书.docx"
    ref_evd = ASSETS / "template-证据清单.docx"
    DOC_REGISTRY["仲裁申请书"] = (generate_arbitration, ref_arb)
    DOC_REGISTRY["证据清单"] = (generate_evidence_list, ref_evd)
    DOC_REGISTRY["行动清单"] = (generate_action_list, None)
    DOC_REGISTRY["研判报告"] = (generate_case_report, None)

_register()


def main():
    ap = argparse.ArgumentParser(description="文书生成器 v3（JLS 版式及交付分层）")
    ap.add_argument("--case", required=True, help="案件数据JSON")
    ap.add_argument("--output", required=True, help="案件根目录；DOCX 将按交付层级进入独立子目录")
    ap.add_argument("--work-dir", help="内部 Markdown 工作目录；默认 <案件根目录>/.casework/drafting")
    ap.add_argument("--types", required=True, help="用户明确要求的文书类型，逗号分隔")
    ap.add_argument("--delivery-status", choices=sorted(DELIVERY_DIRS), default="lawyer_review_draft")
    ap.add_argument("--version", type=int, default=1, help="输出文件版本号，默认 1")
    ap.add_argument("--approved-by", help="最终提交版必须记录作出提交决定的律师姓名")
    ap.add_argument("--strict", action="store_true", help="兼容参数；正式 DOCX 始终按严格模式生成")
    ap.add_argument("--report-char-limit", type=int,
                    help=f"研判报告正文字数上限，默认取 report.篇幅上限 或 {DEFAULT_BODY_LIMIT}")
    args = ap.parse_args()

    if args.version < 1:
        ap.error("--version 必须为正整数。")
    if args.delivery_status == "final_submission" and not (args.approved_by or "").strip():
        ap.error("最终提交版必须通过 --approved-by 记录律师提交决定。")

    data = json.loads(Path(args.case).read_text(encoding="utf-8"))
    case = data.get("case", {})
    claims = data.get("claims", [])
    evidence = data.get("evidence", [])
    actions = data.get("actions", {})
    report = data.get("report")

    case_root = Path(args.output)
    out_dir = case_root / DELIVERY_DIRS[args.delivery_status]
    work_dir = Path(args.work_dir) if args.work_dir else case_root / ".casework" / "drafting"
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    types = [t.strip() for t in args.types.split(",") if t.strip()]
    if not types:
        ap.error("--types 至少指定一种文书。")
    unknown = sorted(set(types) - set(DOC_REGISTRY))
    if unknown:
        ap.error("不支持的文书类型：" + "、".join(unknown))
    internal = [doc_type for doc_type in types if doc_type in INTERNAL_DOCUMENT_TYPES]
    if args.delivery_status == "final_submission" and internal:
        ap.error("、".join(internal) + "属于内部工作文件，不得生成最终提交版。")
    if "研判报告" in types and not isinstance(report, dict):
        ap.error("生成研判报告须在 --case 输入中提供 report 对象，结构见 references/case-report-contract.md。")

    planned = []
    for doc_type in types:
        stem = output_stem(doc_type, args.delivery_status, args.version)
        planned.extend([work_dir / f"{stem}.md", work_dir / f"{stem}_版式验证.json", out_dir / f"{stem}.docx"])
        if doc_type == "研判报告":
            planned.append(work_dir / f"{stem}_写作校验.json")
    existing = [path for path in planned if path.exists()]
    if existing:
        ap.error("为避免覆盖既有版本，以下目标已存在：\n" + "\n".join(str(path) for path in existing))
    if shutil.which("pandoc") is None:
        print(PANDOC_MISSING, file=sys.stderr)
        raise SystemExit(1)
    failures = []

    for doc_type in types:
        gen_fn, ref_doc = DOC_REGISTRY[doc_type]

        if doc_type == "仲裁申请书":
            md_content = gen_fn(case, claims)
        elif doc_type == "证据清单":
            md_content = gen_fn(case, evidence)
        elif doc_type == "行动清单":
            md_content = gen_fn(case, actions)
        elif doc_type == "研判报告":
            stem = output_stem(doc_type, args.delivery_status, args.version)
            try:
                lint = lint_report(report, body_limit=args.report_char_limit)
            except (TypeError, ValueError) as exc:
                failures.append(f"研判报告: report 输入格式有误：{exc}")
                continue
            note_report_growth(lint, work_dir, args.delivery_status, args.version)
            (work_dir / f"{stem}_写作校验.json").write_text(
                json.dumps(lint, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
            )
            if lint["status"] == "blocked":
                blocking = [item for item in lint["findings"] if item["severity"] == "high"]
                failures.append("研判报告: 写作校验未通过（" + str(len(blocking)) + " 项）：\n" + "\n".join(
                    f"  - [{item['rule']}] {item['message']}" + (f"｜{item['excerpt']}" if item["excerpt"] else "")
                    for item in blocking
                ))
                continue
            md_content = gen_fn(case, report)
        else:
            continue

        stem = output_stem(doc_type, args.delivery_status, args.version)
        md_file = work_dir / f"{stem}.md"
        report_file = work_dir / f"{stem}_版式验证.json"
        docx_file = out_dir / f"{stem}.docx"
        md_file.write_text(md_content, encoding="utf-8")
        ok, err = md_to_docx(md_file, docx_file, ref_doc)
        if ok:
            try:
                apply_jls_style(docx_file, doc_type, args.delivery_status)
                findings = validate_jls_docx(docx_file, doc_type, args.delivery_status)
                report = {
                    "status": "pass" if not findings else "blocked",
                    "profile": PROFILE_ID,
                    "document_type": doc_type,
                    "delivery_status": args.delivery_status,
                    "approved_by": (args.approved_by or "").strip() or None,
                    "document_path": str(docx_file.resolve()),
                    "findings": findings,
                }
                report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                if findings:
                    raise ValueError("\n".join(findings))
            except (OSError, ValueError, BadZipFile) as exc:
                ok, err = False, str(exc)
        if ok:
            print(f"  OK {doc_type} ({docx_file.stat().st_size}B) → {docx_file}")
        else:
            failures.append(f"{doc_type}: {err.strip() or 'Pandoc 转换失败'}")
            if docx_file.exists():
                docx_file.unlink()

    if failures:
        print("文书转换失败：\n" + "\n".join(failures), file=sys.stderr)
        raise SystemExit(1)
    print(f"\n→ {out_dir}")


if __name__ == "__main__":
    main()
