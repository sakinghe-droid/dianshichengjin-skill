"""
f6_l2.py — F6 L2大单验证引擎

五维评分 → L2乘数。仅高位/超高位时调用。

用法:
    from core.f6_l2 import l2_verify
    result = l2_verify(active_buy_ratio=0.65, super_large_net=80000000, inst_vs_retail=1.8)
"""

from typing import Dict


def l2_verify(
    active_buy_ratio: float = 0.5,
    super_large_net: float = 0,
    inst_vs_retail: float = 1.0,
    continuity_3d: int = 1,
    big_order_direction: str = "",
    need_l2: bool = True,
) -> Dict:
    """
    F6 L2大单五维验证
    
    Args:
        active_buy_ratio: 主动买入占比 (0-1)
        super_large_net: 特大单净额 (元)
        inst_vs_retail: 机构/散户比 (>1.3=机构主导, <0.8=散户主导)
        continuity_3d: 近3日大单净流入天数
        big_order_direction: 大单方向 "in"/"out"/"neutral" (可覆盖自动判定)
        need_l2: 是否需要L2验证（E5 level_code>=3）
    
    Returns:
        {
            "confirm_level": str,
            "l2_mult": float,
            "score": int (总分 0-10),
            "sub_scores": [5个, 含大单方向±1],
            "signal": str,
            "vetoed": bool
        }
    """
    if not need_l2:
        return {
            "confirm_level": "N/A（非高位无需L2）",
            "l2_mult": 1.0,
            "score": 10,
            "sub_scores": [2, 2, 2, 2, 1],
            "signal": "buy",
            "vetoed": False,
        }
    
    # ① 主动买占比 (0-2分)
    if active_buy_ratio > 0.4:
        s1 = 2
    elif active_buy_ratio >= 0.25:
        s1 = 1
    else:
        s1 = 0
    
    # ② 特大单净额 (0-2分)，单位: 元
    if super_large_net > 50000000:  # >5000万
        s2 = 2
    elif super_large_net >= 10000000:  # >1000万
        s2 = 1
    else:
        s2 = 0
    
    # ③ 机构vs散户 (0-2分)
    if inst_vs_retail > 1.3:
        s3 = 2  # inst_buy
    elif inst_vs_retail >= 0.8:
        s3 = 1  # same
    else:
        s3 = 0  # inst_sell
    
    # ④ 3日连续性 (0-2分)
    if continuity_3d >= 3:
        s4 = 2
    elif continuity_3d >= 2:
        s4 = 1
    else:
        s4 = 0
    
    # ⑤ 大单方向 (±1分)
    if big_order_direction in ("in", "净买入"):
        s5 = 1
    elif big_order_direction in ("out", "净卖出"):
        s5 = -1
    else:
        # 自动: 特大单净额方向
        if super_large_net > 0:
            s5 = 1
        elif super_large_net < 0:
            s5 = -1
        else:
            s5 = 0
    
    total = s1 + s2 + s3 + s4 + s5
    
    # 综合判定
    if total >= 7:
        confirm = "强确认"
        l2_mult = 1.0
        signal = "buy"
    elif total >= 4:
        confirm = "中确认"
        l2_mult = 0.6
        signal = "hold"
    elif total >= 2:
        confirm = "弱确认"
        l2_mult = 0.3
        signal = "sell"
    else:
        confirm = "拒绝"
        l2_mult = 0.0
        signal = "sell"
    
    return {
        "confirm_level": confirm,
        "l2_mult": l2_mult,
        "score": total,
        "sub_scores": [s1, s2, s3, s4, s5],
        "sub_labels": ["主动买占比", "特大单净额", "机构vs散户", "3日连续性", "大单方向"],
        "signal": signal,
        "vetoed": l2_mult == 0,
    }
