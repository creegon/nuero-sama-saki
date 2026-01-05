# -*- coding: utf-8 -*-
"""
Live2D 交互 Prompt 定义

定义触摸区域和对应的交互提示词
"""

# ====================
# 触摸区域定义
# ====================
# 相对于窗口高度的比例 (start, end)
TOUCH_ZONES = {
    "head": (0.0, 0.4),    # 头部: 0-40% (包括兔耳朵)
    "body": (0.4, 1.0),    # 身体: 40-100%
}


# ====================
# 触摸 Prompt 模板
# ====================
TOUCH_PROMPTS = {
    "head": "（主人正在摸你的脑袋）",
    "body": "（主人轻轻抚摸了你的身体）",
}


# ====================
# 拖动 Prompt
# ====================
# 开始拖动时触发
DRAG_START_PROMPT = "（主人开始拖动你）"
# 拖动结束时触发（如果拖的时间较长）
DRAG_END_PROMPT = "（主人终于把你放下来了，拖了好久）"


def get_touch_zone(y_ratio: float) -> str:
    """
    根据 y 位置比例获取触摸区域名称
    
    Args:
        y_ratio: y 坐标相对于窗口高度的比例 (0.0 ~ 1.0)
    
    Returns:
        触摸区域名称: "head" 或 "body"
    """
    for zone_name, (start, end) in TOUCH_ZONES.items():
        if start <= y_ratio < end:
            return zone_name
    return "body"  # 默认返回身体


def get_touch_prompt(zone: str) -> str:
    """
    获取触摸区域对应的 prompt
    
    Args:
        zone: 区域名称
    
    Returns:
        对应的 prompt 字符串
    """
    return TOUCH_PROMPTS.get(zone, TOUCH_PROMPTS["body"])

