"""
trade_orchestrator.py — 交易编排器

串联: G0 → 六维博弈 → 场景化触发 → 经典四视角 → 双引擎共识仲裁 → T0 → P3

用法:
    python orchestrators/trade_orchestrator.py --code 000001 --kline kline.json --sentiment neutral
"""

import json
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.math_utils import e5_full_analysis
from core.game_theory_6d import analyze as game_analyze
from core.classic_4p import classic_analyze
from core.trend_forecaster import consensus_arbitration, forecast as tf_forecast
from core.g0_scanner import g0_scan
from core.t0_engine import t0_check
from core.p3_position import p3_probability, p3_kelly, p3_ceiling
from core.position import calculate_position, classify_emotion


def orchestrate(
    code: str,
    topic_name: str = "自动分析",
    klines: list = None,
    input_data: dict = None,
    sentiment: str = "中性",
    topic_rank: int = 5,
    topic_limit_up_count: int = 0,
    topic_net_amount: float = 0,
) -> dict:
    """
    一站式编排: G0 → 六维 → 经典 → 共识 → T0 → P3 → 仓位
    """
    if input_data is None and klines is None:
        return {"error": "需要 input_data 或 klines"}
    
    # 从K线构建输入
    if klines and input_data is None:
        closes = [k['close'] for k in klines]
        highs = [k['high'] for k in klines]
        lows = [k['low'] for k in klines]
        price = closes[-1]
        e5 = e5_full_analysis(klines, price)
        
        input_data = {
            "code": code, "price": price,
            "ddx_5d": 0.3, "ddx_10d": 0.1,
            "main_amount": 50000000,
            "low_60d": min(lows[-60:]), "high_60d": max(highs[-60:]),
            "ma20": sum(closes[-20:])/20 if len(closes)>=20 else price,
            "ma5": sum(closes[-5:])/5 if len(closes)>=5 else price,
            "rsi": e5['rsi'], "volatility": e5['annual_volatility'],
            "amplitude": e5['amplitude_today'],
            "active_buy_ratio": 0.55, "super_large_net": 20000000, "inst_vs_retail": 1.1,
            "topic": topic_name, "topic_rank": topic_rank,
            "is_limit_up": False, "lianban_days": 0,
            "E5_position_pct": e5['band_position_pct'],
            "vol_ratio": e5['vol_ratio_vs_20d'],
            "sentiment": sentiment,
        }
    
    result = {"code": code, "topic": topic_name}
    
    # === Layer 1: G0 ===
    g0 = g0_scan(
        code=code, topic_name=topic_name,
        topic_rank=topic_rank,
        topic_limit_up_count=topic_limit_up_count,
        topic_net_amount=topic_net_amount,
    )
    result["g0"] = g0
    
    # === Layer 2: 六维博弈 ===
    game = game_analyze(input_data, klines)
    result["game_6d"] = game
    
    # === 场景化触发: 需要经典版? ===
    need_classic = (
        game.get("final_score", 0) >= 70 or
        input_data.get("is_limit_up", False) or
        input_data.get("lianban_days", 0) > 0 or
        input_data.get("topic_rank", 99) <= 3 or
        e5.get("level_code", 0) >= 3 if klines else False
    )
    
    if need_classic:
        classic = classic_analyze(input_data)
        result["classic_4p"] = classic
        classic_score = classic["total_score"]
    else:
        classic_score = 50  # 默认中性
    
    # === Layer 3: 共识仲裁 ===
    six_score = game.get("final_score", 50)
    base_pos = game.get("position_pct", 1.0) * 10  # 转为成数
    consensus = consensus_arbitration(six_score, classic_score, base_pos)
    forecast_r = tf_forecast(six_score, classic_score)
    result["consensus"] = consensus
    result["forecast"] = forecast_r
    
    # === Layer 4: T0 (条件触发) ===
    g0_score = g0.get("g0_score", 0)
    game_score = game.get("final_score", 0)
    amplitude = e5.get("amplitude_today", 3.0) if klines else input_data.get("amplitude", 3.0)
    
    t0 = t0_check(
        g0_score=g0_score,
        game_score=game_score,
        amplitude=amplitude,
        topic_strength_score=g0.get("topic_strength", 0),
    )
    result["t0"] = t0
    
    # === Layer 5: P3 (T0触发时) ===
    if t0["triggered"]:
        prob = p3_probability(
            topic_momentum=g0_score / 10,
            capital_flow=0.7 if input_data.get("main_amount", 0) > 0 else 0.3,
            relative_strength=0.75,
            position_safety=min(0.9, amplitude / 15),
            volume_confirmation=min(1.0, input_data.get("vol_ratio", 1.0) / 2),
        )
        kelly = p3_kelly(prob["up_prob"], prob["down_prob"])
        ceiling = p3_ceiling(g0_score, game_score, input_data.get("volatility", 0.03), sentiment)
        result["p3"] = {"probability": prob, "kelly": kelly, "ceiling": ceiling}
    
    # === 最终仓位 ===
    e5_ceiling_val = e5.get("ceiling", 0.20) if klines else 0.20
    e5_level_code = e5.get("level_code", 2) if klines else 2
    vol_level = e5.get("volatility", "中波") if klines else "中波"
    
    # emotion from limit_up stats
    emotion = classify_emotion(topic_limit_up_count if topic_limit_up_count > 0 else 25)
    
    pos = calculate_position(
        emotion=emotion,
        stage="主升期",
        e5_level_code=e5_level_code,
        e5_ceiling=e5_ceiling_val,
        vol_level=vol_level,
        g0_score=g0_score,
    )
    result["position"] = pos
    
    # === 综合决策 ===
    consensus_signal = consensus["signal"]
    action_map = {
        "strong_buy": "强烈买入",
        "buy": "买入",
        "reduce_buy": "谨慎买入",
        "light_buy": "轻仓试探",
        "hold": "持有观察",
        "sell": "卖出",
        "sell_all": "清仓",
    }
    
    result["decision"] = {
        "action": action_map.get(consensus_signal, "观望"),
        "signal": consensus_signal,
        "merged_score": consensus["merged_score"],
        "final_position_cheng": consensus["final_position_pct"],
        "t0_triggered": t0["triggered"],
        "t0_direction": t0.get("direction", "N/A"),
    }
    
    return result


def main():
    parser = argparse.ArgumentParser(description="交易编排器 (开源版)")
    parser.add_argument("--code", required=True, help="股票代码")
    parser.add_argument("--topic_name", default="自动分析")
    parser.add_argument("--kline", help="K线JSON文件")
    parser.add_argument("--input", help="输入JSON文件")
    parser.add_argument("--sentiment", default="中性")
    parser.add_argument("--output", "-o", help="输出文件")
    args = parser.parse_args()
    
    klines = None
    if args.kline:
        with open(args.kline) as f:
            kd = json.load(f)
        klines = kd if isinstance(kd, list) else kd.get('data', [])
    
    input_data = None
    if args.input:
        with open(args.input) as f:
            input_data = json.load(f)
    
    result = orchestrate(
        code=args.code, topic_name=args.topic_name,
        klines=klines, input_data=input_data, sentiment=args.sentiment,
    )
    
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
