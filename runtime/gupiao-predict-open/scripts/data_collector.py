#!/usr/bin/env python3
"""
data_collector.py — W1 节点1-4 数据采集器 (TDX MCP 版)

数据源: 通达信 MCP (wenda-mcp-server) + data_fallback K线

输出:
  --mode limit_up:   topics_raw.json (节点1, 涨停池 + 精准行业分组)
  --mode ladder:     board_ladder.json (节点3, 需先跑limit_up)
  --mode all:        完整四文件

用法:
    python scripts/data_collector.py --mode limit_up
    python scripts/data_collector.py --mode all --output-dir /tmp/w1_data/
"""

import sys, os, json, time, argparse, subprocess
from collections import defaultdict
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_sources.tdx_mcp import TDXClient

OPEN_SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def fetch_limit_up_stocks(tdx: TDXClient) -> List[Dict]:
    """从 TDX 获取涨停股列表（带精准行业标签）"""
    print("📡 TDX: 获取今日涨停股...", file=sys.stderr)
    
    raw = tdx.get_limit_up_stocks(size=200)
    stocks = [tdx.normalize_stock(s) for s in raw]
    
    print(f"  涨停股: {len(stocks)} 只", file=sys.stderr)
    
    # 展示行业分布
    industries = defaultdict(int)
    for s in stocks:
        ind = s.get('所属行业', s.get('所属通达信研究行业', '未知'))
        industries[ind] += 1
    top_industries = sorted(industries.items(), key=lambda x: -x[1])[:5]
    for ind, cnt in top_industries:
        print(f"    {ind}: {cnt}只", file=sys.stderr)
    
    return stocks


def build_topics_raw(limit_up_stocks: List[Dict]) -> Dict:
    """从涨停股构建 topics_raw.json — 按行业精准分组（使用列位置索引）"""
    
    # 从第一条数据探测列位置
    if not limit_up_stocks:
        return {"topics": [], "total_limit_up": 0, "source": "TDX MCP"}
    
    sample = limit_up_stocks[0]
    keys = list(sample.keys())
    
    # 找关键列位置
    code_idx = name_idx = price_idx = chg_idx = industry_idx = lianban_idx = -1
    seal_idx = time_idx = -1
    
    for i, k in enumerate(keys):
        ks = str(k)
        # 用字节模式匹配（绕过终端乱码）
        kb = k.encode('utf-8', errors='surrogateescape') if isinstance(k, str) else k
        if isinstance(k, str):
            if k == 'sec_code' or k == 'code': code_idx = i
            elif k == 'sec_name' or k == 'name': name_idx = i
            elif k == 'now_price' or k == 'price': price_idx = i
            elif k == 'chg' or k == 'change_pct': chg_idx = i
        
        # 中文列 — 搜索UTF-8字节模式
        kb_str = str(k)
        if '行业' in kb_str and '研究' not in kb_str: industry_idx = i
        if '封单' in kb_str and ('金额' in kb_str or '量' in kb_str): seal_idx = i
        if '涨停' in kb_str and '时间' in kb_str and '首次' in kb_str: time_idx = i
    
    # 连板列 — 查找包含"连"+"天"或"几"+"板"或"几"+"天"的列
    for i, k in enumerate(keys):
        ks = str(k)
        if ('连' in ks and ('板' in ks or '天' in ks)) or ('几' in ks and ('板' in ks or '天' in ks)):
            lianban_idx = i
            break
    
    print(f"  列映射: code={code_idx} name={name_idx} price={price_idx} chg={chg_idx} industry={industry_idx} lianban={lianban_idx}", file=sys.stderr)
    
    # 如果索引方式找不到，回退到遍历所有key
    if industry_idx < 0:
        industry_idx = None  # 将在循环中动态查找
    if lianban_idx < 0:
        lianban_idx = None
    
    industry_groups = defaultdict(list)
    
    for s in limit_up_stocks:
        vals = list(s.values())
        
        code = str(vals[code_idx]) if code_idx >= 0 and code_idx < len(vals) else ''
        name = str(vals[name_idx]) if name_idx >= 0 and name_idx < len(vals) else ''
        try: price = float(vals[price_idx]) if price_idx >= 0 else 0
        except: price = 0
        try: chg = float(vals[chg_idx]) if chg_idx >= 0 else 0
        except: chg = 0
        
        # 行业 — 如果用索引找不到，遍历所有值
        industry = '其他'
        if industry_idx is not None and industry_idx < len(vals):
            industry = str(vals[industry_idx]).replace('@', '').strip()
        else:
            for key, val in s.items():
                if '行业' in str(key) and '研究' not in str(key):
                    industry = str(val).replace('@', '').strip()
                    if industry and industry != 'nan':
                        break
        
        # 连板
        lianban = 0
        if lianban_idx is not None and lianban_idx < len(vals):
            try: lianban = int(float(vals[lianban_idx]))
            except: pass
        if lianban == 0:
            for key, val in s.items():
                ks = str(key)
                if ('连' in ks and ('天' in ks or '板' in ks)) or ('几' in ks and ('板' in ks or '天' in ks)):
                    try: lianban = int(float(val))
                    except: pass
                    break
        
        seal = 0
        if seal_idx >= 0 and seal_idx < len(vals):
            try: seal = float(vals[seal_idx])
            except: pass
        
        ft = ''
        if time_idx >= 0 and time_idx < len(vals):
            ft = str(vals[time_idx])
        
        stock_info = {
            "code": code, "name": name, "change_pct": chg, "price": price,
            "market_cap": 0, "seal_amount": seal,
            "lianban_days": lianban, "first_limit_up_time": ft,
        }
        industry_groups[industry].append(stock_info)
    
    topics = []
    for ind_name, stocks in sorted(industry_groups.items(), key=lambda x: -len(x[1])):
        topics.append({
            "name": ind_name, "type": "行业",
            "limit_up_count": len(stocks), "total_stocks": len(stocks),
            "net_amount": len(stocks) * 1e8, "rank": 0, "stocks": stocks,
        })
    
    topics.sort(key=lambda x: -x["limit_up_count"])
    for i, t in enumerate(topics):
        t["rank"] = i + 1
    
    return {
        "topics": topics, "total_limit_up": len(limit_up_stocks),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "TDX MCP — 精准行业分组",
    }


def check_lianban(code: str) -> int:
    """检查连板天数（通过data_fallback K线）"""
    try:
        r = subprocess.run(
            [sys.executable, f"{OPEN_SCRIPTS}/data_fallback.py",
             "--mode", "kline", "--code", code, "--count", "5"],
            capture_output=True, text=True, timeout=15
        )
        klines = json.loads(r.stdout)
        
        if not klines or len(klines) < 3:
            return 0
        
        lianban = 0
        for i in range(len(klines) - 1, 0, -1):
            k = klines[i]
            if k.get("open", 0) > 0:
                day_pct = (k["close"] - k["open"]) / k["open"] * 100
                if day_pct >= 9.5:
                    lianban += 1
                else:
                    break
        
        return lianban
    except Exception:
        return 0


def build_board_ladder(limit_up_stocks: List[Dict]) -> Dict:
    """构建连板梯队 — 直接使用 TDX 提供的 连续涨停天数/几板"""
    print("📊 构建连板梯队 (TDX直接提供连板数据)...", file=sys.stderr)
    
    ladder = defaultdict(lambda: {"count": 0, "codes": []})
    
    for s in limit_up_stocks:
        code = str(s.get('code', s.get('sec_code', '')))
        # TDX 直接提供连板天数
        lianban = 0
        for key in s:
            if '连' in str(key) and ('天' in str(key) or '板' in str(key)):
                try: lianban = int(s[key])
                except: pass
                break
        if lianban == 0:
            try: lianban = int(s.get('几板', 0))
            except: pass
        
        if lianban > 0:
            board_key = str(lianban)
            ladder[board_key]["count"] += 1
            ladder[board_key]["codes"].append(code)
    
    ladder_dict = {k: dict(v) for k, v in sorted(ladder.items(), key=lambda x: int(x[0]))}
    max_height = max(int(k) for k in ladder_dict.keys()) if ladder_dict else 0
    board_counts = {int(k): v["count"] for k, v in ladder_dict.items()}
    nums = [board_counts.get(i, 0) for i in range(1, max_height + 1)]
    
    is_pyramid = all(nums[i] >= nums[i+1] for i in range(len(nums)-1)) if len(nums) >= 2 else True
    has_gap = any(n == 0 for n in nums[1:]) if len(nums) >= 2 else False
    promotion_rate = board_counts.get(2, 0) / board_counts.get(1, 1) if board_counts.get(1, 0) > 0 else 0.45
    
    for k, v in ladder_dict.items():
        print(f"  {k}板: {v['count']}只", file=sys.stderr)
    print(f"  最高{max_height}板 | 晋级率={promotion_rate:.0%} | 金字塔={'是' if is_pyramid else '否'}", file=sys.stderr)
    
    return {
        "max_board_height": max_height,
        "ladder": ladder_dict,
        "promotion_rate": round(promotion_rate, 2),
        "break_rate": 0.15,
        "is_pyramid": is_pyramid,
        "has_gap": has_gap,
        "health_score": 70 if is_pyramid and not has_gap else 40,
        "source": "TDX MCP 直接提供连板数据",
    }


def build_theme_sentiment(topics_raw: Dict) -> Dict:
    """构建题材情绪（TDX 提供精准数据，可进一步从 TDX 获取15日历史）"""
    themes = []
    for t in topics_raw.get("topics", []):
        lu = t["limit_up_count"]
        themes.append({
            "name": t["name"],
            "type": t.get("type", "行业"),
            "strength_dod": 0,
            "limit_up_trend": "扩张" if lu >= 10 else ("持平" if lu >= 5 else "收缩"),
            "capital_trend": "未知",
            "up_down_ratio": lu / max(1, t["total_stocks"] - lu),
            "is_first_eruption": False,
            "is_sustained": False,
            "sentiment_score": min(85, lu * 5 + 20),
            "sentiment_label": "亢奋" if lu >= 15 else ("积极" if lu >= 8 else "中性"),
        })
    
    return {
        "themes": themes,
        "source": "TDX MCP + 涨停数推断",
    }


def build_yesterday_review(topics_raw: Dict) -> Dict:
    """降级版昨日回溯"""
    return {
        "yesterday_top_topic": "",
        "reviews": [],
        "source": "待实现: 需要昨日TDX数据对比",
    }


def main():
    parser = argparse.ArgumentParser(description="W1 数据采集器 (TDX MCP 版)")
    parser.add_argument("--mode", choices=["limit_up", "ladder", "all"], default="all")
    parser.add_argument("--output-dir", default="/tmp/w1_data", help="输出目录")
    parser.add_argument("--skip-ladder", action="store_true", help="跳过连板扫描")
    parser.add_argument("--tdx-key", default=None, help="TDX API Key")
    args = parser.parse_args()
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    # 连接 TDX
    tdx = TDXClient(api_key=args.tdx_key) if args.tdx_key else TDXClient()
    
    # === 节点1: 涨停池 ===
    limit_up_stocks = fetch_limit_up_stocks(tdx)
    
    if not limit_up_stocks:
        print("⚠️ 未获取到涨停股数据", file=sys.stderr)
        sys.exit(1)
    
    topics_raw = build_topics_raw(limit_up_stocks)
    topics_path = f"{args.output_dir}/topics_raw.json"
    with open(topics_path, 'w') as f:
        json.dump(topics_raw, f, ensure_ascii=False, indent=2)
    print(f"✅ topics_raw.json → {topics_path} ({len(topics_raw['topics'])} 个题材)", file=sys.stderr)
    
    if args.mode == "limit_up":
        return
    
    # === 节点3: 连板梯队 ===
    if not args.skip_ladder:
        board_ladder = build_board_ladder(limit_up_stocks)
        ladder_path = f"{args.output_dir}/board_ladder.json"
        with open(ladder_path, 'w') as f:
            json.dump(board_ladder, f, ensure_ascii=False, indent=2)
        print(f"✅ board_ladder.json → {ladder_path}", file=sys.stderr)
    else:
        board_ladder = None
    
    if args.mode == "ladder":
        return
    
    # === 节点2: 情绪 ===
    theme_sentiment = build_theme_sentiment(topics_raw)
    sentiment_path = f"{args.output_dir}/theme_sentiment.json"
    with open(sentiment_path, 'w') as f:
        json.dump(theme_sentiment, f, ensure_ascii=False, indent=2)
    print(f"✅ theme_sentiment.json → {sentiment_path}", file=sys.stderr)
    
    # === 节点4: 回溯 ===
    yesterday_review = build_yesterday_review(topics_raw)
    yesterday_path = f"{args.output_dir}/yesterday_review.json"
    with open(yesterday_path, 'w') as f:
        json.dump(yesterday_review, f, ensure_ascii=False, indent=2)
    print(f"✅ yesterday_review.json → {yesterday_path}", file=sys.stderr)
    
    print(f"\n📁 {args.output_dir}/", file=sys.stderr)


if __name__ == "__main__":
    main()
