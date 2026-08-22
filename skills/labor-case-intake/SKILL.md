---
name: labor-case-intake
description: 劳动争议案件接入、材料盘点和初步分流。当需要建立材料清单、案件时间轴、当事人询问提纲、识别劳动关系类型或判断程序阶段时使用。不用于直接撰写诉讼文书。
homepage: https://jinlishan.com/
author: 金莉珊律师（微信jinlishan_）
version: "1.2.0"
license: AGPL-3.0
---

# 劳动争议案件接入

1. 先读 `.casework/case_state.json`；不改动原始材料。如 `task_context` 未完整、`representation=undetermined` 或 `stage=undetermined`，立即返回 `task_intake`，不得建立案件底盘或继续分析。
2. 为每份材料记录来源、形成时间、真实性、关联性、合法性、证明目的及待核问项。
3. 建立时间轴，严格区分有证据支撑、当事人陈述、对方主张、双方争议和待查明。
4. 识别主体、关系性质、用工时间、工作地、合同、工资、社保、解除终止及程序现状。
5. 将材料清单、时间轴和初步分流写入同一份 `01_案件研判报告_vN.md`；待询问项和缺失材料写入 `03_待补材料与行动清单_vN.md`。不单独生成“接入底稿”。
6. 不做最终责任判断；将可能争点交给 `labor-issue-analysis`。
7. 完成节点前，将每条事实以唯一 `fact_id`、事实陈述、状态和来源写入 `facts[]`；不得只更新人读报告而让案件状态保持为空。

完成条件见 [节点契约](../../references/node-contracts.md)，案件状态规则见 [case-state](../../references/case-state.md)。
