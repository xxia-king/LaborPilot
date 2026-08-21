---
name: LaborPilot
homepage: https://jinlishan.com/
author: 金莉珊律师（微信jinlishan_）
version: "1.0.0"
license: AGPL-3.0
description: 中国劳动争议智能办案引擎。输入案件材料,产出法律分析、金额计算和仲裁文书。内置96个争点知识卡(全国规则+浙江地方口径双层,地方口径依据浙江省现行规定编译)。当用户需要分析劳动争议案件、计算经济补偿/赔偿金/加班费/工伤待遇、生成仲裁申请书或证据清单时使用。产出的所有分析结果和法律文书均由AI辅助生成,仅供参考,必须经专业律师审核后方可使用。
---

# LaborPilot — 劳动争议智能办案引擎

## 免责声明

**LaborPilot 产出的所有分析结果和法律文书均由 AI 辅助生成,仅供参考,不构成法律意见,必须经专业律师审核后方可使用。**

## 输入

支持多种输入形式:
- 案件材料文件(PDF / 扫描件 / 图片)
- 案件描述(自然语言 / 结构化 JSON)
- 聊天记录 / 录音转写

引擎自动完成材料摄取、文字识别、要素提取。

## 产出

| 产出物 | 格式 |
|--------|------|
| 法律分析(争点识别 / 构成要件 / 举证分配) | 交互式查询 |
| 金额计算(N / 2N / 加班费 / 工伤待遇) | 精确到分 |
| 仲裁申请书 | .docx |
| 证据清单 | .docx |
| 行动清单 | .docx |

文书模板持续更新中,支持自定义加入。

## 依赖

- 核心: Python 3 标准库(零外部依赖)
- 文书生成: [pandoc](https://pandoc.org)(推荐)
- 扫描件 OCR: 可接入外部识别引擎
- 法律数据校验: 可外接 MCP 数据源

## 用法

```bash
# 查询争点
python3 scripts/issue_router.py --search "违法解除" --full

# 生成文书(结构化JSON输入)
python3 scripts/generate_docs.py --case my_case.json --output ./output
```

## 工作流

task_intake → material_ingestion → issue_analysis → evidence ∥ authority → claims_procedure → drafting → validation → lawyer_approval
