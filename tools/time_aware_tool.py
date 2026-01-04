# -*- coding: utf-8 -*-
"""
时间感知工具 - 让桌宠知道当前时间

提供:
- 当前时间 (小时、分钟)
- 时间段 (凌晨/早上/上午/中午/下午/傍晚/晚上/深夜)
- 星期几
- 是否节假日/特殊日期
"""

from datetime import datetime
from loguru import logger

from .base import BaseTool, ToolResult


# 时间段定义
TIME_PERIODS = {
    (0, 5): ("凌晨", "很晚了", "sleepy"),
    (5, 7): ("清晨", "起得真早", "surprised"),
    (7, 9): ("早上", "早上好", "happy"),
    (9, 11): ("上午", "上午好", "neutral"),
    (11, 13): ("中午", "该吃午饭了", "curious"),
    (13, 14): ("午后", "午休时间", "sleepy"),
    (14, 17): ("下午", "下午好", "neutral"),
    (17, 19): ("傍晚", "快到晚饭时间了", "curious"),
    (19, 22): ("晚上", "晚上好", "neutral"),
    (22, 24): ("深夜", "这么晚还不睡", "worried"),
}

# 星期映射
WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

# 特殊日期
SPECIAL_DATES = {
    (1, 1): ("元旦", "新年快乐！新的一年要继续努力哦~"),
    (2, 14): ("情人节", "今天是情人节呢..."),
    (3, 8): ("妇女节", "三八妇女节快乐~"),
    (4, 1): ("愚人节", "今天是愚人节，小心被骗哦~"),
    (5, 1): ("劳动节", "劳动节快乐！今天有好好休息吗？"),
    (5, 4): ("青年节", "青年节快乐！"),
    (6, 1): ("儿童节", "儿童节快乐~虽然你已经不是小孩子了吧..."),
    (10, 1): ("国庆节", "国庆节快乐！"),
    (10, 31): ("万圣节", "万圣节快乐！不给糖就捣蛋~"),
    (12, 24): ("平安夜", "平安夜快乐~"),
    (12, 25): ("圣诞节", "圣诞节快乐！Merry Christmas~"),
    (12, 31): ("跨年夜", "今天是一年的最后一天呢..."),
}


class TimeAwareTool(BaseTool):
    """
    时间感知工具
    
    获取当前时间信息，用于生成符合时间的问候语
    """
    
    name = "time_aware"
    description = "获取当前时间信息"
    usage_hint = "了解现在几点、星期几、是否特殊日期。"
    usage_example = (
        "现在几点了",
        "[curious] 让我看看现在几点了... [CALL:time_aware]"
    )
    parallel_hint = "嗯..."
    requires_context = False
    
    async def execute(self, context: str = "", **kwargs) -> ToolResult:
        """
        获取当前时间信息
        
        Returns:
            ToolResult 包含时间详情
        """
        try:
            now = datetime.now()
            
            # 基本时间信息
            hour = now.hour
            minute = now.minute
            month = now.month
            day = now.day
            weekday = now.weekday()
            
            # 确定时间段
            period_name = "未知"
            period_hint = ""
            period_emotion = "neutral"
            
            for (start, end), (name, hint, emotion) in TIME_PERIODS.items():
                if start <= hour < end:
                    period_name = name
                    period_hint = hint
                    period_emotion = emotion
                    break
            
            # 检查特殊日期
            special_date = SPECIAL_DATES.get((month, day))
            special_name = special_date[0] if special_date else None
            special_hint = special_date[1] if special_date else None
            
            # 判断是否周末
            is_weekend = weekday >= 5
            
            # 构建结果
            result = {
                "time": f"{hour:02d}:{minute:02d}",
                "hour": hour,
                "minute": minute,
                "period": period_name,
                "period_hint": period_hint,
                "period_emotion": period_emotion,
                "weekday": WEEKDAYS[weekday],
                "is_weekend": is_weekend,
                "date": f"{month}月{day}日",
                "special_date": special_name,
                "special_hint": special_hint,
            }
            
            # 格式化为易读文本
            text_parts = [
                f"现在是 {result['time']}，{period_name}。",
                f"今天是 {result['date']}，{result['weekday']}。",
            ]
            
            if is_weekend:
                text_parts.append("今天是周末。")
            
            if special_name:
                text_parts.append(f"今天是{special_name}！{special_hint}")
            
            text_parts.append(f"建议情绪: {period_emotion}")
            text_parts.append(f"建议问候: {period_hint}")
            
            result_text = "\n".join(text_parts)
            
            logger.info(f"⏰ 时间感知: {result['time']} {period_name}")
            
            return ToolResult(
                success=True,
                data=result_text
            )
            
        except Exception as e:
            logger.error(f"时间感知失败: {e}")
            return ToolResult(
                success=False,
                data="",
                error=str(e)
            )


def get_time_info() -> dict:
    """
    直接获取时间信息 (非异步版本，用于启动打招呼)
    
    Returns:
        时间信息字典
    """
    now = datetime.now()
    
    hour = now.hour
    minute = now.minute
    month = now.month
    day = now.day
    weekday = now.weekday()
    
    # 确定时间段
    period_name = "未知"
    period_hint = ""
    period_emotion = "neutral"
    
    for (start, end), (name, hint, emotion) in TIME_PERIODS.items():
        if start <= hour < end:
            period_name = name
            period_hint = hint
            period_emotion = emotion
            break
    
    # 检查特殊日期
    special_date = SPECIAL_DATES.get((month, day))
    
    return {
        "time": f"{hour:02d}:{minute:02d}",
        "hour": hour,
        "minute": minute,
        "period": period_name,
        "period_hint": period_hint,
        "period_emotion": period_emotion,
        "weekday": WEEKDAYS[weekday],
        "is_weekend": weekday >= 5,
        "date": f"{month}月{day}日",
        "special_date": special_date[0] if special_date else None,
        "special_hint": special_date[1] if special_date else None,
    }
