# -*- coding: utf-8 -*-
"""
工具基类 - 所有工具继承此类
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Any
    error: Optional[str] = None


class BaseTool(ABC):
    """
    工具基类
    
    所有工具必须实现:
    - name: 工具名称
    - description: 工具描述
    - execute(): 执行方法
    """
    
    # 工具名称 (用于 [CALL:name])
    name: str = "base_tool"
    
    # 工具描述 (简短)
    description: str = "基础工具"
    
    # 工具用途说明 (给 LLM 看的，解释什么时候用)
    usage_hint: str = ""
    
    # 使用示例 (User 说什么 -> Assistant 怎么调用)
    usage_example: tuple[str, str] = ("", "")  # (user_says, assistant_response)
    
    # 执行时的提示语 (用于并行执行时先说的话)
    parallel_hint: str = ""
    
    # 是否需要对话上下文
    requires_context: bool = False
    
    @abstractmethod
    async def execute(self, context: str = "", **kwargs) -> ToolResult:
        """
        执行工具
        
        Args:
            context: 对话上下文
            **kwargs: 额外参数
        
        Returns:
            ToolResult 对象
        """
        pass
    
    def get_prompt_description(self) -> str:
        """获取用于 prompt 的简短描述"""
        return f"[CALL:{self.name}] {self.description}"
    
    def get_full_prompt_description(self) -> str:
        """获取用于 prompt 的完整描述（包括示例）"""
        lines = [f"**{self.description}** [CALL:{self.name}]"]
        
        if self.usage_hint:
            lines.append(self.usage_hint)
        
        if self.usage_example[0] and self.usage_example[1]:
            lines.append("示例：")
            lines.append(f"User: {self.usage_example[0]}")
            lines.append(f"Assistant: {self.usage_example[1]}")
        
        return "\n".join(lines)

