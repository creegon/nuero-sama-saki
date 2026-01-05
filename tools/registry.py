# -*- coding: utf-8 -*-
"""
工具注册表 - 管理所有可用工具
支持动态注册和发现
"""

from typing import Dict, Optional, List
from loguru import logger

from .base import BaseTool


class ToolRegistry:
    """
    工具注册表
    
    管理所有已注册的工具，支持:
    - 注册新工具
    - 按名称获取工具
    - 生成 prompt 描述
    """
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool) -> None:
        """注册一个工具"""
        if tool.name in self._tools:
            logger.warning(f"工具 {tool.name} 已存在，将被覆盖")
        
        self._tools[tool.name] = tool
        logger.debug(f"注册工具: {tool.name}")
    
    def get(self, name: str) -> Optional[BaseTool]:
        """按名称获取工具"""
        return self._tools.get(name)
    
    def list_tools(self) -> List[str]:
        """列出所有工具名称"""
        return list(self._tools.keys())
    
    def get_all(self) -> Dict[str, BaseTool]:
        """获取所有工具"""
        return self._tools.copy()
    
    def get_prompt_section(self) -> str:
        """
        生成用于 prompt 的工具描述段落
        """
        if not self._tools:
            return ""
        
        lines = ["**你的能力：**", ""]
        
        for i, tool in enumerate(self._tools.values(), 1):
            lines.append(f"{i}. {tool.get_full_prompt_description()}")
            lines.append("")  # 空行分隔
        
        lines.append("**使用方法：**")
        lines.append('需要时直接加 [CALL:工具名]，不用刻意说"让我查查""让我看看"这种过渡语。')
        lines.append('收到结果后，基于结果自然地继续回答，不用特意说"查到了"。')
        
        return "\n".join(lines)


# 全局注册表
_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """获取全局工具注册表"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        # 注册默认工具
        _register_default_tools(_registry)
    return _registry


def _register_default_tools(registry: ToolRegistry) -> None:
    """注册默认工具"""
    from .screenshot_tool import ScreenshotTool
    from .memory_tools import KnowledgeSearchTool, AddKnowledgeTool
    from .live2d_control_tool import Live2DControlTool
    from .web_search_tool import WebSearchTool
    # from .window_tool import WindowTitleTool  # 功能已自动附加到 prompt

    # 🔥 screenshot 仍然保留为工具，让小祥可以主动调用
    # window_title 不再作为工具（自动附加到每次对话）
    registry.register(ScreenshotTool())
    registry.register(KnowledgeSearchTool())
    registry.register(AddKnowledgeTool())
    # TimeAwareTool 已移除，时间信息直接注入 prompt
    registry.register(Live2DControlTool())
    registry.register(WebSearchTool())

    logger.info(f"🔧 已注册 {len(registry.list_tools())} 个工具: {registry.list_tools()}")


# 便捷函数
def get_tool(name: str) -> Optional[BaseTool]:
    """获取工具"""
    return get_tool_registry().get(name)


def list_tools() -> List[str]:
    """列出所有工具"""
    return get_tool_registry().list_tools()
