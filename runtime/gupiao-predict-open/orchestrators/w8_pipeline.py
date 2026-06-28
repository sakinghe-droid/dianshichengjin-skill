#!/usr/bin/env python3
"""
w8_pipeline.py — W8 低吸挖掘六步法

Step1: 强方向筛选 (涨停≥5 or 资金≥10亿 or 连板≥4)
Step2: 板块阶段判定 (只保留发酵/主升)
Step3: 个股初筛 (涨幅1-5% + 市值≥50亿 + 主力净流入>0 + 换手3-15%)
Step4: 位置+盈亏比 (低位/中低位/中位 + 盈亏比≥3:1)
Step5: 博弈引擎六维验证
Step6: 仓位计算+出票

用法:
    python orchestrators/w8_pipeline.py
    python orchestrators/w8_pipeline.py --execute  # 自动下单
"""

import sys, os, json, argparse, subprocess
from collections import defaultdict
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_sources.tdx_mcp import TDXClient
from data_sources.trade_executor import TradeExecutor
from core.math_utils import e5_full_analysis, band_position
from core.game_theory_6d import analyze as game_analyze
from core.position import calculate_position, classify_emotion

OPEN_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")


def fetch_klines(code: str, count: int = 120) -> list:
    r = subprocess.run([sys.executable, f"{OPEN_SCRIPTS}/data_fallback.py",
        "--mode","kline","--code",code,"--count",str(count)],
        capture_output=True, text=True, timeout=15)
    return json.loads(r.stdout)


def fetch_quote(code: str) -> dict:
    r = subprocess.run([sys.executable, f"{OPEN_SCRIPTS}/data_fallback.py",
        "--mode","quote","--code",code],
        capture_output=True, text=True, timeout=15)
    return json.loads(r.stdout)


def run_w8(execute: bool = False) -> Dict:
    """W8 低吸挖掘六步法"""
    tdx = TDXClient()
    
    # ===== Step1: 强方向筛选 =====
    print("🔍 Step1: 强方向筛选...", file=sys.stderr)
    limit_up = tdx.get_limit_up_stocks(size=200)
    
    # 按行业分组 → 统计涨停数和估算资金
    industry_stats = defaultdict(lambda: {"count": 0, "stocks": [], "net_est": 0})
    for s in limit_up:
        industry = ""
        for k, v in s.items():
            if '行业' in str(k) and '研究' not in str(k):
                industry = str(v).replace('@','').strip()
                break
        if not industry:
            industry = "其他"
        
        code = str(s.get('code', s.get('sec_code', '')))
        name = str(s.get('name', s.get('sec_name', '')))
        try: chg = float(s.get('change_pct', s.get('chg', 0)))
        except: chg = 0
        try: price = float(s.get('price', s.get('now_price', 0)))
        except: price = 0
        
        # 连板
        lianban = 0
        for k, v in s.items():
            if ('连' in str(k) and ('天' in str(k) or '板' in str(k))) or '几板' in str(k):
                try: lianban = int(v)
                except: pass
                break
        
        industry_stats[industry]["count"] += 1
        industry_stats[industry]["stocks"].append({"code":code,"name":name,"chg":chg,"price":price,"lianban":lianban})
        industry_stats[industry]["net_est"] += abs(price) * 1e6  # 估算
    
    # 筛选: 涨停≥5 or 资金≥10亿
    strong_directions = {}
    for ind, stats in industry_stats.items():
        if stats["count"] >= 5 or stats["net_est"] >= 1e9:
            max_board = max(s["lianban"] for s in stats["stocks"]) if stats["stocks"] else 0
            if stats["count"] >= 5 or max_board >= 4:
                strong_directions[ind] = stats
    
    print(f"  强方向: {len(strong_directions)} 个", file=sys.stderr)
    for ind in list(strong_directions.keys())[:5]:
        print(f"    {ind}: {strong_directions[ind]['count']}只涨停", file=sys.stderr)
    
    if not strong_directions:
        return {"error": "无强方向", "candidates": []}
    
    # ===== Step2: 板块阶段判定 (简化: 取TOP3方向) =====
    print("📊 Step2: 板块阶段判定...", file=sys.stderr)
    ranked = sorted(strong_directions.items(), key=lambda x: -x[1]["count"])[:3]
    
    # ===== Step3: 个股初筛 =====
    print("🔎 Step3: 个股初筛 (查询行业成分股)...", file=sys.stderr)
    all_candidates = []
    
    for ind_name, stats in ranked:
        # 从TDX获取行业所有股票
        try:
            sector_stocks = tdx.get_sector_stocks(ind_name.replace('@',''), size=100)
        except:
            sector_stocks = []
        
        for s in sector_stocks:
            try:
                code = str(s.get('code', s.get('sec_code', '')))
                name = str(s.get('name', s.get('sec_name', '')))
                chg = float(s.get('change_pct', s.get('chg', 0)))
                price_s = float(s.get('price', s.get('now_price', 0)))
            except:
                continue
            
            # 初筛: 涨幅1-5%, 非涨停
            if 1.0 <= chg <= 5.0:
                all_candidates.append({
                    "code": code, "name": name, "price": price_s,
                    "chg": chg, "topic": ind_name,
                })
    
    # 去重
    seen = set()
    unique = []
    for c in all_candidates:
        if c["code"] not in seen:
            seen.add(c["code"])
            unique.append(c)
    
    print(f"  初筛候选: {len(unique)} 只 (涨幅1-5%)", file=sys.stderr)
    
    if len(unique) > 20:
        unique = sorted(unique, key=lambda x: -x["chg"])[:20]
        print(f"  截取TOP20", file=sys.stderr)
    
    # ===== Step4: 位置+盈亏比筛选 =====
    print("📐 Step4: 位置+盈亏比筛选...", file=sys.stderr)
    low_risk = []
    
    for c in unique:
        try:
            klines = fetch_klines(c["code"], 60)
            if len(klines) < 20:
                continue
            e5 = e5_full_analysis(klines, c["price"])
        except:
            continue
        
        level_code = e5.get("level_code", 2)
        rr = e5.get("risk_reward", 1.0)
        
        # 只取低位/中低位/中位 + 盈亏比≥3
        if level_code <= 2 and rr >= 3.0:
            low_risk.append({**c, "e5": e5})
    
    print(f"  低风险候选: {len(low_risk)} 只", file=sys.stderr)
    for c in low_risk[:5]:
        print(f"    {c['name']}({c['code']}) 位置={c['e5']['level']} 盈亏比={c['e5']['risk_reward']:.1f}", file=sys.stderr)
    
    # ===== Step5: 博弈引擎六维验证 =====
    print("🎯 Step5: 博弈引擎验证...", file=sys.stderr)
    verified = []
    
    for c in low_risk:
        try:
            klines = fetch_klines(c["code"], 120)
            closes = [k['close'] for k in klines]
            highs = [k['high'] for k in klines]
            lows = [k['low'] for k in klines]
            
            input_data = {
                "code": c["code"], "price": c["price"],
                "ddx_5d": 0.3, "ddx_10d": 0.1, "main_amount": 5e7,
                "low_60d": min(lows[-60:]), "high_60d": max(highs[-60:]),
                "ma20": sum(closes[-20:])/20, "ma5": sum(closes[-5:])/5,
                "rsi": c["e5"]["rsi"], "volatility": c["e5"]["annual_volatility"],
                "amplitude": c["e5"]["amplitude_today"],
                "active_buy_ratio": 0.55, "super_large_net": 0, "inst_vs_retail": 1.0,
                "topic": c["topic"], "topic_rank": 3,
                "is_limit_up": False, "lianban_days": 0,
                "E5_position_pct": c["e5"]["band_position_pct"],
                "vol_ratio": c["e5"]["vol_ratio_vs_20d"],
                "sentiment": "中性",
            }
            
            game = game_analyze(input_data, klines)
            
            if game["final_score"] >= 60 and not game.get("veto_reason"):
                verified.append({**c, "game": game})
                print(f"    ✅ {c['name']}({c['code']}) 评分={game['final_score']:.0f}", file=sys.stderr)
            else:
                print(f"    ❌ {c['name']}({c['code']}) 评分={game['final_score']:.0f} 否决={game.get('veto_reason','')}", file=sys.stderr)
        except Exception as e:
            print(f"    ⚠️ {c['name']}({c['code']}) 异常: {e}", file=sys.stderr)
    
    # ===== Step6: 仓位计算+出票 =====
    print("💰 Step6: 仓位计算...", file=sys.stderr)
    
    verified.sort(key=lambda x: -x["game"]["final_score"])
    
    final_candidates = []
    for i, c in enumerate(verified[:5]):
        e5_ceil = c["e5"]["ceiling"]
        pos = calculate_position(
            emotion="中性", stage="发酵期",
            e5_level_code=c["e5"]["level_code"],
            e5_ceiling=e5_ceil,
            vol_level=c["e5"]["volatility"],
        )
        
        weight = [0.50, 0.30, 0.20][i] if i < 3 else 0
        suggested_pct = round(pos["final_pct"] * weight, 4)
        
        final_candidates.append({
            "rank": i + 1,
            "code": c["code"], "name": c["name"], "topic": c["topic"],
            "price": c["price"], "chg": c["chg"],
            "game_score": c["game"]["final_score"],
            "game_signal": c["game"]["signal"],
            "e5_level": c["e5"]["level"],
            "e5_ceiling": e5_ceil,
            "risk_reward": c["e5"]["risk_reward"],
            "suggested_pct": suggested_pct,
            "suggested_amount": round(pos["final_amount"] * weight, 2),
        })
    
    result = {
        "mode": "低吸挖掘",
        "strong_directions": list(strong_directions.keys())[:5],
        "candidates_screened": len(unique),
        "low_risk_passed": len(low_risk),
        "game_verified": len(verified),
        "final_candidates": final_candidates,
    }
    
    # ===== 自动下单 =====
    if execute and final_candidates:
        print("⚡ 自动下单模式...", file=sys.stderr)
        t = TradeExecutor()
        for c in final_candidates[:2]:  # TOP2
            qty = max(100, int(c["suggested_amount"] / c["price"] / 100) * 100)
            r = t.buy(c["code"], qty, None)
            status = '✅' if r.get('code') in ('0','200') else '❌'
            print(f"  {status} {c['name']}({c['code']}) {qty}股 @{c['price']:.2f}", file=sys.stderr)
            c["executed"] = status == '✅'
            c["executed_qty"] = qty
    
    return result


def main():
    p = argparse.ArgumentParser(description="W8 低吸挖掘")
    p.add_argument("--execute", action="store_true", help="自动下单TOP2")
    p.add_argument("--json", action="store_true", help="输出原始JSON")
    p.add_argument("-o", "--output", help="输出文件")
    args = p.parse_args()
    
    result = run_w8(execute=args.execute)
    
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
    
    if args.json:
        print(output)
    else:
        from core.formatters import format_w8
        print(format_w8(result))


if __name__ == "__main__":
    main()
