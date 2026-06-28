#!/usr/bin/env python3
"""
e5_position — E5 位置波动率分析 (CLI入口)

兼容开源 data_fallback.py 的 K线输出格式。

用法:
    python scripts/e5_position.py --kline <kline.json> --price <当前价>
    python scripts/e5_position.py --code 000001 --price 10.23
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入开源 data_fallback
OPEN_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if OPEN_SCRIPTS not in sys.path:
    sys.path.insert(0, OPEN_SCRIPTS)

import argparse
import json
import subprocess

from core.math_utils import e5_full_analysis


def fetch_klines(code: str, count: int = 60) -> list:
    """通过开源 data_fallback 获取K线"""
    result = subprocess.run(
        [sys.executable, f"{OPEN_SCRIPTS}/data_fallback.py",
         "--mode", "kline", "--code", code, "--count", str(count)],
        capture_output=True, text=True, timeout=30
    )
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description="E5 位置波动率分析 (开源版)")
    parser.add_argument("--kline", help="K线数据JSON文件路径")
    parser.add_argument("--code", help="股票代码（自动获取K线）")
    parser.add_argument("--count", type=int, default=60, help="K线数量（--code 模式）")
    parser.add_argument("--price", type=float, help="当前价格（可选，默认取K线最新收盘价）")
    parser.add_argument("--json", action="store_true", help="输出原始JSON")
    args = parser.parse_args()
    
    if args.kline:
        with open(args.kline, 'r') as f:
            klines = json.load(f)
        if isinstance(klines, dict):
            klines = klines.get('data', klines.get('klines', []))
        if not isinstance(klines, list):
            print("错误: K线数据格式不正确")
            sys.exit(1)
    elif args.code:
        klines = fetch_klines(args.code, args.count)
    else:
        print("错误: 需要 --kline 或 --code 参数")
        sys.exit(1)
    
    if not klines:
        print("错误: 无法获取K线数据")
        sys.exit(1)
    
    price = args.price or klines[-1]['close']
    result = e5_full_analysis(klines, price)
    
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        from core.formatters import format_e5
        print(format_e5(result))


if __name__ == "__main__":
    main()
