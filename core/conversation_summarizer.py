# -*- coding: utf-8 -*-
"""
会话摘要生成器
负责将对话历史摘要并存入知识库作为情境记忆 (episode)
"""

import asyncio
import time
from typing import List, Dict, Optional
from loguru import logger


class ConversationSummarizer:
    """
    会话摘要生成器
    
    当 conversation_history 超过阈值时，自动：
    1. 摘要旧消息
    2. 存入知识库作为 episode 记忆
    3. 截断历史
    
    情境记忆 vs 事实记忆：
    - 情境记忆 (episode): "今天下午聊了面试、压力、放松" → 用于回答"刚才聊什么"
    - 事实记忆 (fact): "主人明天要面试" → 由后台小祥提取
    """
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self._kb = None
    
    def _get_kb(self):
        """懒加载知识库"""
        if self._kb is None:
            from knowledge import get_knowledge_base
            self._kb = get_knowledge_base()
        return self._kb
    
    async def check_and_summarize(
        self, 
        conversation_history: List[Dict],
        threshold: int = 30,
        keep_recent: int = 10
    ) -> List[Dict]:
        """
        检查并摘要对话历史
        
        Args:
            conversation_history: 当前对话历史
            threshold: 触发摘要的阈值（消息数）
            keep_recent: 保留最近的消息数
            
        Returns:
            处理后的对话历史（可能被截断）
        """
        if len(conversation_history) < threshold:
            return conversation_history
        
        # 需要摘要的旧消息
        messages_to_summarize = conversation_history[:-keep_recent]
        messages_to_keep = conversation_history[-keep_recent:]
        
        try:
            # 生成摘要
            summary = await self._generate_summary(messages_to_summarize)
            
            if summary:
                # 存入知识库作为 episode
                self._save_as_episode(summary)
                
                logger.info(f"📝 对话摘要已生成: {summary[:50]}...")
                
                # 返回精简后的历史（带摘要标记）
                summary_marker = {
                    "role": "system",
                    "content": f"[之前聊了: {summary[:100]}...]"
                }
                return [summary_marker] + messages_to_keep
            else:
                # 摘要失败，直接截断
                return messages_to_keep
                
        except Exception as e:
            logger.error(f"生成对话摘要失败: {e}")
            return messages_to_keep
    
    async def _generate_summary(self, messages: List[Dict]) -> str:
        """
        使用 LLM 生成对话摘要
        
        Args:
            messages: 要摘要的消息列表
            
        Returns:
            摘要文本
        """
        # 格式化消息
        formatted = []
        for msg in messages:
            role = "主人" if msg.get("role") == "user" else "小祥"
            content = msg.get("content", "")
            # 清理情绪标签
            import re
            content = re.sub(r'\[\w+\]', '', content).strip()
            if content:
                formatted.append(f"{role}: {content[:100]}")
        
        if not formatted:
            return ""
        
        conversation_text = "\n".join(formatted[-20:])  # 最多取20条
        
        prompt = f"""请简洁概括以下对话的主要话题和具体内容（80-120字）：

要求：
1. 包含具体的话题/关键词（不要只说"聊天"）
2. 提及讨论的具体内容或观点
3. 如有特别的互动（如调侃、吐槽），也要提及

对话内容：
{conversation_text}

摘要："""
        
        try:
            messages = [{"role": "user", "content": prompt}]
            
            full_response = ""
            async for chunk in self.llm_client.chat_stream(
                messages,
                system_prompt="你是一个对话摘要助手。只输出简洁的摘要，不要解释。"
            ):
                full_response += chunk
            
            # 清理摘要
            summary = full_response.strip()
            summary = summary.replace("摘要：", "").replace("摘要:", "").strip()
            
            return summary[:200]  # 增加长度限制
            
        except Exception as e:
            logger.error(f"LLM 摘要生成失败: {e}")
            return ""
    
    def _save_as_episode(self, summary: str):
        """
        将摘要存入知识库作为情境记忆
        
        Args:
            summary: 摘要文本
        """
        try:
            from datetime import datetime
            now = datetime.now()
            time_str = now.strftime("%Y-%m-%d %H:%M")
            
            # 添加时间标记
            episode_text = f"[{time_str}] {summary}"
            
            kb = self._get_kb()
            doc_id = kb.add(
                episode_text,
                metadata={
                    "category": "episode",
                    "importance": 1.0,
                    "source": "conversation_summarizer",
                }
            )
            
            logger.info(f"📝 情境记忆已保存: [{doc_id}] {episode_text[:50]}...")
            
        except Exception as e:
            logger.error(f"保存情境记忆失败: {e}")
    
    async def force_summarize(self, conversation_history: List[Dict]) -> str:
        """
        强制生成当前对话的摘要（不截断历史）
        用于会话结束时保存
        
        Args:
            conversation_history: 对话历史
            
        Returns:
            摘要文本
        """
        if not conversation_history:
            return ""
        
        try:
            summary = await self._generate_summary(conversation_history)
            if summary:
                self._save_as_episode(summary)
            return summary
        except Exception as e:
            logger.error(f"强制摘要失败: {e}")
            return ""


# 全局单例
_conversation_summarizer: Optional[ConversationSummarizer] = None


def get_conversation_summarizer(llm_client=None) -> Optional[ConversationSummarizer]:
    """获取全局会话摘要器实例"""
    global _conversation_summarizer
    if _conversation_summarizer is None:
        if llm_client is None:
            return None
        _conversation_summarizer = ConversationSummarizer(llm_client)
    return _conversation_summarizer
