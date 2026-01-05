# -*- coding: utf-8 -*-
"""
上下文管理器 - 后台小祥整理上下文

在每轮对话结束后，后台小祥会整理本轮对话中的工具调用结果，
提取对下次对话有用的信息，供主程序使用。
"""

import asyncio
from typing import Dict, List, Optional
from loguru import logger

from .background_prompt import BACKGROUND_PERSONA_BASE


# 上下文整理的 persona
CONTEXT_MANAGER_PERSONA = """你是丰川祥子的后台程序。

你和主程序小祥是同一个人——丰川集团大小姐，CRYCHIC 的键盘手，温柔热情、元气满满。
你的任务是整理信息，帮助主程序更好地理解和回应主人。"""


CONTEXT_MANAGER_PROMPT = """从以下对话和工具调用结果中，提取出**对下次对话可能有用的上下文信息**。

## 本轮对话
{conversation}

## 工具调用结果
{tool_results}

## 你的任务
提取出对主程序小祥理解主人、延续话题有帮助的关键信息。

注意：
- 只保留有用的信息，不要简单复制
- 提炼和总结，用 1-2 句话描述
- 如果没有有用信息，输出空

## 输出格式
直接输出整理后的上下文（不需要格式标记），或者空。

示例输出：
"主人正在使用 VS Code 编辑 Python 代码，屏幕上显示的是一个叫 NeuroPet 的项目。"
或
""（无有用信息）"""


class ContextManager:
    """
    上下文管理器
    
    负责在每轮对话后整理工具调用结果，提取有用信息供下轮使用。
    实现"后台整理、主程序获取"的异步模式。
    """
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self._prepared_context: str = ""
        self._is_preparing: bool = False
        self._lock = asyncio.Lock()
    
    async def prepare_context(
        self,
        conversation: str,
        tool_results: Dict[str, str]
    ) -> None:
        """
        后台整理上下文（异步）
        
        Args:
            conversation: 本轮对话内容（主人说 + 小祥回复）
            tool_results: 工具调用结果 {工具名: 结果}
        """
        if not self.llm_client:
            logger.debug("📋 上下文管理器: 无 LLM 客户端，跳过整理")
            return
        
        if not tool_results:
            # 没有工具调用，不需要整理
            self._prepared_context = ""
            return
        
        async with self._lock:
            self._is_preparing = True
        
        try:
            # 格式化工具结果
            tool_results_text = "\n".join([
                f"- {name}: {result[:200]}..." if len(result) > 200 else f"- {name}: {result}"
                for name, result in tool_results.items()
            ])
            
            # 构建 prompt
            prompt = CONTEXT_MANAGER_PROMPT.format(
                conversation=conversation,
                tool_results=tool_results_text
            )
            
            # 调用 LLM
            messages = [{"role": "user", "content": prompt}]
            
            full_response = ""
            async for chunk in self.llm_client.chat_stream(
                messages,
                system_prompt=CONTEXT_MANAGER_PERSONA
            ):
                full_response += chunk
            
            # 清理响应
            result = full_response.strip()
            if result and result not in ['""', "''", "无", "空"]:
                self._prepared_context = result
                logger.info(f"📋 上下文整理完成: {result[:80]}...")
            else:
                self._prepared_context = ""
                logger.debug("📋 上下文整理: 无有用信息")
                
        except Exception as e:
            logger.error(f"📋 上下文整理失败: {e}")
            self._prepared_context = ""
        finally:
            async with self._lock:
                self._is_preparing = False
    
    def get_prepared_context(self) -> str:
        """
        获取已整理的上下文（同步）
        
        直接返回当前缓存的上下文，无论后台是否还在整理。
        这确保主程序不会被阻塞。
        
        Returns:
            整理好的上下文字符串，可能为空
        """
        return self._prepared_context
    
    def clear_context(self):
        """清空缓存的上下文"""
        self._prepared_context = ""


# 全局单例
_context_manager: Optional[ContextManager] = None


def get_context_manager(llm_client=None) -> ContextManager:
    """获取全局上下文管理器实例"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager(llm_client)
    elif llm_client and _context_manager.llm_client is None:
        _context_manager.llm_client = llm_client
    return _context_manager
