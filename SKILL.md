---
name: LaborPilot
homepage: https://jinlishan.com/
author: 金莉珊律师（微信jinlishan_）
version: "1.0.0"
license: AGPL-3.0
description: 中国劳动争议智能办案引擎。内置96个争点(覆盖23个案由门)、浙江裁判口径、文书生成器。当用户需要分析劳动争议案件、计算经济补偿/赔偿金/加班费/工伤待遇、生成仲裁申请书或证据清单时使用。产出的所有分析结果和法律文书均由AI辅助生成,仅供参考,必须经专业律师审核后方可使用。
---

# LaborPilot — 劳动争议智能办案引擎

## 免责声明

**LaborPilot 产出的所有分析结果和法律文书均由 AI 辅助生成,仅供参考,不构成法律意见,必须经专业律师审核后方可使用。**

## 快速开始

```bash
# 列出全部案由门
python3 scripts/issue_router.py --list-gates

# 按关键词查争点
python3 scripts/issue_router.py --search "违法解除"

# 查看争点详情
python3 scripts/issue_router.py --card E10 --full

# 生成法律文书
python3 scripts/generate_docs.py --case my_case.json --output ./output
```

## 工作流

十节点: task_intake → material_ingestion → intake → issue_analysis → [evidence ∥ authority] → claims_procedure → strategy_approval → drafting → validation → lawyer_approval → stage_close

每个节点对应 skills/ 下的一个子技能。
