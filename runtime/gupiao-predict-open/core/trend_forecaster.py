"""
trend_forecaster.py — 双引擎共识仲裁（纯Python实现）

9场景共识矩阵 + merged_score + reliability + 走势预判

用法:
    python core/trend_forecaster.py --mode consensus --six_dim_score 82 --classic_score 75 --base_position 1.5
    python core/trend_forecaster.py --mode forecast --six_dim_score 82 --classic_score 75
"""

import argparse
import json
import sys


# ============================================================
# 共识仲裁（与六维共识规则一致，6场景版本）
# ============================================================

def consensus_arbitration(six_dim_score: float, classic_score: float, base_position: float) -> dict:
    """
    双引擎共识仲裁
    
    Args:
        six_dim_score: 六维评分 (0-100)
        classic_score: 经典评分 (0-100)
        base_position: 基础仓位（成数，如 1.5 = 1.5成）
    
    Returns:
        共识结果字典
    """
    # merged_score
    merged = (six_dim_score + classic_score) / 2.0
    
    # 9场景 → 实际6场景
    if six_dim_score >= 70 and classic_score >= 70:
        consensus_type = "高共识看多"
        consensus_level = "dual_confirm"
        reliability = 0.92
        position_mult = 1.2
        signal = "strong_buy"
    elif six_dim_score >= 70 and classic_score >= 40:
        consensus_type = "偏多共识"
        consensus_level = "partial_confirm"
        reliability = 0.78
        position_mult = 1.0
        signal = "buy"
    elif six_dim_score >= 70:  # classic < 40
        consensus_type = "背离（六强经弱）"
        consensus_level = "divergence"
        reliability = 0.45
        position_mult = 0.5
        signal = "reduce_buy"
    elif classic_score >= 70 and six_dim_score < 40:
        consensus_type = "背离（经强六弱）"
        consensus_level = "divergence"
        reliability = 0.35
        position_mult = 0.3
        signal = "light_buy"
    elif six_dim_score < 40 and classic_score < 40:
        consensus_type = "高共识看空"
        consensus_level = "dual_confirm"
        reliability = 0.90
        position_mult = 0.0
        signal = "sell_all"
    else:  # 40-69 区间
        consensus_type = "分歧"
        consensus_level = "divergence"
        reliability = 0.50
        position_mult = 0.7
        signal = "hold"
    
    final_position = round(base_position * position_mult, 1)
    
    return {
        "consensus_type": consensus_type,
        "consensus_level": consensus_level,
        "reliability": reliability,
        "final_position_pct": final_position,
        "signal": signal,
        "merged_score": round(merged, 1),
        "position_mult": position_mult,
        "dispute_flags": {
            "risk_dispute": abs(six_dim_score - classic_score) > 30,
            "direction_dispute": (six_dim_score >= 70) != (classic_score >= 70) if six_dim_score != classic_score else False,
        }
    }


def forecast(six_dim_score: float, classic_score: float) -> dict:
    """
    走势预判（基于 merged_score）
    """
    merged = (six_dim_score + classic_score) / 2.0
    
    if merged >= 85:
        direction = "强势上涨"
        height_range = [15, 30]
        days_range = [3, 5]
        confidence = 0.85
    elif merged >= 70:
        direction = "温和上涨"
        height_range = [8, 15]
        days_range = [2, 3]
        confidence = 0.75
    elif merged >= 55:
        direction = "震荡偏多"
        height_range = [3, 8]
        days_range = [1, 2]
        confidence = 0.60
    elif merged >= 40:
        direction = "震荡"
        height_range = [-3, 3]
        days_range = [1, 1]
        confidence = 0.40
    elif merged >= 25:
        direction = "震荡偏空"
        height_range = [-3, -8]
        days_range = [1, 2]
        confidence = 0.55
    else:
        direction = "下跌"
        height_range = [-15, -8]
        days_range = [2, 3]
        confidence = 0.70
    
    return {
        "direction": direction,
        "height_range": height_range,
        "days_range": days_range,
        "confidence": confidence,
        "merged_score": round(merged, 1),
    }


def main():
    parser = argparse.ArgumentParser(description="走势预判 + 双引擎共识仲裁 (开源版)")
    parser.add_argument("--mode", choices=["consensus", "forecast"], default="consensus")
    parser.add_argument("--six_dim_score", type=float, required=True)
    parser.add_argument("--classic_score", type=float, required=True)
    parser.add_argument("--base_position", type=float, default=1.0)
    args = parser.parse_args()
    
    if args.mode == "consensus":
        result = consensus_arbitration(args.six_dim_score, args.classic_score, args.base_position)
    else:
        result = forecast(args.six_dim_score, args.classic_score)
    
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
