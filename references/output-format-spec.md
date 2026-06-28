# 格式规范

## 输出格式

所有 CLI 脚本和编排器默认输出**人类可读格式**（表格+emoji+分区），`--json` 标志输出原始 JSON。

格式由 `core/formatters.py` 统一管理:
- `format_e5()` — E5 位置波动率分析
- `format_game()` — 六维博弈引擎
- `format_w8()` — W8 低吸挖掘
- `format_mainline()` — 主线推演
- `format_w5()` — W5 持仓分析
- `format_w10()` — W10 趋势波段

## 数据来源标注

六维博弈输出底部显示：

```
📡 数据来源:
  实时: main_amount, ddx_5d, ddx_10d, _ddx_source ✅
  缺失: active_buy_ratio, inst_vs_retail ⚠️
```

- ✅ = 从数据源获取的真实值
- ⚠️ = 无法获取, 使用引擎默认中性值
- 当 DDX 全部缺失时额外显示 "⚠️ 未获取到DDX数据, DDX一票否决功能不可用"

## 评分可视化

六维评分用进度条: `█████░░░░░ 50/100`

## 输出格式要求

- 禁止: 裸 JSON / 硬编码默认值 / 无数据质量标识
- 点石成金: 人类可读 / 真实数据优先 / 明确标注数据来源质量
