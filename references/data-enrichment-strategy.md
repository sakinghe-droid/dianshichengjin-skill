# 数据充实策略

## 核心原则

**行情数据必须实时获取，禁用默认值。** DDX/主力资金/PE/题材必须从数据源查询，不依赖硬编码 fallback。

## 数据优先级

| 字段 | 首选 | 降级 | 当前状态 |
|------|------|------|---------|
| DDX 多周期(3/5/10日) | mx-data (需有效 MX_APIKEY) | — | ⚠️ 暂无可用源 |
| DDX 单日快照 | L2大单净额/成交额 | TDX 主力净额 | ✅ data_fallback L2 |
| 主力净流入 | data_fallback L2 big_order.net_amount | TDX "主力资金净流入" | ✅ |
| PE | TDX query_financials | — | ⚠️ 部分股票返0 |
| 题材/行业 | TDX 涨停池 所属行业标签 | 自填 | ✅ |
| RSI/MA/波动率 | K线自算 (始终真实) | — | ✅ |

## 多周期 DDX 的已知缺口

- TDX MCP：不提供 DDE/DDX 指标
- data_fallback capital：eltdx main_net 全返 0
- data_fallback L2：仅单日快照，无法推算 3/5/10 日趋势
- mx-data：需有效 MX_APIKEY（当前 key 已过期，错误码 114）

**多周期 DDX 应优先来自 mx-data 或 TDX MCP；不可使用硬编码默认值。**

## 补偿方案

1. 获取新 MX_APIKEY → mx-data 可查询 DDX/DDE 多周期数据
2. 用户手动输入: "分析301232，DDX 10日+4.403，5日+2.353，3日+1.71"
3. 每日自动累积 L2 单日值建立本地 DDX 历史数据库

## 用户偏好

- 不接受默认值替代真实数据
- 输出需标注数据来源（实时 ✅ vs 默认 ⚠️）
- 缺失数据要明确提示用户补充
