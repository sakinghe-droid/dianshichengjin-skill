#!/usr/bin/env python3
"""
pre_market_scan.py — 盘前宏观扫描（降级模式）

开源盘前扫描协议实现。
免费HTTP源: Sina全市场 + 腾讯实时行情/K线。
当 TDX MCP 不可用时自动降级到此模式。

5步采集 (约15秒):
  1. 健康检查 (data_fallback)
  2. 五大指数行情 (腾讯 gtimg.cn)
  3. 全市场涨跌分布 (Sina 分页)
  4. 热点板块识别 (TOP50关键词匹配)
  5. 指数趋势分析 (腾讯30日K线)

用法:
    python scripts/pre_market_scan.py
    python scripts/pre_market_scan.py --json-output
"""

import sys, os, json, time, requests, subprocess
from collections import defaultdict
from typing import Dict, List

OPEN_SCRIPTS = os.path.dirname(os.path.abspath(__file__))

# 题材关键词 (pre-market-scan-protocol.md 方案B)
TOPIC_KEYWORDS = {
    "芯片半导体": ["微", "芯", "半导", "集成", "电路", "存储", "韦尔", "兆易", "圣邦", "中芯"],
    "光电/激光":   ["光电", "激光", "光韵达", "杰普特", "锐科", "大族"],
    "AI/科技":     ["科技", "智能", "数据", "数字", "互联", "软件", "信息", "网络", "通信", "算力"],
    "新材料":      ["新材", "材料", "聚石", "世华", "斯迪克", "道恩", "沃特"],
    "消费电子":    ["信维", "三环", "汇成", "立讯", "歌尔", "蓝思", "京东方"],
    "新能源":      ["新能", "锂", "光伏", "风", "储能", "电池", "充电", "阳光", "隆基", "通威"],
    "汽车":        ["汽", "车", "比亚迪", "长城", "长安", "上汽", "广汽", "江淮", "塞力斯"],
    "医药":        ["药", "医", "生物", "恒瑞", "药明", "迈瑞", "爱尔", "泰格"],
    "机器人/自动化": ["机器", "自动化", "减速", "伺服", "汇川", "埃斯顿", "绿的"],
    "稀土永磁":    ["稀土", "永磁", "磁材", "北方稀土", "中科三环", "金力"],
    "军工":        ["军工", "航", "卫星", "导弹", "雷达", "中航", "航天", "兵器"],
    "金融":        ["银行", "证券", "保险", "金融", "信托", "招商", "中信", "平安"],
    "地产基建":    ["地产", "建筑", "建材", "水泥", "万科", "保利", "海螺"],
    "消费":        ["食品", "饮料", "白酒", "家电", "旅游", "茅台", "五粮液", "美的", "格力"],
    "电力":        ["电力", "电网", "发电", "核电", "长江电力", "华能", "国电"],
}


def health_check() -> dict:
    """Step 1: 数据源健康检查"""
    r = subprocess.run([sys.executable, f"{OPEN_SCRIPTS}/data_fallback.py",
        "--mode","health"], capture_output=True, text=True, timeout=15)
    return json.loads(r.stdout)


def fetch_index_quotes() -> dict:
    """Step 2: 五大指数行情 (腾讯)"""
    codes = "sh000001,sz399001,sz399006,sz399005,sz399678"
    url = f"http://qt.gtimg.cn/q={codes}"
    
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        r.encoding = 'gbk'
        text = r.text
    except:
        return {}
    
    indices = {}
    for line in text.strip().split('\n'):
        if not line.strip() or '=' not in line:
            continue
        parts = line.split('~')
        if len(parts) < 5:
            continue
        
        name = parts[1]
        price = float(parts[3]) if parts[3] else 0
        prev_close = float(parts[4]) if parts[4] else price
        change_pct = (price - prev_close) / prev_close * 100 if prev_close else 0
        
        indices[name] = {
            "price": round(price, 2),
            "change_pct": round(change_pct, 2),
            "prev_close": round(prev_close, 2),
        }
    
    return indices


def fetch_market_breadth() -> dict:
    """Step 3: 全市场涨跌分布 (Sina 双向采样)"""
    all_stocks = []
    
    # 取涨幅前500 (asc=0)
    for page in range(1, 6):
        url = (
            f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            f"Market_Center.getHQNodeData?page={page}&num=100"
            f"&sort=changepercent&asc=0&node=hs_a&_s_r_a=init"
        )
        try:
            r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            batch = json.loads(r.text)
            if not batch: break
            all_stocks.extend(batch)
        except: break
    
    # 取跌幅前200 (asc=1, 跌的最多的在前面)
    for page in range(1, 3):
        url = (
            f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            f"Market_Center.getHQNodeData?page={page}&num=100"
            f"&sort=changepercent&asc=1&node=hs_a&_s_r_a=init"
        )
        try:
            r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            batch = json.loads(r.text)
            if not batch: break
            all_stocks.extend(batch)
        except: break
    
    if not all_stocks:
        return {"error": "Sina数据获取失败"}
    
    # 统计
    up = sum(1 for s in all_stocks if float(s.get("changepercent", 0)) > 0)
    down = sum(1 for s in all_stocks if float(s.get("changepercent", 0)) < 0)
    flat = len(all_stocks) - up - down
    limit_up = sum(1 for s in all_stocks if float(s.get("changepercent", 0)) >= 9.5)
    limit_down = sum(1 for s in all_stocks if float(s.get("changepercent", 0)) <= -9.5)
    up5 = sum(1 for s in all_stocks if float(s.get("changepercent", 0)) >= 5)
    down5 = sum(1 for s in all_stocks if float(s.get("changepercent", 0)) <= -5)
    
    ratio = up / max(down, 1)
    
    # 情绪判定
    if limit_up > 50 and ratio > 3:
        sentiment = "亢奋"
    elif ratio > 1.5 and limit_up >= 30:
        sentiment = "积极"
    elif ratio >= 1.0:
        sentiment = "中性"
    elif limit_up < 15:
        sentiment = "谨慎"
    else:
        sentiment = "恐慌" if limit_down > 10 else "中性"
    
    return {
        "total_scanned": len(all_stocks),
        "up": up, "down": down, "flat": flat,
        "ratio": round(ratio, 2),
        "limit_up_count": limit_up,
        "limit_down_count": limit_down,
        "up5_count": up5,
        "down5_count": down5,
        "sentiment": sentiment,
        "stocks": all_stocks,  # 供Step4使用
    }


def identify_hot_sectors(stocks: List[Dict]) -> Dict:
    """Step 4: 热点板块识别 (TOP50涨幅关键词匹配)"""
    top50 = sorted(stocks, key=lambda x: -float(x.get("changepercent", 0)))[:50]
    
    # 市场分布
    markets = {"创业板(30xxxx)": 0, "科创板(68xxxx)": 0,
               "深主板(00xxxx)": 0, "沪主板(60xxxx)": 0, "北交所(92xxxx)": 0}
    for s in top50:
        code = str(s.get("code", ""))
        if code.startswith("30"): markets["创业板(30xxxx)"] += 1
        elif code.startswith("68"): markets["科创板(68xxxx)"] += 1
        elif code.startswith("00"): markets["深主板(00xxxx)"] += 1
        elif code.startswith("60"): markets["沪主板(60xxxx)"] += 1
        elif code.startswith("92"): markets["北交所(92xxxx)"] += 1
    
    sci_tech_ratio = (markets["创业板(30xxxx)"] + markets["科创板(68xxxx)"]) / 50
    if sci_tech_ratio > 0.6:
        style = "科技成长行情"
    elif markets["沪主板(60xxxx)"] / 50 > 0.4:
        style = "传统蓝筹行情"
    else:
        style = "普涨格局"
    
    # 关键词匹配
    theme_hits = defaultdict(int)
    for s in top50:
        name = str(s.get("name", ""))
        for theme, keywords in TOPIC_KEYWORDS.items():
            if any(kw in name for kw in keywords):
                theme_hits[theme] += 1
    
    top_themes = sorted(theme_hits.items(), key=lambda x: -x[1])[:5]
    
    return {
        "market_distribution": markets,
        "style": style,
        "top_themes": [{"name": t, "count": c} for t, c in top_themes],
    }


def fetch_index_trend() -> dict:
    """Step 5: 指数趋势分析 (腾讯30日K线)"""
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000001,day,,,30,qfq"
    
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        data = r.json()
        klines = (data.get('data', {}).get('sh000001', {}).get('day', []) or
                  data.get('data', {}).get('sh000001', {}).get('qfqday', []))
    except:
        return {"error": "腾讯K线获取失败"}
    
    if not klines:
        return {"error": "无K线数据"}
    
    closes = [float(k[2]) for k in klines if len(k) >= 3]
    if len(closes) < 5:
        return {"error": "K线不足"}
    
    # 近5日方向
    chg_5d = (closes[-1] - closes[-5]) / closes[-5] * 100
    if chg_5d > 3:
        trend_5d = "连续上涨"
    elif chg_5d < -3:
        trend_5d = "连续下跌"
    else:
        trend_5d = "震荡"
    
    # 20日均线
    ma20 = sum(closes[-20:]) / min(20, len(closes))
    ma20_slope = (closes[-1] - closes[-5]) / 5 if len(closes) >= 5 else 0
    
    # 支撑/压力
    high_30 = max(closes)
    low_30 = min(closes)
    support = round(low_30, 2)
    resistance = round(high_30, 2)
    
    return {
        "price": round(closes[-1], 2),
        "change_5d_pct": round(chg_5d, 2),
        "trend_5d": trend_5d,
        "ma20": round(ma20, 2),
        "ma20_slope": "向上" if ma20_slope > 0 else ("向下" if ma20_slope < 0 else "走平"),
        "support": support,
        "resistance": resistance,
        "distance_to_support_pct": round((closes[-1] - support) / support * 100, 2),
        "distance_to_resistance_pct": round((resistance - closes[-1]) / closes[-1] * 100, 2),
    }


def run_scan() -> dict:
    """执行完整盘前扫描"""
    
    # Step 1
    health = health_check()
    
    # Step 2
    indices = fetch_index_quotes()
    
    # Step 3
    breadth = fetch_market_breadth()
    
    # Step 4
    sectors = {}
    if breadth.get("stocks"):
        sectors = identify_hot_sectors(breadth["stocks"])
        del breadth["stocks"]  # 不输出原始数据
    
    # Step 5
    trend = fetch_index_trend()
    
    # 综合研判
    sentiment = breadth.get("sentiment", "中性")
    limit_up = breadth.get("limit_up_count", 0)
    limit_down = breadth.get("limit_down_count", 0)
    ratio = breadth.get("ratio", 1.0)
    
    if sentiment == "亢奋" and limit_up > 30:
        outlook = "市场情绪高涨，涨停家数充足，可积极参与主线方向"
        strategy = "重仓出击"
    elif sentiment in ("积极", "亢奋"):
        outlook = "市场偏暖，可适度参与，关注早盘方向确认"
        strategy = "正常仓位"
    elif sentiment == "中性":
        outlook = "市场震荡，精选个股，控制仓位"
        strategy = "半仓"
    elif sentiment == "谨慎":
        outlook = "市场偏弱，涨停稀少，建议轻仓或观望"
        strategy = "轻仓"
    else:
        outlook = f"市场恐慌，跌停{limit_down}只，建议空仓等待"
        strategy = "空仓"
    
    if limit_up > 50 and limit_down > 10:
        outlook += "。⚠️ 涨跌极端分化，切忌追高"
    
    return {
        "scan_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "Sina + 腾讯K线 (盘前扫描降级模式)",
        "health": health,
        "indices": indices,
        "market_breadth": breadth,
        "hot_sectors": sectors,
        "index_trend": trend,
        "outlook": outlook,
        "strategy": strategy,
    }


def main():
    import argparse
    p = argparse.ArgumentParser(description="盘前宏观扫描")
    p.add_argument("--json", action="store_true", help="纯JSON输出")
    p.add_argument("-o", "--output", help="输出文件")
    args = p.parse_args()
    
    result = run_scan()
    
    if args.json:
        output = json.dumps(result, ensure_ascii=False, indent=2)
    else:
        # 人类可读输出
        b = result['market_breadth']
        t = result['index_trend']
        s = result['hot_sectors']
        
        lines = [
            f"📊 盘前宏观扫描 | {result['scan_time']}",
            f"",
            f"一、指数回顾",
        ]
        for name, data in result['indices'].items():
            lines.append(f"  {name}: {data['price']} ({data['change_pct']:+.2f}%)")
        
        lines += [
            f"",
            f"二、市场情绪: {b['sentiment']}",
            f"  涨跌比: {b['up']}:{b['down']} ({b['ratio']:.1f}:1)",
            f"  涨停≥9.5%: {b['limit_up_count']} | 跌停≤-9.5%: {b['limit_down_count']}",
            f"  涨幅≥5%: {b['up5_count']} | 跌幅≥5%: {b['down5_count']}",
            f"",
            f"三、热点分析",
            f"  风格: {s.get('style','')}",
        ]
        for th in s.get('top_themes', []):
            lines.append(f"  {th['name']}: {th['count']}只")
        
        lines += [
            f"",
            f"四、技术面关键位置",
            f"  上证: 支撑{t.get('support','?')} → 压力{t.get('resistance','?')}",
            f"  近5日: {t.get('trend_5d','?')} ({t.get('change_5d_pct',0):+.1f}%)",
            f"  MA20: {t.get('ma20','?')} ({t.get('ma20_slope','?')})",
            f"",
            f"五、今日预判",
            f"  {result['outlook']}",
            f"  建议策略: {result['strategy']}",
        ]
        output = "\n".join(lines)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output if isinstance(output, str) else json.dumps(json.loads(output), ensure_ascii=False, indent=2))
    else:
        print(output)


if __name__ == "__main__":
    main()
