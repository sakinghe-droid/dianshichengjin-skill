#!/usr/bin/env python3
"""Full test suite for gupiao-predict-open"""
import sys, json, subprocess, math, os
sys.path.insert(0, '.')

passed = 0; failed = 0; results = []

def t(name, cond, detail=""):
    global passed, failed
    if cond: passed += 1; results.append(f"  ✅ {name}")
    else: failed += 1; results.append(f"  ❌ {name} — {detail}")

def hdr(s):
    results.append(f"\n{'='*50}\n  {s}\n{'='*50}")

# Get real data once
r = subprocess.run([sys.executable, 'DATA_FALLBACK',
    '--mode','kline','--code','000001','--count','60'], capture_output=True, text=True, timeout=30)
klines = json.loads(r.stdout)
price = klines[-1]['close']

# ====== 1. math_utils ======
hdr("1. math_utils")
from core.math_utils import *
t("RSI in 0-100", 0 <= (rsi_wilder([10]*20) or 50) <= 100)
t("RSI score oversold=9", rsi_score(20) == 9)
t("RSI score overbought=3", rsi_score(75) == 3)
t("MA5", abs((ma([1,2,3,4,5],5) or 0) - 3) < 0.01)
t("MA none", ma([1,2],5) is None)
t("MA dev +10%", abs(ma_deviation(110,100) - 10) < 0.01)
t("MA dev score safe=10", ma_deviation_score(2,3) == 10)
t("MA dev score overshoot=2", ma_deviation_score(20,30) == 2)
t("Vol high=0.7", volatility_level(1.5) == ('高波',0.7))
t("Vol low=1.0", volatility_level(0.5) == ('低波',1.0))
t("Band 50%", abs(band_position(15,10,20) - 50) < 1)
t("Band score mid=6", band_position_score(50) == 6)
t("Vol ratio normal=6", volume_ratio_score(1.0) == 6)
t("Vol ratio sky=2", volume_ratio_score(4.0) == 2)
lvl, code, ceil, need = position_level(10, 45)
t("Low pos", code == 0 and ceil == 0.30 and not need)
lvl, code, ceil, need = position_level(90, 70)
t("Super high pos", code == 4 and ceil == 0.05 and need)
lvl, code, ceil, need = position_level(70, 66)
t("High pos triggers L2", code == 3 and need)

# ====== 2. e5_position ======
hdr("2. e5_position")
from core.e5_position import e5_full_analysis
e5 = e5_full_analysis(klines, price)
t("E5 all keys", all(k in e5 for k in ['level','ceiling','volatility','mp','bp','rv','vd','sa','rsi']))
t("E5 ceiling valid", 0 < e5['ceiling'] <= 0.30)
t("E5 vol_mult", 'vol_mult' in e5)
t("E5 need_l2", isinstance(e5.get('need_l2'), bool))
t("E5 empty=error", 'error' in e5_full_analysis([], 10))
t("E5 rsi range", 0 <= e5['rsi'] <= 100, f"rsi={e5['rsi']:.1f}")
t("E5 ma20", e5['ma20'] > 0)

# ====== 3. game_theory_6d ======
hdr("3. game_theory_6d")
from core.game_theory_6d import *
a1 = a1_analysis({"ddx_5d":1.5,"ddx_10d":2.0,"main_amount":300e6})
t("A1 buy", a1["signal"]=="buy" and a1["stage"]=="拉升期")
a1v = a1_analysis({"ddx_5d":-2,"ddx_10d":0,"main_amount":0})
t("A1 veto", a1v["veto"] and a1v["score"]==0)
a1v10 = a1_analysis({"ddx_5d":-0.5,"ddx_10d":-4,"main_amount":0})
t("A1 10d veto", a1v10["veto"])
b2b = b2_analysis({"sentiment":"bullish"})
t("B2 bullish", b2b["coefficient"]==1.0 and b2b["score"]==90)
b2p = b2_analysis({"sentiment":"恐慌"})
t("B2 panic", b2p["coefficient"]==0)
c3 = c3_analysis({"price":50,"rsi":55,"volatility":0.02,"vol_ratio":1.5})
t("C3 break_prob", 0<c3["break_prob"]<=1)
t("C3 kelly>=0", c3["kelly_fraction"]>=0)
d4 = d4_analysis({"volatility":0.02,"vol_ratio":1.0,"rsi":50})
t("D4 low risk", d4["tail_risk"]=="Low")
d4h = d4_analysis({"volatility":0.09,"vol_ratio":4.0,"rsi":90})
t("D4 high risk", d4h["tail_risk"]=="High")
f6s = f6_analysis({"active_buy_ratio":0.65,"super_large_net":80e6,"inst_vs_retail":1.8,"continuity_3d":3}, True)
t("F6 strong", f6s["confirm_level"]=="强确认" and f6s["l2_mult"]==1.0)
f6r = f6_analysis({"active_buy_ratio":0.1,"super_large_net":-50e6,"inst_vs_retail":0.3,"continuity_3d":0}, True)
t("F6 reject", f6r["confirm_level"]=="拒绝" and f6r["l2_mult"]==0)
f6n = f6_analysis({}, False)
t("F6 no L2 needed", f6n["l2_mult"]==1.0)

data = {"code":"000001","price":10,"ddx_5d":0.5,"ddx_10d":0.3,"main_amount":50e6,
    "low_60d":8,"high_60d":12,"ma20":10,"ma5":10.2,"rsi":50,"volatility":0.02,"amplitude":3,
    "active_buy_ratio":0.55,"super_large_net":20e6,"inst_vs_retail":1.1,
    "topic":"test","topic_rank":5,"is_limit_up":False,"lianban_days":0,
    "E5_position_pct":50,"vol_ratio":1.0,"sentiment":"neutral"}
r = analyze(data, klines)
t("Game has signal", r["signal"] in ("buy","hold","sell","hold_watch"))
t("Game score 0-100", 0<=r["final_score"]<=100)
t("Game has 6 dims", all(k in r.get("dimensions",{}) for k in ["A1","B2","C3","D4","E5","F6"]))
t("Game action", "action" in r)
t("Game veto reason", "veto_reason" not in r or r.get("veto_reason") is None)

# ====== 4. classic_4p ======
hdr("4. classic_4p")
from core.classic_4p import *
c = classic_analyze(data)
t("Classic score 0-100", 0<c["total_score"]<=100)
t("Classic 4 views", all(k in c["perspectives"] for k in ["Z","Y","Q","M"]))
t("Classic forecast", "direction" in c["forecast"])
t("Classic signal", c["signal"] in ("buy","hold","sell"))

# ====== 5. trend_forecaster ======
hdr("5. trend_forecaster")
from core.trend_forecaster import *
scenarios = [(85,85,"高共识看多","strong_buy",1.2),(85,55,"偏多共识","buy",1.0),
             (85,30,"背离（六强经弱）","reduce_buy",0.5),(55,85,"分歧","hold",0.7),
             (55,55,"分歧","hold",0.7),(30,30,"高共识看空","sell_all",0.0)]
for six,cl,exp_type,exp_sig,exp_mult in scenarios:
    c = consensus_arbitration(six,cl,1.0)
    t(f"{six}/{cl}→{exp_type}", c["consensus_type"]==exp_type and c["signal"]==exp_sig and c["position_mult"]==exp_mult,
      f"got {c['consensus_type']}/{c['signal']}/{c['position_mult']}")
f = forecast(90,90)
t("Forecast bullish", f["direction"]=="强势上涨" and f["confidence"]>=0.8)

# ====== 6. position ======
hdr("6. position")
from core.position import *
t("classify 3=恐慌", classify_emotion(3)=="恐慌")
t("classify 25=中性", classify_emotion(25)=="中性")
t("classify 55=积极", classify_emotion(55)=="积极")
p = calculate_position(emotion="积极",stage="主升期",e5_level_code=1,l2_total_score=8,vol_level="低波")
t("pos positive >10%", p["final_pct"]>0.10, f'{p["final_pct"]:.4f}')
p2 = calculate_position(emotion="恐慌",stage="主升期",e5_level_code=0)
t("pos panic=0", p2["final_pct"]==0)
p3 = calculate_position(emotion="积极",stage="主升期",e5_level_code=3,l2_total_score=0)
t("pos L2 veto=0", p3["final_pct"]==0)

# ====== 7-9. f6_l2, g0, t0 ======
hdr("7. f6_l2 + g0_scanner + t0_engine")
from core.f6_l2 import l2_verify
r = l2_verify(0.65,80e6,1.8,3,need_l2=True)
t("L2 strong", r["confirm_level"]=="强确认")
r2 = l2_verify(0.3,20e6,1.0,2,need_l2=True)
t("L2 medium", r2["confirm_level"]=="中确认" and r2["l2_mult"]==0.6, f"score={r2['score']}")

from core.g0_scanner import g0_scan
g0 = g0_scan(code="000831",topic_name="稀土",topic_rank=1,topic_limit_up_count=8,topic_net_amount=5e8,
             stock_rank_in_topic=2,stock_capital_rank=1,core_stock_performing=True,outer_ratio=0.65)
t("G0 score>=7", g0["g0_score"]>=7, f'{g0["g0_score"]}')
t("G0 washing detected", g0["washing_detected"])
t("G0 leader", g0["stock_position"]=="龙头")

from core.t0_engine import *
t0 = t0_check(g0_score=8,game_score=75,big_order_positive=True,amplitude=6.5,topic_strength_score=8)
t("T0 triggered", t0["triggered"] and t0["direction"]=="正T")
t0n = t0_check(g0_score=3,game_score=50,amplitude=2)
t("T0 not triggered", not t0n["triggered"])
sh = t0_position_size(8,5000)
t("T0 shares round 100", sh>0 and sh%100==0)

# ====== 10. p3_position ======
hdr("10. p3_position")
from core.p3_position import *
prob = p3_probability(0.8,0.7,0.75,0.6,0.8)
t("P3 prob sum≈1", abs(prob["up_prob"]+prob["down_prob"]+prob["flat_prob"]-1)<0.01)
kelly = p3_kelly(0.7,0.2,2.5,2.0)
t("P3 kelly>0", kelly["kelly_fraction"]>0.05)
ceil = p3_ceiling(8,82,0.03,"积极")
t("P3 ceiling>10%", ceil["ceiling"]>0.10, f'{ceil["ceiling"]:.3f}')

# ====== 11-13. booster, bobo, capital ======
hdr("11. limit_up_booster + bobo_scorer + capital_scanner")
from core.limit_up_booster import limit_up_boost
b = limit_up_boost({"is_limit_up":False,"lianban_days":0})
t("Boost inactive", not b["triggered"] and b["boost_score"]==0)
b2 = limit_up_boost({"is_limit_up":True,"lianban_days":3,"seal_amount":5e8,"float_market_cap":10e9,"limit_up_time":"09:35","ddz":45})
t("Boost active", b2["triggered"] and b2["boost_score"]>0)

from core.bobo_scorer import bobo_score, bobo_game_fusion
bs = bobo_score(900,3e8,5,"政策","逆势净流入","二浪确认",20,30,"龙头")
t("Bobo>50", bs["total_score"]>50, f'{bs["total_score"]}')
fu = bobo_game_fusion(75,80)
t("Fusion enhance", "增强" in fu["cross_validation"])

from core.capital_scanner import capital_scan
cs = capital_scan(6e8,0.5,1,-0.1,2,"机构","增持",999,100e6,True)
t("Capital strong", cs["total_score"]>=70)
cs2 = capital_scan()
t("Capital weak", cs2["total_score"]<50)

# ====== 14-16. wave, ddx, concept ======
hdr("14. wave_analyzer + ddx_calculator + concept")
from core.wave_analyzer import wave_analyze
trend = [{"open":10+i*0.3-0.1,"high":10+i*0.3+0.2,"low":10+i*0.3-0.2,"close":10+i*0.3,"volume":10e6+i*5e5} for i in range(60)]
wa = wave_analyze(trend)
t("Wave stage", wa["wave_stage"]!="数据不足")
t("Wave chanlun", "has_pivot" in wa["chanlun"])
t("Wave empty error", "error" in wave_analyze([]))

from core.ddx_calculator import *
da = calculate_ddx_from_amount(50e6,1e9,50)
t("DDX amount>0", da["ddx"]>0)
dt = calculate_ddx_from_trades([{"volume":600,"type":"买入"}]*60+[{"volume":600,"type":"卖出"}]*30,1e9,500)
t("DDX trades>0", dt["ddx"]>0)
md = calculate_multi_day_ddx([0.2,0.3,0.4,0.5,0.6,-2,-1.5,-2.5,-3,-1])
t("DDX multi veto", md["veto"])

from core.concept import map_sub_topics
main=["000001","000002","000003","000004","000005","000006","000007","000008","000009","000010"]
subs={"银行":["000001","000002","000003","000011"],"金融":["000001","000002","000003","000004","000005"],"地产":["000006","000007"],"科技":["000020"]}
m = map_sub_topics(main,subs)
t("Concept strong", len(m["strong"])>=1)
t("Concept moderate", len(m["moderate"])>=1)

# ====== 17. orchestrator ======
hdr("17. trade_orchestrator")
from orchestrators.trade_orchestrator import orchestrate
orch = orchestrate(code="000001",topic_name="银行",klines=klines,sentiment="中性",topic_rank=5,topic_limit_up_count=25)
t("Orch all layers", all(k in orch for k in ["g0","game_6d","consensus","forecast","t0","position","decision"]))
t("Orch decision", "action" in orch["decision"] and "signal" in orch["decision"])

# ====== SUMMARY ======
hdr("SUMMARY")
results.append(f"\n  Total: {passed+failed} | ✅ Pass: {passed} | ❌ Fail: {failed}")
if failed == 0: results.append("  🎉 ALL TESTS PASSED")
for r in results: print(r)
