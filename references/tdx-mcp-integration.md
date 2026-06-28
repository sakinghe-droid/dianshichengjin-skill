# TDX MCP 集成要点

## 连接参数

```python
BASE = "https://mcp.tdx.com.cn:3001"
HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/event-stream',  # ← 必须同时接受两种格式
    'tdx-api-key': 'TDX-b0696b2392e0c80e42d1a68196e01ebe',
}
```

## 编码修复 (关键!)

TDX MCP 返回的 JSON 中文字段名被 latin-1 误解释，必须在 `_parse_table` 前修复：

```python
def fix_encoding(obj):
    if isinstance(obj, dict):
        return {fix_encoding(k): fix_encoding(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [fix_encoding(v) for v in obj]
    elif isinstance(obj, str):
        try:
            return obj.encode('latin-1').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            return obj
    return obj
```

## 数据能力矩阵

| 能力 | TDX MCP | 可用? |
|------|---------|-------|
| 涨停池+行业标签 | "今日涨停股票" | ✅ |
| 行业成分股 | "半导体行业板块成分股" | ✅ 但字段名为中文需编码修复 |
| 个股技术指标 | "000001 RSI MACD KDJ" | ✅ RSI(6,12,24)非14，周期不同 |
| 主力资金排名 | "今日主力资金净流入排名" | ✅ |
| PE/财务 | "000001 PE PB ROE" | ✅ |
| DDX/DDE | — | ❌ 不提供 |
| 多周期DDX | — | ❌ 不提供 |

## RSI 周期差异

TDX RSI(6,12,24) ≠ 我们的 RSI(14)。两者不混用，RSI 继续从 K线自算。
详见: 2026-06-26 会话中的对比验证。
