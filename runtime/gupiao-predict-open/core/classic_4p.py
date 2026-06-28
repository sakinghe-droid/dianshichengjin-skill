"""
classic_4p.py — 经典版四视角博弈引擎

Z 庄家视角 (30%) / Y 游资视角 (25%) / Q 量化专家 (25%) / M 数学家 (20%)

输出: 综合评分 + 四视角明细 + 走势预判（方向/高度/天数/置信度）

用法:
    from core.classic_4p import classic_analyze
    result = classic_analyze(data)
"""

from typing import Dict, Optional


# ============================================================
# Z: 庄家视角 (30%)
# ============================================================

def z_score(data: Dict) -> Dict:
    """
    庄家视角评分 (满分30分)
    
    主力净流入趋势(10) + 大单占比(8) + DDX强度(6) + DDZ强度(6)
    """
    ddx_5d = data.get("ddx_5d", 0)
    main_amount = data.get("main_amount", 0)
    active_buy_ratio = data.get("active_buy_ratio", 0.5)
    
    # 主力净流入趋势 (0-10)
    if main_amount > 200000000:  # >2亿
        s1 = 10
    elif main_amount > 100000000:
        s1 = 7
    elif main_amount > 0:
        s1 = 4
    else:
        s1 = 0
    
    # 大单占比 (0-8)
    if active_buy_ratio > 0.40:
        s2 = 8
    elif active_buy_ratio > 0.25:
        s2 = 5
    elif active_buy_ratio > 0.15:
        s2 = 3
    else:
        s2 = 0
    
    # DDX强度 (0-6)
    if ddx_5d > 1.0:
        s3 = 6
    elif ddx_5d > 0.5:
        s3 = 4
    elif ddx_5d > 0.2:
        s3 = 2
    else:
        s3 = 0
    
    # DDZ强度 (0-6)  — 用 inst_vs_retail 近似
    inst = data.get("inst_vs_retail", 1.0)
    if inst > 2.0:
        s4 = 6
    elif inst > 1.5:
        s4 = 4
    elif inst > 1.0:
        s4 = 2
    else:
        s4 = 0
    
    total = s1 + s2 + s3 + s4  # 满分30
    
    # 行为分类
    if ddx_5d < -1 or (ddx_5d < 0 and main_amount < 0):
        stage = "出货期"
        signal = "sell"
    elif ddx_5d > 1.0 and main_amount > 50000000:
        stage = "拉升期"
        signal = "buy"
    elif ddx_5d > 0.5 and main_amount > 0:
        stage = "建仓期"
        signal = "buy"
    elif ddx_5d > 0 and main_amount >= 0:
        stage = "建仓期"
        signal = "hold"
    else:
        stage = "观望期"
        signal = "hold"
    
    return {
        "score": total,
        "score_normalized": round(total / 30 * 100, 1),
        "signal": signal,
        "stage": stage,
        "detail": {
            "main_trend": s1, "big_order_ratio": s2,
            "ddx": s3, "ddz": s4,
        }
    }


# ============================================================
# Y: 游资视角 (25%)
# ============================================================

def y_score(data: Dict) -> Dict:
    """
    游资视角评分 (满分25分)
    
    封单强度(10) + 涨停时间(6) + 换手率健康(5) + 连板质量(4)
    """
    is_limit_up = data.get("is_limit_up", False)
    lianban_days = data.get("lianban_days", 0)
    vol_ratio = data.get("vol_ratio", 1.0)
    
    if not is_limit_up and lianban_days == 0:
        # 非涨停股，游资视角不适用
        return {
            "score": 12,  # 中性默认分
            "score_normalized": 48.0,
            "signal": "hold",
            "cycle": "无涨停",
            "detail": {"seal": 0, "time": 0, "turnover": 3, "quality": 0},
            "note": "非涨停/连板股，游资视角不适用，返回中性",
        }
    
    # 封单强度 (0-10)
    seal_strength = data.get("seal_strength", 0)
    if seal_strength > 5:
        s1 = 10
    elif seal_strength > 3:
        s1 = 7
    elif seal_strength > 1:
        s1 = 4
    else:
        s1 = 0
    
    # 涨停时间 (0-6)
    limit_up_time = data.get("limit_up_time", "")
    if "09:30" in str(limit_up_time):
        s2 = 6
    elif "10:00" in str(limit_up_time) or "09:" in str(limit_up_time):
        s2 = 4
    elif "11:00" in str(limit_up_time) or "10:" in str(limit_up_time):
        s2 = 2
    else:
        s2 = 0 if limit_up_time else 1  # 未知默认午后
    
    # 换手率健康 (0-5)
    turnover = data.get("turnover_rate", 10)
    if 5 <= turnover <= 15:
        s3 = 5
    elif 15 < turnover <= 25:
        s3 = 3
    elif turnover > 25 or turnover < 3:
        s3 = 0
    else:
        s3 = 3
    
    # 连板质量 (0-4)
    if lianban_days >= 3:
        s4 = 4
    elif lianban_days >= 2:
        s4 = 3
    elif lianban_days >= 1:
        s4 = 2
    else:
        s4 = 1
    
    total = s1 + s2 + s3 + s4  # 满分25
    
    # 情绪周期
    if lianban_days >= 4:
        cycle = "接力期"
    elif lianban_days >= 2:
        cycle = "接力期"
    elif is_limit_up:
        cycle = "点火期"
    else:
        cycle = "冰点期"
    
    if total >= 18:
        signal = "buy"
    elif total >= 12:
        signal = "hold"
    else:
        signal = "sell"
    
    return {
        "score": total,
        "score_normalized": round(total / 25 * 100, 1),
        "signal": signal,
        "cycle": cycle,
        "detail": {
            "seal_strength": s1, "limit_up_time": s2,
            "turnover_health": s3, "lianban_quality": s4,
        }
    }


# ============================================================
# Q: 量化专家视角 (25%)
# ============================================================

def q_score(data: Dict) -> Dict:
    """
    量化专家视角评分 (满分25分)
    
    _A突破概率(10) + _D尾部风险(7) + _E订单流(5) + _F主力结构(3)
    """
    volatility = data.get("volatility", 0.03)
    rsi = data.get("rsi", 50)
    vol_ratio = data.get("vol_ratio", 1.0)
    inst_vs_retail = data.get("inst_vs_retail", 1.0)
    
    # _A 突破概率 (0-10)
    bp = 0.5
    if 40 <= rsi <= 65 and 1.0 <= vol_ratio <= 2.0:
        bp = 0.75
    elif rsi < 30:
        bp = 0.55
    elif rsi > 75:
        bp = 0.30
    
    if bp > 0.7:
        s1 = 10
    elif bp > 0.5:
        s1 = 7
    elif bp > 0.3:
        s1 = 4
    else:
        s1 = 0
    
    # _D 尾部风险 (0-7)
    if volatility < 0.03:
        s2 = 7
    elif volatility < 0.05:
        s2 = 4
    else:
        s2 = 0
    
    # _E 订单流 (0-5)
    active_buy = data.get("active_buy_ratio", 0.5)
    if active_buy > 0.55:
        s3 = 5  # Up
    elif active_buy > 0.45:
        s3 = 2  # Flat
    else:
        s3 = 0  # Down
    
    # _F 主力结构 (0-3)
    if inst_vs_retail > 1.5:
        s4 = 3  # M(主力主导)
    elif inst_vs_retail > 0.8:
        s4 = 1  # B(均衡)
    else:
        s4 = 0  # R(散户主导)
    
    total = s1 + s2 + s3 + s4  # 满分25
    
    if total >= 18:
        signal = "buy"
    elif total >= 12:
        signal = "hold"
    else:
        signal = "sell"
    
    return {
        "score": total,
        "score_normalized": round(total / 25 * 100, 1),
        "signal": signal,
        "detail": {
            "break_prob": s1, "tail_risk": s2,
            "order_flow": s3, "main_structure": s4,
        }
    }


# ============================================================
# M: 数学家视角 (20%)
# ============================================================

def m_score(data: Dict) -> Dict:
    """
    数学家视角评分 (满分20分)
    
    胜率估计(8) + 盈亏比(6) + 凯利仓位(3) + 波动率惩罚(3)
    """
    volatility = data.get("volatility", 0.03)
    rsi = data.get("rsi", 50)
    
    # 胜率估计 (0-8): 基于RSI区间的历史胜率近似
    if 40 <= rsi <= 60:
        wr = 0.55
    elif 30 <= rsi <= 70:
        wr = 0.50
    elif rsi < 30:
        wr = 0.60
    else:
        wr = 0.40
    
    if wr > 0.60:
        s1 = 8
    elif wr > 0.50:
        s1 = 5
    elif wr > 0.40:
        s1 = 3
    else:
        s1 = 0
    
    # 盈亏比 (0-6)
    support = data.get("low_60d", data.get("price", 10) * 0.9)
    resistance = data.get("high_60d", data.get("price", 10) * 1.1)
    price = data.get("price", 10)
    if price > support:
        rr = (resistance - price) / (price - support)
    else:
        rr = 5
    
    if rr > 3:
        s2 = 6
    elif rr > 2:
        s2 = 4
    elif rr > 1:
        s2 = 2
    else:
        s2 = 0
    
    # 凯利仓位 (0-3): f* = (p×b - q) / b
    b = rr
    p = wr
    q = 1 - p
    if b > 0:
        kelly = max(0, (p * b - q) / b)
    else:
        kelly = 0
    
    if kelly > 0.05:
        s3 = 3
    elif kelly > 0.03:
        s3 = 2
    elif kelly > 0.01:
        s3 = 1
    else:
        s3 = 0
    
    # 波动率惩罚 (0-3): 年化<30%=3, <50%=2, <80%=1, >80%=0
    ann_vol = volatility  # 已经是年化
    if ann_vol < 0.30:
        s4 = 3
    elif ann_vol < 0.50:
        s4 = 2
    elif ann_vol < 0.80:
        s4 = 1
    else:
        s4 = 0
    
    total = s1 + s2 + s3 + s4  # 满分20
    
    if total >= 14:
        signal = "buy"
    elif total >= 9:
        signal = "hold"
    else:
        signal = "sell"
    
    return {
        "score": total,
        "score_normalized": round(total / 20 * 100, 1),
        "signal": signal,
        "detail": {
            "win_rate_est": s1, "risk_reward": s2,
            "kelly_position": s3, "volatility_penalty": s4,
        },
        "kelly_fraction": round(kelly, 3),
    }


# ============================================================
# 综合
# ============================================================

def classic_analyze(data: Dict) -> Dict:
    """
    经典四视角综合评分
    
    权重: Z×0.30 + Y×0.25 + Q×0.25 + M×0.20
    
    Args:
        data: 同 game_theory_engine 输入格式
    
    Returns:
        四视角明细 + 综合评分 + 走势预判
    """
    z = z_score(data)
    y = y_score(data)
    q = q_score(data)
    m = m_score(data)
    
    # 加权总分
    total = (
        z["score_normalized"] * 0.30 +
        y["score_normalized"] * 0.25 +
        q["score_normalized"] * 0.25 +
        m["score_normalized"] * 0.20
    )
    
    # 走势预判
    if total >= 85:
        forecast = {"direction": "强势上涨", "height_pct": [15, 30], "days": [3, 5], "confidence": 0.85}
    elif total >= 70:
        forecast = {"direction": "温和上涨", "height_pct": [8, 15], "days": [2, 3], "confidence": 0.75}
    elif total >= 55:
        forecast = {"direction": "震荡偏多", "height_pct": [3, 8], "days": [1, 2], "confidence": 0.60}
    elif total >= 40:
        forecast = {"direction": "震荡", "height_pct": [-3, 3], "days": [1, 1], "confidence": 0.40}
    elif total >= 25:
        forecast = {"direction": "震荡偏空", "height_pct": [-3, -8], "days": [1, 2], "confidence": 0.55}
    else:
        forecast = {"direction": "下跌", "height_pct": [-15, -8], "days": [2, 3], "confidence": 0.70}
    
    # 共识度判定
    directions = [z["signal"], y["signal"], q["signal"], m["signal"]]
    buys = directions.count("buy")
    sells = directions.count("sell")
    
    if buys == 4:
        consensus = "四视角一致看多 — 强共识"
    elif buys == 3:
        consensus = "三多一中性 — 偏多共识"
    elif sells == 4:
        consensus = "四视角一致看空 — 强看空"
    elif sells == 3:
        consensus = "三空一中性 — 偏空共识"
    elif buys >= 2 and sells >= 2:
        consensus = "两多两空 — 分歧"
    else:
        consensus = "信号混合 — 中性"
    
    return {
        "total_score": round(total, 1),
        "signal": "buy" if total >= 70 else ("hold" if total >= 40 else "sell"),
        "consensus": consensus,
        "forecast": forecast,
        "perspectives": {
            "Z": z, "Y": y, "Q": q, "M": m,
        }
    }
