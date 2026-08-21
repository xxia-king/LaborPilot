---
name: labor-authority-research
description: 劳动争议法律法规、规范性文件和浙江地方口径的检索与引用校验。当需要按争点、法规名、文号、条号、地域、时间效力检索，或核验 document_id、article_id、页码和效力状态时使用。
homepage: https://jinlishan.com/
author: 金莉珊律师（微信jinlishan_）
version: "0.2.0"
license:
---

# 劳动争议法源研究

1. 完整读取 [法源适配协议](../../references/corpus-adapter.md)。
2. 优先使用配置的 `local_markdown`只读法规库；未命中且 `fallback=true` 时生成外部检索任务。
3. 分层展示国家规则、浙江地方规则和参考口径，不得混同效力层级。
4. 根据 `analysis_date` 校验新旧法、废止状态和适用条件。
5. 法源异常、已废止规则或汇编原文疑点必须显式警示，不静默修正。
6. 未回填权威来源前，外部检索结果只能标记“待核验”。

已验证法源、适用条件与浙江口径写入 `01_案件研判报告_vN.md`；索引、检索 JSON 和引用校验结果存入 `.casework/authority/`，不单独向用户交付“法源检索记录”。

使用 `../../scripts/corpus.py` 建立索引、检索和验证引用。
