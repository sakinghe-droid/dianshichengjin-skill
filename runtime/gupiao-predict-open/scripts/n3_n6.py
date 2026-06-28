#!/usr/bin/env python3
"""
n3_n6.py — N3 持仓体检(批量) + N6 北向资金

用法:
    python scripts/n3_n6.py --mode holdings  # 批量E5扫描
    python scripts/n3_n6.py --mode northbound  # 北向资金
"""

import sys, os, json, argparse, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OPEN_SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def batch_position_check(holdings_file: str = None) -> dict:
    """N3: 批量持仓E5扫描"""
    if holdings_file:
        with open(holdings_file) as f:
            holdings = json.load(f)
        if isinstance(holdings, dict):
            holdings = holdings.get("holdings", [holdings])
    else:
        # 从 mx-moni 获取持仓
        from data_sources.trade_executor import TradeExecutor
        t = TradeExecutor()
        pos = t.get_position()
        holdings = pos.get("holdings", [])
    
    if not holdings:
        return {"error": "无持仓数据"}
    
    from core.math_utils import e5_full_analysis
    
    results = []
    for h in holdings:
        code = h.get("code", "")
        try:
            r = subprocess.run([sys.executable, f"{OPEN_SCRIPTS}/data_fallback.py",
                "--mode","kline","--code",code,"--count","60"],
                capture_output=True, text=True, timeout=15)
            klines = json.loads(r.stdout)
            price = klines[-1]['close'] if klines else 0
            e5 = e5_full_analysis(klines, price)
            
            results.append({
                "code": code, "name": h.get("name",""),
                "shares": h.get("shares",0),
                "price": price,
                "e5_level": e5["level"],
                "ceiling": e5["ceiling"],
                "volatility": e5["volatility"],
                "rsi": round(e5["rsi"],1),
                "risk": "⚠️" if e5["level_code"] >= 3 else ("✅" if e5["level_code"] <= 1 else "—"),
            })
        except Exception as e:
            results.append({"code": code, "name": h.get("name",""), "error": str(e)})
    
    return {"holdings": results, "total": len(results)}


def northbound_query() -> dict:
    """N6: 北向资金查询 (通过TDX MCP)"""
    from data_sources.tdx_mcp import TDXClient
    tdx = TDXClient()
    
    # 查询北向资金
    result = tdx.query("北向资金今日净买入", size=5)
    
    return {
        "source": "TDX MCP",
        "data": result.get("data", [])[:5] if result else [],
    }


def main():
    p = argparse.ArgumentParser(description="N3/N6 工具")
    p.add_argument("--mode", choices=["holdings","northbound"], default="holdings")
    p.add_argument("--file", help="持仓JSON文件(可选,默认从mx-moni读取)")
    p.add_argument("-o", "--output", help="输出文件")
    args = p.parse_args()
    
    if args.mode == "holdings":
        result = batch_position_check(args.file)
    else:
        result = northbound_query()
    
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
