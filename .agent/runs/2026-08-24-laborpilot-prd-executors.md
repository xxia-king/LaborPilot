# LaborPilot 锁定文章 PRD 执行器记录

- 日期：2026-08-24
- 范围：公开版 LaborPilot 引擎 Plugin
- PRD：`/Users/jinls/Documents/02-🧠知识库/00-Inbox个人/🗒我的公众号写作/2026-08-22-LaborPilot公众号文章_v2.md`
- 边界：PRD 文章只读；私有知识源文件与 `scripts/build_cards.py` 不进入公开包；本轮不 commit、不 push。

## 本轮完成

### 材料接入与事实时间轴

- 实现 `scripts/ingest_materials.py`：原件只读、流式 SHA-256、类型／MIME／页数、PDF 逐页文字层状态、外部 OCR 路由、派生文本及 JSON／Markdown 索引。
- 实现 `scripts/build_timeline.py`：显式事实接入、日期句待核实提取、事实分层、来源验证、时间排序和身份证号／手机号脱敏。
- 工作流和独立验证器会重新计算源文件哈希，核对大小、逐材料接入记录、派生文件及事实来源。

### 请求／抗辩矩阵

- 实现 `scripts/build_issue_matrix.py --discover`：根据已确认任务和事实调用内置知识路由，只生成字段受限的 `to_review` 候选文件，不写入 `issues[]`。
- 实现 `scripts/build_issue_matrix.py --input`：验证代理立场、构成要件、事实／证据／法源 ID、支持状态与缺口、对方最强观点与回应、备选路径和失败后果。
- `issue_analysis` 完成条件由“存在 `issue_id`”升级为完整矩阵验证。旧占位争点可在显式 `--replace-existing-issues` 后升级，替换前状态自动保留在 `.casework/history/`。

### 证据链与举证责任

- 实现 `scripts/build_evidence_chain.py --scaffold`：按已复核争点的每个构成要件生成 `to_review` 骨架，不写入 `evidence[]`。
- 实现 `scripts/build_evidence_chain.py --input`：核验争点／要件／事实／材料引用，记录证据方向、证据项、举证主体、证据控制方、责任转移、不利后果、缺口和补证行动。
- 执行器重建构成要件和对方路径的双向 `evidence_ids`；每个构成要件必须有证据链或缺口链，不允许豁免。
- 证据评估为 `sufficient` 时，至少须有一项已关联材料且真实性状态已明确的 `available` 证据。旧占位证据可通过 `--replace-existing-evidence` 显式升级，替换前状态自动保留。

### 法源核验与适用性

- 实现 `scripts/build_authorities.py --scaffold`：按争点构成要件生成待核验任务，不将内置知识线索写入 `rules[]`。
- 实现 `scripts/build_authorities.py --input`：适配官方来源或法律数据库的经复核结果，保存完整条文及哈希、文件／条文锚点、来源 URL、检索时间、效力起止、地域和本案相关日期。
- 正式采用项必须已核验且明确适用；未生效、效力未明、地域错配或相关日期越界规则不得采用。历史旧法需同时满足相关日期位于效力期间并写明警示。
- 法源与构成要件、对方路径的 `rule_ids` 由执行器双向回写；每个构成要件均须覆盖，不得豁免。旧占位法源可通过 `--replace-existing-rules` 显式升级并保留历史快照。

### 专业金额计算与版本化参数

- 实现 `scripts/claims_engine.py` 和 `scripts/calculate_claims.py`：由律师／Agent 选择法律路径，脚本执行 N、N＋1、2N、三类加班工资、工伤一次性伤残补助金／伤残津贴／地域待遇／三笔一次性待遇合计、竞业限制补偿及金额合计。
- 每个数值输入必须引用案件状态中的已登记来源；计算记录保存公式版本、适用法源、相关日期、输入与来源、参数包版本及 SHA-256、假设、风险、算式、中间步骤、舍入口径、金额和内容摘要。
- N、N＋1、2N 必须明确确认三倍社平工资封顶是否适用；适用时必须提供 `monthly_wage_cap` 参数。脚本不自动择高，也不以金额反推请求权成立。
- 增加 `references/parameter-package.schema.json` 及全国工资折算、浙江最低工资参数包；外部年度社平工资等参数可按同一契约追加，效力期间、地域和官方来源均受校验。
- `--scaffold` 只生成待复核骨架；存在 `pending_inputs` 时金额、算式和步骤保持为空，且金额节点不得豁免。旧占位请求仅可通过显式 `--replace-existing-calculations` 升级并保留历史快照。
- 独立验证器重新执行公式并核对 `claims[]`／`calculations[]` 双向关系、输入来源、法源、参数包文件及哈希、金额、步骤和内容摘要，能够拦截参数日期／地域错配与手工篡改。

### 实质性对抗验证

- 实现 `scripts/adversarial_validation.py`，对每个争点生成我方结论、对方最强论证及引用、回应、待核实事项、失败边界、备选路径、事实分层和要件引用快照。
- 四项机器检查分别覆盖 `opponent_case`、`failure_boundaries`、`fact_layering` 和 `citation_consistency`；空挑战矩阵、已支持要件没有已证事实、对方论证无任何依据或待核实项等情形不能自报通过。
- 报告以 SHA-256 绑定当前案件业务状态。`record-validation` 登记时重新计算完整报告，并要求固定验证器身份；节点转换再次核对报告文件哈希和当前业务内容，阻止任意 JSON、过期报告和事后修改。
- 新增 4 项专项正反例，覆盖真实业务结果、合法登记、任意或过期报告拒绝、事实分层与反方论证缺口、空矩阵和文件篡改。
- 加入对抗验证后，本地与排除 `.git`、缓存、字节码及私有 `scripts/build_cards.py` 的隔离公开包均为 44 项测试通过；Python 编译、版本同步、Plugin 校验、6 个 JSON 解析、diff 和敏感信息扫描通过。

### 端到端办案回归

- 新增 `tests/test_end_to_end_casework.py`，以完全虚构材料依次调用公开脚本完成任务确认、材料接入、事实时间轴、争点矩阵、证据链、法源适配、2N 金额计算、策略审批、起草、双重验证、律师审批和阶段回写。
- 新增 `case_state.py record-decision`，把工资、计发月数和封顶适用性等经确认口径通过正式命令写入 `decisions[]`，供金额输入按来源 ID 引用。
- `generate_docs.py` 增加 `--work-dir` 和 `--strict`：内部 Markdown 写入 `.casework/drafting/`；Pandoc 失败时不能以 Markdown 生成成功冒充 DOCX 完成。
- 回归使用本机 Pandoc 3.10 真实生成 DOCX，并读取 `word/document.xml` 断言虚构当事人和 70,000.00 元请求已进入文书。该断言证明内容链真实可用，不宣称已经完成 JLS 最终提交版的字体、行距、缩进和落款验收。
- 首轮暴露确定性验证器不会创建 `.casework/validation/`，已修复为创建父目录且继续拒绝覆盖已有报告；修复后整条链到达 `stage_close`。
- 加入端到端回归后，本地与隔离公开包均为 45 项测试通过；Python 编译、版本同步、Plugin 校验、6 个 JSON 解析、diff、安全扫描和私有 `scripts/build_cards.py` 排除检查通过。

### 正式产物端到端追溯

- 新增 `references/artifact-traceability.md`，把正式产物的验收固定为五段链：业务来源、直接上游产物、生成器／LaborPilot 版本／文件哈希、绑定实际文件的验证报告、绑定产物与报告快照的律师审批。
- `register-artifact` 增加 `delivery_status`、`generator` 和 `source_refs`，自动写入当前公开包版本和业务记录规范化 SHA-256；`derived_from` 只表示真实上游产物，不再混入事实、决定等业务 ID。
- `record-validation` 保存被验证产物的哈希快照；`lawyer_approval` 必须绑定具体正式产物和当前风险等级要求的全部最新验证记录。阶段结案再次复算文件、来源、报告和审批快照。
- 增加 `trace-artifact` 命令及独立验证接入。来源记录事后改变、上游或正式文件改变、上游循环、报告改变、审批未绑定实际产物等情形均会被阻断。
- 金额台账同步改用 `source_refs` 指向计算、请求和经确认输入来源，并登记为 `internal_work_product`，修复过去将决定 ID 填入 `derived_from` 的语义混用。
- 聚焦回归 16 项、本地全量 48 项和隔离公开包 48 项测试均通过；`TASKS.md` 的正式产物端到端追溯项据此标记完成。

### 知识构建统计清单

- 新增 `data/knowledge-build-stats.json` 和 `scripts/knowledge_stats.py`。公开包可从 `issue_router.py` 的当前编译载荷复算卡片数量、路由类别数量及载荷哈希，不输出完整知识卡。
- 96 张知识卡的机器统计为 82 张争点卡、14 张案由门卡和 80 张含浙江口径卡；22 项细分案由标签加编译载荷中的 1 个劳动合同纠纷兜底运行路由，共 23 类。
- 149 份来源文件在公开清单中仅保留连续编号、范围、文件大小、标题哈希和内容哈希；公开包可验证清单内部一致性，开发环境提供私有来源目录后才能逐份复算来源承诺。
- `scripts/sync_version.py` 同步并校验统计清单的 `package_version`，避免版本发布后统计清单漂移。
- 知识统计专项 3 项和本地全量 51 项测试通过；私有来源目录复算 149 份承诺一致。
- 新隔离公开包 `/private/tmp/laborpilot-stats-public.tos4Ii/LaborPilot` 共 79 个文件、1142784 字节；51 项测试、28 个公开 Python 文件语法、版本 `1.2.0`、统计复算、Plugin 校验、9 个 JSON 解析和敏感模式扫描均通过，且不含 `scripts/build_cards.py`。
- `TASKS.md` 的构建统计清单项据此标记完成；本轮未修改锁定文章，未启动 Word 或领域评测任务。

## 对抗性审查与修复

- 重新接入已完成 OCR 的 PDF 时，不再以新的 pdftotext 暂存件覆盖 OCR 派生文本；保留外部工具附加字段与其他产物。
- 接入前后复算哈希，材料在过程中变化时拒绝写入。
- 超过 32 MiB 的本地文本不整体解码入内存；事实句以有界缓冲区流式扫描。
- 事实 ID 不再包含状态；同一事实可从 `to_verify` 升级为 `supported`，不生成重复事实。
- 拒绝不安全的事实／材料 ID，以及 `.casework/materials/` 之外的派生文本路径。
- 旧占位争点不会在基础状态读取阶段锁死修复命令，但会被工作流门禁和独立验证器阻断。
- 证据链不能以一条占位 ID、单向链接或豁免绕过；全部为缺失／待核实证据时不得将评估标为充分。
- 法源输入反例覆盖内部知识冒充权威来源、URL 无效、条文哈希不符、地方口径与管辖地错配、时间越界、待核验法源冒充正式采用、废止规则无警示以及要件覆盖不完整。

## 验证证据

- 金额执行器加入前，`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` 及隔离公开包均为 32 项通过。
- 金额执行器加入后，本地全量测试 40 项通过；`python3 -m py_compile scripts/*.py tests/*.py` 通过。
- 排除 `.git/`、`__pycache__/`、`*.pyc` 和 `scripts/build_cards.py` 的隔离公开包：40 项测试与 Python 编译通过，共 71 个文件、974848 字节。
- `python3 scripts/sync_version.py --check`：版本一致，当前为 `1.2.0`。
- 本地仓库与隔离公开包的 `validate_plugin.py .`：Plugin validation passed。
- `workflow/graph.json`、`references/case-state.schema.json`、`references/parameter-package.schema.json`、`.codex-plugin/plugin.json` 及两个内置参数包：本地与隔离公开包共 6 个 JSON 解析通过。
- `git diff --check`：通过。
- 本地仓库与隔离公开包的 API Key／Token／密码赋值及私钥头模式扫描：未发现命中。
- `scripts/build_cards.py`：继续由 `.gitignore` 排除，未被 Git 跟踪，隔离公开包中不存在。
- 正式产物追溯加入后，本地与隔离公开包均为 48 项测试通过；Python 编译、版本 1.2.0 同步、Plugin 整包校验、6 个 JSON 解析、`git diff --check` 和敏感信息模式扫描通过。隔离公开包共 76 个文件、896196 字节，路径为 `/private/tmp/laborpilot-trace-public.EFzfdU/LaborPilot`，不含私有 `scripts/build_cards.py`。

金额专项共 8 项，覆盖专业公式正例、官方与外接参数包、封顶适用性确认、精确输入契约、待确认门禁、篡改检测和旧占位升级。金额阶段的静态检查、Plugin 整包检查和干净公开包端到端复验均已通过，`TASKS.md` 中专业金额与版本化参数项据此标记完成。

## Task 19：领域评测持续机制

- 新增 `scripts/domain_eval.py` 和 `evals/legal-version-cases.json`，并将 `evals/evals.json` 升级为版本化评测数据。当前基线覆盖 13 个路由场景和 4 个法律版本边界场景，该数量只是当前数据集状态，不代表持续评测已永久完成。
- 路由评测断言公开可见的争点和结果数量，同时检查否定语境与非劳动争议的误召回。数据契约拒绝 `expected_cards`、`expected_gate` 等内部字段，报告不输出知识卡正文或内部卡号。
- 法律版本评测以相关日期而非公布日判断适用版本；`selection_mode=single_active` 要求时间线任意日期只有一个有效版本，重叠和空档均由反例测试阻断。
- `scripts/sync_version.py` 已将 `evals/evals.json.package_version` 纳入 `VERSION` 唯一版本源，包含设置、一致性检查和版本漂移反例。
- Task 19 验收结果：本地和隔离公开包均为 65 项测试通过；当前领域与法律版本结果均为 17／17 通过。隔离包 `/private/tmp/laborpilot-domain-public.h7WUQv/LaborPilot` 完成版本 1.2.0、知识统计、Plugin、31 个 Python 文件、11 个 JSON、敏感赋值、内部评测字段和私有构建脚本排除检查；共 84 个文件、1039765 字节。

## Task 20：材料分页、程序路径与独立验证补齐

- Task 20.1：材料接入记录和总索引增加连续 `page_index`，逐页保存文字层、可提取字符数和 OCR 状态；删除或篡改分页索引会被 `traceable_material` 门禁阻断。本地和隔离公开包全量 65 项均通过。
- Task 20.2：新增 `scripts/analyze_procedure.py` 和 `procedural_assessments[]`，逐争点记录时效、管辖、一裁终局、临时救济和后续救济路径；法源、日期、地域、待确认项和 `procedure_digest` 受结构化校验。金额与程序双门禁均不可豁免。本地和隔离公开包全量 67 项、领域评测 17／17 均通过。
- Task 20.3：事实冲突使用双向 `conflicts_with_fact_ids`、`conflict_status`、`conflict_explanation` 和 `conflict_next_action`；拒绝自引用、不存在引用、单向链接、冲突状态不一致和未解决冲突冒充已证事实。
- 对抗验证报告版本升级为 1.1，以六项检查覆盖对方最强论证、失败边界、事实分层、事实冲突、引用一致性和程序完整性；报告增加事实冲突矩阵、程序矩阵，并将 `procedural_assessments[]` 纳入业务状态摘要。
- Task 20.3 本地与隔离公开包均为 70 项测试通过，领域评测均为 17／17。最终隔离包 `/private/tmp/laborpilot-conflict-public.Vrkj2z/LaborPilot` 共 85 个文件、1318912 字节；版本 1.2.0、Plugin、全部 JSON 和 32 个公开 Python 文件语法通过，不含 `.git`、缓存、字节码、`.DS_Store` 或私有 `scripts/build_cards.py`。
- 锁定文章未修改，版本未变，本轮未 commit、未 push。

## Task 20.4：锁定文章最终能力审计

- 新增 `references/article-prd-capability-audit.md`，按“可执行实现、Agent／Skill 驱动、外部能力、产品输出边界和发布状态”逐项建立声明—证据矩阵。
- 审计已覆盖 149／96／82／14／23 数字口径、动态争点覆盖与非完整卡片输出、1＋9 Skill、完整工作链、材料分页、事实分层与冲突、请求／抗辩、证据、法源、金额、程序、三类 DOCX、六项独立验证、离线能力、外部 OCR／法源／Pandoc、通用 Agent 与 Codex Plugin。
- 未发现需要继续补代码的文章能力缺口。锁定文章写 v1.1.0，而当前本地和 GitHub 公开版本为 v1.2.0；本轮增强仍未提交、未推送，因此“本地候选包已实现”和“GitHub 已发布”继续分开记录。
- 最终验收通过：本地与隔离公开包均为 70 项测试、领域与法律版本评测 17／17；版本 1.2.0、知识统计、Plugin、32 个 Python 文件、11 个 JSON、敏感赋值和禁止项检查均通过。
- 最终隔离包为 `/private/tmp/laborpilot-final-public.VXRYP1/LaborPilot`，共 86 个文件、1129411 字节，不含 `.git`、缓存、字节码、`.DS_Store` 或私有 `scripts/build_cards.py`。

## 完成状态与发布边界

- Task 18 已增加 JLS Word 版式修正／结构校验、`01_律师复核初稿/` 与 `02_最终提交版/` 交付分层、内部 Markdown／版式报告、防覆盖、显式 `--types`、最终版律师决定／占位符／行动清单门禁，以及最终版直接来源于当前已批准初稿的追溯门禁。
- DOCX 专项测试 6 项通过；三类虚构文书经仅用于本机视觉 QA 的 Fontconfig 映射渲染为单页，未发现中文方框、裁切、重叠，证据目录提交时间保持单行。正式 OOXML 仍声明 `仿宋_GB2312`，没有写入本机回退字体替代。
- Task 18 最终验收通过：本地全量 57 项、隔离公开包全量 57 项均通过；公开副本中 30 个 Python 文件语法、版本 1.2.0、Plugin 清单、10 个 JSON 和私有构建脚本排除检查通过。隔离包为 `/private/tmp/laborpilot-word-public.qpIMtM/LaborPilot`，共 83 个文件、1208320 字节；三类虚构 DOCX 在隔离包中真实生成、结构校验并渲染为 3 份单页 PDF，中文文本可提取。
- Task 18 已据此完成并在 `TASKS.md` 勾选。Task 19 已建立版本化持续评测机制并完成当前基线验收；以后的路由或法律口径变更仍须递增数据集版本。
- Task 17—20.4 均已完成，本轮不再开启新的能力补齐任务。
- 当前工作树未提交、未推送；本轮完成的是本地候选实现与干净公开包验收，不得将本记录解读为已在 GitHub 发布。
