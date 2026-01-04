# -*- coding: utf-8 -*-
"""
记忆相关工具
包含：
1. KnowledgeSearchTool: 搜索记忆
2. AddKnowledgeTool: 添加记忆
"""

import sys
import os
import re
from loguru import logger
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .base import BaseTool, ToolResult


class KnowledgeSearchTool(BaseTool):
    """
    知识库搜索工具
    
    搜索知识库获取相关信息
    """
    
    name = "knowledge"
    description = "搜索记忆/知识库"
    usage_hint = "回忆关于主人或某事的信息，需要提供搜索关键词。"
    usage_example = (
        "你还记得我最喜欢吃什么吗",
        "[curious] 我怎么知道你喜欢吃什么啦！但没办法，让我去我的知识库里查查好了。[CALL:knowledge:主人喜欢的食物]"
    )
    parallel_hint = "让我想想..."
    requires_context = False  # 改为 False，使用 args 参数
    
    def __init__(self):
        self._kb = None
    
    def _get_kb(self):
        """懒加载知识库"""
        if self._kb is None:
            from knowledge import get_knowledge_base
            self._kb = get_knowledge_base()
        return self._kb
    
    async def execute(self, context: str = "", args: str = "", **kwargs) -> ToolResult:
        """执行知识库搜索"""
        try:
            kb = self._get_kb()
            
            # 优先使用 args（LLM 指定的查询），否则使用 context
            query = args.strip() if args and args.strip() else context
            
            # 如果查询还是占位符，使用通用搜索
            if not query or query == "[语音输入]":
                query = "主人 最近 相关"
                logger.warning(f"📚 知识库搜索: 未提供有效查询，使用默认: {query}")
            
            # 搜索知识库
            result = kb.get_context_for_llm(query, n_results=3)
            
            if result:
                logger.info(f"📚 知识库搜索成功: {len(result)}字")
                return ToolResult(
                    success=True,
                    data=result
                )
            else:
                logger.info("📚 知识库无相关结果")
                return ToolResult(
                    success=True,
                    data="[没有找到相关记忆]"
                )
            
        except Exception as e:
            logger.error(f"知识库搜索失败: {e}")
            return ToolResult(success=False, data="", error=str(e))


class AddKnowledgeTool(BaseTool):
    """
    添加知识工具

    让桌宠主动记忆对话中的重要信息
    """

    name = "add_knowledge"
    description = "记住信息"
    usage_hint = "当主人告诉你重要信息时，你可以主动记住它。"
    usage_example = (
        "我最喜欢吃寿司",
        "[happy] 原来是这样啊，那好吧，本神明勉强记住啦！[CALL:add_knowledge:主人最喜欢吃寿司]"
    )
    parallel_hint = "让我记住..."
    requires_context = True

    def __init__(self):
        self._kb = None

    def _get_kb(self):
        """懒加载知识库"""
        if self._kb is None:
            from knowledge import get_knowledge_base
            self._kb = get_knowledge_base()
        return self._kb

    async def execute(self, context: str = "", args: str = "", **kwargs) -> ToolResult:
        """执行添加知识"""
        try:
            kb = self._get_kb()
            
            # 优先使用显式参数
            content_to_save = args.strip()
            
            # 如果没有参数，尝试自动提取（向后兼容）
            if not content_to_save:
                # 从 kwargs 中获取对话历史
                conversation_history = kwargs.get("conversation_history", [])
                for msg in reversed(conversation_history):
                    if msg["role"] == "user":
                        content_to_save = msg["content"]
                        break
                if not content_to_save:
                    content_to_save = context
            
            # 清理系统标记
            content_to_save = re.sub(r'\[系统:.*?\]', '', content_to_save).strip()
            
            if not content_to_save:
                return ToolResult(success=False, error="没有可保存的内容")

            # 构建知识条目
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            knowledge_entry = f"{content_to_save} (记录于 {timestamp})"

            # 添加到知识库
            doc_id = kb.add(
                text=knowledge_entry,
                metadata={
                    "category": "user_info",
                    "source": "conversation",
                    "timestamp": timestamp
                }
            )

            logger.info(f"💾 已记住: [{doc_id}] {content_to_save[:50]}...")

            return ToolResult(
                success=True,
                data=f"已记住：{content_to_save[:30]}..."
            )

        except Exception as e:
            logger.error(f"添加知识失败: {e}")
            return ToolResult(success=False, data="", error=str(e))
