"""
formatters.py — 统一输出格式化器

所有编排器/CLI 的 `--json` 模式由入口脚本处理，
默认输出调用此模块的函数生成人类可读格式。
"""

import json


def format_e5(result: dict) -> str:
    """E5 位置波动率分析"""
    lines = [
        "=" * 55,
        f"📊 E5 位置波动率分析",
        "=" * 55,
        "",
        f"  位置评级: {result.get('level','?')}",
        f"  仓位天花板: {result.get('ceiling',0)*100:.0f}%  ← 这只票的最大仓位!",
        f"  波动率评级: {result.get('volatility','?')}",
        f"  是否需要L2验证: {'⚠️ 是' if result.get('need_l2') else '否'}",
        "",
        "  子指标明细:",
    ]
    for key, label in [("mp","均线偏离"), ("bp","波段位置"), ("rv","RSI评分"),
                        ("vd","量价偏离"), ("sa","空间评估")]:
        v = result.get(key, 0)
        bar = "█" * (v // 2) + "░" * (5 - v // 2)
        lines.append(f"    {label:8s}: {bar} {v}/10")
    
    raw = result.get('price', 0)
    try: price_val = float(raw)
    except: price_val = 0
    lines += [
        "",
        "  原始数据:",
        f"    现价: {price_val:.2f}",
        f"    MA20: {float(result.get('ma20',0)):.2f}  偏离: {float(result.get('ma20_dev',0)):+.1f}%",
        f"    RSI(14): {float(result.get('rsi',0)):.1f}",
        f"    年化波动率: {float(result.get('annual_volatility',0))*100:.2f}%",
        f"    当日振幅: {float(result.get('amplitude_today',0)):.2f}%",
        f"    量比(vs20日): {float(result.get('vol_ratio_vs_20d',0)):.2f}",
        f"    波段位置: {float(result.get('band_position_pct',0)):.1f}%  (60日区间)",
        f"    支撑: {float(result.get('support',0)):.2f}  压力: {float(result.get('resistance',0)):.2f}",
        f"    盈亏比: {float(result.get('risk_reward',0)):.2f}",
    ]
    
    # 风险提示
    level_code = result.get('level_code', 2)
    if level_code >= 4:
        lines += ["", "⚠️ 极度危险！股价处于60日最高区域，仓位仅5%，不建议追高"]
    elif level_code == 3:
        lines += ["", "⚠️ 高位风险！建议仓位不超过10%"]
    elif level_code <= 1:
        lines += ["", "✅ 安全边际充足，可积极参与"]
    
    return "\n".join(lines)


def format_game(result: dict, code: str = "", name: str = "") -> str:
    """六维博弈引擎"""
    label = f"{name}({code})" if name and code else code
    
    lines = [
        "=" * 55,
        f"🎯 {label} 六维博弈分析" if label else "🎯 六维博弈分析",
        "=" * 55,
        "",
        f"  综合评分: {result.get('final_score',0):.1f}/100",
        f"  信号: {result.get('signal','?')}    方向: {result.get('direction','?')}",
        f"  建议仓位: {result.get('position_pct',0)*100:.0f}%",
        f"  卖出倾向: {result.get('sell_tendency',0):.0%}    风险等级: {result.get('risk_level','?')}",
        f"  操作建议: {result.get('action','?')}",
        "",
        "  六维明细:",
    ]
    
    for dim, label, weight in [("A1","主力行为",25),("B2","情绪周期",15),("C3","量化风报比",15),
                                ("D4","统计分布",10),("E5","位置波动率",20),("F6","L2验证",15)]:
        d = result.get('dimensions', {}).get(dim, {})
        score = d.get('score', 0)
        bar = "█" * int(score/10) + "░" * (10 - int(score/10))
        veto = " ⚠️ 一票否决!" if d.get('veto') else ""
        signal = d.get('signal', '')
        lines.append(f"    {label}({weight}%): {bar} {score:.0f}/100  {signal}{veto}")
    
    # 共识
    consensus = result.get('consensus')
    if consensus:
        lines += [
            "",
            "📊 双引擎共识:",
            f"  类型: {consensus.get('consensus_type','?')}",
            f"  可靠性: {consensus.get('reliability',0):.2f}",
            f"  合并评分: {consensus.get('merged_score',0):.1f}",
            f"  信号: {consensus.get('signal','?')}",
        ]
    
    # 风险提示
    veto = result.get('veto_reason')
    if veto:
        lines += ["", f"  ⚠️ 一票否决: {veto}"]
    
    # 数据来源标注
    enriched = result.get('_data_source', {})
    if enriched:
        real_keys = [k for k in enriched if enriched[k] == 'enriched' and not k.startswith('_')]
        # Check DDX availability from enrichment keys
        has_ddx = any(k in real_keys for k in ['ddx_5d', 'ddx_10d', 'ddx_3d'])
        missing = [k for k in ['active_buy_ratio', 'inst_vs_retail', 'continuity_3d'] if k not in real_keys]
        if not has_ddx:
            missing[:0] = ['多周期DDX']
            lines += [
                "",
                "📡 数据来源:",
                f"  实时: {', '.join(real_keys[:5])} ✅",
                f"  缺失: {', '.join(missing)} ⚠️",
                "  ⚠️ 未获取到DDX数据, DDX一票否决功能不可用",
            ]
    
    return "\n".join(lines)


def format_w8(result: dict) -> str:
    """W8 低吸挖掘"""
    lines = [
        "=" * 55,
        "🔍 W8 低吸挖掘 · 六步法",
        "=" * 55,
        "",
        f"  强方向: {', '.join(result.get('strong_directions',[])[:3])}",
        f"  初筛候选: {result.get('candidates_screened',0)} 只 (涨幅1-5%)",
        f"  低风险通过: {result.get('low_risk_passed',0)} 只 (低位+盈亏比≥3)",
        f"  博弈验证: {result.get('game_verified',0)} 只 (评分≥60)",
    ]
    
    candidates = result.get('final_candidates', [])
    if candidates:
        lines += ["", "  📋 出票列表:", ""]
        for c in candidates:
            lines.append(f"  #{c['rank']} {c['name']}({c['code']})")
            lines.append(f"     评分: {c['game_score']:.0f}/100 | 位置: {c['e5_level']} | 盈亏比: {c['risk_reward']:.1f}")
            lines.append(f"     建议仓位: {c['suggested_pct']*100:.0f}% | 金额: {c.get('suggested_amount',0):.0f}元")
    else:
        lines += ["", "  ⚠️ 无票可出 — 过滤过程:"]
        lines.append(f"     Step3初筛→Step4位置过滤→Step5博弈验证(要求≥60分)")
        lines.append(f"     当前市场无主线(D象限)+梯队畸形，低位票技术面得分不足")
    
    return "\n".join(lines)


def format_mainline(result: dict) -> str:
    """主线推演"""
    comp = result.get('data_completeness', {})
    lines = [
        "=" * 55,
        "📊 主线推演",
        "=" * 55,
    ]
    
    if comp.get('degraded_mode'):
        lines += ["", f"  ⚠️ 降级模式运行 ({len(comp.get('missing_files',[]))} 个文件缺失)"]
        for w in result.get('data_warnings', []):
            lines.append(f"     {w}")
        lines.append("")
    else:
        lines.append("")
    
    lines += [
        f"  全局情绪: {result.get('global_sentiment','?')}",
        f"  市场阶段: {result.get('global_stage','?')}",
        f"  主线: {'✅ 有' if result.get('has_mainline') else '❌ 无'} | 象限: {result.get('quadrant','?')}",
        f"  含义: {result.get('quadrant_desc','')}",
        f"  扩散: {result.get('diffusion','')}",
        f"  资金路径: {result.get('capital_path','')}",
        "",
        f"  题材分析:",
    ]
    
    for t in result.get('topic_analysis', [])[:8]:
        adj = t.get('adjustments', {})
        adj_count = sum(len(v) for v in adj.values())
        arrow = "⬇" if adj_count > 2 else ("⬆" if adj_count > 0 else "—")
        lines.append(f"  #{t['rank']:2d} {t['name']:8s} {t['base_quadrant']}→{t['quadrant']:2s} {arrow} 强度={t['strength_score']:.0f}  涨停={t['limit_up_count']}  中军={'✅' if t.get('zhongjun_strong') else '—'}  修正={adj_count}")
    
    return "\n".join(lines)


def format_w5(result: dict) -> str:
    """W5 持仓分析"""
    lines = [
        "=" * 55,
        f"📋 {result.get('code','?')} 持仓分析",
        "=" * 55,
        "",
        f"  现价: {result.get('price',0):.2f}  盈亏: {result.get('pnl_pct',0):+.1f}%",
        f"  决策: {result.get('decision','?')}",
        f"  原因: {result.get('reason','?')}",
        f"  路径: {result.get('pipeline_path','?')}",
        "",
        f"  G0评分: {result.get('g0',{}).get('score',0):.1f}/10  定位: {result.get('g0',{}).get('position','?')}",
        f"  E5位置: {result.get('e5',{}).get('level','?')}  天花板: {result.get('e5',{}).get('ceiling',0)*100:.0f}%",
        f"  博弈评分: {result.get('game',{}).get('final_score',0):.0f}/100",
        f"  信号: {result.get('game',{}).get('signal','?')}  方向: {result.get('game',{}).get('direction','?')}",
        f"  卖出倾向: {result.get('game',{}).get('sell_tendency',0):.0%}",
    ]
    
    if result.get('game', {}).get('veto'):
        lines.append(f"  ⚠️ 触发一票否决!")
    
    t0 = result.get('t0')
    if t0 and t0.get('triggered'):
        lines += ["", f"  ⚡ T0触发: {t0.get('direction','')} — {t0.get('position_shares',0)}股"]
    
    return "\n".join(lines)


def format_w10(result: dict) -> str:
    """W10 趋势波段"""
    lines = [
        "=" * 55,
        f"📈 {result.get('code','?')} 趋势波段分析",
        "=" * 55,
        "",
        f"  现价: {result.get('price',0):.2f}",
        f"  浪型: {result.get('wave_analysis',{}).get('stage','?')}",
        f"  模式: {result.get('wave_analysis',{}).get('pattern','?')}",
        f"  旗形: {'是' if result.get('wave_analysis',{}).get('flag') else '否'}",
        f"  二浪: {'确认' if result.get('wave_analysis',{}).get('wave2') else '否'}",
        "",
        f"  波波六维: {result.get('bobo_score',{}).get('total',0):.0f}/85",
        f"  博弈六维: {result.get('game_score',{}).get('total',0):.0f}/100",
    ]
    
    fusion = result.get('fusion', {})
    if fusion:
        lines += [
            f"  双引擎融合: {fusion.get('merged_score',0):.0f}  {fusion.get('cross_validation','')}",
        ]
    
    dec = result.get('decision', {})
    lines += [
        "",
        f"  决策: {dec.get('signal','?')}  仓位: {dec.get('position_pct',0)*100:.0f}%",
        f"  T0触发: {'是' if dec.get('t0_triggered') else '否'}",
        f"  风险: {result.get('risk',{}).get('level','?')}",
    ]
    
    return "\n".join(lines)
