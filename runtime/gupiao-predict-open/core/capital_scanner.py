"""
capital_scanner.py — 资金全景扫描器

五维: 北向资金(20) + 融资融券(20) + 大宗交易(20) + 股东增减持(20) + 龙虎榜(20)

用法:
    from core.capital_scanner import capital_scan
"""

from typing import Dict


def capital_scan(
    north_5d_net: float = 0,
    north_holding_change: float = 0,
    margin_balance_change: float = 0,
    short_balance_change: float = 0,
    block_trade_premium: float = 0,
    block_buyer_type: str = "散户",
    holder_action: str = "无变动",
    lockup_days: int = 999,
    dragon_institution_net: float = 0,
    dragon_famous_trader: bool = False,
) -> Dict:
    """
    资金全景五维扫描
    
    Args:
        north_5d_net: 北向近5日净买入 (元)
        north_holding_change: 北向持股比例变化 (%)
        margin_balance_change: 融资余额变化 (正=增加)
        short_balance_change: 融券余额变化 (正=做空增加)
        block_trade_premium: 大宗交易溢价率 (%)
        block_buyer_type: 大宗买方类型 (机构/游资/散户)
        holder_action: 股东动作 (增持/回购/无变动/减持/解禁)
        lockup_days: 距解禁天数
        dragon_institution_net: 龙虎榜机构净买入 (元)
        dragon_famous_trader: 是否有知名游资参与
    """
    
    # === ① 北向资金 (0-20) ===
    if north_5d_net > 5e8 and north_holding_change > 0:
        s1 = 20
    elif north_5d_net > 2e8:
        s1 = 14
    elif north_5d_net > 0:
        s1 = 8
    else:
        s1 = 0
    
    # === ② 融资融券 (0-20) ===
    if margin_balance_change > 0 and short_balance_change <= 0:
        s2 = 20  # 融资↑+融券↓
    elif margin_balance_change > 0:
        s2 = 14  # 融资↑
    elif margin_balance_change == 0:
        s2 = 8
    else:
        s2 = 0
    
    # === ③ 大宗交易 (0-20) ===
    if block_trade_premium > 0 and block_buyer_type == "机构":
        s3 = 20  # 溢价+机构
    elif block_trade_premium >= 0 and block_buyer_type == "机构":
        s3 = 14  # 平价+机构
    elif block_trade_premium > -5:
        s3 = 8
    else:
        s3 = 0   # 大幅折价
    
    # === ④ 股东增减持 (0-20) ===
    if holder_action in ("增持", "回购"):
        s4 = 20
    elif holder_action == "无变动":
        s4 = 14
    elif holder_action == "减持":
        s4 = 8
    elif lockup_days < 30:
        s4 = 0  # 即将解禁
    else:
        s4 = 14
    
    # === ⑤ 龙虎榜 (0-20) ===
    if dragon_institution_net > 0 and dragon_famous_trader:
        s5 = 20  # 机构+知名游资
    elif dragon_institution_net > 0:
        s5 = 14  # 机构净买入
    elif dragon_institution_net == 0 and dragon_famous_trader:
        s5 = 8   # 仅游资接力
    elif dragon_institution_net < 0:
        s5 = 0   # 机构净卖出
    else:
        s5 = 8   # 无上榜
    
    total = s1 + s2 + s3 + s4 + s5  # 满分100
    
    return {
        "total_score": total,
        "max_score": 100,
        "sub_scores": {
            "north_bound": {"score": s1, "max": 20, "label": "北向资金"},
            "margin_trading": {"score": s2, "max": 20, "label": "融资融券"},
            "block_trade": {"score": s3, "max": 20, "label": "大宗交易"},
            "holder_change": {"score": s4, "max": 20, "label": "股东增减持"},
            "dragon_list": {"score": s5, "max": 20, "label": "龙虎榜"},
        },
        "level": "强" if total >= 70 else ("中" if total >= 40 else "弱"),
        "signal": "buy" if total >= 70 else ("hold" if total >= 40 else "sell"),
    }
