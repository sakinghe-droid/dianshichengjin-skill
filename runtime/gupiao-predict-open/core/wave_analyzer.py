"""
wave_analyzer.py — 趋势波段分析器

浪型定位 + 模式ABC + 旗形六要素 + 二浪确认 + 缠论 + 催化持续性

用法:
    from core.wave_analyzer import wave_analyze
"""

from typing import Dict, List


def wave_analyze(klines: List[Dict], catalyst_type: str = "新闻") -> Dict:
    """
    趋势波段分析
    
    Args:
        klines: K线列表 [{"open","high","low","close","volume"}, ...]，按时间升序
        catalyst_type: 催化类型 (政策/技术/供需/新闻/情绪)
    
    Returns:
        浪型定位 + 模式 + 旗形 + 二浪 + 缠论
    """
    if len(klines) < 20:
        return {"error": "K线不足（需≥20条）", "wave_stage": "数据不足"}
    
    closes = [k['close'] for k in klines]
    highs = [k['high'] for k in klines]
    lows = [k['low'] for k in klines]
    volumes = [k['volume'] for k in klines]
    
    price = closes[-1]
    low_60 = min(lows[-60:]) if len(lows) >= 60 else min(lows)
    high_60 = max(highs[-60:]) if len(highs) >= 60 else max(highs)
    band_pct = (price - low_60) / (high_60 - low_60) * 100 if high_60 != low_60 else 50
    
    # === 浪型定位 ===
    # 简化的浪型判定
    change_20d = (closes[-1] - closes[-20]) / closes[-20] * 100 if len(closes) >= 20 else 0
    change_5d = (closes[-1] - closes[-5]) / closes[-5] * 100 if len(closes) >= 5 else 0
    vol_trend = sum(volumes[-5:]) / sum(volumes[-10:-5]) if len(volumes) >= 10 else 1.0
    
    if band_pct < 20 and vol_trend < 1.2:
        wave_stage = "建仓期"
    elif change_20d > 15 and vol_trend > 1.0:
        wave_stage = "一浪"
    elif abs(change_5d) < 5 and vol_trend < 0.8:
        wave_stage = "盘整"
    elif change_5d > 5 and vol_trend > 1.2 and change_20d > 10:
        wave_stage = "二浪"
    elif change_5d > 10 and vol_trend > 1.5:
        wave_stage = "加速"
    elif band_pct > 60 and change_20d > 30:
        wave_stage = "三浪"
    elif band_pct > 80 and vol_trend > 0.8 and change_5d < 3:
        wave_stage = "派发"
    else:
        wave_stage = "盘整中"
    
    # === 模式ABC ===
    if change_20d > 20 and vol_trend > 1.2:
        pattern = "A(业绩共振)"
    elif catalyst_type in ("政策", "技术"):
        pattern = "B(催化驱动)"
    else:
        pattern = "C(困境反转)"
    
    # === 旗形整理检测（简化六要素） ===
    flag_detected = False
    flag_details = []
    
    # 检查最近是否有涨停触发（涨幅≥7%）
    recent_max_change = 0
    for i in range(max(0, len(closes)-15), len(closes)):
        if i > 0 and closes[i-1] > 0:
            daily_chg = (closes[i] - closes[i-1]) / closes[i-1] * 100
            recent_max_change = max(recent_max_change, daily_chg)
    
    has_trigger = recent_max_change >= 7
    flag_details.append(f"涨停触发: {'是' if has_trigger else '否'} ({recent_max_change:.1f}%)")
    
    # 横盘检查（最近5日振幅）
    recent_5 = closes[-5:]
    range_5d = (max(recent_5) - min(recent_5)) / min(recent_5) * 100
    is_sideways = range_5d < 8
    flag_details.append(f"横盘(5日振幅{range_5d:.1f}%): {'是' if is_sideways else '否'}")
    
    # 缩量
    vol_ratio_5 = sum(volumes[-5:]) / sum(volumes[-10:-5]) if len(volumes) >= 10 else 1.0
    is_shrinking = vol_ratio_5 < 0.8
    flag_details.append(f"缩量({vol_ratio_5:.1f}x): {'是' if is_shrinking else '否'}")
    
    flag_detected = has_trigger and is_sideways and is_shrinking
    
    # === 二浪确认 ===
    wave2_confirmed = False
    wave2_reasons = []
    
    if wave_stage == "二浪":
        # 检查一浪涨幅≥20%
        if change_20d >= 20:
            wave2_confirmed = True
            wave2_reasons.append("一浪涨幅≥20%")
        # 检查放量突破
        if vol_trend > 1.5:
            wave2_confirmed = wave2_confirmed and True
            wave2_reasons.append("放量突破")
    
    # === 缠论简析 ===
    # 中枢: 最近20根K线的高低点重叠区间
    recent_20_highs = highs[-20:]
    recent_20_lows = lows[-20:]
    pivot_high = max(recent_20_highs)
    pivot_low = min(recent_20_lows)
    has_pivot = (pivot_high - pivot_low) / pivot_low > 0.05  # 中枢宽度>5%
    
    # 背驰: 价格新高但RSI不新高（简化）
    if len(closes) >= 14:
        from core.math_utils import rsi_wilder
        rsi_now = rsi_wilder(closes) or 50
        rsi_5d_ago = rsi_wilder(closes[:-5]) or 50
        divergence = (price > max(closes[-10:-5])) and (rsi_now < rsi_5d_ago)
    else:
        divergence = False
    
    # === 催化持续性 ===
    catalyst_map = {"政策": "政策驱动(持续性10)", "技术": "技术驱动(持续性8)",
                    "供需": "供需驱动(持续性7)", "新闻": "新闻驱动(持续性3)",
                    "情绪": "情绪驱动(持续性1)"}
    
    return {
        "wave_stage": wave_stage,
        "pattern": pattern,
        "flag_pattern": flag_detected,
        "flag_details": flag_details,
        "wave2_confirmed": wave2_confirmed,
        "wave2_reasons": wave2_reasons,
        "chanlun": {
            "has_pivot": has_pivot,
            "pivot_range": [round(pivot_low, 2), round(pivot_high, 2)],
            "divergence": divergence,
            "pivot_width_pct": round((pivot_high - pivot_low) / pivot_low * 100, 1) if pivot_low > 0 else 0,
        },
        "catalyst": {
            "type": catalyst_type,
            "description": catalyst_map.get(catalyst_type, "未知"),
        },
        "metrics": {
            "change_20d_pct": round(change_20d, 1),
            "change_5d_pct": round(change_5d, 1),
            "band_position_pct": round(band_pct, 1),
            "volume_trend": round(vol_trend, 2),
        }
    }
