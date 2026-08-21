# LaborPilot

> 中国劳动争议智能办案引擎

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

LaborPilot 是一个知识驱动的劳动争议办案助手。内置 **96 张争点卡**(覆盖 23 个案由门)、**浙江裁判口径**、**文书生成器**,开箱即用。

## ⚠️ 免责声明

**LaborPilot 产出的所有分析结果和法律文书均由 AI 辅助生成,仅供参考,不构成法律意见,必须经专业律师审核后方可使用。**

## 功能

| 功能 | 命令 |
|------|------|
| 列出全部案由门 | `python3 scripts/issue_router.py --list-gates` |
| 按关键词查争点 | `python3 scripts/issue_router.py --search "违法解除"` |
| 查看争点卡详情 | `python3 scripts/issue_router.py --card E10 --full` |
| 生成法律文书 | `python3 scripts/generate_docs.py --case data.json --output out/` |

## 快速开始

```bash
git clone https://github.com/yourname/LaborPilot.git
cd LaborPilot

# 无需额外配置,开箱即用
python3 scripts/issue_router.py --list-gates
```

## 覆盖范围

| 案由门 | 卡数 | 争点示例 |
|--------|------|---------|
| 劳动合同纠纷(兜底) | 19 | 违法解除2N / 二倍工资 / 调岗调薪 |
| 追索劳动报酬 | 13 | 加班费三倍率 / 拖欠工资 / 停工停产 / 高温津贴 |
| 经济补偿金 | 8 | N/N+1/2N / 三倍封顶 / 跨2008分段 |
| 工伤保险待遇 | 11 | 工伤认定 / 停工留薪 / 三笔一次性 / 工亡 |
| 竞业限制 | 2 | 补偿标准 / 违约金 / 解释(二)新规 |
| 福利待遇 | 3 | 年休假300% / 浙江育儿假 / 女职工保护 |
| 超龄用工 | 3 | 超龄工伤 / 权益边界 |
| 挂靠用工责任 | 1 | 违法发包连带清偿 |
| 人事争议 | 2 | 事业编聘用合同 |
| 新就业形态 | 2 | 平台骑手 / 支配性劳动管理 |
| 程序性争端 | 11 | 时效 / 管辖 / 一裁终局 / 举证 / 裁审衔接 |

每张争点卡包含: **构成要件 / 法律依据(条文号) / 举证责任分配 / 金额算式 / 期限 / 浙江裁判口径 / 文书模板指向**

## 文书生成

支持的文书类型:

| 类型 | 输出格式 | 说明 |
|------|---------|------|
| 劳动仲裁申请书 | .docx | 含当事人/请求项/事实理由/落款 |
| 证据清单 | .docx | 含证据名称/来源/证明目的 |
| 行动清单 | .docx | 含待核实/待补证/金额核对 |

```bash
# 准备案件数据 JSON(格式见 docs/DATA-FORMAT.md)
python3 scripts/generate_docs.py \
  --case my_case.json \
  --output ./output \
  --types "仲裁申请书,证据清单,行动清单"
```

## 争点卡格式

每张卡遵循七节结构:

```markdown
---
card_id: E10
title: 违法解除·赔偿金(2N)
gate: 205(6)经济补偿金
basis:
  - {law: 劳动合同法, article: "48"}
  - {law: 劳动合同法, article: "87"}
---

# E10 违法解除·赔偿金(2N)

## 构成要件(违法情形审查清单)
## 法律依据(条文号级)
## 举证责任与证明事项
## 算式/后果
## 期限
## 浙江口径
## 文书指向
```

如果你想为其他省份/领域构建自己的争点卡,参见 [docs/BUILD-YOUR-CARDS.md](docs/BUILD-YOUR-CARDS.md)。

## 架构

```
┌─────────────────────────────────┐
│  _kb.pyc (预编译知识数据)        │  ← 96张卡,开箱即用
├─────────────────────────────────┤
│  scripts/issue_router.py       │  ← 争点路由(按门/卡/搜索)
│  scripts/generate_docs.py     │  ← 文书生成(md→docx)
│  scripts/build_cards.py       │  ← 知识构建(源码→编译)
├─────────────────────────────────┤
│  skills/ (10个子技能)           │  ← 工作流节点
│  assets/ (文书模板)             │  ← 律师定稿格式
│  evals/ (评测用例)             │  ← 质量保障
└─────────────────────────────────┘
```

## 许可

- **引擎代码**: [AGPL 3.0](LICENSE)
- **产出物免责**: 所有 AI 产出仅供参考,须经专业律师审核

## 作者

[金莉珊律师](https://jinlishan.com/) (微信: jinlishan_)
