#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文书生成器 v2:按金律师定稿格式生成。

格式基准: assets/template-仲裁申请书.docx / template-证据清单.docx(2026-08-21律师调整版)
生成纪律: 输出必须完全按照上述格式,不偏离。

用法: python3 generate_docs.py --case case.json --output 输出目录 [--types 仲裁申请书,证据清单]
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
ASSETS = SKILL_DIR / "assets"

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


def md_to_docx(md_file: Path, docx_file: Path, ref_doc: Path = None):
    """pandoc md→docx,可指定参考样式文档。"""
    cmd = ["pandoc", str(md_file), "-o", str(docx_file),
           "--from=markdown", "--to=docx", "-V", "lang=zh-CN"]
    if ref_doc and ref_doc.exists():
        cmd.extend(["--reference-doc", str(ref_doc)])
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0, r.stderr


def generate_arbitration(case, claims):
    """仲裁申请书——严格按律师定稿格式。"""
    lines = []
    # 标题
    lines.append("劳动仲裁申请书")
    lines.append("")
    # 当事人(律师格式:冒号分隔,句号结尾,不用markdown加粗)
    lines.append(f"申请人:{case.get('申请人','【申请人姓名】')},{case.get('性别','【性别】')},"
                f"{case.get('出生年月','【年月日】')}出生,{case.get('民族','汉族')},"
                f"住{case.get('户籍地址','【户籍地址】')},公民身份号码:{case.get('身份证号','【身份证号】')}。"
                f"联系电话:{case.get('电话','【电话】')}。")
    lines.append("")
    lines.append(f"被申请人:{case.get('被申请人','【公司名称】')},"
                f"住所地:{case.get('被申请人地址','【注册地址】')}。"
                + (f"统一社会信用代码:{case.get('统一社会信用代码','【统一社会信用代码】')}" if case.get('统一社会信用代码') else ""))
    lines.append("")
    # 仲裁请求(律师格式:一、二、三中文编号)
    cn = ["一","二","三","四","五","六","七","八","九","十",
          "十一","十二","十三","十四","十五","十六","十七","十八","十九","二十"]
    lines.append("仲裁请求:")
    lines.append("")
    for i, c in enumerate(claims):
        if c.get("金额"):
            item = f"请求裁决被申请人支付申请人{c['事项']}{c['金额']:,.2f}元"
            if c.get("计算式"):
                item += f"({c['计算式']})"
            item += ";"
        else:
            item = f"请求裁决被申请人{c['事项']};"
        num = cn[i] if i < len(cn) else str(i + 1)
        lines.append(f"{num}、{item}")
    lines.append("")
    # 事实与理由(律师格式:段落体,不用markdown标题)
    lines.append("事实与理由:")
    lines.append("")
    lines.append(case.get("事实与理由", case.get("事实概要", "【按时间轴组织,不添加未确认事实】")))
    lines.append("")
    # 落款(律师格式:中文数字日期)
    lines.append("此致")
    lines.append("")
    lines.append(f"{case.get('仲裁委','【劳动人事争议仲裁委员会】')}")
    lines.append("")
    lines.append(f"申请人:{case.get('申请人','【申请人签名】')}")
    lines.append("")
    lines.append(cn_date())
    return "\n".join(lines)


def generate_evidence_list(case, evidence_items):
    """证据清单——严格按律师定稿格式。"""
    lines = []
    # 标题(含案件信息)
    applicant = case.get("申请人", "【申请人】")
    respondent = case.get("被申请人", "【被申请人】")
    cause = case.get("案由", "【案由】")
    lines.append(f"{applicant}与{respondent}{cause}劳动仲裁一案")
    lines.append("")
    lines.append("证据目录")
    lines.append("")
    # 表格(律师格式:5列,不用争点卡列)
    lines.append("| 序号 | 证据名称 | 来源 | 页码 | 证明目的 |")
    lines.append("|---:|---|---|---|---|")
    for i, e in enumerate(evidence_items, 1):
        lines.append(f"| {i} | {e.get('名称','')} | {e.get('来源','')} | "
                    f"{e.get('页码','')} | {e.get('证明目的','')} |")
    lines.append("")
    # 落款
    lines.append(f"提交人:{case.get('申请人','【申请人签名】')}")
    lines.append("")
    lines.append(f"提交时间:{date.today().strftime('%Y年%m月%d日')}")
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
        lines.append(f"| {a.get('优先级','')} | {a.get('问题','')} | {a.get('影响','')} | 待核实 |")
    lines.append("")
    lines.append("二、待补证据")
    lines.append("")
    lines.append("| 优先级 | 材料 | 持有人 | 证明目的 | 状态 |")
    lines.append("|---|---|---|---|---|")
    for a in actions.get("证据", []):
        lines.append(f"| {a.get('优先级','')} | {a.get('材料','')} | {a.get('持有人','')} | {a.get('证明目的','')} | 待收集 |")
    lines.append("")
    lines.append("三、金额与程序核对")
    lines.append("")
    lines.append("| 事项 | 当前口径 | 风险/后果 | 状态 |")
    lines.append("|---|---|---|---|")
    for a in actions.get("核对", []):
        lines.append(f"| {a.get('事项','')} | {a.get('口径','')} | {a.get('风险','')} | 待核对 |")
    lines.append("")
    return "\n".join(lines)


# 文档类型 → 生成函数 + 参考样式
DOC_REGISTRY = {}

def _register():
    ref_arb = ASSETS / "template-仲裁申请书.docx"
    ref_evd = ASSETS / "template-证据清单.docx"
    DOC_REGISTRY["仲裁申请书"] = (generate_arbitration, ref_arb)
    DOC_REGISTRY["证据清单"] = (generate_evidence_list, ref_evd)
    DOC_REGISTRY["行动清单"] = (generate_action_list, None)

_register()


def main():
    ap = argparse.ArgumentParser(description="文书生成器v2(按律师定稿格式)")
    ap.add_argument("--case", required=True, help="案件数据JSON")
    ap.add_argument("--output", required=True, help="输出目录")
    ap.add_argument("--types", default="仲裁申请书,证据清单,行动清单")
    args = ap.parse_args()

    data = json.loads(Path(args.case).read_text(encoding="utf-8"))
    case = data.get("case", {})
    claims = data.get("claims", [])
    evidence = data.get("evidence", [])
    actions = data.get("actions", {})

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    types = [t.strip() for t in args.types.split(",")]

    for doc_type in types:
        if doc_type not in DOC_REGISTRY:
            print(f"  SKIP {doc_type}: 未支持")
            continue

        gen_fn, ref_doc = DOC_REGISTRY[doc_type]

        if doc_type == "仲裁申请书":
            md_content = gen_fn(case, claims)
        elif doc_type == "证据清单":
            md_content = gen_fn(case, evidence)
        elif doc_type == "行动清单":
            md_content = gen_fn(case, actions)
        else:
            continue

        md_file = out_dir / f"{doc_type}.md"
        docx_file = out_dir / f"{doc_type}.docx"
        md_file.write_text(md_content, encoding="utf-8")
        ok, err = md_to_docx(md_file, docx_file, ref_doc)
        size = docx_file.stat().st_size if docx_file.exists() else md_file.stat().st_size
        status = "OK" if ok else "WARN(md only)"
        print(f"  {status} {doc_type} ({size}B)" + (f" ref={ref_doc.name}" if ref_doc and ref_doc.exists() else ""))

    print(f"\n→ {out_dir}")


if __name__ == "__main__":
    main()
