"""
game_theory_6d.py — 六维博弈引擎（纯Python实现）

A1 主力行为 (25%) / B2 情绪周期 (15%) / C3 量化风报比 (15%)
D4 统计分布 (10%) / E5 位置波动率 (20%) / F6 L2大单验证 (15%)

输入: JSON（与原始 game_theory_engine 相同格式）
输出: final_signal, final_score, position_pct, sell_tendency, risk_level, forecast

用法:
    python core/game_theory_6d.py --input <input.json> [--kline <kline.json>]
"""

import json
import sys
import os
import argparse
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.math_utils import e5_full_analysis


# ============================================================
# A1: 主力行为 (权重 25%)
# ============================================================

def a1_analysis(data: dict) -> dict:
    """
    A1 主力行为分析
    
    判定: 建仓期 / 拉升期 / 出货期 / 观望期
    一票否决: 5日DDX<-1 或 10日DDX<-3
    """
    ddx_5d = data.get("ddx_5d", 0)
    ddx_10d = data.get("ddx_10d", 0)
    main_amount = data.get("main_amount", 0)
    
    # === 一票否决 ===
    veto = False
    veto_reason = None
    if ddx_5d < -1:
        veto = True
        veto_reason = f"DDX一票否决: 5日DDX={ddx_5d} < -1"
    elif ddx_10d < -3:
        veto = True
        veto_reason = f"DDX一票否决: 10日DDX={ddx_10d} < -3"
    
    # === 行为分类 ===
    # 简化判定（在没有完整DDX/大单时序数据时）
    if veto:
        stage = "出货期"
        stage_cn = "出货期(否决)"
        signal = "sell"
        confidence = 0.9
    elif ddx_5d > 0.5 and main_amount > 0:
        if ddx_5d > 1.0:
            stage = "拉升期"
            stage_cn = "拉升期"
        else:
            stage = "建仓期"
            stage_cn = "建仓期"
        signal = "buy"
        confidence = 0.6 if ddx_5d > 1.0 else 0.45
    elif ddx_5d < 0 and main_amount < 0:
        stage = "出货期"
        stage_cn = "出货期"
        signal = "sell"
        confidence = 0.55
    else:
        stage = "观望期"
        stage_cn = "观望期"
        signal = "hold"
        confidence = 0.3
    
    # === 评分 (0-100) ===
    if veto:
        score = 0
    elif stage == "拉升期":
        score = 85
    elif stage == "建仓期":
        score = 70
    elif stage == "出货期":
        score = 20
    else:
        score = 50
    
    return {
        "stage": stage,
        "cn": stage_cn,
        "signal": signal,
        "confidence": confidence,
        "score": score,
        "veto": veto,
        "veto_reason": veto_reason,
        "ddx_5d": ddx_5d,
        "ddx_10d": ddx_10d,
        "main_amount": main_amount,
    }


# ============================================================
# B2: 情绪周期 (权重 15%)
# ============================================================

def b2_analysis(data: dict) -> dict:
    """
    B2 情绪周期分析
    
    情绪系数:
        亢奋(涨停>50,炸板<15%)=1.0  /  积极(30-50)=0.8
        中性(15-30)=0.5             /  谨慎(<15)=0.3
        恐慌(<5 或 炸板>40%)=0
    """
    sentiment = data.get("sentiment", "neutral")
    
    coeff_map = {
        "亢奋": 1.0, "bullish": 1.0, "positive": 0.8,
        "积极": 0.8,
        "neutral": 0.5, "中性": 0.5,
        "谨慎": 0.3, "cautious": 0.3,
        "恐慌": 0.0, "panic": 0.0, "negative": 0.3,
    }
    
    coeff = coeff_map.get(sentiment, 0.5)
    
    # 评分
    if coeff >= 1.0:
        score = 90
    elif coeff >= 0.8:
        score = 75
    elif coeff >= 0.5:
        score = 55
    elif coeff >= 0.3:
        score = 35
    else:
        score = 10
    
    # 游资情绪周期
    is_limit_up = data.get("is_limit_up", False)
    lianban_days = data.get("lianban_days", 0)
    
    if lianban_days >= 4:
        cycle = "接力期"
    elif lianban_days >= 2:
        cycle = "接力期"
    elif is_limit_up:
        cycle = "点火期"
    elif coeff < 0.3:
        cycle = "冰点期"
    else:
        cycle = "正常"
    
    return {
        "coefficient": coeff,
        "sentiment": sentiment,
        "cycle": cycle,
        "signal": "buy" if coeff >= 0.8 else ("hold" if coeff >= 0.3 else "sell"),
        "score": score,
        "limit_up_count_hint": data.get("topic_rank", -1),
    }


# ============================================================
# C3: 量化风报比 (权重 15%)
# ============================================================

def c3_analysis(data: dict, e5_result: dict = None) -> dict:
    """
    C3 量化风报比分析
    
    包含: 突破概率评估 / 凯利仓位 / 风报比
    """
    price = data.get("price", 10)
    volatility = data.get("volatility", 0.03)
    rsi = data.get("rsi", 50)
    vol_ratio = data.get("vol_ratio", 1.0)
    
    # === 突破概率评估 (简化的 _A 模型) ===
    # 基于 RSI + 量比 + 波动率
    prob_factors = 0
    
    # RSI因子
    if 40 <= rsi <= 65:
        prob_factors += 0.35  # 安全区间
    elif rsi < 30:
        prob_factors += 0.25  # 超卖反弹
    elif rsi > 75:
        prob_factors += 0.05  # 超买风险
    
    # 量比因子
    if 1.0 <= vol_ratio <= 2.0:
        prob_factors += 0.35  # 放量健康
    elif vol_ratio > 2.0:
        prob_factors += 0.15  # 过度放量
    else:
        prob_factors += 0.20  # 缩量
    
    # 波动率因子
    if volatility < 0.03:
        prob_factors += 0.30  # 低波安全
    elif volatility < 0.05:
        prob_factors += 0.20
    else:
        prob_factors += 0.05
    
    break_prob = min(0.95, prob_factors)
    
    # === 尾部风险评估 ===
    if volatility > 0.06:
        tail_risk = "High"
        tail_score = 0
    elif volatility > 0.04:
        tail_risk = "Med"
        tail_score = 4
    else:
        tail_risk = "Low"
        tail_score = 7
    
    # === 风报比 ===
    # 简化: 基于E5的空间评估
    if e5_result and "risk_reward" in e5_result:
        risk_reward_ratio = e5_result["risk_reward"]
    else:
        support = data.get("low_60d", price * 0.9)
        resistance = data.get("high_60d", price * 1.1)
        if price > support:
            risk_reward_ratio = (resistance - price) / (price - support)
        else:
            risk_reward_ratio = 5.0
    
    expected_return_pct = min(30, max(1, (risk_reward_ratio - 1) * 5))
    stop_loss_pct = min(10, max(1, 10 / risk_reward_ratio)) if risk_reward_ratio > 0 else 10
    
    # === 凯利仓位 ===
    win_rate = max(0.25, min(0.80, break_prob))
    b = risk_reward_ratio
    if b > 0:
        kelly_fraction = max(0, (win_rate * b - (1 - win_rate)) / b)
    else:
        kelly_fraction = 0
    
    # === 信号 ===
    if break_prob >= 0.7 and risk_reward_ratio >= 2.0:
        signal = "buy"
    elif break_prob >= 0.5:
        signal = "hold"
    else:
        signal = "sell"
    
    # === 评分 (0-100) ===
    score = break_prob * 50 + (min(risk_reward_ratio, 5) / 5) * 30 + (1 - volatility / 0.1) * 20
    score = min(100, max(0, score))
    
    return {
        "break_prob": round(break_prob, 2),
        "tail_risk": tail_risk,
        "tail_score": tail_score,
        "risk_reward_ratio": round(risk_reward_ratio, 2),
        "expected_return_pct": round(expected_return_pct, 1),
        "stop_loss_pct": round(stop_loss_pct, 1),
        "win_rate": round(win_rate, 2),
        "kelly_fraction": round(kelly_fraction, 2),
        "signal": signal,
        "score": round(score, 1),
    }


# ============================================================
# D4: 统计分布 (权重 10%)
# ============================================================

def d4_analysis(data: dict) -> dict:
    """
    D4 统计分布分析
    
    简化的偏度/峰度/异常检测。
    """
    volatility = data.get("volatility", 0.03)
    vol_ratio = data.get("vol_ratio", 1.0)
    rsi = data.get("rsi", 50)
    
    # === 异常检测 ===
    anomalies = []
    if volatility > 0.08:
        anomalies.append("极高波动率")
    if vol_ratio > 3.0:
        anomalies.append("天量成交")
    if rsi > 85:
        anomalies.append("严重超买")
    if rsi < 15:
        anomalies.append("严重超卖")
    
    # === 尾部风险 ===
    if volatility > 0.06 or len(anomalies) >= 2:
        tail_risk = "High"
    elif volatility > 0.04 or len(anomalies) >= 1:
        tail_risk = "Medium"
    else:
        tail_risk = "Low"
    
    # === 评分 (0-100) ===
    if tail_risk == "Low":
        score = 75
    elif tail_risk == "Medium":
        score = 50
    else:
        score = 20
    
    return {
        "tail_risk": tail_risk,
        "anomalies": anomalies,
        "score": score,
        "signal": "hold" if tail_risk != "High" else "sell",
    }


# ============================================================
# F6: L2大单验证 (权重 15%)
# ============================================================

def f6_analysis(data: dict, need_l2: bool = False) -> dict:
    """
    F6 L2大单验证
    
    仅当 E5 判定 need_l2=True（高位/超高位）时强制调用。
    否则返回默认值 l2_mult=1.0。
    
    五维验证 (满分10):
        ① 主动买占比 (>40%=2, 25-40%=1, <25%=0)
        ② 特大单净额 (>5000万=2, 1000-5000万=1, <1000万=0)
        ③ 机构vs散户 (inst_buy=2, same=1, inst_sell=0)
        ④ 3日连续性 (3日=2, 2日=1, ≤1日=0)
        ⑤ 大单方向 (in=+1, neutral=0, out=-1)
    """
    if not need_l2:
        return {
            "confirm_level": "N/A（非高位无需L2）",
            "l2_mult": 1.0,
            "score": 10,
            "signal": "buy",
            "vetoed": False,
        }
    
    # 从输入数据提取 L2 信息
    active_buy_ratio = data.get("active_buy_ratio", 0.5)
    super_large_net = data.get("super_large_net", 0)
    inst_vs_retail = data.get("inst_vs_retail", 1.0)
    continuity_3d = data.get("continuity_3d", 1) if "continuity_3d" in data else 1
    
    # ① 主动买占比
    if active_buy_ratio > 0.4:
        score1 = 2
    elif active_buy_ratio >= 0.25:
        score1 = 1
    else:
        score1 = 0
    
    # ② 特大单净额 (万元)
    if super_large_net > 50000000:  # >5000万
        score2 = 2
    elif super_large_net >= 10000000:  # >1000万
        score2 = 1
    else:
        score2 = 0
    
    # ③ 机构vs散户
    if inst_vs_retail > 1.3:
        score3 = 2  # inst_buy
    elif inst_vs_retail >= 0.8:
        score3 = 1  # same
    else:
        score3 = 0  # inst_sell
    
    # ④ 3日连续性
    if continuity_3d >= 3:
        score4 = 2
    elif continuity_3d >= 2:
        score4 = 1
    else:
        score4 = 0
    
    # ⑤ 大单方向
    big_order_direction = 0  # 简化
    if super_large_net > 0:
        big_order_direction = 1
    elif super_large_net < 0:
        big_order_direction = -1
    
    total = score1 + score2 + score3 + score4 + big_order_direction
    
    # 判定
    if total >= 7:
        confirm_level = "强确认"
        l2_mult = 1.0
        signal = "buy"
    elif total >= 4:
        confirm_level = "中确认"
        l2_mult = 0.6
        signal = "hold"
    elif total >= 2:
        confirm_level = "弱确认"
        l2_mult = 0.3
        signal = "sell"
    else:
        confirm_level = "拒绝"
        l2_mult = 0
        signal = "sell"
    
    return {
        "confirm_level": confirm_level,
        "l2_mult": l2_mult,
        "score": total,
        "signal": signal,
        "vetoed": l2_mult == 0,
        "detail": {
            "active_buy_ratio": active_buy_ratio,
            "super_large_net": super_large_net,
            "inst_vs_retail": inst_vs_retail,
            "continuity_3d": continuity_3d,
            "big_order_direction": "in" if big_order_direction > 0 else ("out" if big_order_direction < 0 else "neutral"),
            "sub_scores": [score1, score2, score3, score4, big_order_direction],
        }
    }


# ============================================================
# _judge: 综合裁决
# ============================================================

def comprehensive_judge(
    a1: dict, b2: dict, c3: dict, d4: dict, e5: dict, f6: dict,
    data: dict
) -> dict:
    """
    六维综合裁决
    
    权重: A1=25%, B2=15%, C3=15%, D4=10%, E5=20%, F6=15%
    """
    # G0修正（如果有的话，否则不影响）
    g0_modifier = data.get("g0_score", None)
    
    # === 否决检查 ===
    if a1.get("veto"):
        return {
            "signal": "sell",
            "final_score": 0,
            "position_pct": 0,
            "sell_tendency": 1.0,
            "risk_level": "extreme",
            "forecast": {"direction": "下跌", "height_pct": -10, "days": 1, "confidence": 0.9},
            "veto_reason": a1.get("veto_reason"),
            "dimensions": {"A1": a1, "B2": b2, "C3": c3, "D4": d4, "E5": e5, "F6": f6},
        }
    
    if f6.get("vetoed", False) and e5.get("level_code", 0) >= 3:
        return {
            "signal": "sell",
            "final_score": 10,
            "position_pct": 0,
            "sell_tendency": 0.9,
            "risk_level": "high",
            "forecast": {"direction": "下跌", "height_pct": -5, "days": 2, "confidence": 0.7},
            "veto_reason": f"E5+F6联合否决: 高位({e5.get('level')})+L2拒绝",
            "dimensions": {"A1": a1, "B2": b2, "C3": c3, "D4": d4, "E5": e5, "F6": f6},
        }
    
    # === 加权评分 ===
    weighted = (
        a1.get("score", 50) * 0.25 +
        b2.get("score", 50) * 0.15 +
        c3.get("score", 50) * 0.15 +
        d4.get("score", 50) * 0.10 +
        e5.get("score", 10) / 20 * 100 * 0.20 +  # E5归一化到0-100
        f6.get("score", 5) / 10 * 100 * 0.15     # F6归一化到0-100
    )
    
    # G0修正（从各维度匀3%）
    if g0_modifier is not None:
        # G0评分影响各维度权重
        pass
    
    final_score = round(weighted, 1)
    
    # === 方向判定 ===
    if final_score >= 70:
        direction = "up"
        signal = "buy"
    elif final_score >= 55:
        direction = "flat"
        signal = "hold"
    elif final_score >= 40:
        direction = "flat"
        signal = "hold_watch"
    else:
        direction = "down"
        signal = "sell"
    
    # === 仓位计算 ===
    emotion_coeff = b2.get("coefficient", 0.5)
    # 阶段系数从 topic_rank 反推（简化）
    stage_coeff = 0.5  # 默认中性
    base_pct = emotion_coeff * stage_coeff * 0.30
    
    # ceiling
    e5_ceiling = e5.get("ceiling", 0.20)
    l2_mult = f6.get("l2_mult", 1.0)
    vol_mult = e5.get("vol_mult", 1.0)
    ceiling = min(0.30, e5_ceiling * l2_mult * vol_mult)
    
    # 情绪调节（仅低位/中低位）
    level_code = e5.get("level_code", 2)
    if level_code <= 1:
        if emotion_coeff >= 0.8:
            ceiling = min(0.30, ceiling * 1.2)
        elif emotion_coeff <= 0.3:
            ceiling *= 0.5
    
    position_pct = round(min(base_pct, ceiling), 3)
    
    # === 卖出倾向 ===
    sell_tendency = 0.0
    
    if a1.get("stage") == "出货期":
        sell_tendency += 0.30
    if a1.get("stage") == "砸盘期":
        sell_tendency += 0.40
    if e5.get("level_code", 0) >= 4:
        sell_tendency += 0.30
    elif e5.get("level_code", 0) == 3:
        sell_tendency += 0.15
    if f6.get("signal") == "sell":
        sell_tendency += 0.30
    if b2.get("coefficient", 0.5) <= 0.3:
        sell_tendency += 0.20
    
    sell_tendency = min(1.0, sell_tendency)
    
    # === 风险等级 ===
    if final_score >= 75 and level_code <= 1:
        risk_level = "low"
    elif final_score >= 60 and level_code <= 2:
        risk_level = "medium_low"
    elif final_score >= 50 and level_code >= 3:
        risk_level = "medium"
    elif level_code >= 4:
        risk_level = "high"
    else:
        risk_level = "medium"
    
    # === 走势预估 ===
    if signal == "buy" and final_score >= 75:
        forecast = {"direction": "强势看多", "height_pct": 10, "days": 3, "confidence": 0.80}
    elif signal == "buy":
        forecast = {"direction": "偏多", "height_pct": 5, "days": 2, "confidence": 0.65}
    elif signal == "hold":
        forecast = {"direction": "震荡", "height_pct": 2, "days": 1, "confidence": 0.50}
    elif signal == "hold_watch":
        forecast = {"direction": "震荡偏空", "height_pct": -3, "days": 2, "confidence": 0.55}
    else:
        forecast = {"direction": "偏空", "height_pct": -5, "days": 2, "confidence": 0.70}
    
    return {
        "signal": signal,
        "direction": direction,
        "final_score": final_score,
        "position_pct": position_pct,
        "sell_tendency": round(sell_tendency, 2),
        "risk_level": risk_level,
        "forecast": forecast,
        "dimensions": {"A1": a1, "B2": b2, "C3": c3, "D4": d4, "E5": e5, "F6": f6},
        "_data_source": data.get("_data_source", {}),
    }


# ============================================================
# 主入口
# ============================================================

def analyze(data: dict, klines: list = None) -> dict:
    """
    六维博弈引擎完整分析
    
    Args:
        data: 输入JSON字典（与原始 game_theory_engine 相同格式）
        klines: 可选的K线数据列表，用于E5计算
    
    Returns:
        综合裁决字典
    """
    # E5 位置分析（使用K线或输入数据中的指标）
    if klines and len(klines) >= 20:
        price = data.get("price", klines[-1]["close"])
        e5 = e5_full_analysis(klines, price)
    else:
        # 回退到输入数据中的 E5 相关字段
        price = data.get("price", 10)
        band_pct = data.get("E5_position_pct", 50)
        rsi_val = data.get("rsi", 50)
        from core.math_utils import position_level, volatility_level
        
        level_name, level_code, ceiling, need_l2 = position_level(band_pct, rsi_val)
        vol_ratio_val = data.get("volatility", 0.03) / 0.02  # 近似
        vol_level, vol_mult = volatility_level(vol_ratio_val)
        
        e5 = {
            "level": level_name,
            "level_code": level_code,
            "ceiling": ceiling,
            "volatility": vol_level,
            "vol_ratio": round(vol_ratio_val, 2),
            "vol_mult": vol_mult,
            "need_l2": need_l2,
            "score": 10,  # 默认中位
            "mp": 5, "bp": 5, "rv": 5, "vd": 5, "sa": 5,
            "rsi": rsi_val,
        }
    
    # 六维分析
    a1 = a1_analysis(data)
    b2 = b2_analysis(data)
    c3 = c3_analysis(data, e5)
    d4 = d4_analysis(data)
    f6 = f6_analysis(data, e5.get("need_l2", False))
    
    # 综合裁决
    result = comprehensive_judge(a1, b2, c3, d4, e5, f6, data)
    
    # 卖出倾向 → 操作建议
    st = result["sell_tendency"]
    if st >= 0.6:
        result["action"] = "清仓"
        result["action_ratio"] = 1.0
    elif st >= 0.4:
        result["action"] = "减仓"
        result["action_ratio"] = 0.5
    elif st >= 0.2:
        result["action"] = "持有观察"
        result["action_ratio"] = 0.0
    else:
        result["action"] = "可加仓"
        result["action_ratio"] = -0.3  # 负值表示加仓
    
    return result


def main():
    parser = argparse.ArgumentParser(description="六维博弈引擎 V5.8.1 (开源版)")
    parser.add_argument("--input", "-i", required=True, help="JSON输入文件路径")
    parser.add_argument("--kline", "-k", help="K线数据JSON文件路径（用于E5分析）")
    parser.add_argument("--output", "-o", help="输出JSON文件路径")
    args = parser.parse_args()
    
    with open(args.input, 'r') as f:
        data = json.load(f)
    
    klines = None
    if args.kline:
        with open(args.kline, 'r') as f:
            kline_data = json.load(f)
        if isinstance(kline_data, list):
            klines = kline_data
        elif isinstance(kline_data, dict) and 'data' in kline_data:
            klines = kline_data['data']
    
    result = analyze(data, klines)
    
    output = json.dumps(result, ensure_ascii=False, indent=2)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"结果已写入 {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
