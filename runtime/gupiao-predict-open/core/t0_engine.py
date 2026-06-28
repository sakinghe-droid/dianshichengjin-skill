"""
t0_engine.py — T0 做T引擎

触发条件: G0≥7 + 博弈≥70 + 大单>0 + 振幅>4% + 非退潮期
做T方向: 正T(先买后卖) / 反T(先卖后买)

用法:
    from core.t0_engine import t0_check, t0_execute
    result = t0_check(g0_score=8, game_score=75, big_order_positive=True, amplitude=6.5, ...)
"""

from typing import Dict, Optional, Tuple


def t0_check(
    g0_score: float = 0,
    game_score: float = 0,
    big_order_positive: bool = True,
    amplitude: float = 0,
    topic_strength_score: float = 0,
    is_recession: bool = False,
) -> Dict:
    """
    T0 做T触发条件检查
    
    Returns:
        {"triggered": bool, "reason": str, "direction": str, ...}
    """
    conditions = []
    
    # ① G0 ≥ 7
    c1 = g0_score >= 7
    conditions.append(("G0≥7", c1, f"G0={g0_score}"))
    
    # ② 博弈评分 ≥ 70
    c2 = game_score >= 70
    conditions.append(("博弈≥70", c2, f"博弈={game_score}"))
    
    # ③ 大单净额 > 0
    c3 = big_order_positive
    conditions.append(("大单>0", c3, "大单净买入" if c3 else "大单净卖出"))
    
    # ④ 振幅 > 4%
    c4 = amplitude > 4.0
    conditions.append(("振幅>4%", c4, f"振幅={amplitude:.1f}%"))
    
    # ⑤ 非退潮期
    c5 = not is_recession
    conditions.append(("非退潮期", c5, "退潮期" if is_recession else "正常"))
    
    all_met = all(c[1] for c in conditions)
    failed = [c for c in conditions if not c[1]]
    
    if not all_met:
        return {
            "triggered": False,
            "reason": f"条件不满足: {', '.join(c[0] for c in failed)}",
            "direction": "hold",
            "buy_zone": None,
            "sell_zone": None,
            "stop_loss": None,
            "conditions": [{"name": c[0], "met": c[1], "detail": c[2]} for c in conditions],
        }
    
    # 方向判定
    if topic_strength_score >= 7 and big_order_positive:
        direction = "正T"  # 先买后卖
    elif topic_strength_score >= 7 and not big_order_positive:
        direction = "反T"  # 先卖后买
    elif not big_order_positive:
        direction = "反T"
    else:
        direction = "正T"
    
    return {
        "triggered": True,
        "reason": "全部条件满足",
        "direction": direction,
        "buy_zone": None,   # 需行情数据计算
        "sell_zone": None,  # 需行情数据计算
        "stop_loss": None,
        "conditions": [{"name": c[0], "met": c[1], "detail": c[2]} for c in conditions],
    }


def t0_calculate_zones(
    open_price: float,
    avg_price: float,
    ma30_price: float,
    high_price: float,
    current_price: float,
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """
    计算买卖区间
    
    支撑 = max(开盘价, 均价, 30分钟均线) × 0.995
    压力 = max(最高价, 当前价×1.03)
    买入区间 = [支撑, 支撑×1.005]
    卖出区间 = [压力×0.995, 压力]
    """
    support = max(open_price, avg_price, ma30_price) * 0.995
    resistance = max(high_price, current_price * 1.03)
    
    buy_zone = (round(support, 2), round(support * 1.005, 2))
    sell_zone = (round(resistance * 0.995, 2), round(resistance, 2))
    
    return buy_zone, sell_zone


def t0_position_size(amplitude: float, base_shares: int) -> int:
    """
    做T仓位计算
    
    T系数 = min(振幅/10%, 0.5)
    振幅<3% → 0 / 3-6% → 0.3 / 6-10% → 0.5 / >10% → 0.7
    做T股数 = 底仓 × T系数（取整百股）
    """
    if amplitude < 3:
        t_coeff = 0
    elif amplitude <= 6:
        t_coeff = 0.3
    elif amplitude <= 10:
        t_coeff = 0.5
    else:
        t_coeff = 0.7
    
    shares = int(base_shares * t_coeff / 100) * 100  # 取整百股
    return shares
