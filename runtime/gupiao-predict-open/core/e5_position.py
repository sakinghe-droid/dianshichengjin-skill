"""
e5_position.py — E5 位置波动率引擎

纯Python实现，开源 CLI 接口和输出格式。

用法:
    python core/e5_position.py --kline <kline.json> --price <当前价>
    python core/e5_position.py --kline <kline.json> --price <当前价> --json-output
"""

import json
import sys
import os
import argparse

# 允许从项目根或 scripts/ 目录调用
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.math_utils import e5_full_analysis


def load_kline(path: str) -> list:
    """加载K线JSON文件（兼容 data_fallback 输出格式）"""
    with open(path, 'r') as f:
        data = json.load(f)
    
    # data_fallback 返回的是数组
    if isinstance(data, list):
        return data
    # 有些格式包装在 data 字段中
    if isinstance(data, dict):
        if 'data' in data:
            return data['data']
        if 'klines' in data:
            return data['klines']
    
    return data


def main():
    parser = argparse.ArgumentParser(description="E5 位置波动率分析")
    parser.add_argument("--kline", required=True, help="K线数据JSON文件路径")
    parser.add_argument("--price", type=float, required=True, help="当前价格")
    parser.add_argument("--json-output", action="store_true", help="纯JSON输出")
    args = parser.parse_args()
    
    klines = load_kline(args.kline)
    result = e5_full_analysis(klines, args.price)
    
    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 人类可读输出
        if "error" in result:
            print(f"❌ {result['error']}")
            sys.exit(1)
        
        print(f"=== E5 位置波动率分析 ===")
        print(f"位置评级: {result['level']} (level_code={result['level_code']})")
        print(f"仓位天花板: {result['ceiling']*100:.0f}% ({result['ceiling']:.2f})")
        print(f"波动率评级: {result['volatility']} (倍数={result['vol_ratio']}, 乘数={result['vol_mult']})")
        print(f"是否需要L2验证: {'是' if result['need_l2'] else '否'}")
        print(f"E5综合评分: {result['score']}/20")
        print(f"")
        print(f"子指标明细:")
        print(f"  均线偏离(MP): {result['mp']}/10  (MA20偏离={result['ma20_dev']:+.2f}%)")
        print(f"  波段位置(BP): {result['bp']}/10  (位置={result['band_position_pct']:.1f}%)")
        print(f"  RSI评分(RV):  {result['rv']}/10  (RSI={result['rsi']:.1f})")
        print(f"  量价偏离(VD): {result['vd']}/10  (量比={result['vol_ratio_vs_20d']:.2f})")
        print(f"  空间评估(SA): {result['sa']}/10  (支撑={result['support']:.2f}, 压力={result['resistance']:.2f}, 盈亏比={result['risk_reward']:.2f})")
        print(f"")
        print(f"原始数据:")
        print(f"  MA20={result['ma20']:.2f}, MA60={result.get('ma60')}")
        print(f"  年化波动率={result['annual_volatility']*100:.2f}%")
        print(f"  当日振幅={result['amplitude_today']:.2f}%")


if __name__ == "__main__":
    main()
