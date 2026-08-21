---
name: LaborPilot
homepage: https://jinlishan.com/
author: 金莉珊律师（微信jinlishan_）
version: "1.0.0"
license: AGPL-3.0
description: 中国劳动争议智能办案引擎。输入案件信息,产出法律分析、金额计算和仲裁文书。内置96个争点、浙江裁判口径、文书生成器。当用户需要分析劳动争议案件、计算经济补偿/赔偿金/加班费/工伤待遇、生成仲裁申请书或证据清单时使用。产出的所有分析结果和法律文书均由AI辅助生成,仅供参考,必须经专业律师审核后方可使用。
---

# LaborPilot — 劳动争议智能办案引擎

## 免责声明

**LaborPilot 产出的所有分析结果和法律文书均由 AI 辅助生成,仅供参考,不构成法律意见,必须经专业律师审核后方可使用。**

## 用法

### 生成文书(主要用法)

准备案件数据 JSON(当事人/时间线/工资标准/解除原因),运行:

```bash
python3 scripts/generate_docs.py --case my_case.json --output ./output
```

产出: `仲裁申请书.docx` + `证据清单.docx` + `行动清单.docx`

文书模板持续更新中,支持自定义加入。

### 查特定法律问题(辅助用法)

如需单独查询某个法律争点(不生成整套文书):

```bash
python3 scripts/issue_router.py --search "违法解除" --full
```

## 工作流

task_intake → material_ingestion → issue_analysis → evidence ∥ authority → claims_procedure → drafting → validation → lawyer_approval
