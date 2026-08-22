# LaborPilot 1.2.0 收尾记录

- 日期：2026-08-22
- 范围：公开版 LaborPilot 引擎插件
- 目标：补齐领域评测与工作流机器门禁，同步版本和文档，完成发布前审查。

## 本轮完成

- 将 8 个劳动争议领域场景纳入自动回归，并断言核心争点召回。
- 为材料、事实、争点、证据、法源、请求、初稿和验证增加机器完成条件。
- 增加结构化用户确认豁免；初稿产物和 JSON 验证报告不可豁免。
- 要求 `pass`／`escalate` 验证结论必须由含 `status`、`findings` 的 JSON 报告支撑。
- 修复无报告升级绕过，以及有报告升级后被错误阻断于律师审批之前的问题。
- 将整包 Plugin、内置 Skills、README 与变更日志版本统一为 `1.2.0`。

## 验证证据

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`：14 项通过。
- `python3 scripts/sync_version.py --check`：版本一致性校验通过。
- `validate_plugin.py .`：Plugin validation passed。
- `git diff --check`：通过。
- 三个 JSON 文件经 `python3 -m json.tool` 解析通过。

## 边界与后续

- 公开路由继续只输出办案分析所需字段，不返回完整知识卡正文、内部卡号或原始字段结构。
- OCR、法律数据库和 MCP 仍属于按任务调用的外部能力，不写成插件内置自动能力。
- 干净公开 checkout 的端到端办案回归、构建统计复核及业务执行器扩展继续保留在 `TASKS.md`。
