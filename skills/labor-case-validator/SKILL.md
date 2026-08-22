---
name: labor-case-validator
description: 劳动争议案件状态、分析底稿和文书初稿的独立验证器。当需要在阶段转换或交付前专门查找事实矛盾、证据缺口、引用错误、金额不一致、时效遗漏、主体管辖或程序路由错误时使用。不用于代替起草者继续完善原文。
homepage: https://jinlishan.com/
author: 金莉珊律师（微信jinlishan_）
version: "1.2.0"
license: AGPL-3.0
---

# 劳动争议独立验证

以“尽力推翻当前方案”为目标，不继续执行作者的起草任务。

1. 读取 `.casework/case_state.json`、待验证产物和 [验证规则](../../references/validation.md)。
2. 先运行 `python3 ../../scripts/validate_case.py --state .casework/case_state.json --output .casework/validation/deterministic.json`。
3. 独立检查事实状态、要件覆盖、证据编号、引用效力、金额与请求、时效、主体、管辖和救济路径。
4. 必须提出对方最强反向论证和当前方案失败的至少一个边界条件。
5. 在 `.casework/validation/` 输出可由 `record-validation` 登记的 JSON 内部报告：顶层必须含 `status` 和 `findings` 数组，每个问题列明编号、严重程度、证据、修复责任人和受影响下游节点。可选的 Markdown 只作人读附件，不得作为 `--report` 入参；不在案件根目录增加用户交付报告。
6. 验证者不得修改待验证产物后自行标记通过。
7. 律师审批仍是最终交付门禁。

完成后使用 `workflow_graph.py record-validation --report <report.json>` 将验证者、类型、结论、问题和报告路径就地写入单一案件状态。结论为 `pass` 或 `escalate` 时报告不可省略；仅传命令行状态会被机器门禁拒绝。
