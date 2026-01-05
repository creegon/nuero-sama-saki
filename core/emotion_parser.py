# -*- coding: utf-8 -*-
"""
表情解析器
负责解析 LLM 响应中的情绪标签
"""

import re
from typing import List, Tuple
from loguru import logger


class EmotionParser:
    """
    表情解析器
    
    解析 LLM 响应中的情绪标签，支持动态表情切换
    """
    
    def __init__(self, tool_executor=None):
        self.tool_executor = tool_executor
    
    def split_by_emotion(self, text: str) -> List[Tuple[str, str]]:
        """
        按情绪标签分段
        
        例如: "[pout] 第一句 [shm] 第二句" 
        返回: [("pout", "第一句"), ("shm", "第二句")]
        
        特殊处理: "[pout] [CALL:xxx] 文本" -> [(\"pout\", \"文本\")]
        工具调用会在解析时立即执行，不等待播放
        """
        # 🔥 防御性处理：修复 [xxx/yyy] 格式（只保留第一个情绪）
        # 例如 [neutral/shy] -> [neutral]
        text = re.sub(r'\[(\w+)/\w+\]', r'[\1]', text)
        
        # 先执行工具调用（立即异步执行，不阻塞 TTS）
        if self.tool_executor:
            self._execute_inline_tool_calls(text)
            text = self.tool_executor.remove_tool_calls(text)
        
        # 匹配情绪标签（只匹配已知的情绪标签，避免匹配其他方括号内容）
        from llm.character_prompt import EMOTION_TAGS
        emotion_pattern = r'\[(' + '|'.join(EMOTION_TAGS) + r')\]'
        
        # 找所有情绪标签位置
        matches = list(re.finditer(emotion_pattern, text, re.IGNORECASE))
        
        if not matches:
            # 没有情绪标签，使用默认 neutral
            clean = re.sub(r'\s+', '', text.strip())
            return [("neutral", clean)] if clean else []
        
        segments = []
        last_emotion = "neutral"
        
        for i, match in enumerate(matches):
            emotion = match.group(1).lower()
            start = match.end()
            
            # 到下一个情绪标签或文本末尾
            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(text)
            
            
            segment_text = text[start:end]
            
            # 🔥 移除所有情绪标签（确保TTS文本干净）
            segment_text = re.sub(emotion_pattern, '', segment_text, flags=re.IGNORECASE)
            
            # 🔥 移除工具调用（以防有残留）
            if self.tool_executor:
                segment_text = self.tool_executor.remove_tool_calls(segment_text)
            
            # 清理多余空白（合并连续空格为单个空格，而不是完全删除）
            segment_text = re.sub(r'\s+', ' ', segment_text).strip()

            
            if segment_text:
                segments.append((emotion, segment_text))
                last_emotion = emotion
            else:
                # 如果当前情绪段没有文本，记住这个情绪给下一段用
                last_emotion = emotion
        
        # 如果有记住的情绪但没有找到对应文本，尝试将其应用到下一段
        # （处理 [pout] [CALL:xxx] 文本 这种情况）
        
        # 检查第一个标签之前是否有文本
        if matches[0].start() > 0:
            before_text = text[:matches[0].start()]
            before_text = re.sub(r'\s+', ' ', before_text).strip()
            if before_text:
                segments.insert(0, ("neutral", before_text))
        
        return segments
    
    def _execute_inline_tool_calls(self, text: str) -> None:
        """
        执行文本中的工具调用（不阻塞）
        
        工具调用应该在解析时立即执行，而不是等到对应的 TTS 播放完成。
        例如: [Call:move_self:bottom_left] 应该在解析时立即移动。
        """
        import asyncio
        
        calls = self.tool_executor.parse_tool_calls(text)
        for tool_name, args, _ in calls:
            logger.info(f"🔧 立即执行内联工具: {tool_name}" + (f" (args: {args})" if args else ""))
            try:
                # 创建异步任务，不等待结果
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(
                        self.tool_executor.execute_tool(tool_name, args=args)
                    )
                else:
                    # 如果没有运行的事件循环，同步执行
                    loop.run_until_complete(
                        self.tool_executor.execute_tool(tool_name, args=args)
                    )
            except Exception as e:
                logger.error(f"内联工具执行失败: {e}")
    
    def extract_initial_emotion(self, text: str) -> str:
        """提取首个情绪标签"""
        from llm.character_prompt import EMOTION_TAGS
        emotion_pattern = r'\[(' + '|'.join(EMOTION_TAGS) + r')\]'
        match = re.search(emotion_pattern, text, re.IGNORECASE)
        return match.group(1).lower() if match else "neutral"


# 全局单例
_emotion_parser = None


def get_emotion_parser(tool_executor=None) -> EmotionParser:
    """获取全局表情解析器实例"""
    global _emotion_parser
    if _emotion_parser is None:
        _emotion_parser = EmotionParser(tool_executor)
    return _emotion_parser
