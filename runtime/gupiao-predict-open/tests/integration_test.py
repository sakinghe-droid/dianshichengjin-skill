#!/usr/bin/env python3
"""Full integration test suite — tests all modules end-to-end"""
import sys, os, json, subprocess, time
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
DATA_FALLBACK = os.path.join(PROJECT_ROOT, "scripts", "data_fallback.py")

PASS, FAIL, ERR = 0, 0, 0
results = []

def t(name, ok, detail=""):
    global PASS, FAIL
    if ok: PASS += 1; results.append(f"  ✅ {name}")
    else: FAIL += 1; results.append(f"  ❌ {name} — {detail}")

def hdr(s):
    results.append(f"\n{'='*50}\n  {s}\n{'='*50}")

# ====== 1. Data Sources ======
hdr("1. Data Sources")

# TDX MCP
try:
    from data_sources.tdx_mcp import TDXClient
    tdx = TDXClient()
    lu = tdx.get_limit_up_stocks(size=5)
    t("TDX MCP connect", len(lu) >= 1, f"{len(lu)} stocks")
    
    ind = tdx.query_indicators("000001")
    t("TDX indicators", len(ind) >= 3, f"{len(ind)} keys")
except Exception as e:
    ERR += 1; results.append(f"  ❌ TDX MCP: {e}")

# data_fallback
try:
    r = subprocess.run([sys.executable,
        'DATA_FALLBACK',
        '--mode','health'], capture_output=True, text=True, timeout=15)
    health = json.loads(r.stdout)
    t("data_fallback health", health.get('primary_ok', False))
except Exception as e:
    ERR += 1; results.append(f"  ❌ data_fallback: {e}")

# mx-moni
try:
    from data_sources.trade_executor import TradeExecutor
    te = TradeExecutor()
    pos = te.get_position()
    t("mx-moni position", pos.get('total_asset', 0) > 0, f"asset={pos.get('total_asset',0)}")
except Exception as e:
    ERR += 1; results.append(f"  ❌ mx-moni: {e}")

# ====== 2. Core Engines ======
hdr("2. Core Engines")

# math_utils
try:
    from core.math_utils import rsi_wilder, e5_full_analysis, band_position, position_level
    rsi = rsi_wilder([10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25])
    t("RSI(14)", rsi is not None and rsi > 50)
    lvl, code, ceil, need = position_level(10, 45)
    t("E5 low position", code == 0 and ceil == 0.30)
except Exception as e:
    ERR += 1; results.append(f"  ❌ math_utils: {e}")

# E5 with real data
try:
    r = subprocess.run([sys.executable,
        'DATA_FALLBACK',
        '--mode','kline','--code','000001','--count','60'],
        capture_output=True, text=True, timeout=15)
    klines = json.loads(r.stdout)
    e5 = e5_full_analysis(klines, klines[-1]['close'])
    t("E5 analysis", 'level' in e5 and 'ceiling' in e5, f"level={e5['level']}")
except Exception as e:
    ERR += 1; results.append(f"  ❌ E5: {e}")

# game_theory_6d
try:
    from core.game_theory_6d import analyze as game_analyze
    data = {"code":"000001","price":10,"ddx_5d":0.5,"ddx_10d":0.3,"main_amount":5e7,
        "low_60d":8,"high_60d":12,"ma20":10,"ma5":10.2,"rsi":50,"volatility":0.02,
        "amplitude":3,"active_buy_ratio":0.55,"super_large_net":2e7,"inst_vs_retail":1.1,
        "topic":"test","topic_rank":5,"is_limit_up":False,"lianban_days":0,
        "E5_position_pct":50,"vol_ratio":1.0,"sentiment":"neutral"}
    r = game_analyze(data)
    t("Game 6D", r['signal'] in ('buy','hold','sell') and 0<=r['final_score']<=100,
      f"score={r['final_score']:.0f} signal={r['signal']}")
except Exception as e:
    ERR += 1; results.append(f"  ❌ game_6d: {e}")

# classic_4p
try:
    from core.classic_4p import classic_analyze
    r = classic_analyze(data)
    t("Classic 4P", 0<=r['total_score']<=100, f"score={r['total_score']:.0f}")
except Exception as e:
    ERR += 1; results.append(f"  ❌ classic_4p: {e}")

# trend_forecaster
try:
    from core.trend_forecaster import consensus_arbitration
    r = consensus_arbitration(85, 85, 1.0)
    t("Consensus", r['consensus_type']=='高共识看多' and r['signal']=='strong_buy')
except Exception as e:
    ERR += 1; results.append(f"  ❌ trend_forecaster: {e}")

# position
try:
    from core.position import calculate_position
    r = calculate_position(emotion="积极", stage="主升期", e5_level_code=1)
    t("Position calc", r['final_pct'] > 0.10, f"pct={r['final_pct']*100:.0f}%")
except Exception as e:
    ERR += 1; results.append(f"  ❌ position: {e}")

# f6_l2, g0, t0, p3
try:
    from core.f6_l2 import l2_verify
    r = l2_verify(0.65, 80e6, 1.8, 3, need_l2=True)
    t("F6 L2", r['confirm_level']=='强确认', f"score={r['score']}")
    
    from core.g0_scanner import g0_scan
    r = g0_scan(code="000831", topic_name="稀土", topic_rank=1, topic_limit_up_count=8)
    t("G0 scan", r['g0_score'] >= 0, f"score={r['g0_score']}")
    
    from core.t0_engine import t0_check
    r = t0_check(g0_score=8, game_score=75, amplitude=6.5)
    t("T0 engine", r['triggered'], f"direction={r['direction']}")
    
    from core.p3_position import p3_probability
    r = p3_probability(0.8, 0.7, 0.75, 0.6, 0.8)
    t("P3 prob", abs(r['up_prob']+r['down_prob']+r['flat_prob']-1)<0.01)
except Exception as e:
    ERR += 1; results.append(f"  ❌ engines: {e}")

# bobo, capital, wave, ddx, concept, limit_up
try:
    from core.bobo_scorer import bobo_score
    r = bobo_score(900, 3e8, 5, "政策", "逆势净流入", "二浪确认", 20, 30, "龙头")
    t("Bobo scorer", r['total_score'] > 0, f"score={r['total_score']}")
    
    from core.capital_scanner import capital_scan
    r = capital_scan(6e8, 0.5, 1, -0.1, 2, "机构", "增持")
    t("Capital scan", r['total_score'] > 0, f"score={r['total_score']}")
    
    from core.wave_analyzer import wave_analyze
    trend = [{"open":10+i*0.3-0.1,"high":10+i*0.3+0.2,"low":10+i*0.3-0.2,"close":10+i*0.3,"volume":10e6} for i in range(60)]
    r = wave_analyze(trend)
    t("Wave analyzer", r['wave_stage'] != '数据不足', f"stage={r['wave_stage']}")
    
    from core.ddx_calculator import calculate_ddx_from_amount
    r = calculate_ddx_from_amount(50e6, 1e9, 50)
    t("DDX calc", r['ddx'] > 0, f"ddx={r['ddx']:.4f}")
    
    from core.concept import map_sub_topics
    r = map_sub_topics(["000001","000002","000003"], {"银行":["000001","000002"]})
    t("Concept map", len(r['strong']) >= 1)
    
    from core.limit_up_booster import limit_up_boost
    r = limit_up_boost({"is_limit_up": True, "lianban_days": 3, "seal_amount": 5e8, "float_market_cap": 10e9, "limit_up_time": "09:35", "ddz": 45})
    t("Limit up boost", r['triggered'] and r['boost_score'] > 0, f"boost={r['boost_score']}")
except Exception as e:
    ERR += 1; results.append(f"  ❌ sub-engines: {e}")

# ====== 3. Orchestrators ======
hdr("3. Orchestrators")

# mainline_engine
try:
    topics = [{"name":"AI","limit_up_count":18,"net_amount":3.5e9,"rank":1,"stocks":[
        {"code":"688256","change_pct":10.0,"market_cap":250e8,"seal_amount":5e8}]}]
    from orchestrators.mainline_engine import run_quadrant_analysis, locate_leaders
    r = run_quadrant_analysis(topics)
    t("Mainline run", r['has_mainline'] == True, f"quadrant={r['quadrant']}")
    
    leaders = locate_leaders(topics[0]['stocks'])
    t("Mainline -p", len(leaders) >= 1)
except Exception as e:
    ERR += 1; results.append(f"  ❌ mainline: {e}")

# w5_pipeline
try:
    from orchestrators.w5_pipeline import analyze_single_holding
    r = analyze_single_holding("000001", hold_shares=5000, cost_price=10.50, topic_name="银行")
    t("W5 pipeline", r['decision'] in ('持有','持有或做T','加仓','减仓','清仓'), f"decision={r['decision']}")
except Exception as e:
    ERR += 1; results.append(f"  ❌ w5: {e}")

# review_engine
try:
    from orchestrators.review_engine import generate_report
    r = generate_report()
    t("W6 review", 'logic_review' in r and 'benchmark' in r)
except Exception as e:
    ERR += 1; results.append(f"  ❌ w6: {e}")

# trade_orchestrator
try:
    from orchestrators.trade_orchestrator import orchestrate
    r = orchestrate(code="000001", topic_name="银行", klines=klines, sentiment="中性")
    t("Trade orch", all(k in r for k in ['g0','game_6d','consensus','decision']))
except Exception as e:
    ERR += 1; results.append(f"  ❌ trade_orch: {e}")

# ====== 4. CLI Scripts ======
hdr("4. CLI Scripts")

# e5_position
try:
    r = subprocess.run([sys.executable, 'scripts/e5_position.py', '--code','000001','--count','60'],
        capture_output=True, text=True, timeout=20)
    d = json.loads(r.stdout)
    t("e5_position CLI", 'level' in d, f"level={d.get('level','?')}")
except Exception as e:
    ERR += 1; results.append(f"  ❌ e5_position CLI: {e}")

# game_theory_6d
try:
    r = subprocess.run([sys.executable, 'scripts/game_theory_6d.py', '--code','000001'],
        capture_output=True, text=True, timeout=20)
    d = json.loads(r.stdout)
    t("game_theory_6d CLI", 'final_score' in d, f"score={d.get('final_score',0):.0f}")
except Exception as e:
    ERR += 1; results.append(f"  ❌ game_theory_6d CLI: {e}")

# n3_n6
try:
    r = subprocess.run([sys.executable, 'scripts/n3_n6.py', '--mode','holdings'],
        capture_output=True, text=True, timeout=15)
    d = json.loads(r.stdout)
    t("n3_n6 CLI", 'total' in d or 'error' in d, f"{d.get('total', d.get('error','?'))}")
except Exception as e:
    ERR += 1; results.append(f"  ❌ n3_n6 CLI: {e}")

# ====== SUMMARY ======
hdr("SUMMARY")
results.append(f"\n  Total: {PASS+FAIL} | ✅ Pass: {PASS} | ❌ Fail: {FAIL} | ⚠️ Errors: {ERR}")
if FAIL == 0 and ERR == 0:
    results.append("  🎉 ALL TESTS PASSED")
else:
    results.append("  ⚠️ SOME TESTS FAILED")

for r in results:
    print(r)
