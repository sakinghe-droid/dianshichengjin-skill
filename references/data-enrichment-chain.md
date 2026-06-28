# 数据补全链 (Data Enrichment Chain)

六维博弈引擎 `enrich_real_data()` 的多源降级补全链。优先级从上到下：

## DDX 多周期数据

```
1. 妙想 mx-data
   查询: "{code} 近10日DDX DDY 主力资金DDE大单净量"
   解析: 调用 mx_data.py → 读取输出的 .xlsx → parse Sheet "XX当前的3日DDX、3日DDY等"
   输出: ddx_3d, ddx_5d, ddx_10d
   标注: _ddx_source = 'mx-data'
   陷阱: 必须带"主力资金DDE大单净量"关键词才返回 DDX 表；纯数字代码可能不返回，需附带股票名称

2. ddx_calculator 兜底
   条件: mx-data 失败 + 已有 main_amount (来自 TDX/L2)
   方法: calculate_ddx_from_amount(main_net_inflow, float_shares, current_price)
   估算: float_shares ≈ kline_amount * 20 / price  (假设换手率5%)
   输出: ddx_5d (单日), ddx_10d = ddx_5d * 0.8 (保守估计)
   标注: _ddx_source = 'calculated'

3. 默认值
   条件: 以上全部失败
   输出: ddx_5d=0.5, ddx_10d=0.3
   标注: ⚠️ 默认值 (输出中显示警告)
```

## 主力资金

```
1. 妙想 mx-data → main_amount (带单位: 万元/亿元需转换)
2. TDX MCP → "主力资金净流入" 查询 → 解析净额列
3. data_fallback L2 → big_order.net_amount
4. 默认: quote.amount * 0.1
```

## PE / 估值

```
1. 妙想 mx-data → Excel Sheet "市盈率PE(TTM)"
2. TDX MCP → query_financials() → PE 字段
3. 默认: 无
```

## 行业 / 题材

```
1. TDX MCP → query_financials() → 含"行业"的字段 → 去 @ 符号
2. 默认: "自动分析"
```

## TDX MCP 编码修复

TDX MCP (wenda-mcp-server) 返回的 JSON 中文键名可能被 Latin-1 误解释。
修复方法: `fix_encoding()` 递归遍历，对每个 str 做 `encode('latin-1').decode('utf-8')` 并捕获异常。

见 `runtime/gupiao-predict-open/data_sources/tdx_mcp.py` 的 `_call()` 方法。
