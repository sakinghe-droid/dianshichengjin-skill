#!/usr/bin/env python3
"""
review_engine.py — W6 复盘引擎

收集当日操作记录 + 工作流输出 → 生成五步复盘报告

用法:
    python orchestrators/review_engine.py --date 2026-06-26
"""

import sys, os, json, argparse
from datetime import datetime, timedelta
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_sources.trade_executor import TradeExecutor

OP_LOG_DIR = os.path.expanduser("~/.hermes/trade_logs")


def collect_weekly_data(end_date: str) -> list:
    """收集近5个交易日的历史数据 (涨停/跌停/炸板/北向/指数)"""
    from datetime import datetime, timedelta
    dt = datetime.strptime(end_date, "%Y-%m-%d")
    
    from data_sources.tdx_mcp import TDXClient
    tdx = TDXClient()
    
    daily_snapshots = []
    for i in range(5):
        d = (dt - timedelta(days=i)).strftime("%Y-%m-%d")
        data = {"date": d, "limit_up": 0, "limit_down": 0, 
                "blow_rate": 0, "northbound": 0, "index": {}}
        try:
            # 涨停/跌停
            lu = tdx.query(f"{d} A股涨停股票", size=200)
            data["limit_up"] = lu.get("total", 0)
            ld = tdx.query(f"{d} A股跌停股票", size=200)
            data["limit_down"] = ld.get("total", 0)
            
            # 炸板率: 需要当日实时数据, 历史不可用
            # 北向资金
            nb = tdx.query(f"{d} 北向资金净买入", size=1)
            for row in nb.get("data", [])[:1]:
                for h, v in zip(nb["headers"], row):
                    hs = str(h)
                    if '净买' in hs or '净额' in hs:
                        try: 
                            val = float(str(v).replace("亿","").replace("万","").strip())
                            if '万' in str(v): val /= 10000
                            data["northbound"] = round(val, 1)
                        except: pass
            
            # 上证指数
            idx = tdx.query(f"{d} 上证指数行情", size=1)
            for row in idx.get("data", [])[:1]:
                if len(row) > 5:
                    try:
                        data["index"] = {"price": float(row[4]), "chg": float(row[5])}
                    except: pass
        except:
            pass
        daily_snapshots.append(data)
    
    daily_snapshots.reverse()
    return daily_snapshots


def collect_daily_data(date: str) -> Dict:
    """收集当日所有数据"""
    t = TradeExecutor()
    
    # 1. 操作记录
    operations = t.get_daily_log(date)
    
    # 2. 当前持仓
    position = t.get_position()
    
    # 3. 委托记录
    orders = t.get_orders()
    
    # 4. 工作流输出 (尝试读取)
    workflow_outputs = {}
    for wf_name in ["W1", "W5", "W10"]:
        for path in [f"/tmp/{wf_name.lower()}_output.json",
                     f"/tmp/w1_data/mainline_result.json"]:
            if os.path.exists(path):
                try:
                    with open(path) as f:
                        workflow_outputs[wf_name] = json.load(f)
                except:
                    pass
    
    return {
        "date": date,
        "operations": operations,
        "position": position,
        "orders": orders,
        "workflow_outputs": workflow_outputs,
    }


def review_logic(operations: List[Dict], position: Dict) -> Dict:
    """出票逻辑复盘: 做对/做错/错过"""
    did_right = []
    did_wrong = []
    missed = []
    
    buys = [o for o in operations if o.get("action") == "BUY"]
    sells = [o for o in operations if o.get("action") == "SELL"]
    
    # 做对: 有买入且盈利
    for h in position.get("holdings", []):
        if h.get("pnl", 0) > 0:
            did_right.append(f"持仓 {h['name']}({h['code']}) 盈利 {h['pnl']:.2f}")
    
    # 做错: 有买入但亏损
    for h in position.get("holdings", []):
        if h.get("pnl", 0) < 0:
            did_wrong.append(f"持仓 {h['name']}({h['code']}) 亏损 {h['pnl']:.2f}")
    
    # 错过: 当日无操作
    if not buys and not sells:
        missed.append("当日无任何交易操作")
    
    if not operations:
        missed.append("无操作记录 — 可能未启用自动交易")
    
    return {
        "did_right": did_right or ["暂无数据"],
        "did_wrong": did_wrong or ["暂无数据"],
        "missed": missed or ["暂无数据"],
        "total_operations": len(operations),
        "buy_count": len(buys),
        "sell_count": len(sells),
    }


def benchmark_analysis(position: Dict) -> Dict:
    """对比基准: 当前持仓 vs 市场"""
    holdings = position.get("holdings", [])
    total_pnl = position.get("total_pnl", 0)
    total_asset = position.get("total_asset", 100000)
    
    return_rate = (total_pnl / total_asset * 100) if total_asset > 0 else 0
    
    return {
        "total_asset": total_asset,
        "total_pnl": total_pnl,
        "return_rate": round(return_rate, 2),
        "holding_count": len(holdings),
        "rating": "优秀" if return_rate > 5 else ("良好" if return_rate > 2 else ("一般" if return_rate > -2 else "需改进")),
    }


def optimization_suggestions(logic: Dict, benchmark: Dict) -> List[Dict]:
    """优化方案"""
    suggestions = []
    
    if benchmark["return_rate"] < -2:
        suggestions.append({
            "target": "仓位管理",
            "suggestion": "连续亏损，建议降低情绪系数0.1，收紧仓位上限",
            "reason": f"收益率{benchmark['return_rate']:.1f}%",
            "expected": "减少回撤幅度",
        })
    
    if logic["total_operations"] == 0:
        suggestions.append({
            "target": "交易执行",
            "suggestion": "当日无操作，检查是否启用自动交易模式",
            "reason": "0笔交易",
            "expected": "确保策略信号能执行",
        })
    
    if logic["buy_count"] > 5:
        suggestions.append({
            "target": "交易频率",
            "suggestion": "买入过于频繁(>5笔)，考虑提高买入门槛",
            "reason": f"{logic['buy_count']}笔买入",
            "expected": "减少手续费损耗",
        })
    
    return suggestions


def tomorrow_plan(position: Dict) -> Dict:
    """明日建议"""
    holdings = position.get("holdings", [])
    
    to_sell = [h for h in holdings if h.get("pnl", 0) > 500]  # 盈利>500可考虑止盈
    to_hold = [h for h in holdings if -200 < h.get("pnl", 0) <= 500]
    to_cut = [h for h in holdings if h.get("pnl", 0) <= -200]  # 亏损>200考虑止损
    
    return {
        "early_sell": [f"{h['name']}({h['code']})" for h in to_sell] or ["无"],
        "continue_hold": [f"{h['name']}({h['code']})" for h in to_hold] or ["无"],
        "cut_loss": [f"{h['name']}({h['code']})" for h in to_cut] or ["无"],
        "strategy": "轻仓" if position.get("total_pnl", 0) < 0 else "正常",
    }


def generate_report(date: str = None) -> Dict:
    """生成完整复盘报告"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    data = collect_daily_data(date)
    weekly = collect_weekly_data(date)
    logic = review_logic(data["operations"], data["position"])
    benchmark = benchmark_analysis(data["position"])
    suggestions = optimization_suggestions(logic, benchmark)
    tomorrow = tomorrow_plan(data["position"])
    
    return {
        "report_date": date,
        "generated_at": datetime.now().isoformat(),
        
        # 一、出票逻辑复盘
        "logic_review": logic,
        
        # 二、持仓表现
        "position_summary": {
            "total_asset": data["position"].get("total_asset", 0),
            "available": data["position"].get("available", 0),
            "holdings": data["position"].get("holdings", []),
        },
        
        # 三、对比基准
        "benchmark": benchmark,
        
        # 四、优化方案
        "optimization": suggestions,
        
        # 五、明日建议
        "tomorrow_plan": tomorrow,
        
        # 六、本周数据
        "weekly_snapshots": weekly,
        
        # 原始数据
        "raw": {
            "operations": data["operations"],
            "orders": data["orders"],
            "workflow_outputs": list(data.get("workflow_outputs", {}).keys()),
        },
    }


def main():
    p = argparse.ArgumentParser(description="W6 复盘引擎")
    p.add_argument("--date", help="复盘日期 YYYY-MM-DD")
    p.add_argument("-o", "--output", help="输出文件")
    args = p.parse_args()
    
    report = generate_report(args.date)
    output = json.dumps(report, ensure_ascii=False, indent=2)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"✅ 复盘报告 → {args.output}")
    else:
        # 人类可读输出
        print("=" * 50)
        print(f"📊 复盘报告 — {report['report_date']}")
        print("=" * 50)
        
        print("\n一、出票逻辑复盘")
        lr = report['logic_review']
        print(f"  总操作: {lr['total_operations']}笔 (买{lr['buy_count']}/卖{lr['sell_count']})")
        
        print("\n二、持仓表现")
        ps = report['position_summary']
        print(f"  总资产: {ps['total_asset']:.0f} | 可用: {ps['available']:.0f}")
        for h in ps['holdings']:
            print(f"  {h['name']}({h['code']}): {h['shares']}股 盈亏{h['pnl']:+.0f}")
        
        print("\n三、收益基准")
        bm = report['benchmark']
        print(f"  收益率: {bm['return_rate']:+.2f}% | 评级: {bm['rating']}")
        
        print("\n四、优化方案")
        for s in report['optimization']:
            print(f"  [{s['target']}] {s['suggestion']}")
        
        print("\n五、明日建议")
        tp = report['tomorrow_plan']
        print(f"  早盘卖出: {', '.join(tp['early_sell'])}")
        print(f"  继续持有: {', '.join(tp['continue_hold'])}")
        print(f"  止损: {', '.join(tp['cut_loss'])}")
        print(f"  策略: {tp['strategy']}")
        
        print("\n六、本周市场数据 (TDX历史回采)")
        for snap in report.get('weekly_snapshots', []):
            lu = snap.get('limit_up', 0)
            ld = snap.get('limit_down', 0)
            br = snap.get('blow_rate', 0)
            nb = snap.get('northbound', 0)
            idx = snap.get('index', {})
            bar = '🟢' if lu > 30 else ('🟡' if lu > 15 else '🔴')
            parts = [f"涨停{lu} 跌停{ld}"]
            if br: parts.append(f"炸板{br}%")
            if nb: parts.append(f"北向{nb:+.0f}亿")
            if idx: parts.append(f"上证{idx.get('price',0):.0f}({idx.get('chg',0):+.1f}%)")
            print(f"  {snap['date']}: {' | '.join(parts)} {bar}")
        print(f"\n七、下周预判")
        print(f"  (需AI综合本周数据+今日扫描生成)")


if __name__ == "__main__":
    main()
