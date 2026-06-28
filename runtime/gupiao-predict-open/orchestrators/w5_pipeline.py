#!/usr/bin/env python3
"""
w5_pipeline.py — W5 持仓管理完整流水线

四层串联: W9前置(洗盘识别) → G0全局扫描 → 六维博弈 → T0/P3战术

用法:
    python orchestrators/w5_pipeline.py --code 000001 --hold-shares 1000 --cost 10.50
    python orchestrators/w5_pipeline.py --batch holdings.json
"""

import sys, os, json, argparse, subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OPEN_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")

from core.math_utils import e5_full_analysis
from core.game_theory_6d import analyze as game_analyze
from core.g0_scanner import g0_scan
from core.t0_engine import t0_check, t0_position_size, t0_calculate_zones
from core.p3_position import p3_probability, p3_kelly, p3_ceiling
from core.position import calculate_position, classify_emotion


def fetch_klines(code: str, count: int = 120) -> list:
    r = subprocess.run(
        [sys.executable, f"{OPEN_SCRIPTS}/data_fallback.py",
         "--mode", "kline", "--code", code, "--count", str(count)],
        capture_output=True, text=True, timeout=30
    )
    return json.loads(r.stdout)


def fetch_quote(code: str) -> dict:
    r = subprocess.run(
        [sys.executable, f"{OPEN_SCRIPTS}/data_fallback.py",
         "--mode", "quote", "--code", code],
        capture_output=True, text=True, timeout=30
    )
    return json.loads(r.stdout)


def analyze_single_holding(
    code: str,
    hold_shares: int = 0,
    cost_price: float = 0,
    topic_name: str = "自动分析",
    topic_rank: int = 5,
    topic_limit_up_count: int = 0,
    topic_net_amount: float = 0,
    sentiment: str = "中性",
    ddx_5d: float = 0.3,
    ddx_10d: float = 0.1,
) -> dict:
    """对单只持仓执行完整 W5 四层分析"""
    
    # 获取数据
    klines = fetch_klines(code, 120)
    quote = fetch_quote(code)
    price = klines[-1]['close'] if klines else quote.get('price', 10)
    e5 = e5_full_analysis(klines, price)
    
    # 盈亏计算
    pnl_pct = (price - cost_price) / cost_price * 100 if cost_price > 0 else 0
    
    # ===== 第一层: W9前置 — 洗盘识别 (内嵌在G0中) =====
    g0 = g0_scan(
        code=code, topic_name=topic_name,
        topic_rank=topic_rank,
        topic_limit_up_count=topic_limit_up_count,
        topic_net_amount=topic_net_amount,
    )
    
    # 洗盘判定 → 直接决策
    if g0["washing_detected"]:
        return {
            "code": code, "price": price, "pnl_pct": round(pnl_pct, 2),
            "decision": "持有观察",
            "reason": f"W9洗盘识别: 置信度{g0['washing_confidence']:.0%} → 跳过博弈引擎",
            "pipeline_path": "W9→跳过后续",
            "g0": g0, "e5": {k: e5[k] for k in ['level','ceiling','volatility','rsi']},
        }
    
    if g0.get("stock_position") == "卫星" and g0.get("topic_strength", 0) < 4:
        return {
            "code": code, "price": price, "pnl_pct": round(pnl_pct, 2),
            "decision": "减仓/清仓",
            "reason": f"W9出货信号: 题材弱({g0.get('topic_strength')}) + 个股卫星定位 → 建议清仓",
            "pipeline_path": "W9→直接决策",
            "g0": g0, "e5": {k: e5[k] for k in ['level','ceiling','volatility','rsi']},
        }
    
    # ===== 第二层: G0 (已计算) =====
    
    # ===== 第三层: 六维博弈 =====
    closes = [k['close'] for k in klines]
    highs = [k['high'] for k in klines]
    lows = [k['low'] for k in klines]
    volumes = [k['volume'] for k in klines]
    
    input_data = {
        "code": code, "price": price,
        "ddx_5d": ddx_5d, "ddx_10d": ddx_10d,
        "main_amount": quote.get("amount", 0) * 0.08,
        "low_60d": min(lows[-60:]), "high_60d": max(highs[-60:]),
        "ma20": sum(closes[-20:])/20, "ma5": sum(closes[-5:])/5,
        "rsi": e5['rsi'], "volatility": e5['annual_volatility'],
        "amplitude": e5['amplitude_today'],
        "active_buy_ratio": 0.55, "super_large_net": 0, "inst_vs_retail": 1.0,
        "topic": topic_name, "topic_rank": topic_rank,
        "is_limit_up": False, "lianban_days": 0,
        "E5_position_pct": e5['band_position_pct'],
        "vol_ratio": e5['vol_ratio_vs_20d'],
        "sentiment": sentiment,
    }
    
    game = game_analyze(input_data, klines)
    
    # 决策矩阵
    final_score = game["final_score"]
    direction = game["direction"]
    ceiling = e5["ceiling"]
    sell_tendency = game["sell_tendency"]
    
    if game.get("veto_reason"):
        decision = "立即清仓"
        reason = f"一票否决: {game['veto_reason']}"
    elif final_score >= 70 and direction == "up" and ceiling >= 0.02:
        decision = "加仓"
        reason = f"高分({final_score:.0f})+上涨+天花板{ceiling*100:.0f}% → 追加当前持仓×30%"
    elif final_score >= 70 and direction == "up":
        decision = "持有"
        reason = f"高分({final_score:.0f})+上涨但天花板不足({ceiling*100:.0f}%) → 持有不动"
    elif 50 <= final_score < 70 and direction == "flat":
        decision = "持有或做T"
        reason = f"中等({final_score:.0f})+震荡 → 持有为主，条件满足可做T"
    elif 50 <= final_score < 70 and direction == "down":
        decision = "减仓50%"
        reason = f"中等({final_score:.0f})+下跌 → 减仓一半观望"
    elif final_score < 50 and direction == "down":
        decision = "清仓"
        reason = f"低分({final_score:.0f})+下跌 → 清仓离场"
    elif final_score < 50 and direction == "flat":
        decision = "减仓70%"
        reason = f"低分({final_score:.0f})+震荡 → 大幅减仓"
    else:
        decision = "持有观察"
        reason = f"评分{final_score:.0f}，方向不明 → 观望"
    
    # ===== 第四层: T0 + P3 (仅在"持有"且G0≥7时) =====
    t0_result = None
    p3_result = None
    
    g0_score = g0["g0_score"]
    if decision in ("持有", "持有或做T") and g0_score >= 7:
        t0 = t0_check(
            g0_score=g0_score, game_score=final_score,
            big_order_positive=input_data["main_amount"] > 0,
            amplitude=e5["amplitude_today"],
            topic_strength_score=g0["topic_strength"],
        )
        if t0["triggered"]:
            t0_result = t0
            # P3
            prob = p3_probability(
                topic_momentum=g0_score/10,
                capital_flow=0.7 if input_data["main_amount"] > 0 else 0.3,
                relative_strength=0.75, position_safety=min(0.9, e5["amplitude_today"]/15),
                volume_confirmation=min(1.0, e5["vol_ratio_vs_20d"]/2),
            )
            kelly = p3_kelly(prob["up_prob"], prob["down_prob"])
            ceil = p3_ceiling(g0_score, final_score, e5["annual_volatility"], sentiment)
            p3_result = {"probability": prob, "kelly": kelly, "ceiling": ceil}
            t0["position_shares"] = t0_position_size(e5["amplitude_today"], hold_shares)
    
    return {
        "code": code, "price": price, "pnl_pct": round(pnl_pct, 2),
        "hold_shares": hold_shares, "cost_price": cost_price,
        "decision": decision, "reason": reason,
        "pipeline_path": "W9→G0→六维→T0/P3",
        "g0": {"score": g0_score, "position": g0["stock_position"], "topic_strength": g0["topic_strength"]},
        "e5": {k: e5[k] for k in ['level','level_code','ceiling','volatility','rsi','band_position_pct','vol_mult']},
        "game": {
            "final_score": final_score, "signal": game["signal"], "direction": direction,
            "position_pct": game["position_pct"], "sell_tendency": sell_tendency,
            "risk_level": game["risk_level"], "action": game["action"],
            "veto": game.get("veto_reason") is not None,
        },
        "t0": t0_result,
        "p3": p3_result,
    }


def main():
    parser = argparse.ArgumentParser(description="W5 持仓管理流水线 (开源版)")
    parser.add_argument("--code", help="单只股票代码")
    parser.add_argument("--batch", help="批量持仓JSON文件")
    parser.add_argument("--hold-shares", type=int, default=0, help="持仓股数")
    parser.add_argument("--cost", type=float, default=0, help="成本价")
    parser.add_argument("--topic", default="自动分析")
    parser.add_argument("--topic-rank", type=int, default=5)
    parser.add_argument("--sentiment", default="中性")
    parser.add_argument("--ddx-5d", type=float, default=0.3)
    parser.add_argument("--ddx-10d", type=float, default=0.1)
    parser.add_argument("--execute", action="store_true", help="自动执行交易(买入/卖出)")
    parser.add_argument("-o", "--output", help="输出文件")
    args = parser.parse_args()
    
    results = []
    
    if args.code:
        r = analyze_single_holding(
            code=args.code, hold_shares=args.hold_shares, cost_price=args.cost,
            topic_name=args.topic, topic_rank=args.topic_rank, sentiment=args.sentiment,
            ddx_5d=args.ddx_5d, ddx_10d=args.ddx_10d,
        )
        results.append(r)
    
    elif args.batch:
        with open(args.batch) as f:
            holdings = json.load(f)
        if isinstance(holdings, dict):
            holdings = holdings.get("holdings", [holdings])
        for h in holdings:
            r = analyze_single_holding(
                code=h.get("code",""), hold_shares=h.get("shares",0), cost_price=h.get("cost",0),
                topic_name=h.get("topic","自动分析"), sentiment=args.sentiment,
            )
            results.append(r)
            print(f"  {r['code']}: {r['decision']} ({r['reason'][:50]}...)", file=sys.stderr)
    
    if not results:
        print("用法: --code CODE 或 --batch holdings.json", file=sys.stderr)
        sys.exit(1)
    
    # ===== 自动交易模式 =====
    if args.execute:
        from data_sources.trade_executor import TradeExecutor
        t = TradeExecutor()
        pos = t.get_position()
        
        for r in results:
            decision = r["decision"]
            code = r["code"]
            price = r.get("price", 0)
            
            if decision == "加仓":
                # 追加当前持仓30%
                current = next((h for h in pos["holdings"] if h["code"] == code), None)
                add_qty = int(current["shares"] * 0.3 / 100) * 100 if current else 0
                if add_qty >= 100:
                    result = t.buy(code, add_qty, None)
                    print(f"  🔄 {code}: 加仓 {add_qty}股 {'✅' if result.get('code') in ('0','200') else '❌'}", file=sys.stderr)
            
            elif decision == "清仓":
                current = next((h for h in pos["holdings"] if h["code"] == code), None)
                if current:
                    result = t.sell(code, current["shares"], None)
                    print(f"  🔄 {code}: 清仓 {current['shares']}股 {'✅' if result.get('code') in ('0','200') else '❌'}", file=sys.stderr)
            
            elif decision.startswith("减仓"):
                current = next((h for h in pos["holdings"] if h["code"] == code), None)
                if current:
                    ratio = 0.5 if "50" in decision else 0.7
                    sell_qty = int(current["shares"] * ratio / 100) * 100
                    if sell_qty >= 100:
                        result = t.sell(code, sell_qty, None)
                        print(f"  🔄 {code}: 减仓 {sell_qty}股 {'✅' if result.get('code') in ('0','200') else '❌'}", file=sys.stderr)
            
            elif decision == "持有或做T" and r.get("t0", {}).get("triggered"):
                t0 = r["t0"]
                if t0.get("direction") == "正T":
                    t_qty = t0.get("position_shares", 0)
                    if t_qty >= 100:
                        t.buy(code, t_qty, None)
                        print(f"  🔄 {code}: T0正T买入 {t_qty}股", file=sys.stderr)
    
    output = json.dumps(results if len(results) > 1 else results[0], ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
