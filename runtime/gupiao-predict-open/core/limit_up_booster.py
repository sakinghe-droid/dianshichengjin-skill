"""
limit_up_booster.py — 涨停增强引擎

仅涨停/连板股触发，输出 0-30分加成。
四维: 封单强度 + 涨停时间 + 连板质量 + DDZ

用法:
    from core.limit_up_booster import limit_up_boost
"""

from typing import Dict


def limit_up_boost(data: Dict) -> Dict:
    """
    涨停增强评估
    
    仅限 is_limit_up=True 或 lianban_days>0 的股票。
    
    Args:
        data: {"is_limit_up": bool, "lianban_days": int, "seal_amount": float,
               "float_market_cap": float, "limit_up_time": str, "ddz": float,
               "volume_ratio": float}
    
    Returns:
        {"boost_score": 0-30, "cycle": str, "triggered": bool}
    """
    is_limit_up = data.get("is_limit_up", False)
    lianban_days = data.get("lianban_days", 0)
    
    if not is_limit_up and lianban_days == 0:
        return {"boost_score": 0, "cycle": "非涨停", "triggered": False, "reason": "非涨停/连板股"}
    
    # ① 封单强度 (0-10)
    seal_amount = data.get("seal_amount", 0)
    float_mcap = data.get("float_market_cap", 10e9)  # 默认100亿
    if float_mcap > 0:
        seal_ratio = seal_amount / float_mcap * 100
    else:
        seal_ratio = 0
    
    if seal_ratio > 5:
        s1 = 10
    elif seal_ratio > 3:
        s1 = 7
    elif seal_ratio > 1:
        s1 = 4
    else:
        s1 = min(3, int(seal_ratio * 3))
    
    # ② 涨停时间 (0-10)
    limit_up_time = str(data.get("limit_up_time", ""))
    if "09:30" in limit_up_time or "09:3" in limit_up_time:
        s2 = 10
    elif "09:" in limit_up_time or "10:00" in limit_up_time:
        s2 = 7
    elif "10:" in limit_up_time or "11:00" in limit_up_time:
        s2 = 5
    elif "13:" in limit_up_time:
        s2 = 3
    else:
        s2 = 1  # 尾盘
    
    # ③ 连板质量 (0-10)
    vol_ratio = data.get("volume_ratio", 1.0)
    if lianban_days >= 3 and vol_ratio < 0.8:
        s3 = 10  # 缩量加速
    elif lianban_days >= 2 and 0.8 <= vol_ratio <= 2.0:
        s3 = 7   # 放量换手
    elif lianban_days >= 1:
        s3 = 5
    else:
        s3 = 3   # 首板
    
    # ④ DDZ强度 (0-10)
    ddz = data.get("ddz", 25)
    if ddz > 50:
        s4 = 10
    elif ddz > 30:
        s4 = 7
    elif ddz > 20:
        s4 = 5
    elif ddz > 10:
        s4 = 3
    else:
        s4 = 1
    
    total = s1 + s2 + s3 + s4
    
    # 情绪周期
    if lianban_days >= 4:
        cycle = "接力期"
    elif lianban_days >= 2:
        cycle = "接力期"
    elif is_limit_up:
        cycle = "点火期"
    else:
        cycle = "退潮期"
    
    return {
        "boost_score": total,
        "max_boost": 30,
        "cycle": cycle,
        "triggered": True,
        "detail": {
            "seal_strength": {"score": s1, "seal_ratio_pct": round(seal_ratio, 2)},
            "limit_up_time": {"score": s2, "time": limit_up_time or "未知"},
            "lianban_quality": {"score": s3, "days": lianban_days, "vol_ratio": vol_ratio},
            "ddz": {"score": s4, "value": ddz},
        }
    }
