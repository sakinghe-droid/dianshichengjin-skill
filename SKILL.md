---
name: 点石成金
description: 🪨→💎 点石成金 — A股AI交易系统开源版。说"点石成金"即可唤起。通达信MCP+妙想驱动，16引擎+8编排器，W1-W10+N1-N6全覆盖。触发词：分析位置、六维博弈、扫描市场、持仓决策、低吸挖掘、趋势波段、复盘、挖掘产业链、自动挖掘
dependency:
  python:
    - requests>=2.28.0
    - eltdx>=0.2.0
    - opentdx>=0.2.0
---

# 🪨→💎 点石成金 · A股AI交易系统 V5.8.1

纯 Python 实现，数据层：通达信 MCP + 开源 data_fallback(eltdx/opentdx) + 妙想6skills。

**项目路径**: `${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open/`

**可迁移运行方式**: 本技能仓库已内置运行时代码到 `runtime/`。执行命令前先定位技能目录：

```bash
export DIANSHICHENGJIN_SKILL_DIR="${DIANSHICHENGJIN_SKILL_DIR:-$(pwd)}"
```

在 Hermes 技能环境中，`DIANSHICHENGJIN_SKILL_DIR` 应指向包含本 `SKILL.md` 的目录。若是手动 clone 测试，请先 `cd` 到技能目录再执行上面的 `export`。

---

## 执行铁律

1. **任何扫描/出票前必须先跑 mainline_engine -m run** — ABCD象限是出票的前置条件
2. **D象限+无主线 → 立即终止出票** — 转低吸挖掘(W8)或等明日，不勉强
3. **73涨停≠亢奋** — 晋级率+中军共振才是真主线，涨停数量会骗人
4. **E5 位置天花板高于一切手工判断** — 引擎说 5% 就是 5%
5. **DDX 需多周期验证** — 单日DDX快照不足，需3/5/10日趋势。四级降级: 妙想mx-data→TDX大单→L2+ddx_calculator→标注缺失
6. **绝不使用硬编码默认值** — DDX/主力资金/PE 获取失败时标注 ⚠️"数据缺失"，不填假值
7. **输出默认人类可读格式** — 带表格/emoji/风险提示, `--json` 模式给程序调用
7. **🚨 个股分析前必须查证代码** — 禁止猜测。用 `requests.get('https://suggest3.sinajs.cn/suggest/type=11&key=股票名')` 获取真实代码（教训：飞沃科技猜成300893，实为301232）
8. **涨停过滤分档** — 10cm≥9.5%, 20cm≥19%, 30cm≥28.5% 剔除
9. **DDX默认值不可信** — 引擎在无外部DDX时填充0.3/0.1（看似中性偏弱），但真实DDX可能从1.45暴跌到0.085。E5低位≠可以买，需交叉验证。见 `references/known-limitations.md`

---

## 数据层架构

| 管道 | 提供 | 状态 |
|------|------|------|
| `data_fallback.py` (开源) | K线/行情 — eltdx→opentdx双保险 | ✅ 始终可用 |
| **妙想 mx-data** | 多周期DDX(3/5/10日)/DDY/主力净流入/PE | ✅ 首选DDX源 |
| **TDX MCP** (wenda-mcp-server) | 涨停池/行业分类/技术指标/**大单净额**/连板天数 | ✅ DDX二级兜底 |
| **data_fallback L2** | 大单买入/卖出量 (opentdx) | ✅ DDX三级兜底 |
| **妙想 mx-moni** | 模拟交易 (持仓/买卖/委托/操作日志) | ✅ 账户1000元 |
| **Sina + 腾讯K线** | 盘前扫描降级模式 (TDX不可用时的fallback) | ✅ |

### DDX 数据获取优先级（严禁使用默认值）

详见 `references/ddx-pipeline.md` — 四级降级链、mx-data查询格式、编码修复。

---

## 问法与执行模式

| 问法 | 执行 | 说明 |
|------|------|------|
| "分析{CODE}位置" / "{CODE} E5分析" | E5位置波动率 | 7子指标 → 位置+天花板+波动率 |
| "{CODE}六维博弈" / "{CODE}博弈分析" / "能不能买{CODE}" | 六维博弈引擎 | A1-F6 → 综合裁决+仓位+卖出倾向 |
| "{CODE}卖出分析" / "要不要卖{CODE}" / "{CODE}走不走" | 六维博弈(卖出侧重) | 重点输出卖出倾向+操作建议 |
| "{CODE}完整分析" / "分析{CODE}" | 全链路编排 | G0→六维→经典→共识→T0→P3→仓位 |
| "{CODE}经典四视角" / "{CODE}庄家游资分析" | 经典四视角 | Z/Y/Q/M + 走势预判 |
| "{CODE}共识仲裁" / "{CODE}双引擎" | 六维+经典+共识 | 完整三件套 |
| "{CODE}波段分析" / "{CODE}趋势波段" | 浪型分析 | 浪型+旗形+二浪+缠论 |
| "{CODE}资金全景" / "{CODE}主力资金面" | 资金全景扫描 | 北向/融资/大宗/增减持/龙虎榜 |
| "{CODE}波波评分" / "{CODE}基本面评分" | 波波六维 | 板块共振+催化+资金+技术+估值+行业 |
| "{CODE}涨停评估" / "{CODE}连板分析" | 涨停增强 | 封单/时间/连板/DDZ 四维 |
| "计算{CODE} DDX" / "{CODE}DDX" | DDX计算 | 额基近似（需提供主力净流入） |
| "计算仓位 {参数}" | 统一仓位公式 | 参数化仓位计算 |
| "对比{CODE1}和{CODE2}" | 多只对比 | 分别跑六维 → 对比表 |
| "扫描市场" / "主线推演" / "今天主线" | 数据采集+主线判定 | data_collector → mainline_engine -m run |
| "{TOPIC}龙头定位" / "找龙头" | 龙头排序 | mainline_engine -m p |
| "{TOPIC}上游挖掘" | 卫星推导 | mainline_engine -m u |
| "批量博弈" | 批量六维 | mainline_engine -m g |
| "{CODE}持仓分析" / "持仓博弈{CODE}" | W5完整流水线 | W9→G0→六维→T0→P3 |
| "批量持仓" / "持仓体检" | 批量W5分析 | w5_pipeline --batch |
| "{CODE}趋势波段" / "{CODE}深度分析" | W10模式A 9步 | wave+bobo+game→双引擎融合 |
| "持仓决策{CODE}" / "自动交易" | W5 + 自动执行 | w5_pipeline --execute → mx-moni交易 |
| "低吸挖掘" / "低吸出票" | W8 六步法 | w8_pipeline → 强方向→初筛→位置→博弈→出票 |
| "最强出击" | W2 一键 | w2w3_pipeline --mode w2 |
| "切片出击" | W3 多题材 | w2w3_pipeline --mode w3 |
| "盘前扫描" / "盘前宏观" | 降级模式 | pre_market_scan (Sina+腾讯, TDX不可用时的fallback) |
| "挖掘{TOPIC}产业链" / "拆解{TOPIC}" | W4 五层深挖 | AI画全景图 → TDX查标的 → 引擎验证 |
| "自动挖掘" / "自动找题材" | W7 全自动 | data_collector → TOP3 → W4×3 → 合并 |
| "复盘今天" / "复盘" / "复盘今日行情" | W6 复盘+周度回采 | review_engine(自动TDX历史回采5日) + data_collector + AI预测 |

---

## 工作流详解

### 1. E5 位置波动率分析

**触发**: "分析000001位置" / "000001 E5分析"

```bash
python ${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open/scripts/e5_position.py --code {CODE} --count 120
# JSON输出: 加 --json
```

**输出格式**:
```
📊 {NAME}({CODE}) E5 位置波动率分析

位置评级: {level} (level_code={level_code})
仓位天花板: {ceiling*100:.0f}%  ← 这只票的最大仓位!
波动率: {volatility} (倍数={vol_ratio}, 乘数={vol_mult})

子指标明细:
  均线偏离: {mp}/10  (MA20={ma20:.2f} 偏离{ma20_dev:+.1f}%)
  波段位置: {bp}/10  (60日区间 {band_position_pct:.1f}%)
  RSI评分:  {rv}/10  (RSI={rsi:.1f})
  量价偏离: {vd}/10  (量比={vol_ratio_vs_20d:.2f})
  空间评估: {sa}/10  (支撑={support:.2f} 压力={resistance:.2f} 盈亏比={risk_reward:.2f})
```

### 2. 六维博弈引擎

**触发**: "{CODE}六维博弈" / "能不能买{CODE}"

```bash
python ${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open/scripts/game_theory_6d.py --code {CODE} --consensus
# JSON输出: 加 --json
```

**数据自动补全**（无需用户手动输入）:
- DDX 3日/5日/10日: 妙想 mx-data 自动查询
- 主力净流入: 妙想 mx-data → L2大单兜底
- PE/行业/题材: 妙想 mx-data → TDX MCP 兜底
- RSI/MA/波动率/波段位置/量比: K线自动计算（始终真实）

**输入数据自动构建规则**（当自动补全失败时）:
- `ddx_5d/ddx_10d`: 默认 0.3/0.1
- `sentiment`: 默认 "中性", `topic_rank`: 默认 5
- 用户可通过自然语言覆盖: "DDX 10日+4.4，市场积极"

### 3. 全链路编排（推荐）

**触发**: "{CODE}完整分析" / "分析{CODE}"

```bash
python ${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open/orchestrators/trade_orchestrator.py \
  --code {CODE} --kline /tmp/kline_{CODE}.json \
  --topic_name "{题材名}" --sentiment {情绪}
```

### 4. 经典四视角分析

**触发**: "{CODE}经典四视角" / "{CODE}庄家游资分析"

```bash
python -c "
import sys, json, subprocess
sys.path.insert(0,'${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open')
r = subprocess.run(['python', '${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open/scripts/data_fallback.py', '--mode','kline','--code','{CODE}','--count','60'], capture_output=True, text=True)
klines = json.loads(r.stdout)
price = klines[-1]['close']; closes = [k['close'] for k in klines]
from core.math_utils import rsi_wilder, daily_returns, daily_volatility
from core.classic_4p import classic_analyze
data = {'code':'{CODE}','price':price,'ddx_5d':0.3,'ddx_10d':0.1,'main_amount':5e7,
    'low_60d':min(k['low'] for k in klines),'high_60d':max(k['high'] for k in klines),
    'volatility':daily_volatility(daily_returns(closes)),'rsi':rsi_wilder(closes) or 50,
    'vol_ratio':1.0,'active_buy_ratio':0.55,'inst_vs_retail':1.0}
result = classic_analyze(data)
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

### 5. 波段分析

**触发**: "{CODE}波段分析"

```bash
python -c "
import sys, json, subprocess
sys.path.insert(0,'${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open')
r = subprocess.run(['python', '${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open/scripts/data_fallback.py', '--mode','kline','--code','{CODE}','--count','60'], capture_output=True, text=True)
klines = json.loads(r.stdout)
from core.wave_analyzer import wave_analyze
result = wave_analyze(klines)
print(f'浪型: {result[\"wave_stage\"]}')
print(f'模式: {result[\"pattern\"]}')
print(f'旗形整理: {\"是\" if result[\"flag_pattern\"] else \"否\"}')
print(f'二浪确认: {\"是\" if result[\"wave2_confirmed\"] else \"否\"}')
print(f'波段位置: {result[\"metrics\"][\"band_position_pct\"]:.1f}%')
"
```

### 7. 波波六维评分

**触发**: "{CODE}波波评分" / "{CODE}基本面评分"

```bash
python -c "
import sys; sys.path.insert(0,'${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open')
from core.bobo_scorer import bobo_score
r = bobo_score(sector_strength={强度}, sector_net_inflow={净流入}, sector_limit_up={涨停数},
               catalyst_type='{催化类型}', fund_signal='{资金信号}', wave_stage='{浪型}',
               pe={PE}, industry_avg_pe={行业PE}, market_position='{地位}')
print(f'波波六维总分: {r[\"total_score\"]}/85')
for k,v in r['sub_scores'].items():
    print(f'  {v[\"label\"]}: {v[\"score\"]}/{v[\"weight\"]}')
for k,v in r['deductions'].items():
    print(f'  折扣({k}): {v[\"reason\"]} → {v[\"deduct\"]}')
"
```

### 8. 涨停增强评估

**触发**: "{CODE}涨停评估" / "{CODE}连板分析"

```bash
python -c "
import sys; sys.path.insert(0,'${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open')
from core.limit_up_booster import limit_up_boost
data = {'is_limit_up': {True/False}, 'lianban_days': {天数}, 'seal_amount': {封单},
        'float_market_cap': {流通市值}, 'limit_up_time': '{封板时间}', 'ddz': {DDZ值}}
r = limit_up_boost(data)
if r['triggered']:
    print(f'涨停增强: +{r[\"boost_score\"]}/30分')
    print(f'情绪周期: {r[\"cycle\"]}')
else:
    print(f'未触发: {r[\"reason\"]}')
"
```

### 9. 资金全景扫描

**触发**: "{CODE}资金全景" / "{CODE}主力资金面"

依赖北向/融资/大宗/龙虎榜数据。TDX MCP可查询主力净流入排名，妙想mx-data可补充财务数据。当数据不足时返回各维度需要的字段清单。

### 10. 多只对比

**触发**: "对比{CODE1}和{CODE2}" / "000001和600519哪个好"

对每只分别跑六维博弈，输出对比表:
```
| 维度 | {CODE1} | {CODE2} |
|------|---------|---------|
| 综合评分 | xx | xx |
| 操作建议 | xx | xx |
| 仓位建议 | xx% | xx% |
| E5位置 | xx | xx |
| 风险等级 | xx | xx |
| 推荐 | ✅/— | ✅/— |
```

### 11. 持仓体检 (N3)

**触发**: "持仓体检"

```bash
python ${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open/scripts/n3_n6.py --mode holdings
```

### 12. 北向资金 (N6)

**触发**: "北向资金" / "外资态度"

```bash
python ${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open/scripts/n3_n6.py --mode northbound
```

**触发**: "{CODE}卖出分析" / "要不要卖{CODE}"

```bash
python ${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open/scripts/game_theory_6d.py --code {CODE}
```

卖出倾向 ≥60% → 建议清仓；40-60% → 减仓50%；20-40% → 持有观察；<20% → 可加仓

---

## 主线引擎工作流 (mainline_engine)

### 主线推演 (-m run)

**触发**: "扫描市场" / "今天主线是什么"

```bash
python ${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open/scripts/data_collector.py --mode all
python ${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open/orchestrators/mainline_engine.py \
  -i /tmp/w1_data/combined_input.json -m run
# JSON输出: 加 --json
```

**三层修正逻辑**:
1. 情绪修正: 亢奋→B升A / 恐慌→A降B
2. 梯队修正: 断层→降级 / 断板率>50%→全降 / 晋级率>50%+3板→B升A
3. 持续性修正: 持续强→确认 / 突然爆发→降级 / 龙头断板→降级

**ABCD象限**: A主线重仓 / B游资轻仓 / C补涨观察 / D空仓

### 龙头定位 (-m p)

```bash
python ${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open/orchestrators/mainline_engine.py -i candidates.json -m p
```
6维评分(涨停时间/封单/连板/换手/涨幅/资金) → ≥70龙头 / ≥50中军 / ≥30跟风

### 上游瓶颈挖掘 (-m u)

```bash
python ${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open/orchestrators/mainline_engine.py -i mainline_result.json -m u
```
内置8条产业链: AI/光通信/芯片/MLCC/先进封装/碳化硅/固态电池/稀土永磁

### 批量博弈 (-m g)

```bash
python ${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open/orchestrators/mainline_engine.py -i candidates.json -m g
```

---

## W5 持仓管理 / W8 低吸挖掘 / W10 趋势波段

### 持仓博弈 (w5_pipeline)

```bash
# 分析
python ${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open/orchestrators/w5_pipeline.py \
  --code {CODE} --hold-shares {股数} --cost {成本价} --topic {题材}

# 自动交易: 加 --execute
```

四层串联: W9前置(洗盘识别) → G0 → 六维 → T0/P3

### 低吸挖掘 (w8_pipeline)

**触发**: "低吸挖掘"

```bash
python ${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open/orchestrators/w8_pipeline.py
# 自动下单: --execute
```

六步法: 强方向筛选→板块阶段→个股初筛(涨幅1-5%)→位置+盈亏比(≥3:1)→博弈验证→仓位出票

### 趋势波段 (w10_orchestrator)

```bash
python ${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open/orchestrators/w10_orchestrator.py \
  --mode A --code {CODE} --topic {题材}
```

9步: 采集→题材定位→浪型→资金全景→波波六维→博弈六维→T0/P3→双引擎融合→报告

### 复盘 (review_engine)

```bash
python ${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open/orchestrators/review_engine.py [--date YYYY-MM-DD]
```
五步: 出票逻辑复盘→持仓表现→收益基准→优化方案→明日建议

**新增: 周度数据自动回采** — review_engine 自动从 TDX MCP 回采近5个交易日数据:
- 涨停数/跌停数日度趋势
- (炸板率/北向资金/上证指数 — TDX历史查询受限, 仅当日可用)

**复盘+预测工作流** (AI 对话模式):
```
1. python review_engine.py → 获取周度数据+操作日志
2. python data_collector.py --mode all → 获取今日扫描
3. python mainline_engine.py -i combined.json -m run → 主线判定
4. AI 综合 1+2+3 → 输出: 本周回溯 + 退潮/发酵判定 + 下周情景预判
```
**关键**: 周度回溯必须从 TDX 查询历史数据 (如"2026-06-25 A股涨停股票"), 不能只依赖当日快照。。
**v2.1 新增**: 自动从 TDX MCP 回采近5日涨停数/跌停数, 输出周趋势。

### 盘前扫描 (降级fallback)

```bash
python ${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open/scripts/pre_market_scan.py
```
Sina+腾讯K线, 5步: 健康检查→指数行情→涨跌分布→热点识别→趋势分析

---

## W4 产业链五层深挖（AI 驱动工作流）

**触发**: "挖掘{TOPIC}产业链" / "拆解{TOPIC}"

由 AI 绘制产业链全景图，标注国产化率/壁垒/成本占比，按三高标准打分：
- 高增长: 行业增速>30%=10分, 20-30%=7分, 10-20%=4分
- 高壁垒: 国产化率<20%=10分, 20-40%=8分, 40-60%=5分
- 高利润: 毛利率>60%=10分, 40-60%=7分, 20-40%=4分

筛选: ≥24=核心★★★ / 18-23=关注★★ / <18=跳过

TDX查询标的 → AI四维市场验证 → 博弈引擎 → 仓位排序。

**产业链知识库**:
- 算力/AI: AI芯片(寒武纪/海光 壁垒9.5) → HBM存储 → 光模块(中际旭创/新易盛) → 先进封装(长电/通富)
- 机器人: 谐波减速器(绿的谐波) / 行星滚柱丝杠 / 六维力传感器
- 固态电池: LLZO电解质(东方锆业) / 硫化物电解质 / 硅碳负极

## W7 自动挖掘（AI 编排工作流）

**触发**: "自动挖掘" / "自动找题材挖掘产业链"

data_collector → TOP3题材 → W4×3并行 → 跨题材合并 → 仓位分配

风控: TOP1>15只涨停→深度; 8-15→标准; <8→浅度

---

## D象限/无主线处理（⚠️ 铁律）

当 `mainline_engine -m run` 输出 **主线: ❌ 无 | 象限: D** 时：

1. **W1出票 → 立即终止**，输出"D象限无主线，不建议出票"
2. **W2最强出击 → 拒绝执行**，返回 error: "无主线，无法执行W2最强出击"
3. **W8低吸 → 大概率0票**，博弈引擎评分<60，可执行但预期空结果
4. **正确路径**：等明日梯队修复（晋级率>30%）或中军出现再扫

**D象限确认三信号**（全满足 = 确认）：
- 全部题材 中军=—（无大市值票共振）
- 晋级率 < 15%
- 金字塔断裂（1板碾压高板）

**虚假繁荣识别**：73涨停但D象限 = 游资各自为战，无一题材有大资金确认方向。涨停多≠亢奋。

**降级分支决策树**：
```
mainline_engine -m run
  ├─ A象限(主线)     → W1出票 / W2最强出击
  ├─ B象限(游资)     → 手动深挖 trade_orchestrator / W8低吸
  ├─ C象限(补涨)     → W8低吸挖掘
  └─ D象限(无主线)   → STOP. 等明日或切片出击
```

**实盘案例（2026-06-26）**：73涨停 → 手动判"亢奋/主线" → 出票乾照光电1成。点石成金引擎判D象限/0票 → 事后验证引擎正确。教训：涨停数量不能替代ABCD象限判定。\n\n---\n\n## 统一仓位计算

```bash
python -c "
import sys; sys.path.insert(0,'${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open')
from core.position import calculate_position
r = calculate_position(emotion='{情绪}', stage='{阶段}', e5_level_code={level_code})
print(f'最终仓位: {r[\"final_pct\"]*100:.1f}%')
"
```

| 用户说 | 参数值 |
|--------|--------|
| 亢奋/积极/中性/谨慎/恐慌 | emotion |
| 主升期/高潮期/发酵期/退潮期 | stage |
| 低位(0)/中低位(1)/中位(2)/高位(3)/超高位(4) | e5_level_code |

---

## DDX 计算

```bash
python -c "
import sys; sys.path.insert(0,'${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open')
from core.ddx_calculator import calculate_ddx_from_amount
r = calculate_ddx_from_amount({主力净流入}, {流通股本}, {现价})
print(f'DDX={r[\"ddx\"]:.4f}  (方法: {r[\"method\"]})')
"
```

---

## 开源实现说明

| 场景 | 点石成金开源实现 |
|------|---------|----------|
| 引擎 | 16个纯 Python 引擎，逻辑透明 |
| DDX 多周期 | 妙想 mx-data(3日/5日/10日) → TDX MCP大单 → 开源 ddx_calculator 额基兜底 |
| 主力资金 | eltdx/东财管道 | **妙想 mx-data** (主力净流入) + L2大单兜底 |
| PE/估值 | 内部网络 | **妙想 mx-data** + TDX MCP 兜底 |
| 题材/行业 | 左岸工科(SSL阻断) | **TDX MCP** 精准行业分组 |
| K线/RSI/波动率 | 开源 data_fallback + Python 指标计算 |
| 输出 | 裸JSON/硬编码默认值 | 人类可读报告 / --json原始 |
| 模拟交易 | mx_position/buy/sell | mx-moni (同样依赖妙想) |

**数据补全优先级**: 
```
① 妙想 mx-data     → 3日/5日/10日 DDX (量基标准, 多周期精确)
② TDX MCP 大单     → 单日 DDX = |大单净额|/流通市值×100 (从TDX查询真实流通市值)
③ L2大单 + ddx_calculator → 额基近似 (成交额×20估流通市值)
④ None             → 跳过DDX评分, 标注 "⚠️ 未获取到DDX数据"
```

**用户补充数据示例**: "分析000001，DDX最近5日+0.8，10日+1.2"

---

## 项目结构

```
${DIANSHICHENGJIN_SKILL_DIR}/runtime/gupiao-predict-open/
├── data_sources/         TDX MCP + trade_executor(mx-moni)
├── core/                 16计算引擎 + formatters
├── orchestrators/        8编排器 (trade/mainline/w5/w6/w8/w10/w2w3/review)
├── scripts/              6 CLI (data_collector/e5_position/game_theory_6d/n3_n6/pre_market_scan)
└── tests/                29项集成测试全通过
```

## 参考文档 (references/)

| 文档 | 内容 |
|------|------|
| `references/ddx-enrichment-chain.md` | DDX 数据补全四级降级链 (妙想→TDX大单→L2→None) |
| `references/tdx-mcp-capabilities.md` | TDX MCP 完整能力矩阵 (查询示例+字段+限制) |
| `references/output-format-spec.md` | 输出格式规范 (人类可读/JSON/数据来源标注) |

## 参考文档

| 文件 | 内容 |
|------|------|
| `references/mx-data-integration.md` | mx-data DDX查询词格式、Excel解析、三级降级链 |
| `references/tdx-mcp-integration.md` | TDX MCP编码修复、数据能力矩阵、RSI周期差异 |
| `references/known-limitations.md` | DDX默认值陷阱、E5低位≠可买、缺失维度、五维交叉验证框架 |
| `references/cross-validation-workflow.md` | 三方交叉验证工作流（点石成金+mx-xuangu+扣子）·验证清单·实盘案例 |

## ⚠️ 关键注意事项

1. **DDX查询需特定格式**: mx-data 必须用 "近10日DDX DDY 主力资金DDE大单净量" 查询词，数据在 Excel 中非 stdout。详见 `references/mx-data-integration.md`。

2. **输出格式**: 所有脚本默认人类可读（表格+emoji），加 `--json` 输出原始 JSON。`core/formatters.py` 统一管理格式。

3. **数据真实性**: `game_theory_6d.py --code` 自动从 mx-data → TDX MCP → L2 三级降级补全真实数据，不再用默认值。输出底部的"📡 数据来源"标明每个字段的数据质量。

4. **mx-data 子进程调用**: 需设置 `cwd=~/skills/mx-data` 否则查询失败。

5. **TDX 中文乱码**: JSON 响应需 `latin-1 → utf-8` 编码修复（`data_sources/tdx_mcp.py` 已内置）。
└── tests/                 29项集成测试全通过
```

## ⚠️ 已知局限（与扣子五维体系对比）

点石成金的核心优势在**E5位置·ABCD象限·博弈六维**，但以下维度需要外部补充：

| 维度 | 点石成金 | 缺口 | 补救 |
|------|---------|------|------|
| DDX多周期趋势 | 单日估算/默认值 | ❌10/5/3日趋势不可见 | mx-xuangu手工查3-5天 |
| 资金拆解 | 仅总量 | ❌超大单/大单/游资/散户分层 | 扣子/同花顺L2 |
| 基本面 | ❌PE/Q1/现金流 | ❌完全缺失 | 扣子/东财F10 |
| 概念纯度 | ❌营收占比 | ❌完全缺失 | 扣子/年报 |

**E5低位≠可以买**：常友科技E5=22.6%低位，但真实DDX从10日1.45暴跌到3日0.085（主力减仓）+ Q1亏损 + 非主线 → 三重否决。E5是必要条件不是充分条件。

详见 `references/known-limitations.md`。

---

## 每周维护：记忆清理流程

触发: "每周一清" / "清理记忆"

```
步骤1: 归档 → 复盘教训写入 references/recent_memory/YYYY-MM-DD-复盘归档.md
步骤2: 清空 → memory remove 所有旧条目
步骤3: 重建 → 3条精简卡片(铁律/DDX/双轨)，目标<800字
```

清理原则：删日级数据，只保留核心规则+V5工作流。
