# -*- coding: utf-8 -*-
"""
截图工具 - 截取屏幕并分析内容
"""

import sys
import os
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .base import BaseTool, ToolResult


class ScreenshotTool(BaseTool):
    """
    截图工具 - 直接将屏幕截图发送给 LLM
    
    不再调用 Vision API 生成描述，而是让主对话 LLM 直接"看到"图片
    这样避免信息损失
    """
    
    name = "screenshot"
    description = "看屏幕"
    usage_hint = "只要你想知道主人在做什么，就可以看。"
    usage_example = (
        "你看我在干嘛",
        "[curious] 欸？你在干嘛...好吧，让我看看你的屏幕。[CALL:screenshot]"
    )
    parallel_hint = "让我看看..."
    requires_context = False
    
    def __init__(self):
        self._screen_capture = None
    
    def _get_screen_capture(self):
        """懒加载屏幕截图器"""
        if self._screen_capture is None:
            from vision import get_screen_capture
            self._screen_capture = get_screen_capture()
        return self._screen_capture
    
    async def execute(self, context: str = "", **kwargs) -> ToolResult:
        """
        执行截图 - 返回图片数据让 LLM 直接看
        
        Returns:
            ToolResult 包含特殊格式的图片数据:
            data = "IMAGE_RESULT:jpeg:base64_data"
        """
        try:
            screen_capture = self._get_screen_capture()
            
            # 截取屏幕
            screenshot = screen_capture.capture(mode="full")
            
            # 返回特殊格式，让 response_handler 识别这是图片
            # 格式: IMAGE_RESULT:格式:base64数据
            image_data = f"IMAGE_RESULT:{screenshot.format}:{screenshot.base64_data}"
            
            logger.info(f"📸 截图完成: {screenshot.width}x{screenshot.height}")
            
            return ToolResult(
                success=True,
                data=image_data
            )
            
        except Exception as e:
            logger.error(f"截图失败: {e}")
            return ToolResult(
                success=False,
                data="",
                error=str(e)
            )


class ScreenshotDescribeTool(BaseTool):
    """
    截图描述工具 (聊天风格)
    
    与 ScreenshotTool 类似，但输出更口语化
    """
    
    name = "screenshot_describe"
    description = "看屏幕并用聊天风格描述"
    parallel_hint = "唔..."
    requires_context = True
    
    def __init__(self):
        self._vision_analyzer = None
    
    def _get_analyzer(self):
        if self._vision_analyzer is None:
            from vision import get_vision_analyzer
            self._vision_analyzer = get_vision_analyzer()
        return self._vision_analyzer
    
    async def execute(self, context: str = "", **kwargs) -> ToolResult:
        try:
            analyzer = self._get_analyzer()
            result = await analyzer.describe_for_chat(context)
            
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, data="", error=str(e))
