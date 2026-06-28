"""
math_utils.py — 基础数学函数库
无外部网络依赖，纯计算。所有引擎模块的基础层。

RSI / MA / 波动率 / 波段位置 / 量比 / 振幅 / 支撑压力
"""

import math
from typing import List, Dict, Optional, Tuple


def rsi_wilder(closes: List[float], period: int = 14) -> Optional[float]:
    """
    Wilder's Smoothing RSI(14)
    
    Args:
        closes: 收盘价序列（按时间升序）
        period: RSI周期，默认14
    
    Returns:
        RSI值 (0-100)，数据不足返回 None
    """
    if len(closes) < period + 1:
        return None
    
    gains, losses = [], []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i-1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def rsi_score(rsi: float) -> int:
    """RSI → 位置评分 (0-10)"""
    if rsi < 30:
        return 9   # 超卖=机会
    elif rsi <= 60:
        return 7   # 中性偏多
    elif rsi <= 70:
        return 5   # 偏强需谨慎
    else:
        return 3   # 超买=风险


def ma(values: List[float], period: int) -> Optional[float]:
    """简单移动平均"""
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ma_deviation(price: float, ma_val: float) -> float:
    """价格相对于均线的偏离度 (%)"""
    if ma_val == 0:
        return 0.0
    return (price - ma_val) / ma_val * 100


def ma_deviation_score(ma20_dev: float, ma60_dev: Optional[float] = None) -> int:
    """均线偏离评分 (0-10)"""
    abs20 = abs(ma20_dev)
    
    if abs20 < 3 and (ma60_dev is None or abs(ma60_dev) < 5):
        return 10  # 贴MA20/MA60，安全
    elif abs20 > 15 or (ma60_dev is not None and abs(ma60_dev) > 25):
        return 2   # 严重偏离高位
    elif abs20 >= 8 or (ma60_dev is not None and abs(ma60_dev) >= 12):
        if ma20_dev < -8 or (ma60_dev is not None and ma60_dev < -15):
            return 8  # 超跌反弹空间
        return 5    # 偏离中位
    else:
        return 6    # 正常范围


def daily_volatility(returns: List[float]) -> float:
    """日波动率（样本标准差）"""
    if len(returns) < 2:
        return 0.0
    mean_r = sum(returns) / len(returns)
    variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance)


def annualized_volatility(daily_vol: float) -> float:
    """年化波动率"""
    return daily_vol * math.sqrt(252)


def volatility_ratio(current_annual: float, historical_avg_annual: float) -> float:
    """波动率倍数"""
    if historical_avg_annual == 0:
        return 1.0
    return current_annual / historical_avg_annual


def volatility_level(ratio: float) -> Tuple[str, float]:
    """
    波动率评级 → (评级, 乘数)
    
    低波: <0.7 → 1.0
    中波: 0.7-1.3 → 1.0
    高波: 1.3-2.0 → 0.7
    极高波: >2.0 → 0.5
    """
    if ratio < 0.7:
        return "低波", 1.0
    elif ratio <= 1.3:
        return "中波", 1.0
    elif ratio <= 2.0:
        return "高波", 0.7
    else:
        return "极高波", 0.5


def band_position(price: float, low_60d: float, high_60d: float) -> float:
    """60日波段位置 (0-100%)"""
    if high_60d == low_60d:
        return 50.0
    return (price - low_60d) / (high_60d - low_60d) * 100


def band_position_score(band_pct: float) -> int:
    """波段位置评分 (0-10)"""
    band = band_pct / 100.0
    if band < 0.3:
        return 8   # 底部区域
    elif band <= 0.6:
        return 6   # 中位
    elif band <= 0.85:
        return 3   # 中高位
    else:
        return 1   # 高位


def volume_ratio(today_volume: float, avg_20d_volume: float) -> float:
    """量比"""
    if avg_20d_volume == 0:
        return 1.0
    return today_volume / avg_20d_volume


def volume_ratio_score(vol_ratio: float) -> int:
    """量价偏离评分 (0-10)"""
    if 0.5 <= vol_ratio <= 1.5:
        return 6   # 量价配合
    elif 1.5 < vol_ratio <= 3.0:
        return 4   # 放量需关注
    elif vol_ratio > 3.0:
        return 2   # 天量风险
    else:  # < 0.5
        return 4   # 缩量


def amplitude(high: float, low: float, prev_close: float) -> float:
    """当日振幅 (%)"""
    if prev_close == 0:
        return 0.0
    return (high - low) / prev_close * 100


def support_resistance(klines: List[Dict], window: int = 20) -> Tuple[float, float]:
    """
    支撑位/压力位（基于近期高低点）
    
    Returns:
        (支撑位, 压力位)
    """
    recent = klines[-window:] if len(klines) >= window else klines
    support = min(k['low'] for k in recent)
    resistance = max(k['high'] for k in recent)
    return support, resistance


def risk_reward_ratio(price: float, support: float, resistance: float) -> float:
    """盈亏比"""
    if price <= support:
        return 10.0  # 已到支撑，极度安全
    upside = resistance - price
    downside = price - support
    if downside <= 0:
        return 10.0
    return upside / downside


def risk_reward_score(rr: float) -> int:
    """空间评估评分 (0-10)"""
    if rr > 2:
        return 5   # 向上空间大
    elif rr >= 1:
        return 4   # 空间合理
    else:
        return 3   # 空间不足


def position_level(band_pct: float, rsi: Optional[float] = None) -> Tuple[str, int, float, bool]:
    """
    位置评级 → (评级, level_code, 仓位天花板, need_l2)
    
    Args:
        band_pct: 60日波段位置 (%)
        rsi: RSI值（可选，用于高位补充判定）
    
    Returns:
        (level_name, level_code, ceiling, need_l2_verify)
        
    level_code:
        0=低位, 1=中低位, 2=中位, 3=高位, 4=超高位
    
    ceiling:
        0.30/0.25/0.20/0.10/0.05
    """
    # RSI 辅助判定
    is_high_rsi = rsi is not None and rsi > 65
    is_extreme_rsi = rsi is not None and rsi > 80
    
    if band_pct > 85 or is_extreme_rsi:
        return "超高位", 4, 0.05, True
    elif band_pct > 65 or is_high_rsi:
        return "高位", 3, 0.10, True
    elif band_pct > 45:
        return "中位", 2, 0.20, False
    elif band_pct > 25:
        return "中低位", 1, 0.25, False
    else:
        return "低位", 0, 0.30, False


def daily_returns(closes: List[float]) -> List[float]:
    """日收益率序列"""
    return [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes)) if closes[i-1] != 0]


def rolling_volatility_avg(close_prices: List[float], window: int = 120) -> Optional[float]:
    """近N日平均年化波动率"""
    if len(close_prices) < window + 1:
        window = len(close_prices) - 1
    if window < 2:
        return None
    
    # 使用滑动窗口计算多个子区间的波动率，取平均
    sub_returns = []
    # 简化：使用最后window天的数据计算
    recent = close_prices[-window-1:]
    rets = daily_returns(recent)
    if len(rets) < 2:
        return None
    return annualized_volatility(daily_volatility(rets))


def e5_full_analysis(klines: List[Dict], price: float) -> Dict:
    """
    E5 位置波动率完整分析
    
    根据 ref_workflow_logic 第七部分设计文档实现。
    
    Args:
        klines: K线列表 [{"open","high","low","close","volume"}, ...]，按时间升序
        price: 当前价格
    
    Returns:
        E5 输出字典（与设计文档格式一致）
    """
    if len(klines) < 20:
        return {"error": "K线数据不足（至少需要20条）"}
    
    closes = [k['close'] for k in klines]
    highs = [k['high'] for k in klines]
    lows = [k['low'] for k in klines]
    volumes = [k['volume'] for k in klines]
    
    # === 波段位置 ===
    low_60d = min(lows[-60:]) if len(lows) >= 60 else min(lows)
    high_60d = max(highs[-60:]) if len(highs) >= 60 else max(highs)
    band_pct = band_position(price, low_60d, high_60d)
    bp_score = band_position_score(band_pct)
    
    # === RSI(14) ===
    rsi = rsi_wilder(closes, 14) or 50.0
    rv_score = rsi_score(rsi)
    
    # === 均线偏离 ===
    ma20 = ma(closes, 20) or price
    ma60 = ma(closes, 60) if len(closes) >= 60 else None
    ma20_dev = ma_deviation(price, ma20)
    ma60_dev = ma_deviation(price, ma60) if ma60 else None
    mp_score = ma_deviation_score(ma20_dev, ma60_dev)
    
    # === 波动率 ===
    rets = daily_returns(closes)
    daily_vol = daily_volatility(rets)
    annual_vol = annualized_volatility(daily_vol)
    hist_annual_vol = rolling_volatility_avg(closes, 120) or annual_vol
    vol_ratio_val = volatility_ratio(annual_vol, hist_annual_vol)
    vol_level, base_vol_mult = volatility_level(vol_ratio_val)
    
    # === 量价偏离 ===
    if len(volumes) >= 21:
        avg_20d_vol = sum(volumes[-21:-1]) / 20
    else:
        avg_20d_vol = sum(volumes[:-1]) / max(len(volumes)-1, 1)
    vol_ratio = volume_ratio(volumes[-1], avg_20d_vol)
    vd_score = volume_ratio_score(vol_ratio)
    
    # === 空间评估 ===
    support, resistance = support_resistance(klines)
    rr = risk_reward_ratio(price, support, resistance)
    sa_score = risk_reward_score(rr)
    
    # === 位置评级 ===
    level_name, level_code, ceiling, need_l2 = position_level(band_pct, rsi)
    
    # === 波动率乘数（高位叠加打折） ===
    vol_mult = base_vol_mult
    if level_code >= 3:  # 高位或超高位
        if vol_level == "高波":
            vol_mult = base_vol_mult * 0.7
        elif vol_level == "极高波":
            vol_mult = base_vol_mult * 0.7
    
    # === E5 总评分 (0-20) ===
    # mp(均线) + bp(波段) + rv(RSI) + vd(量价) + sa(空间) 各0-10分
    raw_total = mp_score + bp_score + rv_score + vd_score + sa_score
    # 映射到0-20
    e5_score = min(20, int(raw_total / 50.0 * 20))
    
    return {
        "level": level_name,
        "level_code": level_code,
        "score": e5_score,
        "ceiling": ceiling,
        "volatility": vol_level,
        "vol_ratio": round(vol_ratio_val, 2),
        "vol_mult": round(vol_mult, 2),
        "need_l2": need_l2,
        # 子指标分
        "mp": mp_score,      # 均线偏离
        "bp": bp_score,      # 波段位置
        "rv": rv_score,      # RSI
        "vd": vd_score,      # 量价偏离
        "sa": sa_score,      # 空间评估
        # 原始值
        "rsi": round(rsi, 2),
        "ma20": round(ma20, 4),
        "ma60": round(ma60, 4) if ma60 else None,
        "ma20_dev": round(ma20_dev, 2),
        "ma60_dev": round(ma60_dev, 2) if ma60_dev is not None else None,
        "band_position_pct": round(band_pct, 2),
        "annual_volatility": round(annual_vol, 4),
        "vol_ratio_vs_20d": round(vol_ratio, 2),
        "support": round(support, 4),
        "resistance": round(resistance, 4),
        "risk_reward": round(rr, 2),
        "amplitude_today": round(amplitude(highs[-1], lows[-1], closes[-2] if len(closes) >= 2 else closes[-1]), 2),
    }
