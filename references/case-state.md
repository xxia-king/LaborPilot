# 案件图状态数据契约

## 用途

`.casework/case_state.json` 是同一案件跨任务、跨阶段的唯一结构化状态入口。它不替代原始案卷，只记录来源、分析状态、工作图运行和经用户确认的决定。完整结构见 [case-state.schema.json](case-state.schema.json)，目录规范见 [output-layout.md](output-layout.md)。

## 基础字段

- `case_id`：案件本地唯一标识，不放身份证号或手机号。
- `task_context`：用户确认的本轮具体任务、期望产物、限制及确认记录。该字段未完整时不得处理案件材料。
- `representation`：`employee`、`employer` 或 `undetermined`。未确认委托立场时必须使用 `undetermined`，不得为了通过 Schema 猜测一方。
- `stage`：未确认时为 `undetermined`；确认后为 `intake`、`pre_arbitration`、`arbitration`、`first_instance`、`second_instance` 或 `closure`。
- `jurisdiction`：默认“浙江省”，具体管辖地另行记录。
- `analysis_date`：ISO 日期，作为时效和新旧法分析基准。
- `risk_level`：`standard`、`complex` 或 `high`，控制验证深度和律师升级要求。

## 业务状态

1. `facts[].status` 只能为 `supported`、`client_statement`、`opponent_allegation`、`disputed` 或 `to_verify`。
2. `supported` 事实至少关联一份材料来源。
3. `decisions[]` 只记录用户明确确认的事实、策略、金额或文书口径，并记录确认人与日期。
4. 不在状态文件中嵌入身份证、病历、聊天记录等原始材料全文，只记录本地路径和摘要。

## 工作图状态

- 新案件必须从 `task_intake` 启动。只有 `task_context`、`representation` 和 `stage` 获得用户确认后，才能进入 `material_ingestion`。
- `current_node`、`pending_nodes` 与 `node_runs`：当前节点、分支待执行节点及每次执行的输入、产物、执行者和结果。
- `validations`：验证者、结论、问题和待验证产物。
- `approvals`：策略审批和律师交付审批。
- `checkpoints` 与 `paused`：暂停原因、恢复条件和恢复位置。
- `artifacts`：产物路径、版本、SHA-256、生成者、生成时间和上游产物。
- `events`：只追加不静默改写的审计日志。

## 版本与迁移

1. 当前 Schema 版本为 `2.0`。
2. 日常阶段变更和工作图转换就地更新单一 `case_state.json`；写入前自动将旧状态保存到 `.casework/history/`，`previous_state` 指向该内部快照。
3. 1.0 状态使用 `python3 scripts/case_state.py migrate` 生成 2.0 文件，不覆盖旧文件；迁移完成后以 `.casework/case_state.json` 作为唯一当前状态。
4. 新材料与旧状态冲突时，保留两种记录并标记待确认，不静默覆盖。

## 材料可追溯字段

原始文件至少登记 `source_path`、`source_sha256`、页码范围和 `original_or_copy`。存在 OCR 或其他派生文件时，同时登记 `derivative_path`、`ocr_engine`、`ocr_language`、`ocr_status` 与 `visual_review_status`。OCR 结果只是定位线索，不因字段齐全而自动变成证据原文。

## 回写闭环

每轮结束至少回写：新增材料、已确认事实、待查事项、证据缺口、法源核验、程序期限、节点结果、验证与审批、成果文件和优先级最高的下一步。
