"""
p3_position.py — P3 概率仓位管理器

五维概率计算 → 凯利仓位 → 仓位天花板

用法:
    from core.p3_position import p3_probability, p3_kelly, p3_ceiling
"""

from typing import Dict


# ============================================================
# 五维概率
# ============================================================

def p3_probability(
    topic_momentum: float = 0.5,
    capital_flow: float = 0.5,
    relative_strength: float = 0.5,
    position_safety: float = 0.5,
    volume_confirmation: float = 0.5,
) -> Dict:
    """
    五维概率计算
    
    维度权重:
        题材动量 30% + 资金流向 25% + 相对强度 20% + 位置安全 15% + 量能确认 10%
    
    Args:
        topic_momentum: 题材动量 (G0评分归一化到0-1)
        capital_flow: 资金流向 (大单净额方向+强度, 0-1)
        relative_strength: 相对强度 (leader=1.0, core=0.75, follower=0.45, edge=0.2)
        position_safety: 位置安全 (振幅空间: >10%=0.9, 6-10%=0.75, 4-6%=0.6)
        volume_confirmation: 量能确认 (量比: >2=1.0, 1.5-2=0.8, 1-1.5=0.6)
    
    Returns:
        总概率 + 各维度明细
    """
    weights = {
        "topic_momentum": 0.30,
        "capital_flow": 0.25,
        "relative_strength": 0.20,
        "position_safety": 0.15,
        "volume_confirmation": 0.10,
    }
    
    dims = {
        "topic_momentum": topic_momentum,
        "capital_flow": capital_flow,
        "relative_strength": relative_strength,
        "position_safety": position_safety,
        "volume_confirmation": volume_confirmation,
    }
    
    total_prob = sum(dims[k] * weights[k] for k in weights)
    total_prob = max(0, min(1, total_prob))
    
    # 概率映射
    up = 0.25 + total_prob * 0.55   # 25%-80%
    down = 0.10 + (1 - total_prob) * 0.45  # 10%-55%
    flat = 1 - up - down
    
    # 等级
    if total_prob >= 0.8:
        level = "高概率"
    elif total_prob >= 0.6:
        level = "中等概率"
    elif total_prob >= 0.4:
        level = "低概率"
    else:
        level = "极低概率"
    
    return {
        "total_prob": round(total_prob, 3),
        "up_prob": round(up, 3),
        "down_prob": round(down, 3),
        "flat_prob": round(flat, 3),
        "level": level,
        "dimensions": {k: round(v, 3) for k, v in dims.items()},
        "weighted_dims": {k: round(v * weights[k], 4) for k, v in dims.items()},
    }


# ============================================================
# 凯利仓位
# ============================================================

def p3_kelly(
    up_prob: float = 0.5,
    down_prob: float = 0.3,
    profit_loss_ratio: float = 2.5,
    base_position: float = 2.0,
) -> Dict:
    """
    凯利仓位公式
    
    f* = (p × b - q) / b
    T仓位 = min(f*, 0.5) × 底仓
    
    Args:
        up_prob: 上涨概率
        down_prob: 下跌概率
        profit_loss_ratio: 盈亏比 b (默认2.5)
        base_position: 底仓（成数）
    
    Returns:
        kelly仓位 + 半凯利
    """
    p = up_prob
    q = down_prob
    b = profit_loss_ratio
    
    if b > 0:
        kelly_f = max(0, (p * b - q) / b)
    else:
        kelly_f = 0
    
    half_kelly = kelly_f / 2
    t_position = min(kelly_f, 0.5) * base_position  # 上限50%
    
    return {
        "kelly_fraction": round(kelly_f, 4),
        "half_kelly_fraction": round(half_kelly, 4),
        "t_position_pct": round(t_position, 2),
        "t_position_capped": min(t_position, base_position * 0.5),
        "formula": f"f* = ({p:.2f}×{b:.1f} - {q:.2f}) / {b:.1f} = {kelly_f:.4f}",
    }


# ============================================================
# 仓位天花板
# ============================================================

def p3_ceiling(
    g0_score: float = 5,
    game_score: float = 70,
    volatility: float = 0.03,
    sentiment: str = "中性",
    max_position: float = 3.0,
) -> Dict:
    """
    P3 仓位天花板
    
    ceiling = base(20%) × G0系数 × 博弈系数 × 波动率系数 × 情绪系数
    
    Args:
        g0_score: G0评分 (0-10)
        game_score: 博弈综合评分 (0-100)
        volatility: 波动率 (小数，如0.03=3%)
        sentiment: 市场情绪
        max_position: 单票最大仓位（成数）
    """
    # G0系数
    if g0_score >= 8:
        g0_coeff = 1.3
    elif g0_score >= 6:
        g0_coeff = 1.1
    elif g0_score >= 4:
        g0_coeff = 1.0
    else:
        g0_coeff = 0.7
    
    # 博弈系数
    if game_score >= 85:
        game_coeff = 1.2
    elif game_score >= 70:
        game_coeff = 1.0
    elif game_score >= 60:
        game_coeff = 0.8
    else:
        game_coeff = 0.5
    
    # 波动率系数
    if volatility < 0.02:
        vol_coeff = 1.1
    elif volatility <= 0.04:
        vol_coeff = 1.0
    elif volatility <= 0.06:
        vol_coeff = 0.8
    else:
        vol_coeff = 0.5
    
    # 情绪系数
    sentiment_map = {"亢奋": 1.2, "bullish": 1.2, "积极": 1.0, "positive": 1.0,
                     "中性": 0.8, "neutral": 0.8, "谨慎": 0.5, "cautious": 0.5,
                     "恐慌": 0.0, "panic": 0.0}
    sent_coeff = sentiment_map.get(sentiment, 0.8)
    
    base = 0.20  # 20%基础
    ceiling = base * g0_coeff * game_coeff * vol_coeff * sent_coeff
    ceiling = min(ceiling, max_position)
    ceiling = max(0.005, ceiling)  # 最小0.5成
    
    return {
        "ceiling": round(ceiling, 3),
        "breakdown": {
            "base": base,
            "g0": {"score": g0_score, "coeff": g0_coeff},
            "game": {"score": game_score, "coeff": game_coeff},
            "volatility": {"value": volatility, "coeff": vol_coeff},
            "sentiment": {"label": sentiment, "coeff": sent_coeff},
        },
        "max_single_stock": max_position,
    }
