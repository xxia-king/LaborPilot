# Getting Started

## 安装

无需安装依赖(纯 Python 3 标准库 + pandoc)。

```bash
# 检查 pandoc(文书生成需要)
pandoc --version

# 如果没有 pandoc
brew install pandoc  # macOS
# apt install pandoc  # Linux
```

## 5分钟上手

### 1. 查看可用案由门

```bash
python3 scripts/issue_router.py --list-gates
```

### 2. 搜索争点

```bash
python3 scripts/issue_router.py --search "加班费"
python3 scripts/issue_router.py --search "违法解除 2N"
```

### 3. 查看完整争点卡

```bash
python3 scripts/issue_router.py --card B1 --full
```

### 4. 生成仲裁申请书

准备案件数据 JSON:

```json
{
  "case": {
    "申请人": "张某",
    "被申请人": "某公司",
    "事实与理由": "..."
  },
  "claims": [
    {"事项": "违法解除劳动合同的赔偿金", "金额": 64000, "计算式": "8000元×4个月×2"}
  ],
  "evidence": [
    {"名称": "银行工资流水", "来源": "申请人", "证明目的": "劳动关系+工资标准"}
  ]
}
```

生成:

```bash
python3 scripts/generate_docs.py --case my_case.json --output ./output --types "仲裁申请书,证据清单"
```

输出: `仲裁申请书.docx` + `证据清单.docx`
