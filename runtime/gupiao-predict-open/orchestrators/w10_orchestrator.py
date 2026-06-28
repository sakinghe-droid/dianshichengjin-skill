#!/usr/bin/env python3
"""
w10_orchestrator.py — W10 趋势波段编排器

模式A: 个股深度9步
模式B: 题材波段挖掘7步

用法:
    python orchestrators/w10_orchestrator.py --mode A --code 000001
    python orchestrators/w10_orchestrator.py --mode B --topic 稀土永磁 --stocks stocks.json
"""

import sys, os, json, argparse, subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OPEN_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")

from core.math_utils import e5_full_analysis, rsi_wilder, daily_returns, daily_volatility
from core.wave_analyzer import wave_analyze
from core.bobo_scorer import bobo_score, bobo_game_fusion
from core.capital_scanner import capital_scan
from core.game_theory_6d import analyze as game_analyze
from core.g0_scanner import g0_scan
from core.t0_engine import t0_check
from core.p3_position import p3_probability, p3_kelly


def fetch_klines(code: str, count: int = 90) -> list:
    r = subprocess.run(
        [sys.executable, f"{OPEN_SCRIPTS}/data_fallback.py",
         "--mode", "kline", "--code", code, "--count", str(count)],
        capture_output=True, text=True, timeout=30
    )
    return json.loads(r.stdout)


def mode_a_individual(code: str, topic_name: str = "自动分析", sentiment: str = "中性",
                      pe: float = 30, industry_pe: float = 30, market_position: str = "跟随者",
                      catalyst_type: str = "新闻") -> dict:
    """模式A: 个股深度9步"""
    
    # Step 1: 数据采集
    klines = fetch_klines(code, 90)
    price = klines[-1]['close']
    e5 = e5_full_analysis(klines, price)
    
    # Step 2: 题材全局定位
    g0 = g0_scan(code=code, topic_name=topic_name)
    
    # Step 3: 趋势波段分析
    wave = wave_analyze(klines, catalyst_type)
    
    # Step 4: 资金全景 (降级版)
    capital = capital_scan()
    
    # Step 5: 波波六维
    bobo = bobo_score(
        sector_strength=500, sector_net_inflow=1e8, sector_limit_up=3,
        catalyst_type=catalyst_type, fund_signal="中性", wave_stage=wave["wave_stage"],
        pe=pe, industry_avg_pe=industry_pe, market_position=market_position,
    )
    
    # Step 6: 博弈引擎六维
    closes = [k['close'] for k in klines]
    highs = [k['high'] for k in klines]
    lows = [k['low'] for k in klines]
    
    input_data = {
        "code": code, "price": price,
        "ddx_5d": 0.3, "ddx_10d": 0.1, "main_amount": 5e7,
        "low_60d": min(lows[-60:]), "high_60d": max(highs[-60:]),
        "ma20": sum(closes[-20:])/20, "ma5": sum(closes[-5:])/5,
        "rsi": e5['rsi'], "volatility": e5['annual_volatility'],
        "amplitude": e5['amplitude_today'],
        "active_buy_ratio": 0.55, "super_large_net": 0, "inst_vs_retail": 1.0,
        "topic": topic_name, "topic_rank": 5, "is_limit_up": False, "lianban_days": 0,
        "E5_position_pct": e5['band_position_pct'], "vol_ratio": e5['vol_ratio_vs_20d'],
        "sentiment": sentiment,
    }
    game = game_analyze(input_data, klines)
    
    # Step 7: T0/P3
    t0 = t0_check(g0_score=g0["g0_score"], game_score=game["final_score"],
                  amplitude=e5["amplitude_today"])
    p3 = None
    if t0["triggered"]:
        prob = p3_probability(topic_momentum=g0["g0_score"]/10)
        p3 = p3_kelly(prob["up_prob"], prob["down_prob"])
    
    # Step 8: 双引擎融合
    fusion = bobo_game_fusion(bobo["total_score"], game["final_score"])
    
    # Step 9: 综合报告
    return {
        "code": code, "price": price,
        "topic_position": {"g0_score": g0["g0_score"], "stock_role": g0["stock_position"]},
        "wave_analysis": {
            "stage": wave["wave_stage"], "pattern": wave["pattern"],
            "flag": wave["flag_pattern"], "wave2": wave["wave2_confirmed"],
            "band_pct": wave["metrics"]["band_position_pct"],
        },
        "capital_panorama": {"total": capital["total_score"], "level": capital["level"]},
        "bobo_score": {"total": bobo["total_score"], "sub": {k: v["score"] for k, v in bobo["sub_scores"].items()}},
        "game_score": {"total": game["final_score"], "signal": game["signal"], "risk": game["risk_level"]},
        "fusion": fusion,
        "decision": {
            "direction": game["direction"], "signal": game["signal"],
            "position_pct": game["position_pct"],
            "t0_triggered": t0["triggered"], "t0_direction": t0.get("direction", "N/A"),
        },
        "risk": {"level": game["risk_level"], "key_risks": [e5["level"]] if e5["level_code"] >= 3 else []},
    }


def mode_b_topic(topic_name: str, stocks_file: str = None) -> dict:
    """模式B: 题材波段挖掘7步 (简化版)"""
    if not stocks_file:
        return {"error": "模式B需要 --stocks 参数提供候选股列表JSON"}
    
    with open(stocks_file) as f:
        stocks = json.load(f)
    
    results = []
    for s in stocks[:10]:  # 最多10只
        try:
            r = mode_a_individual(s["code"], topic_name)
            r["name"] = s.get("name", "")
            results.append(r)
        except Exception as e:
            results.append({"code": s.get("code",""), "error": str(e)})
    
    results.sort(key=lambda x: -(x.get("fusion", {}).get("merged_score", 0) if "fusion" in x else 0))
    
    return {
        "topic": topic_name,
        "total_analyzed": len(results),
        "candidates": results,
        "top_pick": results[0] if results else None,
    }


def main():
    parser = argparse.ArgumentParser(description="W10 趋势波段编排器 (开源版)")
    parser.add_argument("--mode", choices=["A", "B"], default="A")
    parser.add_argument("--code", help="股票代码 (模式A)")
    parser.add_argument("--topic", default="自动分析", help="题材名")
    parser.add_argument("--stocks", help="候选股JSON (模式B)")
    parser.add_argument("--sentiment", default="中性")
    parser.add_argument("--pe", type=float, default=30)
    parser.add_argument("--industry-pe", type=float, default=30)
    parser.add_argument("--position", default="跟随者", help="市场地位")
    parser.add_argument("--catalyst", default="新闻", help="催化类型")
    parser.add_argument("-o", "--output", help="输出文件")
    args = parser.parse_args()
    
    if args.mode == "A" and args.code:
        result = mode_a_individual(args.code, args.topic, args.sentiment,
                                   args.pe, args.industry_pe, args.position, args.catalyst)
    elif args.mode == "B":
        result = mode_b_topic(args.topic, args.stocks)
    else:
        print("模式A需要 --code, 模式B需要 --stocks", file=sys.stderr)
        sys.exit(1)
    
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
