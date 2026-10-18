---
name: labor-document-drafting
description: 劳动争议法律文书起草。基于分析结果,按模板生成仲裁申请书、答辩状、代理词等文书的律师复核初稿。
homepage: https://jinlishan.com/
author: 金莉珊律师（微信jinlishan_）
version: "1.5.0"
license: AGPL-3.0
---

# 劳动争议文书起草

> 废止复核（2026-09-07）：不得用浙江已废止旧解答充当现行法源；旧观点须另核有效条文后再写入正式依据，历史比较应明确来源状态。


1. 读取案件状态和上游分析/证据/金额结果。
2. 按模板起草,每个请求项/抗辩项:
   - 事实段引用证据清单中的证明事项
   - 法律依据段引用条文号(法规名+条号)
   - 金额段引用计算算式和结果
   - 浙江口径在关键争点上引用
   - 全部文字遵循[书面语体规范](../../references/writing-style.md)，同一论点只论述一处
3. 使用 `python3 scripts/generate_docs.py --case <结构化输入.json> --output <case-root> --types <用户明确要求的文书> --delivery-status lawyer_review_draft --strict` 生成 `.docx` 律师复核初稿；不得省略 `--types` 或顺带生成未请求文书。DOCX 进入 `01_律师复核初稿/`，Markdown 和版式报告进入 `.casework/drafting/`，已有同版本文件不得覆盖。
4. 生成《案件研判报告》时，先运行 `python3 scripts/build_report_input.py --state <case-root>/.casework/case_state.json` 从案件状态生成输入脚手架，再按[结构契约](../../references/case-report-contract.md)补写全部“【待撰写】”处并列出论点清单；脚手架预填的金额、期限和法条原文不得手工改写。然后运行 `python3 scripts/report_lint.py --input <输入.json>`，再以 `--types 研判报告` 生成。写作校验被阻断时修改输入，不得绕过；研判报告只生成律师复核稿。
5. 生成器必须在 Pandoc 转换后应用并校验 JLS Word 版式；转换或版式校验失败时，不得以内部 Markdown 或命令成功提示冒充文书完成。
6. 初稿交独立业务验证并由律师针对当前文件哈希审批。只有在律师已批准当前初稿后，才可使用 `--delivery-status final_submission --approved-by <律师姓名>` 生成 `02_最终提交版/` 中的新文件；最终提交版须重新验证并重新审批。行动清单、内部占位符和待确认标记不得进入最终提交版。
7. 禁止引用未经核实的法条或裁判口径。
8. 完成节点前先将起草输入登记为 `internal_work_product`，再运行 `python3 scripts/workflow_graph.py register-artifact --state <case-root>/.casework/case_state.json --path <初稿.docx> --kind <产物类型> --version <版本号> --delivery-status lawyer_review_draft --generator scripts/generate_docs.py --created-by <执行者> --source-ref <集合:记录ID> --derived-from <起草输入artifact_id>` 登记真实存在的初稿文件，并在 `python3 scripts/workflow_graph.py transition --state <case-root>/.casework/case_state.json --event pass --actor <执行者> --output-artifact <初稿artifact_id>` 中关联该产物。正式产物必须形成业务来源链；只写“已起草”或登记不存在的路径不能通过门禁。最终提交版另建 `artifact_id`，并以 `derived_from[]` 直接关联已获律师批准的当前初稿。
