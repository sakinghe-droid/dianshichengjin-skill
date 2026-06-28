"""
g0_scanner.py — G0 全局环境扫描器

博弈引擎第7维，权重15%（从A1-F6各匀3%）。
三维扫描: 催化检查 + 题材强度 + 个股定位 + 洗盘识别

用法:
    from core.g0_scanner import g0_scan
    result = g0_scan(code="000831", topic_name="稀土永磁", ...)
"""

from typing import Dict, List, Optional


def g0_scan(
    code: str,
    topic_name: str,
    topic_rank: int = 5,
    topic_limit_up_count: int = 0,
    topic_net_amount: float = 0,
    topic_rank_change: int = 0,
    stock_rank_in_topic: int = 5,
    stock_capital_rank: int = 5,
    core_stock_performing: bool = False,
    outer_ratio: float = 0.5,
    below_support: bool = False,
) -> Dict:
    """
    G0 全局环境扫描
    
    Args:
        code: 股票代码
        topic_name: 题材名称
        topic_rank: 题材强度排名 (1=最强)
        topic_limit_up_count: 题材内涨停数
        topic_net_amount: 题材资金净额 (元)
        topic_rank_change: 排名变化 (正=上升)
        stock_rank_in_topic: 个股在题材内涨幅排名
        stock_capital_rank: 个股在题材内资金排名
        core_stock_performing: 同题材核心股是否走强
        outer_ratio: 外盘占比 (外盘/总成交量)
        below_support: 是否跌破关键支撑
    """
    
    # ========== G0.1 早盘催化检查 ==========
    catalyst_score = 0
    catalyst_reasons = []
    
    # 题材排名是否上升
    if topic_rank_change > 0:
        catalyst_score += 4
        catalyst_reasons.append(f"题材排名上升{topic_rank_change}位")
    elif topic_rank_change == 0:
        catalyst_score += 2
    
    # 排名TOP3
    if topic_rank <= 3:
        catalyst_score += 3
        catalyst_reasons.append(f"题材排名TOP{topic_rank}")
    
    # 涨停数
    if topic_limit_up_count >= 5:
        catalyst_score += 3
        catalyst_reasons.append(f"题材内涨停{topic_limit_up_count}只")
    
    catalyst_active = catalyst_score >= 5
    catalyst_level = "强" if catalyst_score >= 8 else ("中" if catalyst_score >= 5 else ("弱" if catalyst_score >= 2 else "无"))
    
    # ========== G0.2 题材强度扫描 ==========
    strength_score = 0
    
    if topic_limit_up_count >= 5:
        strength_score += 4
    elif topic_limit_up_count >= 3:
        strength_score += 2
    
    if topic_net_amount > 500000000:  # >5亿
        strength_score += 3
    elif topic_net_amount > 100000000:  # >1亿
        strength_score += 1
    
    if topic_rank <= 3:
        strength_score += 3
    elif topic_rank <= 5:
        strength_score += 2
    elif topic_rank <= 10:
        strength_score += 1
    
    strength_level = "强" if strength_score >= 7 else ("中" if strength_score >= 4 else "弱")
    
    # ========== G0.3 个股题材定位 ==========
    if stock_rank_in_topic <= 3 and stock_capital_rank <= 3:
        position = "龙头"
        position_score = 8
    elif stock_rank_in_topic <= 5 and stock_capital_rank <= 5:
        position = "中军"
        position_score = 6
    elif stock_rank_in_topic <= 10:
        position = "跟风"
        position_score = 4
    else:
        position = "卫星"
        position_score = 2
    
    # ========== 洗盘识别 ==========
    washing_conditions = 0
    washing_reasons = []
    
    # 条件1: 题材强
    if topic_limit_up_count >= 3 and topic_net_amount > 0:
        washing_conditions += 1
        washing_reasons.append("题材强(涨停≥3+净额>0)")
    
    # 条件2: 个股弱但资金未逃
    if outer_ratio > 0.50:
        washing_conditions += 1
        washing_reasons.append(f"外盘占比{outer_ratio:.0%}>50%，资金未逃")
    
    # 条件3: 未破关键支撑
    if not below_support:
        washing_conditions += 1
        washing_reasons.append("未破关键支撑")
    
    # 条件4: 同题材核心股走强
    if core_stock_performing:
        washing_conditions += 1
        washing_reasons.append("同题材核心股走强(龙头涨停)")
    
    washing_detected = washing_conditions >= 4
    washing_confidence = {4: 0.90, 3: 0.70, 2: 0.40, 1: 0.15, 0: 0.0}.get(washing_conditions, 0.0)
    
    # ========== G0 综合评分 (0-10) ==========
    g0_score = catalyst_score * 0.3 + strength_score * 0.4 + position_score / 8 * 10 * 0.3
    g0_score = min(10, max(0, round(g0_score, 1)))
    
    # ========== 建议 ==========
    if washing_detected:
        suggestion = "洗盘确认 → 持有观察，可低吸"
    elif g0_score >= 7:
        suggestion = "做多"
    elif g0_score >= 4:
        suggestion = "持有"
    else:
        suggestion = "观望"
    
    return {
        "g0_score": g0_score,
        "catalyst_active": catalyst_active,
        "catalyst_level": catalyst_level,
        "topic_strength": strength_score,
        "topic_strength_level": strength_level,
        "stock_position": position,
        "stock_position_score": position_score,
        "washing_detected": washing_detected,
        "washing_confidence": washing_confidence,
        "washing_conditions_met": washing_conditions,
        "suggestion": suggestion,
        "details": {
            "catalyst": {
                "active": catalyst_active,
                "score": catalyst_score,
                "level": catalyst_level,
                "reasons": catalyst_reasons,
                "limit_up_count": topic_limit_up_count,
            },
            "topic_strength": {
                "score": strength_score,
                "level": strength_level,
                "limit_up_count": topic_limit_up_count,
                "net_amount": topic_net_amount,
                "rank": topic_rank,
            },
            "stock_position": {
                "level": position,
                "score": position_score,
                "code": code,
                "topic": topic_name,
                "rank_in_topic": stock_rank_in_topic,
                "capital_rank": stock_capital_rank,
            },
            "washing": {
                "detected": washing_detected,
                "confidence": washing_confidence,
                "conditions_met": washing_conditions,
                "reasons": washing_reasons,
            }
        }
    }
