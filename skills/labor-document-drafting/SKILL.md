---
name: labor-document-drafting
description: 劳动争议法律文书起草。基于分析结果,按模板生成仲裁申请书、答辩状、代理词等文书的律师复核初稿。
homepage: https://jinlishan.com/
author: 金莉珊律师（微信jinlishan_）
version: "1.2.0"
license: AGPL-3.0
---

# 劳动争议文书起草

1. 读取案件状态和上游分析/证据/金额结果。
2. 按模板起草,每个请求项/抗辩项:
   - 事实段引用证据清单中的证明事项
   - 法律依据段引用条文号(法规名+条号)
   - 金额段引用计算算式和结果
   - 浙江口径在关键争点上引用
3. 生成 .docx 格式(用户交付);Markdown 仅作内部工作稿。
4. 交独立验证后,经律师审批标注"律师复核初稿"。
5. 禁止引用未经核实的法条或裁判口径。
6. 完成节点前使用 `register-artifact` 登记真实存在的初稿文件，并在 `transition --event pass` 中以 `--output-artifact` 关联该 `artifact_id`；只写“已起草”或登记不存在的路径不能通过门禁。
