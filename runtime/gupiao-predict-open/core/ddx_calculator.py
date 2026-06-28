"""
ddx_calculator.py — DDX自计算引擎

DDX = (大单买入量 - 大单卖出量) / 流通股本 × 100

支持额基近似（mx-data 替补方案）和量基计算（逐笔成交）。

用法:
    from core.ddx_calculator import calculate_ddx_from_amount, calculate_ddx_from_trades
"""

from typing import Dict, List, Optional


def calculate_ddx_from_amount(
    main_net_inflow: float,
    float_shares: float,
    current_price: float,
) -> Dict:
    """
    额基 DDX 近似计算（妙想 mx-data 替补方案）
    
    DDX ≈ 主力净流入 / (流通股本 × 现价) × 10000
    
    Args:
        main_net_inflow: 主力净流入金额（元）
        float_shares: 流通股本（股）
        current_price: 当前价格
    
    Returns:
        {"ddx": float, "method": "amount_based", ...}
    """
    if float_shares <= 0 or current_price <= 0:
        return {"error": "流通股本或现价无效", "ddx": 0}
    
    float_market_cap = float_shares * current_price
    ddx = main_net_inflow / float_market_cap * 10000
    
    return {
        "ddx": round(ddx, 4),
        "method": "amount_based",
        "formula": f"DDX = {main_net_inflow:.0f} / ({float_shares:.0f} × {current_price:.2f}) × 10000",
        "main_net_inflow": main_net_inflow,
        "float_market_cap": float_market_cap,
    }


def calculate_ddx_from_trades(
    trades: List[Dict],
    float_shares: float,
    threshold_hands: int = 500,
) -> Dict:
    """
    量基 DDX 计算（逐笔成交过滤）
    
    DDX = (大单买入量 - 大单卖出量) / 流通股本 × 100
    
    Args:
        trades: 逐笔成交 [{"volume": 手, "type": "买入"/"卖出"}, ...]
        float_shares: 流通股本（股）
        threshold_hands: 大单阈值（手）
    
    Returns:
        {"ddx": float, "method": "volume_based", "big_buy": float, "big_sell": float}
    """
    big_buy = 0.0
    big_sell = 0.0
    
    for t in trades:
        vol = t.get("volume", 0)
        if vol < threshold_hands:
            continue
        
        if t.get("type") in ("买入", "buy", "B"):
            big_buy += vol
        else:
            big_sell += vol
    
    # 转换: 手 → 股 (1手=100股)
    big_buy_shares = big_buy * 100
    big_sell_shares = big_sell * 100
    
    if float_shares > 0:
        ddx = (big_buy_shares - big_sell_shares) / float_shares * 100
    else:
        ddx = 0
    
    return {
        "ddx": round(ddx, 4),
        "method": "volume_based",
        "big_buy_hands": big_buy,
        "big_sell_hands": big_sell,
        "big_buy_shares": big_buy_shares,
        "big_sell_shares": big_sell_shares,
        "net_shares": big_buy_shares - big_sell_shares,
        "threshold_hands": threshold_hands,
        "float_shares": float_shares,
        "total_trades": len(trades),
        "big_trades": sum(1 for t in trades if t.get("volume", 0) >= threshold_hands),
    }


def calculate_multi_day_ddx(ddx_series: List[float]) -> Dict:
    """
    多日 DDX 趋势分析
    
    Args:
        ddx_series: DDX时间序列（按日期升序，最近的在最后）
    
    Returns:
        {"ddx_5d": float, "ddx_10d": float, "trend": str, "veto_5d": bool, "veto_10d": bool}
    """
    if not ddx_series:
        return {"ddx_5d": 0, "ddx_10d": 0, "trend": "neutral", "veto_5d": False, "veto_10d": False}
    
    ddx_5d = sum(ddx_series[-5:]) / min(5, len(ddx_series))
    ddx_10d = sum(ddx_series[-10:]) / min(10, len(ddx_series))
    
    # 趋势判定
    recent_5 = ddx_series[-5:] if len(ddx_series) >= 5 else ddx_series
    if all(d > 0 for d in recent_5) and ddx_5d > 0.5:
        trend = "strong_inflow"
    elif ddx_5d > 0.2:
        trend = "mild_inflow"
    elif ddx_5d >= -0.2:
        trend = "neutral"
    elif ddx_5d > -0.5:
        trend = "mild_outflow"
    else:
        trend = "strong_outflow"
    
    # 一票否决
    veto_5d = ddx_5d < -1
    veto_10d = ddx_10d < -3
    
    return {
        "ddx_5d": round(ddx_5d, 4),
        "ddx_10d": round(ddx_10d, 4),
        "trend": trend,
        "veto_5d": veto_5d,
        "veto_10d": veto_10d,
        "veto": veto_5d or veto_10d,
        "veto_reason": "5日DDX<-1" if veto_5d else ("10日DDX<-3" if veto_10d else None),
        "series_length": len(ddx_series),
    }
