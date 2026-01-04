# -*- coding: utf-8 -*-
"""
Prompt Builder 模块
统一构建 System Prompt 和 User Prompt，参考 MaiBot 架构

结构：
- System Prompt: 角色设定 + 规则 + 工具 + 记忆（一次性注入）
- User Prompt: 时间 + 对话历史（简洁格式）+ 当前输入
"""

from datetime import datetime
from loguru import logger
from typing import List, Dict, Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class PromptBuilder:
    """
    Prompt 构建器
    
    一次性构建完整的 System Prompt，避免每轮调用知识库造成污染
    """
    
    def __init__(self):
        self._cached_system_prompt = None
        self._last_build_time = None
        self._cache_duration = 300  # 5 分钟缓存
    
    def build_system_prompt(self, force_refresh: bool = False) -> str:
        """
        构建完整的 System Prompt（带缓存）
        
        包含：
        1. 角色设定
        2. 对话规则
        3. 工具说明
        4. 记忆/背景信息
        
        Returns:
            完整的 system prompt
        """
        import time
        
        # 检查缓存
        if not force_refresh and self._cached_system_prompt:
            if self._last_build_time and (time.time() - self._last_build_time) < self._cache_duration:
                return self._cached_system_prompt
        
        logger.debug("🔧 构建 System Prompt...")
        
        # 获取基础角色 prompt
        from llm.character_prompt import get_system_prompt
        base_prompt = get_system_prompt()
        
        # 获取记忆上下文（一次性注入）
        memory_context = self._build_memory_context()
        
        # 组合
        full_prompt = base_prompt
        if memory_context:
            full_prompt += f"\n\n{memory_context}"
        
        self._cached_system_prompt = full_prompt
        self._last_build_time = time.time()
        
        return full_prompt
    
    def _build_memory_context(self) -> str:
        """构建记忆上下文（一次性）"""
        from core.memory_injector import get_memory_injector
        
        parts = []
        injector = get_memory_injector()
        
        # 1. 时间信息
        time_context = injector.get_time_context()
        if time_context:
            parts.append(time_context)
        
        # 2. 系统上下文/背景设定
        system_context = injector.get_system_context()
        if system_context:
            parts.append(system_context)
        
        # 3. 重要记忆
        important = injector.get_important_memories()
        if important:
            parts.append(important)
        
        # 4. 最近记忆
        recent = injector.get_recent_memories()
        if recent:
            parts.append(recent)
        
        return "\n\n".join(parts)
    
    def build_user_prompt(
        self,
        current_input: str,
        conversation_history: List[Dict],
        max_history: int = 10
    ) -> str:
        """
        构建 User Prompt（简洁格式）
        
        格式参考 MaiBot：
        ```
        当前时间：2026-01-02 01:15
        
        对话记录：
        01:10:15, 主人: 你好啊
        01:10:18, 小祥(你): [happy] 嗯？怎么了
        01:12:30, 主人: 今天天气怎么样？
        
        现在主人说的: 帮我查一下明天的天气
        ```
        
        Args:
            current_input: 当前用户输入
            conversation_history: 对话历史
            max_history: 最大历史记录数
            
        Returns:
            格式化后的 user prompt
        """
        lines = []
        
        # 1. 当前时间
        now = datetime.now()
        lines.append(f"当前时间：{now.strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        
        # 2. 对话记录（简洁格式）
        if conversation_history:
            lines.append("对话记录：")
            
            # 只取最近的 N 条
            recent = conversation_history[-max_history:]
            
            for msg in recent:
                role = msg.get("role", "")
                content = msg.get("content", "")
                timestamp = msg.get("timestamp", "")
                
                # 格式化时间戳
                if timestamp:
                    time_str = timestamp
                else:
                    time_str = now.strftime("%H:%M:%S")
                
                # 角色名称
                if role == "user":
                    role_name = "主人"
                elif role == "assistant":
                    role_name = f"{config.CHARACTER_NAME}(你)"
                else:
                    role_name = role
                
                # 跳过占位符
                if content == "[语音输入]":
                    content = "(语音)"
                
                # 截断过长内容
                if len(content) > 100:
                    content = content[:97] + "..."
                
                lines.append(f"{time_str}, {role_name}: {content}")
            
            lines.append("")
        
        # 3. 当前输入
        lines.append(f"现在主人说的: {current_input}")
        
        return "\n".join(lines)
    
    def build_messages(
        self,
        current_input: str,
        conversation_history: List[Dict] = None,
        force_refresh_system: bool = False
    ) -> List[Dict]:
        """
        构建完整的消息列表（新架构）
        
        只返回两条消息：
        1. system: 完整的角色设定 + 记忆
        2. user: 对话历史 + 当前输入
        
        Args:
            current_input: 当前用户输入
            conversation_history: 对话历史
            force_refresh_system: 是否强制刷新 system prompt
            
        Returns:
            [{"role": "system", ...}, {"role": "user", ...}]
        """
        system_prompt = self.build_system_prompt(force_refresh=force_refresh_system)
        user_prompt = self.build_user_prompt(
            current_input=current_input,
            conversation_history=conversation_history or []
        )
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    def invalidate_cache(self):
        """使缓存失效（记忆更新时调用）"""
        self._cached_system_prompt = None
        self._last_build_time = None


# 全局单例
_prompt_builder: Optional[PromptBuilder] = None


def get_prompt_builder() -> PromptBuilder:
    """获取全局 PromptBuilder 实例"""
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = PromptBuilder()
    return _prompt_builder
