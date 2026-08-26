# 锁定公众号文章 PRD 能力审计

## 审计基线

- PRD：`2026-08-22-LaborPilot公众号文章_v2.md`，本轮只读，SHA-256 为 `dd46f14a2cbcb2896b0710db72ed7f68747f13ecdc23062a830aa9ade8e1ac6c`。
- 当前发布版本：`1.3.0`。
- 公开入口：`https://github.com/xxia-king/LaborPilot`；仓库与 Plugin 清单均采用 `AGPL-3.0`。
- 功能验收：本地及隔离公开包均为 70 项测试通过；领域与法律版本评测均为 18／18。
- 审计原则：只把可执行代码和动态业务测试认定为确定性实现；Skill／Agent 推理、外部能力和发布状态单独列明。

## 结论

文章中的办案能力主张在当前发布包中均已有相应实现证据，没有继续补代码的功能缺口。OCR、现行法源核验和 Pandoc 仍按文章所述分别属于外部能力或运行环境依赖；实体和程序结论仍需律师／Agent 复核，不属于脚本自动决策。

锁定文章仍保留一项历史状态差异，不属于功能缺口：

1. 锁定文章写“当前公开版本为 v1.1.0”；截至 2026-08-27，GitHub 已发布 `v1.3.0`。文章保持只读，不回写后续发布状态。

因此，当前准确结论是：**文章所述能力已在干净公开包中实现并验收，并已随 `v1.3.0` 发布到 GitHub。**

## 声明—证据矩阵

| 文章能力声明 | 能力层 | 当前证据 | 审计结论 |
|---|---|---|---|
| 149 部法规文献编译为 96 张知识卡 | 可执行实现 | `data/knowledge-build-stats.json`、`scripts/knowledge_stats.py`、`tests/test_knowledge_stats.py` | 通过；公开清单只保留最小统计与哈希承诺，不公开来源标题、路径、正文或完整卡片 |
| 82 张争点卡、14 张案由门卡、23 类案由入口 | 可执行实现 | 知识统计执行器复算 82＋14；22 项细分案由加 1 个兜底运行路由；统计反例回归 | 通过；“23 类”按当前运行路由口径成立 |
| 根据案件需要动态覆盖相关争点，不固定返回若干结果 | 可执行实现 | `scripts/issue_router.py` 使用相关性阈值；`tests/test_issue_router.py` 覆盖宽查询、空查询、重复查询和公开输出结构；领域评测覆盖复合与否定语境 | 通过；结果数量由相关性决定，不采用固定 Top-N |
| 知识卡作为内部办案依据，不完整返回卡片或批量原始数据 | 产品输出边界 | 路由公开 Schema、敏感字段禁止测试、领域 CLI 输出测试 | 通过；这是正常接口输出边界，不是“编译后不可提取”的安全保证 |
| 任务确认至阶段回写的完整工作链和节点门禁 | 可执行实现 | `workflow/graph.json`、`scripts/workflow_graph.py`、`tests/test_workflow_requirements.py`、端到端回归 | 通过；上游状态、真实产物和报告支撑均受机器门禁约束 |
| 代理立场和程序阶段未确认时，不进入实体分析 | 可执行实现＋Agent 确认 | 任务接入契约、`confirmed_representation` 与 `confirmed_stage` 门禁、工作流正反例 | 通过；系统不依据文件名或材料来源静默猜测立场和阶段 |
| 1 个总控加 9 个专业 Skill | Agent／Skill 驱动＋可执行入口 | `skills/` 下共 10 个 Skill，其中 `labor-dispute-casework` 为总控，其余 9 个对应文章所列分工 | 通过；根 `SKILL.md` 是通用 Agent 入口，不另计入“1＋9” |
| 材料只读登记、文字层检测、OCR 路由和分页索引 | 可执行实现＋外部 OCR | `scripts/ingest_materials.py`、逐页 `page_index`、材料哈希门禁、`tests/test_material_fact_executors.py` | 通过；OCR 识别本身由运行环境提供，执行器负责路由、登记和复核状态 |
| 时间轴和事实分层，区分已证事实、双方陈述、争议与待核实事项 | 可执行实现＋Agent 标注 | `scripts/build_timeline.py`、事实状态 Schema、来源关系和脱敏回归 | 通过；自动日期句一律为 `to_verify`，`supported` 必须关联材料 |
| 独立验证器检查事实矛盾 | 可执行实现 | 双向事实冲突字段、`fact_conflicts` 检查、事实冲突矩阵及单向／未解决／冒充已证反例 | 通过；未解决冲突必须有说明和行动，并在审批前退回核实 |
| 请求／抗辩矩阵包含构成要件、对方最强观点、备选路径和失败后果 | 可执行实现＋律师／Agent 复核 | `scripts/build_issue_matrix.py`、`tests/test_issue_matrix_executor.py` | 通过；自动发现仅生成待复核候选，正式矩阵由复核输入形成 |
| 证据链、举证责任、单位掌握证据和补证方向 | 可执行实现＋律师／Agent 复核 | `scripts/build_evidence_chain.py`、双向要件链接、证据缺口与责任转移反例 | 通过；缺证时必须形成缺口链，不能以空记录或豁免替代 |
| 核对法源全称、文号、条号、效力、地域和时间适用性 | 可执行适配器＋外部法源 | `scripts/build_authorities.py`、法源矩阵、条文哈希、来源 URL、时间与地域反例 | 通过；内置知识只作线索，正式引用依赖官方来源或法律数据库的复核结果 |
| 计算 N、N＋1、2N、加班工资、工伤待遇和竞业限制等金额 | 可执行实现＋路径选择 | `scripts/claims_engine.py`、`scripts/calculate_claims.py`、参数包 Schema、金额专项回归 | 通过；公式选择和请求权成立由律师／Agent 复核，脚本只执行已选路径并精确到分 |
| 审查时效、管辖、一裁终局、先予执行和后续救济路径 | 可执行实现＋律师／Agent 复核 | `scripts/analyze_procedure.py`、`procedural_assessments[]`、`reviewed_procedure_path` 不可豁免门禁 | 通过；程序骨架不自动成为结论，待确认项会阻断策略审批 |
| 生成仲裁申请书、证据目录和行动清单初稿 | 可执行实现＋Pandoc | `scripts/generate_docs.py` 支持三类文书；`tests/test_docx_style.py` 实际生成并打开 DOCX | 通过；行动清单只属于内部复核稿，不得生成最终提交版 |
| 策略确认、独立验证和律师审批后再交付 | 可执行实现＋人工审批 | 策略／验证／律师审批门禁、正式产物追溯、`tests/test_artifact_traceability.py` | 通过；最终提交版直接派生自当前已批准初稿并重新验证、审批 |
| 不把无来源陈述当成已证事实，不虚构证据或承诺案件结果 | Agent／Skill 约束＋可执行门禁 | 事实来源关系、证据链门禁、请求失败边界、律师审批及相关反例 | 通过；确定性代码阻断无来源的已证事实和不完整证据链，实体结论仍由律师／Agent 复核 |
| 独立验证检查反方论证、事实分层、事实冲突、证据／法源／金额引用一致性和程序遗漏 | 可执行实现 | `scripts/adversarial_validation.py` 报告版本 1.1，六项检查、事实冲突矩阵、程序矩阵及过期报告反例 | 通过；金额台账由 `citation_consistency` 重算校验，事实或程序业务状态变化后旧报告失效 |
| 核心知识组件和办案逻辑离线运行 | 可执行实现 | 干净隔离公开包无网络完成 70 项回归和 18／18 领域评测 | 通过；OCR、外部法源核验和 Pandoc 按文章说明另行提供 |
| 通用 Agent、专业 Skill 自动发现和 Codex Plugin 入口 | 通用入口＋Codex 适配 | 根 `SKILL.md`、`skills/`、`.codex-plugin/plugin.json`，整包 Plugin 校验通过 | 通过；Codex 是附加入口，不改变通用 Agent 结构 |
| GitHub 公开地址与 AGPL-3.0 许可 | 发布事实 | Git 远端、`LICENSE`、`.codex-plugin/plugin.json` | 通过；仓库地址和许可与当前公开状态一致 |
| 公开仓库包含可运行引擎和编译知识组件，不公开可编辑卡源与构建流水线 | 发布状态 | GitHub `v1.3.0` 已发布；干净公开包完成验收，并排除 `.git`、缓存、字节码和私有构建脚本 | 通过；公开包保留运行所需的编译知识组件，不公开可编辑卡源或私有构建脚本 |

## 最终验收门槛

- 锁定文章保持只读，审计只改变实现和项目内证据记录。
- 本地与干净公开包须同时通过全量测试、领域评测、版本同步、Plugin、JSON、Python 语法和私有构建脚本排除检查。
- 本轮已取得明确授权并完成 commit／push；`v1.3.0` tag、GitHub Release 和对应工作流均已核验通过。
