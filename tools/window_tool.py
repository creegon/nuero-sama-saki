# -*- coding: utf-8 -*-
"""
窗口工具 - 获取前台窗口信息
"""

import sys
import os
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .base import BaseTool, ToolResult


class WindowTitleTool(BaseTool):
    """
    窗口标题工具
    
    获取当前前台窗口的标题，帮助了解主人在做什么
    """
    
    name = "window_title"
    description = "获取前台窗口标题"
    usage_hint = "了解主人正在使用什么程序。"
    usage_example = (
        "你在干嘛",
        "[curious] 让我看看你打开的是什么...[CALL:window_title]"
    )
    parallel_hint = "看看..."
    requires_context = False
    
    async def execute(self, context: str = "", **kwargs) -> ToolResult:
        """获取前台窗口标题"""
        try:
            title = self._get_foreground_window_title()
            
            if title:
                logger.info(f"🪟 前台窗口: {title}")
                return ToolResult(
                    success=True,
                    data=f"主人正在使用: {title}"
                )
            else:
                logger.info("🪟 无法获取前台窗口")
                return ToolResult(
                    success=True,
                    data="[无法获取前台窗口信息]"
                )
                
        except Exception as e:
            logger.error(f"获取窗口标题失败: {e}")
            return ToolResult(success=False, data="", error=str(e))
    
    def _get_foreground_window_title(self) -> str:
        """获取前台窗口标题（Windows 专用）"""
        try:
            import ctypes
            from ctypes import wintypes
            
            user32 = ctypes.windll.user32
            
            # 获取前台窗口句柄
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return ""
            
            # 获取窗口标题长度
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return ""
            
            # 获取窗口标题
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            
            return buffer.value
            
        except Exception as e:
            logger.debug(f"获取窗口标题异常: {e}")
            return ""
