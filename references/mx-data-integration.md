# 妙想 mx-data DDX 多周期数据集成

## 关键发现

mx-data 的 DDX 查询需要特殊的查询词格式，且数据以 Excel 文件返回（非 stdout）。

### 查询词格式

```python
# ✅ 正确: 需含 "近10日DDX DDY 主力资金DDE大单净量"
question = f"{code} 近10日DDX DDY 主力资金DDE大单净量"

# ✅ 资金+PE 查询
question = f"{code} 主力净流入资金 PE市盈率"

# ❌ 错误: 纯代码查询可能不返回 DDX 表
question = f"{code} 3日DDX 5日DDX 10日DDX"  # → "接口返回中无 dataTableDTOList"
```

### 数据返回格式

mx-data 不在 stdout 返回数据，而是生成 Excel 文件：
- `~/.openclaw/workspace/mx_data/output/mx_data_{code}_*.xlsx`
- Sheet 名包含 "3日DDX" 等关键词
- 需用 `openpyxl.load_workbook(..., data_only=True)` 读取

### Excel Sheet 结构

**DDX Sheet** (需要查询词含 "近10日DDX DDY 主力资金DDE大单净量"):
```
| date | 3日DDX | 3日DDY | 5日DDX | 5日DDY | 10日DDX | 10日DDY | DDX飘红天数(10日) | ...
```

**资金 Sheet** (需要查询词含 "主力净流入资金"):
```
| date | (区间)主力净流入资金 | (区间)超大单净流入资金 | (区间)大单净流入资金 | ...
```

**PE Sheet** (需要查询词含 "PE市盈率"):
```
| date | 市盈率PE(TTM) | 主力净流入资金 | ...
```

### 调用注意事项

```python
# subprocess 必须设置 cwd 到 mx-data 目录
subprocess.run(
    [sys.executable, '~/skills/mx-data/mx_data.py', question],
    cwd=os.path.expanduser('~/skills/mx-data'),  # ← 关键!
    env={**os.environ, 'MX_APIKEY': mx_key},
)
```

## 三级数据降级链

`enrich_real_data()` 在 `scripts/game_theory_6d.py` 中实现了自动补全：

```
Level 1: mx-data (DDX多周期 + 主力净流入 + PE)  ← 最完整
  ↓ 失败
Level 2: TDX MCP (主力资金 + PE + 行业分类)
  ↓ 失败
Level 3: data_fallback L2 (大单净额, 单日)
  ↓ 失败
默认值 (仅用于不阻塞计算的字段: active_buy_ratio 等)
```

已自动补全的字段: `ddx_3d`, `ddx_5d`, `ddx_10d`, `main_amount`, `super_large_net`, `pe`, `topic`
仍需默认值的字段: `active_buy_ratio`, `inst_vs_retail`, `continuity_3d`
