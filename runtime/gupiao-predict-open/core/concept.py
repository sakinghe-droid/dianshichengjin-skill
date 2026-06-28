"""
concept.py — 概念题材关联引擎

主题材 + 子题材映射（通过成分股交集）

用法:
    from core.concept import map_sub_topics
"""

from typing import Dict, List, Set


def map_sub_topics(
    main_topic_stocks: List[str],
    sub_topics: Dict[str, List[str]],
    min_overlap: float = 0.10,
) -> Dict:
    """
    主题材 → 子题材关联映射
    
    Args:
        main_topic_stocks: 主题材成分股代码列表
        sub_topics: {子题材名: [成分股代码列表], ...}
        min_overlap: 最小交集率阈值
    
    Returns:
        {
            "strong": [{name, overlap_rate, common_stocks}, ...],
            "moderate": [...],
            "weak": [...],
        }
    """
    main_set = set(main_topic_stocks)
    main_len = len(main_set)
    
    if main_len == 0:
        return {"strong": [], "moderate": [], "weak": []}
    
    strong, moderate, weak = [], [], []
    
    for name, stocks in sub_topics.items():
        sub_set = set(stocks)
        common = main_set & sub_set
        overlap_rate = len(common) / main_len
        
        entry = {
            "name": name,
            "overlap_rate": round(overlap_rate, 3),
            "common_count": len(common),
            "common_stocks": list(common)[:10],  # 最多返回10个
        }
        
        if overlap_rate > 0.30:
            strong.append(entry)
        elif overlap_rate > min_overlap:
            moderate.append(entry)
        else:
            weak.append(entry)
    
    # 按重叠率降序
    strong.sort(key=lambda x: -x["overlap_rate"])
    moderate.sort(key=lambda x: -x["overlap_rate"])
    weak.sort(key=lambda x: -x["overlap_rate"])
    
    return {
        "strong": strong,
        "moderate": moderate,
        "weak": weak,
        "main_topic_size": main_len,
        "total_sub_topics": len(sub_topics),
    }


def get_stock_full_tags(
    code: str,
    topic_map: Dict,
) -> List[str]:
    """
    获取个股完整概念标签
    
    从 concept_topic_map 中提取该股票所属的所有子题材
    """
    tags = []
    for category in ("strong", "moderate", "weak"):
        for entry in topic_map.get(category, []):
            if code in entry.get("common_stocks", []):
                tags.append(entry["name"])
    return tags
