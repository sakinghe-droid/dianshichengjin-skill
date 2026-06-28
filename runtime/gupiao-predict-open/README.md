# gupiao-predict-open v2.0

A股AI交易系统 V5.8.1 开源版 — 纯Python实现，覆盖完整交易工作流。

## 快速开始

```bash
cd runtime/gupiao-predict-open

# 盘前扫描 (Sina+腾讯, 无需TDX)
python scripts/pre_market_scan.py

# 扫描市场 (TDX MCP精准行业分组)
python scripts/data_collector.py --mode all

# 分析个股
python scripts/e5_position.py --code 000001
python scripts/game_theory_6d.py --code 000001 --consensus

# 持仓管理
python orchestrators/w5_pipeline.py --code 000001 --hold-shares 5000 --cost 10.50

# 完整编排
python orchestrators/trade_orchestrator.py --code 000001 --kline /tmp/kline.json
```

## 架构

```
data_sources/         3 数据源 (TDX MCP / trade_executor / data_fallback)
core/                16 计算引擎 (math/E5/game_6d/classic_4p/trend/position/...)
orchestrators/        8 编排器  (trade/mainline/w5/w6/w8/w10/w2w3/review)
scripts/              6 CLI     (data_collector/e5_position/game_theory_6d/n3_n6/pre_market_scan)
tests/                29项集成测试全通过
```

## 工作流覆盖

| 触发词 | 工作流 |
|--------|--------|
| "扫描市场" | W1 数据采集 + 主线推演 |
| "持仓博弈" / "持仓决策" | W5 四层串联 + 自动交易 |
| "复盘今天" | W6 五步复盘 |
| "低吸挖掘" | W8 六步法 |
| "趋势波段" | W10 双引擎融合 |
| "挖掘XX产业链" | W4 AI驱动五层深挖 |
| "能不能买XX" | N1 五维验证 |
| "要不要卖XX" | N2 卖出体检 |
| "盘前扫描" | 降级模式 (Sina+腾讯) |

## 文档

- `product-whitepaper.md` — 产品技术白皮书 (701行)
- `gupiao-open-SKILL.md` — 技能文档 (586行, 24触发词)
- `SKILL.md` — 点石成金技能入口
- `phase1/2/3-*.md` — 接口映射/数据流/黑盒测试

## 数据源

| 数据源 | 用途 | 状态 |
|--------|------|------|
| TDX MCP | 涨停池/行业/技术指标/资金 | ✅ |
| data_fallback (eltdx/opentdx) | K线数据 | ✅ |
| mx-moni (妙想) | 模拟交易 | ✅ 账户1000元 |
| Sina + 腾讯K线 | 盘前扫描降级 | ✅ fallback |
