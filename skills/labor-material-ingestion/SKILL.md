---
name: labor-material-ingestion
description: 劳动争议原始材料接入与本地处理。当案件以 PDF、图片、扫描件或混合文件提供，需要保全原件、检测文字层、决定是否 OCR、生成分页索引或登记派生文件时使用。
homepage: https://jinlishan.com/
author: 金莉珊律师（微信jinlishan_）
version: "0.2.0"
license:
---

# 劳动争议材料接入

1. 保持原始文件只读，计算 SHA-256、页数、大小和文件类型。
2. 先检测文字层的完整性，不因 PDF “能复制几个字”就认定无需 OCR。
3. 案件、客户或执业材料默认仅本地处理；未获明确授权不调用云端 OCR。
4. 对扫描页生成分页图、分页文本和接触表，保留页码对应；不在 OCR 文本中静默修改原文。
5. 在 `materials[]` 登记 `source_path`、`source_sha256`、`page_start/end`、`derivative_path`、`ocr_engine`、`ocr_language`、`ocr_status`、`visual_review_status` 和 `original_or_copy`。
6. 将 OCR 不确定、手写表格、截断聊天、旋转或模糊页列为人工复核任务。
7. 将分页图、OCR、接触表和材料接入索引统一输出到 `<case-root>/.casework/materials/`，不在案件根目录建立用户交付文件；完成后才进入 `intake`。

不识别实体争点，不将 OCR 文本当作经证实事实。
