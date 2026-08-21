---
name: labor-document-drafting
description: 劳动争议法律文书复核初稿起草。基于争点卡的文书指向和模板，生成仲裁申请书、答辩状、代理词等文书的律师复核初稿。
homepage: https://jinlishan.com/
author: 金莉珊律师（微信jinlishan_）
version: "0.2.0"
license:
---

# 劳动争议文书起草

1. 先读 `.casework/case_state.json` 和上游研判/证据/金额报告。
2. **查争点卡的文书指向**：运行 `python3 scripts/issue_router.py --card {卡ID}` 获取该争点对应的文书模板（如 `assets/arbitration-application.md`、`assets/defense.md` 等）。
3. 按模板结构起草，每个请求项/抗辩项的：
   - **事实段**引用证据清单中的证明事项和证据
   - **法律依据段**引用争点卡 basis 中的条文号（法规名+条号，不含条文原文）
   - **金额段**引用金额计算的算式和结果
   - **浙江口径**在关键争点上引用浙高法解答/纪要的裁判口径
4. 代理词须覆盖争点卡中标注的"高频争点"和"高频陷阱"。
5. 生成 `.docx` 格式（用户交付层）；Markdown 仅作为 `.casework/` 内部工作稿。
6. 交 `labor-case-validator` 独立验证后，经律师审批标注"律师复核初稿"。

禁止在文书中引用争点卡未覆盖的法条或裁判口径（防编造）；需补充的标注"待查"并说明来源方向。
