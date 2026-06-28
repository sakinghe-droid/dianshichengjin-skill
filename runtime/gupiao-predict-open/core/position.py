"""
position.py — 统一仓位计算引擎

公式: final_pct = min(base_pct, ceiling)

base_pct = 情绪系数 × 阶段系数 × 0.30
ceiling  = E5位置天花板 × L2验证乘数 × 波动率乘数
           × 情绪调节(仅低位/中低位生效) × G0修正

用法:
    from core.position import calculate_position
    result = calculate_position(emotion="积极", stage="主升期", e5_ceiling=0.20, l2_mult=1.0, vol_mult=1.0)
"""

from typing import Optional


# ============================================================
# 情绪系数
# ============================================================

EMOTION_COEFF = {
    "亢奋": 1.0, "积极": 0.8,
    "中性": 0.5, "谨慎": 0.3,
    "恐慌": 0.0,
    # 英文别名
    "bullish": 1.0, "positive": 0.8,
    "neutral": 0.5, "cautious": 0.3,
    "panic": 0.0, "negative": 0.3,
}

EMOTION_CONDITIONS = {
    "亢奋": "涨停>50只, 炸板率<15%",
    "积极": "涨停30-50只",
    "中性": "涨停15-30只",
    "谨慎": "涨停<15只",
    "恐慌": "涨停<5只 或 炸板率>40%",
}


def get_emotion_coeff(emotion: str) -> float:
    """获取情绪系数"""
    return EMOTION_COEFF.get(emotion, 0.5)


def classify_emotion(limit_up_count: int, break_rate: float = 0.15) -> str:
    """
    根据涨停数和炸板率分类情绪
    
    Args:
        limit_up_count: 全市场涨停数
        break_rate: 炸板率 (0-1)
    """
    if limit_up_count < 5 or break_rate > 0.40:
        return "恐慌"
    elif limit_up_count < 15:
        return "谨慎"
    elif limit_up_count < 30:
        return "中性"
    elif limit_up_count <= 50 or break_rate >= 0.15:
        return "积极"
    else:
        return "亢奋"


# ============================================================
# 阶段系数
# ============================================================

STAGE_COEFF = {
    "主升期": 0.8, "高潮期": 0.5,
    "发酵期": 0.3, "启动期": 0.0,
    "退潮期": 0.0,
    # 英文
    "main_up": 0.8, "climax": 0.5,
    "ferment": 0.3, "start": 0.0,
    "recession": 0.0,
}


def get_stage_coeff(stage: str) -> float:
    """获取阶段系数"""
    return STAGE_COEFF.get(stage, 0.3)


# ============================================================
# E5 位置天花板
# ============================================================

E5_CEILING = {
    0: 0.30,  # 低位 → 3成
    1: 0.25,  # 中低位 → 2.5成
    2: 0.20,  # 中位 → 2成
    3: 0.10,  # 高位 → 1成
    4: 0.05,  # 超高位 → 0.5成
}


def get_e5_ceiling(level_code: int) -> float:
    """E5位置 → 仓位天花板"""
    return E5_CEILING.get(level_code, 0.20)


# ============================================================
# L2 验证乘数
# ============================================================

def get_l2_mult(total_score: int) -> float:
    """
    L2五维总分 → 仓位乘数
    
    ≥7 → 强确认: 1.0
    4-6 → 中确认: 0.6
    2-3 → 弱确认: 0.3
    0-1 → 拒绝: 0
    """
    if total_score >= 7:
        return 1.0
    elif total_score >= 4:
        return 0.6
    elif total_score >= 2:
        return 0.3
    else:
        return 0.0


# ============================================================
# 波动率乘数
# ============================================================

def get_vol_mult(vol_level: str, level_code: int = 0) -> float:
    """
    波动率评级 → 仓位乘数
    
    低波(倍数<0.7): 1.0
    中波(0.7-1.3): 1.0
    高波(1.3-2.0): 0.7
    极高波(>2.0): 0.5
    高位+高波: ×0.7
    高位+极高波: ×0.7
    """
    base = {"低波": 1.0, "中波": 1.0, "高波": 0.7, "极高波": 0.5}.get(vol_level, 1.0)
    
    # 高位叠加打折
    if level_code >= 3 and vol_level in ("高波", "极高波"):
        base *= 0.7
    
    return base


# ============================================================
# G0 修正系数
# ============================================================

def get_g0_modifier(g0_score: float) -> float:
    """
    G0评分 → 仓位修正系数
    
    G0≥8 → 1.3
    G0≥6 → 1.1
    G0≥4 → 1.0
    G0<4 → 0.7
    """
    if g0_score >= 8:
        return 1.3
    elif g0_score >= 6:
        return 1.1
    elif g0_score >= 4:
        return 1.0
    else:
        return 0.7


# ============================================================
# 统一仓位计算
# ============================================================

def calculate_position(
    emotion: str = "中性",
    stage: str = "主升期",
    e5_level_code: int = 2,
    e5_ceiling: Optional[float] = None,
    l2_total_score: int = 5,
    l2_mult: Optional[float] = None,
    vol_level: str = "中波",
    vol_mult_override: Optional[float] = None,
    g0_score: Optional[float] = None,
    total_capital: float = 100000,
    available_capital: Optional[float] = None,
) -> dict:
    """
    统一仓位计算公式
    
    final_pct = min(base_pct, ceiling)
    
    base_pct = 情绪系数 × 阶段系数 × 0.30
    ceiling  = E5天花板 × L2乘数 × 波动率乘数 × G0修正 × 情绪调节
    
    Args:
        emotion: 市场情绪 (亢奋/积极/中性/谨慎/恐慌)
        stage: 题材阶段 (主升期/高潮期/发酵期/启动期/退潮期)
        e5_level_code: E5位置等级 (0-4)
        e5_ceiling: E5仓位天花板（覆盖默认值）
        l2_total_score: L2五维总分 (0-10)
        l2_mult: L2乘数（覆盖计算值）
        vol_level: 波动率评级
        vol_mult_override: 波动率乘数（覆盖计算值）
        g0_score: G0评分 (0-10, 可选)
        total_capital: 总资金
        available_capital: 可用资金（默认=总资金）
    
    Returns:
        {
            "base_pct": float,           # 基础仓位
            "ceiling": float,            # 仓位天花板
            "final_pct": float,          # 最终仓位比例
            "final_amount": float,       # 最终金额
            "final_shares": int,         # 最终股数(整百股)
            "breakdown": dict            # 计算明细
        }
    """
    # === 基础仓位 ===
    e_coeff = get_emotion_coeff(emotion)
    s_coeff = get_stage_coeff(stage)
    base_pct = e_coeff * s_coeff * 0.30
    
    # === 仓位天花板 ===
    ceiling_e5 = e5_ceiling if e5_ceiling is not None else get_e5_ceiling(e5_level_code)
    ceiling_l2 = l2_mult if l2_mult is not None else get_l2_mult(l2_total_score)
    ceiling_vol = vol_mult_override if vol_mult_override is not None else get_vol_mult(vol_level, e5_level_code)
    
    ceiling = ceiling_e5 * ceiling_l2 * ceiling_vol
    
    # G0修正
    g0_mod = 1.0
    if g0_score is not None:
        g0_mod = get_g0_modifier(g0_score)
        ceiling *= g0_mod
    
    # === 情绪调节（仅低位/中低位生效） ===
    if e5_level_code <= 1:  # 低位或中低位
        if e_coeff >= 0.8:
            ceiling = min(0.30, ceiling * 1.2)  # 积极时放大，上限30%
        elif e_coeff <= 0.3:
            ceiling *= 0.5  # 恐慌时缩小
    
    # === 硬约束 ===
    # 恐慌+高位 → 不做
    if e_coeff <= 0.3 and e5_level_code >= 3:
        ceiling = 0
    
    # 阶段=启动/退潮 → 空仓
    if s_coeff == 0:
        ceiling = 0
    
    # L2拒绝 → 不做
    if ceiling_l2 == 0:
        ceiling = 0
    
    # === 最终仓位 ===
    final_pct = min(base_pct, ceiling)
    final_pct = max(0, final_pct)  # 不下负仓
    
    # === 金额计算 ===
    avail = available_capital if available_capital is not None else total_capital
    final_amount = avail * final_pct
    
    # 硬约束
    final_amount = min(final_amount, total_capital * 0.30)  # 单票上限30%
    final_amount = max(final_amount, 0)
    
    # 最小金额检查
    if final_amount < 5000:
        final_amount = 0
        final_pct = 0
    
    # 股数（整百股）
    # 需要当前价格来计算股数，这里只计算比例
    final_shares = 0  # 调用方根据价格计算
    
    return {
        "base_pct": round(base_pct, 4),
        "ceiling": round(ceiling, 4),
        "final_pct": round(final_pct, 4),
        "final_amount": round(final_amount, 2),
        "final_shares": final_shares,
        "breakdown": {
            "emotion": {"label": emotion, "coeff": e_coeff},
            "stage": {"label": stage, "coeff": s_coeff},
            "e5": {"level_code": e5_level_code, "ceiling": ceiling_e5},
            "l2": {"score": l2_total_score, "mult": ceiling_l2},
            "volatility": {"level": vol_level, "mult": ceiling_vol},
            "g0": {"score": g0_score, "modifier": g0_mod} if g0_score is not None else None,
            "emotion_boost_applied": e5_level_code <= 1 and e_coeff >= 0.8,
            "emotion_cut_applied": e5_level_code <= 1 and e_coeff <= 0.3,
            "panic_high_veto": e_coeff <= 0.3 and e5_level_code >= 3,
            "l2_veto": ceiling_l2 == 0,
        },
        "hard_constraints": {
            "max_single_stock": total_capital * 0.30,
            "max_same_topic": total_capital * 0.50,
            "min_amount": 5000,
            "available": avail,
        }
    }


def allocate_positions(candidates: list, final_pct: float, total_capital: float) -> list:
    """
    仓位分配优先级
    
    TOP1: 50%, TOP2: 30%, TOP3: 20%
    超出3只不分配
    """
    total_amount = total_capital * final_pct
    weights = [0.50, 0.30, 0.20]
    result = []
    
    for i, c in enumerate(candidates[:3]):
        amount = total_amount * weights[i]
        result.append({
            **c,
            "allocated_amount": round(amount, 2),
            "allocated_pct": round(weights[i] * final_pct, 4),
        })
    
    return result
