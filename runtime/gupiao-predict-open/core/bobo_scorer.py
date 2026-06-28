"""
bobo_scorer.py — 波波六维评分引擎（基本面+技术面）

六维 + 折扣:
    板块共振(20%) + 催化持续性(15%) + 资金信号(15%) 
    + 技术结构(15%) + 估值安全边际(10%) + 行业地位(10%)
    - 连板过热折扣(-15%)

用法:
    from core.bobo_scorer import bobo_score
"""

from typing import Dict


def bobo_score(
    sector_strength: float = 500,
    sector_net_inflow: float = 1e8,
    sector_limit_up: int = 0,
    catalyst_type: str = "新闻",
    fund_signal: str = "中性",
    wave_stage: str = "盘整中",
    pe: float = 30,
    industry_avg_pe: float = 30,
    market_position: str = "跟随者",
    lianban_days: int = 0,
    ytd_return: float = 0,
) -> Dict:
    """
    波波六维评分
    
    Args:
        sector_strength: 概念强度值 (>800=强)
        sector_net_inflow: 板块净流入 (元)
        sector_limit_up: 板块内涨停数
        catalyst_type: 催化类型 (政策/技术/供需/新闻/情绪)
        fund_signal: 资金信号 (逆势净流入/大单净买入/中性/净卖出)
        wave_stage: 浪型阶段
        pe: 当前PE
        industry_avg_pe: 行业平均PE
        market_position: 行业地位
        lianban_days: 连板天数
        ytd_return: 年初至今涨幅 (%)
    """
    
    # === ① 板块共振 (20%) ===
    s1 = 0
    if sector_strength > 800:
        s1 += 10
    elif sector_strength > 500:
        s1 += 7
    elif sector_strength > 300:
        s1 += 5
    else:
        s1 += 3
    
    if sector_net_inflow > 2e8:  # >2亿
        s1 += 5
    elif sector_net_inflow > 5e7:
        s1 += 3
    
    if sector_limit_up >= 3:
        s1 += 5
    elif sector_limit_up >= 1:
        s1 += 3
    
    s1 = min(20, s1)
    
    # === ② 催化持续性 (15%) ===
    catalyst_map = {"政策": 15, "技术": 12, "供需": 9, "新闻": 6, "情绪": 3}
    s2 = catalyst_map.get(catalyst_type, 6)
    
    # === ③ 资金信号 (15%) ===
    fund_map = {"逆势净流入": 15, "大单净买入": 10, "中性": 5, "净卖出": 0}
    s3 = fund_map.get(fund_signal, 5)
    
    # === ④ 技术结构 (15%) ===
    wave_map = {
        "二浪": 15, "二浪确认": 15, "旗形突破": 12,
        "一浪上涨": 9, "一浪": 9, "盘整中": 6,
        "下跌趋势": 3, "派发": 0,
    }
    s4 = wave_map.get(wave_stage, 6)
    
    # === ⑤ 估值安全边际 (10%) ===
    if industry_avg_pe > 0:
        pe_ratio = pe / industry_avg_pe
    else:
        pe_ratio = 1.0
    
    if pe_ratio < 0.7:
        s5 = 10
    elif pe_ratio <= 1.3:
        s5 = 7
    elif pe_ratio <= 1.5:
        s5 = 4
    else:
        s5 = 0
    
    # === ⑥ 行业地位 (10%) ===
    position_map = {"绝对龙头": 10, "龙头": 10, "细分龙头": 7, "重要参与者": 4, "跟随者": 1}
    s6 = position_map.get(market_position, 1)
    
    # === 折扣: 连板过热 (-15% max) ===
    discount = 0
    if lianban_days >= 5:
        discount += 15
    if ytd_return > 150:
        discount += 10
    if pe > 500:
        discount += 10
    discount = min(15, discount)  # 最大-15%
    
    raw_total = s1 + s2 + s3 + s4 + s5 + s6
    final_total = max(0, raw_total - discount)
    
    return {
        "total_score": round(final_total, 1),
        "max_score": 85,  # 100 - 15(max discount)
        "sub_scores": {
            "sector_resonance": {"score": s1, "weight": 20, "label": "板块共振"},
            "catalyst_persistence": {"score": s2, "weight": 15, "label": "催化持续性"},
            "fund_signal": {"score": s3, "weight": 15, "label": "资金信号"},
            "tech_structure": {"score": s4, "weight": 15, "label": "技术结构"},
            "valuation_margin": {"score": s5, "weight": 10, "label": "估值安全边际"},
            "industry_position": {"score": s6, "weight": 10, "label": "行业地位"},
        },
        "discount": {
            "amount": discount,
            "max_discount": 15,
            "reasons": {
                "lianban_days": lianban_days,
                "ytd_return": ytd_return,
                "pe": pe,
            }
        },
        "raw_total": raw_total,
    }


def bobo_game_fusion(bobo_total: float, game_total: float, bobo_max: float = 85, game_max: float = 100) -> Dict:
    """
    双引擎融合
    
    综合 = 波波归一化×0.50 + 博弈归一化×0.50
    """
    bobo_norm = bobo_total / bobo_max * 100
    game_norm = game_total  # 博弈已是0-100
    
    merged = bobo_norm * 0.5 + game_norm * 0.5
    
    # 交叉验证
    bobo_strong = bobo_norm >= 70
    game_strong = game_norm >= 70
    bobo_weak = bobo_norm < 50
    game_weak = game_norm < 50
    
    if bobo_strong and game_strong:
        rule = "双引擎一致 → 增强信心"
        position_adj = 0.5  # +0.5成
    elif (bobo_strong and game_weak) or (bobo_weak and game_strong):
        rule = "双引擎分歧 → 降权"
        position_adj = -1.0  # -1成
    elif bobo_weak and game_weak:
        rule = "双引擎一致看空 → 排除"
        position_adj = -10.0
    else:
        rule = "中性"
        position_adj = 0
    
    return {
        "merged_score": round(merged, 1),
        "bobo_normalized": round(bobo_norm, 1),
        "game_normalized": round(game_norm, 1),
        "cross_validation": rule,
        "position_adjustment_cheng": position_adj,
    }
