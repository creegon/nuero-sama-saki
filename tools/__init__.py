# -*- coding: utf-8 -*-
"""
工具系统模块

提供可扩展的工具调用框架:
- BaseTool: 工具基类
- ToolRegistry: 工具注册表
- ToolExecutor: 工具执行器

添加新工具:
1. 创建继承 BaseTool 的类
2. 在 registry.py 的 _register_default_tools() 中注册
"""

from .base import BaseTool, ToolResult
from .registry import (
    ToolRegistry,
    get_tool_registry,
    get_tool,
    list_tools,
)
from .executor import ToolExecutor, get_tool_executor

__all__ = [
    # 基类
    "BaseTool",
    "ToolResult",
    # 注册表
    "ToolRegistry",
    "get_tool_registry",
    "get_tool",
    "list_tools",
    # 执行器
    "ToolExecutor",
    "get_tool_executor",
]
