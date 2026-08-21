#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LaborPilot — 劳动争议智能办案引擎

中国劳动争议案件的知识驱动办案助手。
支持劳动者方和用人单位方,内置浙江裁判口径。

用法:
    python3 issue_router.py --list-gates          # 列出全部案由门
    python3 issue_router.py --search "违法解除"    # 内部匹配相关争点
    python3 generate_docs.py --case data.json --output out/  # 生成文书

免责声明:
    LaborPilot 产出的所有分析结果和法律文书均由 AI 辅助生成,
    仅供参考,不构成法律意见,必须经专业律师审核后方可使用。
"""
import argparse
import base64
import json
import marshal
import os
import re
import subprocess
import sys
import zlib
from pathlib import Path
from urllib.parse import unquote

SKILL_DIR = Path(__file__).parent.parent
_KB_PYC = SKILL_DIR / "_kb.pyc"


def load_knowledge_base():
    """加载编译的知识数据。"""
    if not _KB_PYC.exists():
        print("ERROR _kb.pyc not found. Run build_cards.py first.", file=sys.stderr)
        sys.exit(1)
    import importlib.util
    spec = importlib.util.spec_from_file_location("_kb", str(_KB_PYC))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.load()


def get_routing(cards):
    """按gate分组。"""
    routing = {}
    for card in cards:
        gate = card.get("g", "unknown")
        routing.setdefault(gate, []).append({
            "card_id": card["id"],
            "title": card.get("t", ""),
            "has_zhejiang": bool(card.get("zj")),
        })
    return routing


def format_card(card):
    lines = []
    cid = card.get("id", "?")
    title = card.get("t", "")
    gate = card.get("g", "")
    zj = "ZJ" if card.get("zj") else "--"
    lines.append(f"  [{cid}] {title}")
    lines.append(f"    gate: {gate} | {zj}")

    basis = card.get("b", "")
    if basis:
        lines.append(f"    basis: {basis[:120]}")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="LaborPilot issue router")
    ap.add_argument("--list-gates", action="store_true")
    ap.add_argument("--gate", default=None)
    ap.add_argument("--search", default=None)
    args = ap.parse_args()

    cards = load_knowledge_base()

    if args.list_gates:
        routing = get_routing(cards)
        print(f"Available gates ({len(routing)}):")
        for gate, gate_cards in sorted(routing.items(), key=lambda x: str(x[0])):
            zj_count = sum(1 for c in gate_cards if c.get("has_zhejiang"))
            print(f"  {gate} ({len(gate_cards)} cards, ZJ:{zj_count})")
        return

    if args.gate:
        matched = [c for c in cards if args.gate in c.get("g", "")]
        if not matched:
            print(f"Gate '{args.gate}' not found. Use --list-gates.")
            sys.exit(1)
        print(f"Gate '{args.gate}' — {len(matched)} cards:")
        for c in matched:
            print(format_card(c))
        return

    if args.search:
        keywords = args.search.split()
        scored = []
        for c in cards:
            text = json.dumps(c, ensure_ascii=False)
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scored.append((score, c))
        scored.sort(key=lambda x: -x[0])
        if not scored:
            print(f"No results for '{args.search}'.")
            sys.exit(1)
        print(f"Search '{args.search}' — {len(scored)} results:")
        for score, c in scored[:10]:
            print(format_card(c))
        return

    ap.print_help()


if __name__ == "__main__":
    main()
