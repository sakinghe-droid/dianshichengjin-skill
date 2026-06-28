#!/usr/bin/env python3
"""
w2w3_pipeline.py — W2 最强出击 / W3 切片出击 编排器

W2: mainline -m run → -m p → -m g → position
W3: 多题材并行 mainline -m run → per-topic -m p → merge → -m g

用法:
    python orchestrators/w2w3_pipeline.py --mode w2 --topics topics.json
    python orchestrators/w2w3_pipeline.py --mode w3 --topics topics.json
"""

import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrators.mainline_engine import run_quadrant_analysis, locate_leaders, batch_game_verify
from core.position import calculate_position


def run_w2(topics: list, sentiment_data=None, ladder_data=None, yesterday_data=None) -> dict:
    """W2: 最强出击"""
    # [5] 核心题材推演
    mainline = run_quadrant_analysis(topics, sentiment_data, ladder_data, yesterday_data)
    if not mainline["has_mainline"]:
        return {"error": "无主线，无法执行W2最强出击", "mainline": mainline}
    
    # [8] 龙头定位 — 从主线题材中找龙头
    all_candidates = []
    for topic_name in mainline["mainline_topics"]:
        topic_data = next((t for t in topics if t.get("name") == topic_name), None)
        if topic_data:
            all_candidates.extend(topic_data.get("stocks", []))
    
    leaders = locate_leaders(all_candidates) if all_candidates else []
    top_leaders = leaders[:5]
    
    # [11] 博弈验证
    verified = batch_game_verify(top_leaders)
    
    # [12] 仓位
    for i, v in enumerate(verified):
        pos = calculate_position(emotion="积极", stage="主升期", e5_level_code=2)
        weight = [0.50, 0.30, 0.20][i] if i < 3 else 0
        v["suggested_pct"] = round(pos["final_pct"] * weight, 4)
        v["suggested_amount"] = round(100000 * pos["final_pct"] * weight, 2)
    
    return {
        "mode": "W2-最强出击",
        "mainline": mainline,
        "leaders": leaders[:10],
        "verified_top5": verified,
    }


def run_w3(topics: list, sentiment_data=None, ladder_data=None, yesterday_data=None) -> dict:
    """W3: 切片出击 — 多题材并行"""
    if not topics:
        return {"error": "无题材数据"}
    
    # 对TOP5题材分别找龙头
    ranked_topics = sorted(topics, key=lambda x: -x.get("limit_up_count", 0))[:5]
    
    all_candidates = []
    for t in ranked_topics:
        stocks = t.get("stocks", [])
        leaders = locate_leaders(stocks)[:5]
        for l in leaders:
            l["topic"] = t.get("name", "")
        all_candidates.extend(leaders)
    
    # 去重(同股多题材取最高分)
    best = {}
    for c in all_candidates:
        code = c.get("code","")
        if code not in best or c["score"] > best[code]["score"]:
            best[code] = c
    
    unique = sorted(best.values(), key=lambda x: -x["score"])[:20]
    
    # 批量博弈
    verified = batch_game_verify(unique)
    
    return {
        "mode": "W3-切片出击",
        "topics_scanned": len(ranked_topics),
        "cross_topic_candidates": len(unique),
        "verified_top20": verified,
    }


def main():
    p = argparse.ArgumentParser(description="W2/W3 编排器")
    p.add_argument("--mode", choices=["w2","w3"], default="w2")
    p.add_argument("--topics", required=True, help="topics_raw.json")
    p.add_argument("-o", "--output", help="输出文件")
    args = p.parse_args()
    
    with open(args.topics) as f:
        topics_data = json.load(f)
    
    topics = topics_data if isinstance(topics_data, list) else topics_data.get("topics", topics_data.get("data", []))
    
    if args.mode == "w2":
        result = run_w2(topics)
    else:
        result = run_w3(topics)
    
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
