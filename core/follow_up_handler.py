# -*- coding: utf-8 -*-
"""
追问处理器

从 ResponseHandler 提取的追问逻辑
"""

import asyncio
import random
import re
from typing import Callable, List, Optional
import sys
import os

# 添加根目录到path以导入config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

from loguru import logger


class FollowUpHandler:
    """追问处理器 - 处理追问判断、生成和播放"""
    
    def __init__(
        self,
        llm_client,
        audio_queue,
        player,
        tts_engine=None,
        config=None,
    ):
        self.llm_client = llm_client
        self.audio_queue = audio_queue
        self.player = player
        self.tts_engine = tts_engine
        self.config = config
        
        # 取消标志（由外部设置）
        self._cancelled = False
        
        # 回调函数
        self._get_recent_context: Optional[Callable[[], str]] = None
        self._split_by_emotion: Optional[Callable[[str], List[tuple]]] = None
        self._split_into_chunks: Optional[Callable[[str], List[str]]] = None
        self._append_history: Optional[Callable[[dict], None]] = None
    
    def set_callbacks(
        self,
        get_recent_context: Callable[[], str] = None,
        split_by_emotion: Callable[[str], List[tuple]] = None,
        split_into_chunks: Callable[[str], List[str]] = None,
        append_history: Callable[[dict], None] = None,
    ):
        """设置回调函数"""
        if get_recent_context:
            self._get_recent_context = get_recent_context
        if split_by_emotion:
            self._split_by_emotion = split_by_emotion
        if split_into_chunks:
            self._split_into_chunks = split_into_chunks
        if append_history:
            self._append_history = append_history
    
    def cancel(self):
        """取消追问"""
        self._cancelled = True
    
    def reset(self):
        """重置取消标志"""
        self._cancelled = False
    
    async def handle_follow_up(self, user_text: str, ai_response: str) -> None:
        """
        🔥 处理追问：并行判断 + 生成 + 追加到音频队列
        
        与音频播放并行执行，追问内容生成后直接追加到队列
        """
        try:
            from core.proactive_chat import get_proactive_chat_manager
            manager = get_proactive_chat_manager()
            
            if not manager.llm_client or manager.silent_mode:
                return
            
            # 🔥 获取完整对话上下文
            recent_context = "(暂无)"
            if self._get_recent_context:
                recent_context = self._get_recent_context()
            
            # 判断是否需要追问（调用后台小祥）
            from core.proactive_chat import SHOULD_FOLLOW_UP_PROMPT
            
            clean_response = re.sub(r'\[\w+\]', '', ai_response).strip()
            clean_response = re.sub(r'\[CALL:\w+.*?\]', '', clean_response).strip()
            
            prompt = SHOULD_FOLLOW_UP_PROMPT.format(
                recent_context=recent_context,
                user_text=user_text,
                ai_response=clean_response
            )
            
            response = ""
            async for chunk in manager.llm_client.chat_stream(
                [{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.7
            ):
                response += chunk
            
            response = response.strip().upper()
            
            if "[YES]" not in response:
                logger.debug("🤫 后台小祥判断：不需要追问")
                return
            
            
            logger.info("💬 后台小祥判断：需要追问！生成追问内容...")
            
            # 🔥 检查是否被打断
            if self._cancelled:
                logger.debug("🔇 追问生成已取消（被打断）")
                return
            
            # 🔥 等待主回复的音频播放完毕
            logger.debug("⏳ 等待主回复音频播放完毕...")
            while self.audio_queue.has_pending() or self.player.is_playing:
                if self._cancelled or self.audio_queue.is_interrupted:
                    logger.debug("🔇 追问等待期间被打断")
                    return
                await asyncio.sleep(0.1)
            
            # 🔥 主回复播放完毕后，开始延迟计时
            delay = random.randint(
                getattr(config, 'FOLLOW_UP_DELAY_MIN', 2),
                getattr(config, 'FOLLOW_UP_DELAY_MAX', 4)
            )
            logger.info(f"⏳ 追问延迟 {delay}s...（主回复已播放完毕）")
            await asyncio.sleep(delay)
            
            # 🔥 再次检查是否被打断
            if self._cancelled:
                logger.debug("🔇 追问已取消（延迟期间被打断）")
                return
            
            # 🔥 调用主程序小祥生成追问内容
            # 使用 FOLLOW_UP_SYSTEM_PROMPT 作为系统提示
            from core.proactive_chat import FOLLOW_UP_SYSTEM_PROMPT
            from llm.prompt_builder import get_prompt_builder
            
            builder = get_prompt_builder()
            
            # 构建消息：system prompt + 完整对话历史
            # 注意：这里使用主程序的 llm_client 和完整上下文
            messages = builder.build_messages(
                current_input=FOLLOW_UP_SYSTEM_PROMPT,  # 追问提示作为输入
                conversation_history=[]  # 不需要历史，因为 system prompt 已经包含
            )
            
            # 覆盖system message，加入追问提示
            messages[0]['content'] = f"""{messages[0]['content']}

{FOLLOW_UP_SYSTEM_PROMPT}

【参考信息】
最近对话：{recent_context}"""
            
            follow_up_response = ""
            async for chunk in self.llm_client.chat_stream(
                messages,
                max_tokens=100,  # 限制长度，追问应该简短
                temperature=0.8
            ):
                follow_up_response += chunk
            
            if not follow_up_response.strip():
                return
            
            # 🔥 检查是否被打断
            if self._cancelled:
                logger.debug("🔇 追问生成已取消（被打断）")
                return
            
            logger.info(f"🔄 [追问] AI: {follow_up_response}")
            
            # 🔥 处理响应：提取情绪、清理文本、提交TTS
            segments = []
            if self._split_by_emotion:
                segments = self._split_by_emotion(follow_up_response)
            if not segments:
                return
            
            # 提取第一个表情
            initial_emotion = segments[0][0]
            
            # 清理文本：移除所有表情标签和工具调用
            clean_text = re.sub(r'\[[a-zA-Z_]+\]', '', follow_up_response)
            from tools.executor import get_tool_executor
            executor = get_tool_executor()
            clean_text = executor.remove_tool_calls(clean_text)
            clean_text = clean_text.strip()
            
            if not clean_text:
                return
            
            # 整段提交（和response_handler一致）
            self.audio_queue.submit(clean_text, emotion=initial_emotion)
            logger.info(f"💾 追问TTS: 整段提交 ({len(clean_text)} 字)")
            
            # 追加到对话历史
            if self._append_history:
                from datetime import datetime
                timestamp = datetime.now().strftime("%H:%M:%S")
                self._append_history({
                    "role": "assistant",
                    "content": follow_up_response,
                    "timestamp": timestamp
                })
            
        except asyncio.CancelledError:
            logger.debug("🔇 追问任务被取消")
        except Exception as e:
            logger.error(f"追问处理失败: {e}")
            import traceback
            traceback.print_exc()
