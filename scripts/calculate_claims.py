#!/usr/bin/env python3
"""对律师已选定的公式执行可追溯算术，不自动作法律适用判断。"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any


def fail(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def decimal(value: Any, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        fail(f"{field} 不是合法数值：{value}")


def calculate(item: dict[str, Any], prior: dict[str, Decimal]) -> tuple[Decimal, str]:
    formula = item.get("formula")
    inputs = item.get("inputs", {})
    if formula == "multiply":
        factors = inputs.get("factors", [])
        if not factors:
            fail(f"{item.get('item_id')} 的 factors 不得为空。")
        result = Decimal("1")
        for index, factor in enumerate(factors):
            result *= decimal(factor, f"factors[{index}]")
        expression = " × ".join(str(value) for value in factors)
    elif formula == "sum":
        component_ids = inputs.get("component_ids", [])
        missing = [key for key in component_ids if key not in prior]
        if missing:
            fail(f"{item.get('item_id')} 引用了未计算项：{missing}")
        result = sum((prior[key] for key in component_ids), Decimal("0"))
        expression = " + ".join(component_ids)
    elif formula == "monthly_rate_times_months_multiplier":
        rate = decimal(inputs.get("monthly_rate"), "monthly_rate")
        months = decimal(inputs.get("months"), "months")
        multiplier = decimal(inputs.get("multiplier", 1), "multiplier")
        result = rate * months * multiplier
        expression = f"{rate} × {months} × {multiplier}"
    elif formula == "daily_rate_times_days_multiplier":
        rate = decimal(inputs.get("daily_rate"), "daily_rate")
        days = decimal(inputs.get("days"), "days")
        multiplier = decimal(inputs.get("multiplier", 1), "multiplier")
        result = rate * days * multiplier
        expression = f"{rate} × {days} × {multiplier}"
    else:
        fail(f"不支持的公式：{formula}")
    return result, expression


def write_new(path: Path, text: str) -> None:
    if path.exists():
        fail(f"拒绝覆盖已有文件：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="劳动争议金额计算台账")
    parser.add_argument("--input", required=True)
    parser.add_argument("--json-output", required=True)
    parser.add_argument("--markdown-output", required=True)
    args = parser.parse_args()
    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        fail(f"无法读取计算输入：{exc}")
    items = payload.get("items", [])
    if not isinstance(items, list) or not items:
        fail("items 必须是非空数组。")
    scale = int(payload.get("decimal_places", 2))
    if scale < 0 or scale > 8:
        fail("decimal_places 必须在 0—8 之间。")
    quantizer = Decimal("1").scaleb(-scale)
    prior: dict[str, Decimal] = {}
    results = []
    for item in items:
        for required in ("item_id", "name", "formula", "legal_basis", "input_sources", "risk"):
            if required not in item:
                fail(f"计算项缺少 {required}：{item}")
        if not isinstance(item["input_sources"], list) or not item["input_sources"]:
            fail(f"{item['item_id']} 的 input_sources 必须是非空数组。")
        if not isinstance(item.get("pending_inputs", []), list):
            fail(f"{item['item_id']} 的 pending_inputs 必须是数组。")
        raw, expression = calculate(item, prior)
        rounded = raw.quantize(quantizer, rounding=ROUND_HALF_UP)
        prior[item["item_id"]] = rounded
        results.append(
            {
                "item_id": item["item_id"],
                "name": item["name"],
                "formula": item["formula"],
                "expression": expression,
                "amount": format(rounded, f".{scale}f"),
                "legal_basis": item["legal_basis"],
                "input_sources": item["input_sources"],
                "risk": item["risk"],
                "pending_inputs": item.get("pending_inputs", []),
                "alternative": item.get("alternative", False),
            }
        )
    output = {"status": "lawyer_review_required", "currency": payload.get("currency", "CNY"), "rounding": "ROUND_HALF_UP", "items": results}
    markdown = [
        "# 金额计算台账",
        "",
        "> 状态：算术结果待律师复核；公式的法律适用条件不由脚本判断。",
        "",
        "| 项目 | 公式 | 金额 | 法律依据 | 输入来源 | 风险／待确认 |",
        "|---|---|---:|---|---|---|",
    ]
    for item in results:
        pending = "、".join(item["pending_inputs"]) if item["pending_inputs"] else "无"
        sources = "、".join(str(value) for value in item["input_sources"])
        markdown.append(f"| {item['name']} | {item['expression']} | {item['amount']} | {item['legal_basis']} | {sources} | {item['risk']}；待确认：{pending} |")
    write_new(Path(args.json_output), json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    write_new(Path(args.markdown_output), "\n".join(markdown) + "\n")
    print(json.dumps({"status": output["status"], "item_count": len(results)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
