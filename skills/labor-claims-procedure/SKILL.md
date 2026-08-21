---
name: labor-claims-procedure
description: 劳动争议金额计算、时效和程序路径。基于争点卡的算式和浙江口径，计算各项请求金额并确定程序策略。
homepage: https://jinlishan.com/
author: 金莉珊律师（微信jinlishan_）
version: "0.2.0"
license:
---

# 劳动争议金额与程序

1. 先读 `.casework/case_state.json` 和上游研判报告中的争点结论。
2. **查争点卡的算式**：运行 `python3 scripts/issue_router.py --card {卡ID} --full` 获取该争点的计算公式、基数口径和封顶规则。
3. 每项请求按卡中算式逐项计算：
   - 经济补偿 N / 赔偿金 2N / 代通知金（F 系卡）
   - 加班费三倍率（B 系卡）
   - 工伤待遇 / 伤残津贴 / 三笔一次性（H 系卡）
   - 竞业限制补偿（G 系卡）
4. 数值包钩子：社平工资 / 最低工资 / 高温津贴等年度数值从 `data/compensation-standards/` 读取（`compensation_standards.py`），不硬编码。
5. **浙江口径优先**：计算中的浙江特殊规则（如不定时无节假日加班费 / 加班费入补偿基数 / 跨2008分段）按卡的浙口径节执行。
6. 程序路径：根据金额和案件类型判断是否适用一裁终局（K3卡）、先予执行（K4卡）。
7. 生成 `03_金额与程序_vN.md`：逐项列算式、代入数值、结果、依据卡ID。

时效审查联动 K1 卡（兜底门）：普通 1 年 vs 劳动报酬特殊时效。
