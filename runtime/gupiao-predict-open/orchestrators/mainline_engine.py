"""
mainline_engine.py — 主线引擎（纯Python实现）

四模式:
  -m run: ABCD象限推演 + 扩散关系 + 资金路径 → 主线判定
  -m p:   龙头定位（多维度综合打分排序）
  -m u:   卫星推导 / 上游瓶颈挖掘
  -m g:   批量博弈验证（X8六维评分）

用法:
    python orchestrators/mainline_engine.py -i input.json -m run -o output.json
    python orchestrators/mainline_engine.py -i candidates.json -m p
"""

import sys, os, json, argparse, math
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_theory_6d import analyze as game_analyze
from core.classic_4p import classic_analyze
from core.limit_up_booster import limit_up_boost


# ============================================================
# -m run: ABCD象限推演 + 主线判定
# ============================================================

def run_quadrant_analysis(
    topics: List[Dict],
    sentiment_data: Optional[Dict] = None,
    ladder_data: Optional[Dict] = None,
    yesterday_data: Optional[Dict] = None,
) -> Dict:
    """
    ABCD象限分析 — 完整四文件版本
    
    输入:
      topics:        题材列表 (来自节点1 topics_raw.json)
      sentiment_data: 题材情绪 (来自节点2 theme_sentiment.json)
      ladder_data:    连板梯队 (来自节点3 board_ladder.json)
      yesterday_data: 昨日回溯 (来自节点4 yesterday_review.json)
    
    输出: mainline_result.json
    
    ABCD象限:
      A(题材强+中军强) = 主线确认 — 重仓出击
      B(题材强+中军弱) = 游资炒作 — 轻仓参与
      C(题材弱+中军强) = 中军补涨 — 观察
      D(题材弱+中军弱) = 无主线   — 空仓等待
    
    情绪修正:
      亢奋时 B象限可升格为A(游资有信心接力)
      恐慌时 A象限降格为B(大资金也可能撤退)
    
    梯队修正:
      断层(某梯队为0) → A降B(结构不健康)
      断板率>50% → 所有象限降一级(退潮信号)
      晋级率>50% → B升A(接力意愿强)
    
    昨日回溯修正:
      连续强(持续≥3天) → 确认当前象限
      突然爆发(昨日无此题材) → 降级观察(一日游风险)
      昨日龙头全断 → 警惕退潮
    """
    if not topics:
        return {
            "has_mainline": False,
            "quadrant": "D",
            "quadrant_desc": "无数据 — 无法判定",
            "mainline_topics": [],
            "analysis": {},
        }
    
    # ===== 数据完整性检查 =====
    data_warnings = []
    missing_files = []
    
    if sentiment_data is None:
        missing_files.append("theme_sentiment.json (节点2)")
        data_warnings.append("⚠️ 缺少题材情绪数据 → 情绪修正层关闭（全局情绪默认\"中性\"，亢奋/恐慌修正不生效）")
    if ladder_data is None:
        missing_files.append("board_ladder.json (节点3)")
        data_warnings.append("⚠️ 缺少连板梯队数据 → 梯队修正层关闭（断层检测/晋级率/断板率修正不生效，默认健康）")
    if yesterday_data is None:
        missing_files.append("yesterday_review.json (节点4)")
        data_warnings.append("⚠️ 缺少昨日回溯数据 → 持续性修正层关闭（一日游/突然爆发检测不生效，默认中性持续）")
    
    if missing_files:
        data_warnings.insert(0, f"⚠️ 缺少 {len(missing_files)} 个输入文件: {', '.join(missing_files)}，运行在降级模式")
    
    # ===== 预处理: 提取三个辅助文件的关键指标 =====
    
    # 情绪数据 → 全局情绪判定
    global_sentiment = "中性"
    sentiment_map = {}  # {topic_name: sentiment_dict}
    if sentiment_data:
        themes = sentiment_data.get("themes", [])
        for th in themes:
            sentiment_map[th.get("name", "")] = th
        # 全局情绪: 取所有题材的平均
        scores = [th.get("sentiment_score", 50) for th in themes]
        avg_score = sum(scores) / len(scores) if scores else 50
        if avg_score >= 80:
            global_sentiment = "亢奋"
        elif avg_score >= 65:
            global_sentiment = "积极"
        elif avg_score >= 40:
            global_sentiment = "中性"
        elif avg_score >= 25:
            global_sentiment = "谨慎"
        else:
            global_sentiment = "恐慌"
    
    # 梯队数据 → 全局梯队健康度
    promotion_rate = 0.5       # 晋级率，默认50%
    break_rate = 0.15          # 断板率，默认15%
    has_gap = False            # 是否有断层
    max_board_height = 1       # 最高板
    is_pyramid = True          # 是否金字塔形
    if ladder_data:
        promotion_rate = ladder_data.get("promotion_rate", 0.5)
        break_rate = ladder_data.get("break_rate", 0.15)
        has_gap = ladder_data.get("has_gap", False)
        max_board_height = ladder_data.get("max_board_height", 1)
        is_pyramid = ladder_data.get("is_pyramid", True)
    
    # 昨日回溯 → 持续性数据
    yesterday_top_topic = ""
    continuity_map = {}  # {topic_name: continuity_score}
    leader_perf_map = {} # {topic_name: leader_performance_dict}
    if yesterday_data:
        yesterday_top_topic = yesterday_data.get("yesterday_top_topic", "")
        # 如果 yesterday_data 是按题材的列表
        reviews = yesterday_data.get("reviews", [yesterday_data])
        for rev in reviews:
            name = rev.get("topic", rev.get("name", ""))
            continuity_map[name] = rev.get("continuity_score", 5)
            leader_perf_map[name] = rev.get("leader_performance", {})
    
    # ===== 核心: 逐题材四象限分析 =====
    analyzed = []
    
    for t in topics:
        name = t.get("name", "未知")
        limit_up_count = t.get("limit_up_count", 0)
        net_amount = t.get("net_amount", 0)
        rank = t.get("rank", 99)
        
        # ---- 1. 题材强度判定 ----
        topic_strong = (
            (limit_up_count >= 10 and net_amount > 1e8) or
            (limit_up_count >= 5 and net_amount > 5e8) or
            (rank <= 3)
        )
        
        # ---- 2. 中军强度判定 ----
        stocks = t.get("stocks", [])
        large_cap_leaders = [
            s for s in stocks
            if s.get("market_cap", 0) >= 200e8
            and s.get("change_pct", 0) >= 3
        ]
        zhongjun_strong = len(large_cap_leaders) >= 1
        zhongjun_super = any(
            s.get("change_pct", 0) >= 9.5 and s.get("market_cap", 0) >= 200e8
            for s in stocks
        )
        
        # ---- 3. 基础象限 ----
        if topic_strong and zhongjun_strong:
            base_quadrant = "A"
            base_desc = "主线确认 — 题材强+中军确认"
            base_strategy = "重仓出击"
        elif topic_strong and not zhongjun_strong:
            base_quadrant = "B"
            base_desc = "游资炒作 — 题材强但中军不跟"
            base_strategy = "轻仓参与，警惕虚火"
        elif not topic_strong and zhongjun_strong:
            base_quadrant = "C"
            base_desc = "中军补涨 — 中军走强但题材热度不足"
            base_strategy = "观察，可能轮动"
        else:
            base_quadrant = "D"
            base_desc = "无主线 — 题材弱且无中军"
            base_strategy = "空仓等待"
        
        # ---- 4. 情绪修正 (来自 theme_sentiment) ----
        quadrant = base_quadrant
        emotion_adjustments = []
        
        topic_sentiment = sentiment_map.get(name, {})
        topic_sent_score = topic_sentiment.get("sentiment_score", 50)
        topic_sent_label = topic_sentiment.get("sentiment_label", "")
        is_sustained = topic_sentiment.get("is_sustained", False)
        
        if global_sentiment == "亢奋" and base_quadrant == "B":
            quadrant = "A"
            emotion_adjustments.append("全局亢奋 → B升格为A(游资有信心接力)")
        elif global_sentiment == "恐慌" and base_quadrant == "A":
            quadrant = "B"
            emotion_adjustments.append("全局恐慌 → A降格为B(大资金也可能撤退)")
        elif global_sentiment == "积极" and base_quadrant == "B" and zhongjun_super:
            quadrant = "A"
            emotion_adjustments.append("积极+中军涨停 → B升格为A")
        elif topic_sent_label == "亢奋" and base_quadrant == "B":
            quadrant = "A"
            emotion_adjustments.append(f"题材{name}情绪亢奋 → B升A")
        
        # ---- 5. 梯队修正 (来自 board_ladder) ----
        ladder_adjustments = []
        
        if has_gap and base_quadrant in ("A", "B"):
            old = quadrant
            quadrant = "B" if old == "A" else "C"
            ladder_adjustments.append(f"梯队断层(某梯队为0) → {old}降为{quadrant}(结构不健康)")
        
        if break_rate > 0.50:
            old = quadrant
            degrade_map = {"A": "B", "B": "C", "C": "D", "D": "D"}
            quadrant = degrade_map.get(old, old)
            ladder_adjustments.append(f"断板率{break_rate:.0%}>50% → {old}降为{quadrant}(退潮信号)")
        
        if promotion_rate > 0.50 and base_quadrant == "B" and max_board_height >= 3:
            quadrant = "A"
            ladder_adjustments.append(f"晋级率{promotion_rate:.0%}>50%+最高{max_board_height}板 → B升A(接力意愿强)")
        
        if not is_pyramid and base_quadrant == "A":
            quadrant = "B"
            ladder_adjustments.append("梯队非金字塔形 → A降B")
        
        # ---- 6. 持续性修正 (来自 yesterday_review) ----
        continuity_adjustments = []
        continuity_score = continuity_map.get(name, 5)
        is_yesterday_top = (name == yesterday_top_topic)
        
        if continuity_score >= 8:
            # 持续强 → 确认当前象限，加备注
            if quadrant == "A":
                continuity_adjustments.append(f"连续强势(持续{continuity_score}分) → 主线确认加固")
        elif continuity_score <= 3 and is_sustained == False:
            # 突然爆发 → 警惕一日游
            if quadrant in ("A", "B"):
                old = quadrant
                degrade_map = {"A": "B", "B": "C"}
                quadrant = degrade_map.get(old, old)
                continuity_adjustments.append(f"突然爆发(持续仅{continuity_score}分) → {old}降为{quadrant}(警惕一日游)")
        
        if is_yesterday_top and quadrant in ("A", "B"):
            continuity_adjustments.append("昨日最强题材延续 → 确认当前方向")
        
        # 昨日龙头表现
        leader_perf = leader_perf_map.get(name, {})
        broken_count = leader_perf.get("broken_board", 0)
        blown_count = leader_perf.get("blown_board", 0)
        if broken_count + blown_count >= 3 and quadrant in ("A", "B"):
            old = quadrant
            degrade_map = {"A": "B", "B": "C"}
            quadrant = degrade_map.get(old, old)
            continuity_adjustments.append(f"昨日龙头{broken_count}断板+{blown_count}炸板 → {old}降{quadrant}")
        
        # ---- 7. 阶段判定 (五阶段模型) ----
        if limit_up_count >= 20 and break_rate > 0.25:
            stage = "高潮期"
            stage_coeff = 0.5
        elif limit_up_count > 15 and max_board_height >= 4 and not has_gap and is_pyramid:
            stage = "主升期"
            stage_coeff = 0.8
        elif limit_up_count >= 5 and max_board_height >= 2:
            stage = "发酵期"
            stage_coeff = 0.3
        elif break_rate > 0.50 or (limit_up_count < 5 and max_board_height < 2):
            stage = "退潮期" if break_rate > 0.50 or limit_up_count < 3 else "启动期"
            stage_coeff = 0.0
        else:
            stage = "启动期"
            stage_coeff = 0.0
        
        # 全市场退潮检测
        if break_rate > 0.50:
            stage = "退潮期"
            stage_coeff = 0.0
        
        # ---- 8. 最终象限描述 ----
        desc_map = {
            "A": "主线确认 — 可重仓出击" + ("(情绪+梯队+持续确认)" if len(emotion_adjustments+ladder_adjustments+continuity_adjustments) > 0 else ""),
            "B": "游资炒作 — 轻仓参与" + ("(降级风险)" if base_quadrant == "A" else ""),
            "C": "中军补涨 — 观察等待",
            "D": "无主线 — 空仓",
        }
        
        strategy_map = {
            "A": "重仓出击",
            "B": "轻仓参与，警惕虚火",
            "C": "观察，可能轮动",
            "D": "空仓等待",
        }
        
        # ---- 9. 强度评分 (0-100) ----
        strength_score = min(100, (
            min(limit_up_count / 15 * 40, 40) +
            min(net_amount / 1e9 * 30, 30) +
            max(0, (10 - rank) * 3) +
            (15 if zhongjun_super else (10 if zhongjun_strong else 0))
        ))
        
        # 情绪加分
        if topic_sent_score >= 70:
            strength_score = min(100, strength_score + 5)
        elif topic_sent_score < 30:
            strength_score = max(0, strength_score - 5)
        
        # 持续性加分
        if continuity_score >= 8:
            strength_score = min(100, strength_score + 3)
        
        analyzed.append({
            "name": name,
            "base_quadrant": base_quadrant,
            "quadrant": quadrant,
            "quadrant_desc": desc_map.get(quadrant, ""),
            "strategy": strategy_map.get(quadrant, ""),
            "priority": {"A": 1, "B": 2, "C": 3, "D": 4}.get(quadrant, 5),
            "strength_score": round(strength_score, 1),
            "topic_strong": topic_strong,
            "zhongjun_strong": zhongjun_strong,
            "zhongjun_super": zhongjun_super,
            "limit_up_count": limit_up_count,
            "net_amount": net_amount,
            "rank": rank,
            "large_cap_leaders": [s.get("code") for s in large_cap_leaders],
            "stage": stage,
            "stage_coeff": stage_coeff,
            # 修正记录（透明度）
            "adjustments": {
                "base": f"{base_quadrant} → {quadrant}",
                "emotion": emotion_adjustments,
                "ladder": ladder_adjustments,
                "continuity": continuity_adjustments,
            },
        })
    
    # ===== 排序 + 汇总 =====
    analyzed.sort(key=lambda x: (x["priority"], -x["strength_score"]))
    
    mainline = [a for a in analyzed if a["quadrant"] == "A" and a["strength_score"] >= 60]
    secondary = [a for a in analyzed if a["quadrant"] in ("A", "B") and a["strength_score"] >= 40]
    
    # 扩散关系
    if len(analyzed) >= 2:
        top2 = analyzed[:2]
        stocks_a = set()
        stocks_b = set()
        for t in topics:
            if t.get("name") == top2[0]["name"]:
                stocks_a = set(s.get("code") for s in t.get("stocks", []))
            if t.get("name") == top2[1]["name"]:
                stocks_b = set(s.get("code") for s in t.get("stocks", []))
        
        overlap = len(stocks_a & stocks_b)
        overlap_rate = overlap / max(len(stocks_a), 1) if stocks_a else 0
        
        if overlap_rate > 0.3:
            diffusion = f"{top2[0]['name']}↔{top2[1]['name']} 高度关联(重叠{overlap_rate:.0%})，可能合并为主线"
        elif overlap_rate > 0.1:
            diffusion = f"{top2[0]['name']}→{top2[1]['name']} 中度关联，资金可能扩散"
        else:
            diffusion = f"{top2[0]['name']} 与 {top2[1]['name']} 独立运行"
    else:
        diffusion = "题材不足，无法分析扩散关系"
    
    # 资金路径
    capital_flows = sorted(analyzed, key=lambda x: -x["net_amount"])
    flow_desc = " → ".join(f"{c['name']}({c['net_amount']/1e8:.1f}亿)" for c in capital_flows[:3]) if capital_flows else "无资金数据"
    
    # 全局阶段
    global_stage = analyzed[0]["stage"] if analyzed else "启动期"
    
    result = {
        "has_mainline": len(mainline) >= 1,
        "mainline_topics": [m["name"] for m in mainline],
        "secondary_topics": [s["name"] for s in secondary if s["name"] not in [m["name"] for m in mainline]],
        "quadrant": mainline[0]["quadrant"] if mainline else (secondary[0]["quadrant"] if secondary else "D"),
        "quadrant_desc": mainline[0]["quadrant_desc"] if mainline else "无明确主线",
        "overall_strategy": mainline[0]["strategy"] if mainline else "观望",
        "global_stage": global_stage,
        "global_sentiment": global_sentiment,
        "ladder_health": {
            "promotion_rate": promotion_rate,
            "break_rate": break_rate,
            "has_gap": has_gap,
            "max_board_height": max_board_height,
            "is_pyramid": is_pyramid,
        },
        "diffusion": diffusion,
        "capital_path": flow_desc,
        "topic_analysis": analyzed,
        "core_stocks": [],
        "data_warnings": data_warnings,
        "data_completeness": {
            "topics": True,
            "sentiment": sentiment_data is not None,
            "ladder": ladder_data is not None,
            "yesterday": yesterday_data is not None,
            "missing_files": missing_files,
            "degraded_mode": len(missing_files) > 0,
        },
    }
    
    return result


# ============================================================
# -m p: 龙头定位
# ============================================================

def locate_leaders(stocks: List[Dict]) -> List[Dict]:
    """
    龙头定位 — 多维度综合打分排序
    
    评分维度:
      涨停时间 (越早越好)
      封单量 (越大越好)
      连板数 (越多越好)
      换手率 (5-15%最佳)
      资金净流入
      题材内涨幅排名
    """
    scored = []
    for s in stocks:
        code = s.get("code", "")
        name = s.get("name", "")
        change_pct = s.get("change_pct", 0)
        lianban_days = s.get("lianban_days", 0)
        seal_amount = s.get("seal_amount", 0)
        limit_up_time = s.get("limit_up_time", "")
        turnover = s.get("turnover_rate", 10)
        main_net = s.get("main_net_amount", 0)
        market_cap = s.get("market_cap", 100e8)
        is_limit_up = s.get("is_limit_up", change_pct >= 9.5)
        rank_in_topic = s.get("rank_in_topic", 5)
        
        score = 0
        
        # 涨停时间评分 (0-25)
        if "09:30" in str(limit_up_time):
            score += 25
        elif "09:" in str(limit_up_time) or "10:00" in str(limit_up_time):
            score += 20
        elif "10:" in str(limit_up_time):
            score += 15
        elif limit_up_time:
            score += 10
        elif is_limit_up:
            score += 15  # 涨停但时间未知
        
        # 封单量评分 (0-20)
        if market_cap > 0:
            seal_ratio = seal_amount / market_cap
        else:
            seal_ratio = 0
        if seal_ratio > 0.05:
            score += 20
        elif seal_ratio > 0.03:
            score += 15
        elif seal_ratio > 0.01:
            score += 10
        elif seal_amount > 0:
            score += 5
        
        # 连板数评分 (0-20)
        if lianban_days >= 5:
            score += 20
        elif lianban_days >= 3:
            score += 16
        elif lianban_days >= 2:
            score += 12
        elif lianban_days >= 1:
            score += 8
        
        # 换手率健康度 (0-15)
        if 5 <= turnover <= 15:
            score += 15
        elif 3 <= turnover <= 25:
            score += 10
        elif turnover > 0:
            score += 5
        
        # 涨幅排名 (0-10)
        if rank_in_topic <= 3:
            score += 10
        elif rank_in_topic <= 5:
            score += 7
        elif rank_in_topic <= 10:
            score += 4
        
        # 资金净流入 (0-10)
        if main_net > 5e8:
            score += 10
        elif main_net > 1e8:
            score += 7
        elif main_net > 0:
            score += 4
        
        # 角色判定
        if score >= 70:
            role = "龙头"
        elif score >= 50:
            role = "中军" if market_cap >= 200e8 else "核心跟风"
        elif score >= 30:
            role = "跟风"
        else:
            role = "边缘"
        
        scored.append({
            "code": code,
            "name": name,
            "role": role,
            "score": score,
            "change_pct": change_pct,
            "lianban_days": lianban_days,
            "market_cap": market_cap,
            "is_limit_up": is_limit_up,
        })
    
    scored.sort(key=lambda x: -x["score"])
    return scored


# ============================================================
# -m u: 卫星推导 / 上游瓶颈挖掘
# ============================================================

def satellite_derive(mainline_result: Dict, supply_chain_db: Optional[Dict] = None) -> Dict:
    """
    卫星推导 — 从龙头反推资金下一个目标
    
    1. 龙头已封板 → 从供应链知识库中查找上游瓶颈标的
    2. 四维评分: 唯一性(40%) + 客户质量(25%) + 业绩可追踪(20%) + 市值弹性(15%)
    """
    mainline_topics = mainline_result.get("mainline_topics", [])
    if not mainline_topics:
        return {"satellites": [], "reason": "无主线，无法推导卫星"}
    
    # 预设供应链知识库
    default_db = {
        "AI": [{"code": "600367", "name": "红星发展", "bottleneck": "高纯碳酸锶", "score": 97}],
        "光通信": [{"code": "002428", "name": "云南锗业", "bottleneck": "磷化铟衬底", "score": 85}],
        "芯片半导体": [{"code": "600183", "name": "生益科技", "bottleneck": "ABF膜", "score": 88}],
        "MLCC": [{"code": "600367", "name": "红星发展", "bottleneck": "高纯碳酸钡", "score": 90}],
        "先进封装": [{"code": "688012", "name": "中微公司", "bottleneck": "TSV设备", "score": 85}],
        "碳化硅": [{"code": "688234", "name": "天岳先进", "bottleneck": "SiC衬底", "score": 82}],
        "固态电池": [{"code": "002167", "name": "东方锆业", "bottleneck": "氧化锆", "score": 80}],
        "稀土永磁": [{"code": "600111", "name": "北方稀土", "bottleneck": "稀土矿源", "score": 92}],
    }
    
    db = supply_chain_db or default_db
    satellites = []
    
    for topic in mainline_topics:
        # 模糊匹配
        for key, candidates in db.items():
            if key in topic or topic in key:
                for c in candidates:
                    satellites.append({
                        **c,
                        "source_topic": topic,
                        "reason": f"主线{topic}的瓶颈环节: {c['bottleneck']}"
                    })
    
    if not satellites:
        # 尝试部分匹配
        for topic in mainline_topics:
            for key, candidates in db.items():
                if any(word in topic for word in key.split()) or any(word in key for word in topic.split()):
                    for c in candidates:
                        satellites.append({
                            **c,
                            "source_topic": topic,
                            "reason": f"主线{topic}的关联瓶颈: {c['bottleneck']}"
                        })
    
    # 去重
    seen = set()
    unique = []
    for s in satellites:
        if s["code"] not in seen:
            seen.add(s["code"])
            unique.append(s)
    
    unique.sort(key=lambda x: -x["score"])
    
    return {
        "satellites": unique,
        "total": len(unique),
        "recommendation": unique[0] if unique else None,
    }


# ============================================================
# -m g: 批量博弈验证
# ============================================================

def batch_game_verify(candidates: List[Dict], klines_map: Optional[Dict[str, List]] = None) -> List[Dict]:
    """
    批量博弈验证 — 对候选列表逐只跑六维博弈引擎
    
    Args:
        candidates: [{"code": str, "price": float, ...}, ...]
        klines_map: {code: [kline_dicts]} 可选的K线数据
    
    Returns:
        按博弈评分降序的验证结果
    """
    results = []
    for c in candidates:
        code = c.get("code", "")
        klines = klines_map.get(code) if klines_map else None
        
        # 构建输入
        input_data = {
            "code": code,
            "price": c.get("price", 10),
            "ddx_5d": c.get("ddx_5d", 0.3),
            "ddx_10d": c.get("ddx_10d", 0.1),
            "main_amount": c.get("main_amount", 5e7),
            "low_60d": c.get("low_60d", c.get("price", 10) * 0.8),
            "high_60d": c.get("high_60d", c.get("price", 10) * 1.2),
            "ma20": c.get("ma20", c.get("price", 10)),
            "ma5": c.get("ma5", c.get("price", 10)),
            "rsi": c.get("rsi", 50),
            "volatility": c.get("volatility", 0.03),
            "amplitude": c.get("amplitude", 3),
            "active_buy_ratio": c.get("active_buy_ratio", 0.55),
            "super_large_net": c.get("super_large_net", 0),
            "inst_vs_retail": c.get("inst_vs_retail", 1.0),
            "topic": c.get("topic", "批量验证"),
            "topic_rank": c.get("topic_rank", 5),
            "is_limit_up": c.get("is_limit_up", False),
            "lianban_days": c.get("lianban_days", 0),
            "E5_position_pct": c.get("E5_position_pct", 50),
            "vol_ratio": c.get("vol_ratio", 1.0),
            "sentiment": c.get("sentiment", "neutral"),
        }
        
        game_result = game_analyze(input_data, klines)
        
        results.append({
            "code": code,
            "name": c.get("name", ""),
            "final_score": game_result["final_score"],
            "signal": game_result["signal"],
            "direction": game_result["direction"],
            "position_pct": game_result["position_pct"],
            "sell_tendency": game_result["sell_tendency"],
            "risk_level": game_result["risk_level"],
            "action": game_result["action"],
            "veto": "veto_reason" in game_result,
            "veto_reason": game_result.get("veto_reason"),
        })
    
    results.sort(key=lambda x: -x["final_score"])
    return results


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="主线引擎 (开源版)")
    parser.add_argument("-i", help="输入JSON文件路径")
    parser.add_argument("-m", default="run", help="模式: run|p|u|g")
    parser.add_argument("-d", help="附加数据JSON (g模式K线映射)")
    parser.add_argument("-o", help="输出JSON文件路径")
    parser.add_argument("--json", action="store_true", help="输出原始JSON")
    args = parser.parse_args()
    
    if not args.i:
        print("错误: 需要 -i 输入文件")
        sys.exit(1)
    
    with open(args.i, 'r') as f:
        input_data = json.load(f)
    
    result = None
    
    if args.m == "run":
        # 输入: 4文件 {topics, sentiment, ladder, yesterday} 或 简单 topics 列表
        if isinstance(input_data, list):
            topics = input_data
            sentiment_data = None
            ladder_data = None
            yesterday_data = None
        else:
            topics = input_data.get("topics", [])
            sentiment_data = input_data.get("sentiment") or input_data.get("theme_sentiment")
            ladder_data = input_data.get("ladder") or input_data.get("board_ladder")
            yesterday_data = input_data.get("yesterday") or input_data.get("yesterday_review")
        result = run_quadrant_analysis(topics, sentiment_data, ladder_data, yesterday_data)
    
    elif args.m == "p":
        # 输入: 候选股列表
        stocks = input_data if isinstance(input_data, list) else input_data.get("candidates", [])
        result = locate_leaders(stocks)
    
    elif args.m == "u":
        # 输入: mainline_result
        db = None
        if args.d:
            with open(args.d, 'r') as f:
                db = json.load(f)
        result = satellite_derive(input_data, db)
    
    elif args.m == "g":
        # 输入: 候选列表
        candidates = input_data if isinstance(input_data, list) else input_data.get("candidates", [])
        klines_map = None
        if args.d:
            with open(args.d, 'r') as f:
                klines_map = json.load(f)
        result = batch_game_verify(candidates, klines_map)
    
    else:
        print(f"未知模式: {args.m}")
        sys.exit(1)
    
    output = json.dumps(result, ensure_ascii=False, indent=2)
    
    if args.o:
        with open(args.o, 'w') as f:
            f.write(output)
        print(f"输出已写入 {args.o}")
    
    if args.json:
        print(output)
    else:
        from core.formatters import format_mainline
        print(format_mainline(result))


if __name__ == "__main__":
    main()
