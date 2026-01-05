# -*- coding: utf-8 -*-
"""
响应处理器

处理 LLM 响应、工具调用、TTS 输出等
使用组合模式，委托给各专用处理器
"""

import asyncio
import re
from typing import Optional, Callable, List
from loguru import logger

import config
from tools.executor import get_tool_executor, ToolExecutor

# 子模块
from .memory_injector import get_memory_injector
from .follow_up_handler import FollowUpHandler


class ResponseHandler:
    """
    响应处理器 - 核心对话处理类
    
    负责：
    - 处理用户输入（文本/音频）
    - 调用 LLM 生成响应
    - 处理工具调用
    - 管理 TTS 输出
    - 追问逻辑
    """
    
    def __init__(
        self,
        llm_client,
        audio_queue,
        player,
        state_machine,
        knowledge_monitor=None,
    ):
        self.llm_client = llm_client
        self.audio_queue = audio_queue
        self.player = player
        self.state_machine = state_machine
        self.knowledge_monitor = knowledge_monitor

        self.tool_executor: ToolExecutor = get_tool_executor()
        self.conversation_history: List[dict] = []
        self.current_emotion: Optional[str] = None
        self._last_retrieved_memories: List[dict] = []  # 🔥 保存检索到的记忆，传给后台小祥
        self._tool_results_this_turn: Dict[str, str] = {}  # 🔥 本轮工具调用结果，供后台小祥整理

        # 🔥 打断取消机制
        self._cancelled = False  # 取消标志
        self._current_request_id = 0  # 当前请求 ID，用于区分新旧请求

        # 回调
        self._on_expression_change: Optional[Callable[[str], None]] = None
        
        # 🔥 子模块
        self.memory_injector = get_memory_injector()
        # self.audio_manager 已移除，直接使用 self.audio_queue 和 self.player
        
        # 追问处理器（需要 TTS 引擎，延迟初始化）
        self.follow_up_handler: Optional[FollowUpHandler] = None
        self._init_follow_up_handler()
    
    def _init_follow_up_handler(self):
        """初始化追问处理器"""
        try:
            from tts.voxcpm_engine import get_voxcpm_engine
            tts_engine = get_voxcpm_engine()
            
            self.follow_up_handler = FollowUpHandler(
                llm_client=self.llm_client,
                audio_queue=self.audio_queue,
                player=self.player,
                tts_engine=tts_engine,
                config=config,
            )
            
            # 设置回调
            self.follow_up_handler.set_callbacks(
                get_recent_context=self.get_recent_context,
                split_by_emotion=self._split_by_emotion,
                split_into_chunks=self._split_into_chunks,
                append_history=lambda entry: self.conversation_history.append(entry),
            )
        except Exception as e:
            logger.debug(f"追问处理器初始化跳过: {e}")
            self.follow_up_handler = None
    
    # TTS 引擎属性（用于追问）
    @property
    def tts_engine(self):
        try:
            from tts.voxcpm_engine import get_voxcpm_engine
            return get_voxcpm_engine()
        except:
            return None
    
    def set_expression_callback(self, callback: Callable[[str], None]) -> None:
        """设置表情变化回调"""
        self._on_expression_change = callback
    
    def cancel(self) -> None:
        """取消当前响应处理（被打断时调用）"""
        self._cancelled = True
        if self.follow_up_handler:
            self.follow_up_handler.cancel()
        logger.info("🔇 响应处理被取消")
    
    def reset_cancellation(self) -> None:
        """重置取消标志（新请求开始时调用）"""
        self._cancelled = False
        self._current_request_id += 1
        if self.follow_up_handler:
            self.follow_up_handler.reset()
        logger.debug(f"🔄 请求 ID 更新: {self._current_request_id}")
    
    async def process_user_input(self, text: str, was_interrupted: bool = False) -> None:
        """
        处理用户输入
        
        Args:
            text: 用户说的话
            was_interrupted: 是否是打断场景
        """
        # 检查用户意图（静默模式相关）
        self._check_user_intent(text)
        
        # 🔥 如果是打断，注入打断提示
        if was_interrupted:
            text = f"[系统: 主人打断了你说话，并且说]\n{text}"
            logger.info("🔇 打断提示已注入")
        
        await self._process_llm_response(text)
        self.current_emotion = None
        
        # 🔥 检查是否被取消（打断）
        if self._cancelled:
            logger.debug("🔇 process_user_input: 处理已被取消，跳过 finish_speaking")
            return
        
        self.state_machine.finish_speaking()
    
    async def process_audio_input(self, audio_data, was_interrupted: bool = False) -> None:
        """
        处理音频输入 (Voice-to-LLM 模式)
        
        直接将音频发送给 LLM，跳过 STT
        
        Args:
            audio_data: numpy array 格式的音频数据
            was_interrupted: 是否是打断场景
        """
        import numpy as np
        
        # 将 numpy 音频转换为 WAV 字节
        audio_bytes = self._audio_to_wav_bytes(audio_data)
        
        logger.info(f"🎤 Voice-to-LLM: 发送 {len(audio_bytes)//1024}KB 音频")
        
        # 🔥 如果是打断，在提示中注入信息
        if was_interrupted:
            logger.info("🔇 打断场景：将注入打断提示")
        
        await self._process_llm_response_with_audio(audio_bytes, was_interrupted=was_interrupted)
        self.current_emotion = None
        
        # 🔥 检查是否被取消（打断）
        if self._cancelled:
            logger.debug("🔇 process_audio_input: 处理已被取消，跳过 finish_speaking")
            return
        
        self.state_machine.finish_speaking()
    
    def _audio_to_wav_bytes(self, audio_data) -> bytes:
        """将 numpy 音频数据转换为 WAV 字节"""
        import io
        import wave
        import numpy as np
        
        # 确保是 numpy array
        if not isinstance(audio_data, np.ndarray):
            audio_data = np.array(audio_data)
        
        # 转换为 16-bit PCM
        if audio_data.dtype == np.float32 or audio_data.dtype == np.float64:
            audio_data = (audio_data * 32767).astype(np.int16)
        elif audio_data.dtype != np.int16:
            audio_data = audio_data.astype(np.int16)
        
        # 写入 WAV
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(config.AUDIO_SAMPLE_RATE)
            wav_file.writeframes(audio_data.tobytes())
        
        return buffer.getvalue()
    
    async def _process_llm_response_with_audio(self, audio_bytes: bytes, was_interrupted: bool = False):
        """处理带音频的 LLM 响应 (Voice-to-LLM)"""
        from llm.prompt_builder import get_prompt_builder
        builder = get_prompt_builder()
        
        # 1. 获取 System Prompt (带缓存)
        system_prompt = builder.build_system_prompt()
        
        # 打断场景：注入打断提示到 system_prompt (临时修改)
        if was_interrupted:
            system_prompt += "\n\n[系统提示: 主人刚刚打断了你说话！可能有些生气或急事。请立即停止之前的话题，简短地回应主人的打断。]"
            logger.info("🔇 打断提示已注入到 system_prompt")
        
        # 2. 构建 User Prompt (文本部分)
        user_text_prompt = builder.build_user_prompt(
            current_input="(这是一条语音消息)",  # 占位符，实际内容在音频里
            conversation_history=self.conversation_history
        )
        
        # 🔍 Debug: 打印完整 Prompt (只在 debug 级别)
        logger.debug("="*30 + " Prompt Debug " + "="*30)
        logger.debug(f"【System Prompt】:\n{system_prompt}")
        if was_interrupted:
            logger.debug(f"...(包含打断提示)...")
        logger.debug(f"【User Prompt】:\n{user_text_prompt}")
        logger.debug("="*74)
        
        full_response = ""
        try:
            # Voice-to-LLM: 混合消息格式
            # 手动 Base64 编码音频（因为 chat_stream 不处理 bytes）
            import base64
            base64_audio = base64.b64encode(audio_bytes).decode("utf-8")
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": user_text_prompt},
                    {"type": "input_audio", "input_audio": {"data": base64_audio, "format": "wav"}}
                ]}
            ]
            
            # 使用通用的 chat_stream，因为它支持直接传递 messages 列表
            async for chunk in self.llm_client.chat_stream(messages):
                full_response += chunk
        except Exception as e:
            logger.error(f"Voice-to-LLM 失败: {e}")
            return
        
        if not full_response.strip():
            logger.warning("LLM 响应为空")
            return
        
        # 区分不同类型的回复
        if system_prompt and "主动发起聊天" in system_prompt:
            logger.info(f"💬 [主动聊天] AI: {full_response}")
        elif system_prompt and "追问/补充" in system_prompt:
            logger.info(f"🔄 [追问] AI: {full_response}")
        else:
            logger.info(f"🤖 AI: {full_response}")
        
        # 🔥 检测 [IGNORE] - 选择性响应
        if full_response.strip().startswith("[IGNORE]"):
            logger.info("🙈 AI 决定忽略此输入")
            return
        
        # 手动管理对话历史（为了能让后台转录任务引用 user_entry）
        from datetime import datetime
        timestamp_str = datetime.now().strftime("%H:%M:%S")
        
        user_entry = {
            "role": "user",
            "content": "(语音转录中...)",  # 初始占位符
            "timestamp": timestamp_str
        }
        
        assistant_entry = {
            "role": "assistant",
            "content": full_response,
            "timestamp": timestamp_str
        }
        
        self.conversation_history.append(user_entry)
        self.conversation_history.append(assistant_entry)
        
        # 🚀 启动后台转录任务 (委托给 '后台小祥' - ProactiveChatManager)
        # 注意：user_entry 是引用传递，后台任务会直接修改它的 content
        history_snapshot = list(self.conversation_history[:-2])
        
        from core.proactive_chat import get_proactive_chat_manager
        manager = get_proactive_chat_manager()
        asyncio.create_task(
            manager.transcribe_audio(audio_bytes, history_snapshot, user_entry)
        )

        # 检测工具调用
        tool_match = re.search(r'\[CALL:(\w+)(?::([^\]]*))?\]', full_response)
        if tool_match:
            await self._handle_tool_call("[语音输入]", full_response, loop_count=0, append_history=False)
        else:
            # 传递 append_history=False，因为我们已经手动添加了
            await self._speak_response(full_response, "[语音输入]", append_history=False)
    
    async def _process_llm_response(
        self,
        user_text: str,
        tool_result: str = None,
        tool_name: str = None,
        loop_count: int = 0
    ) -> None:
        """处理 LLM 响应 (支持多轮工具调用)"""

        # 构建消息
        if tool_result:
            messages = self._build_messages(user_text)
            tool_display_name = {
                "screenshot": "屏幕内容",
                "screenshot_describe": "屏幕描述",
                "knowledge": "记忆搜索",
                "web_search": "网络搜索"
            }.get(tool_name, "工具")
            
            # 🔥 检查是否是图片结果 (IMAGE_RESULT:格式:base64数据)
            if tool_result.startswith("IMAGE_RESULT:"):
                # 解析图片数据
                parts = tool_result.split(":", 2)
                if len(parts) == 3:
                    image_format = parts[1]  # jpeg or png
                    base64_data = parts[2]
                    
                    # 构建多模态消息，让 LLM 直接"看"图片
                    messages.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"[系统: 这是主人的屏幕截图]\n\n请仔细看这张图片，描述你看到了什么，然后用你的语气回答主人。"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/{image_format};base64,{base64_data}"
                                }
                            }
                        ]
                    })
                    logger.info(f"📸 发送图片给 LLM (格式: {image_format})")
                else:
                    # 格式错误，当作普通文本处理
                    messages.append({
                        "role": "user",
                        "content": f"[系统: {tool_display_name}结果]\n{tool_result}"
                    })
            else:
                # 普通文本工具结果
                messages.append({
                    "role": "user",
                    "content": f"[系统: {tool_display_name}结果]\n{tool_result}\n\n现在请基于这个结果，用你的语气自然地回答主人的问题。如果你需要更多信息，可以继续调用其他工具。记得保持角色性格，不要像客服或机器人。"
                })
        else:
            messages = self._build_messages(user_text)
        
        # 获取 LLM 响应（新架构：system prompt 已在 messages 中）
        full_response = ""
        print("🤖 AI: ", end="", flush=True)
        async for chunk in self.llm_client.chat_stream(messages):
            full_response += chunk
            print(chunk, end="", flush=True)
        print()
        
        # 检测 [IGNORE] - 选择性响应
        if full_response.strip().startswith("[IGNORE]"):
            logger.info("🙈 AI 决定忽略此输入")
            return
        
        # 检测工具调用
        # 确定用于下一轮/历史记录的文本
        # 如果是工具结果回合，历史记录应该显示工具结果（或其摘要），而不是重复原始用户输入
        history_text = user_text
        if tool_result:
            tool_display_name = {
                "screenshot": "屏幕截图",
                "screenshot_describe": "屏幕描述",
                "knowledge": "记忆搜索",
                "web_search": "网络搜索",
                "add_knowledge": "记忆添加",
                "move_self": "移动与控制"
            }.get(tool_name, tool_name)
            
            if tool_result.startswith("IMAGE_RESULT:"):
                history_text = f"[系统: {tool_display_name} (图片)]"
            else:
                # 截断过长的工具结果用于显示
                display_result = tool_result[:50] + "..." if len(tool_result) > 50 else tool_result
                history_text = f"[系统: {tool_display_name}结果] {display_result}"

        if self.tool_executor.has_tool_call(full_response):
            await self._handle_tool_call(history_text, full_response, loop_count)
        else:
            await self._speak_response(full_response, history_text)
    
    async def _handle_tool_call(self, user_text: str, response: str, loop_count: int = 0, append_history: bool = True) -> None:
        """处理工具调用 (委托给 ToolExecutor)"""
        
        MAX_TOOL_LOOPS = 5
        if loop_count >= MAX_TOOL_LOOPS:
            logger.warning(f"⚠️ 达到最大工具循环次数 ({MAX_TOOL_LOOPS})，强制结束")
            return
            
        tool_result, tool_name, after_text = await self.tool_executor.handle_tool_execution(
            response=response,
            user_text=user_text,
            conversation_history=self.conversation_history if append_history else [], # 如果不追加历史，传空列表或根据逻辑调整
            # Callbacks
            on_speak=lambda text, emotion: self.audio_queue.submit(text, emotion),
            on_play_audio=self._play_audio_queue,
            on_expression=self._set_expression,
            is_speaking_check=lambda: self.state_machine.is_speaking,
            start_speaking_call=self.state_machine.start_speaking,
            # Monitors
            knowledge_monitor=self.knowledge_monitor,
            memory_helper=self.memory_injector,  # Executor still expects 'memory_helper' arg, passing injector is compatible if interface matches? 
            # Wait, executor might rely on strict typing or specific methods? 
            # Executor uses: memory_helper.search_raw_memories
            # Injector now has this method. So it's fine.
            last_retrieved_memories=self._last_retrieved_memories
        )
        
        # 如果 append_history 为 False，我们需要自己管理历史? 
        # executor 内部会 append 到传入的 list。如果传入 self.conversation_history，它就会 append。
        # 如果 append_history=False，我们传一个临时 list 避免污染主历史? Or just let executor handle it?
        # 原逻辑：如果 append_history=True 才 append。
        # 所以上面 conversation_history 参数传递取决于 append_history。
        # 这里: conversation_history=self.conversation_history if append_history else [] 是不够的，
        # 因为 executor 内部是直接 append。如果传空 list，原来 append_history=True 的逻辑就没执行到 self.conversation_history。
        # 等等，executor.handle_tool_execution 只有在 append_history=True 时才应该 append 吗？
        # 是的。所以应该传：
        # conversation_history=self.conversation_history if append_history else [] 
        # 这样 executor 会 append 到这个 list (无论是真的还是假的)。如果是假的，就丢弃了。符合预期。

        if not tool_name:
            return
        
        # 🔥 收集工具结果（供后台小祥整理）
        if tool_result and not tool_result.startswith("IMAGE_RESULT:"):
            self._tool_results_this_turn[tool_name] = tool_result[:500]  # 限制长度

        # 🔥 处理工具调用后面的文本
        if after_text:
            clean_after = re.sub(r'\s+', '', after_text.strip())
            if clean_after:
                logger.info(f"📢 播放工具调用后的文本: {clean_after[:30]}...")
                after_segments = self._split_by_emotion(after_text)
                for emotion, text in after_segments:
                    if text:
                        self.audio_queue.submit(text, emotion)
                await self._play_audio_queue()

        await self._process_llm_response(user_text, tool_result, tool_name, loop_count + 1)
    
    def _check_user_intent(self, user_text: str) -> None:
        """检查用户意图（静默/唤醒模式）"""
        from core.proactive_chat import get_proactive_chat_manager
        manager = get_proactive_chat_manager()
        
        # 静默模式关键词
        silent_keywords = ["别吵", "安静", "闭嘴", "去忙", "不聊了", "先不聊"]
        if any(kw in user_text for kw in silent_keywords):
            manager.set_silent_mode(duration_minutes=60)
            return
        
        # 唤醒关键词
        wake_keywords = ["聊聊", "说话", "在吗", "出来", "忙完了"]
        if any(kw in user_text for kw in wake_keywords):
            manager.exit_silent_mode()
            return

    async def _speak_response(self, response: str, user_text: str, append_history: bool = True) -> None:
        """
        处理普通响应 - 支持动态表情和智能分段
        
        逻辑：
        1. 按表情标签将响应切分为多个片段 ([(emo1, text1), (emo2, text2)...])
        2. 对每个片段，如果有工具调用则移除
        3. 对每个文本片段，使用智能分段 (_split_into_chunks) 控制长度（避免长句TTS崩坏）
        4. 依次提交给音频队列，实现"读到哪里变什么表情"
        """
        
        # 1. 按表情标签切分
        segments = self._split_by_emotion(response)
        if not segments:
            logger.warning("响应为空或无法解析")
            return
        
        total_chunks = 0
        
        for emotion, text in segments:
            # 2. 清理工具调用 (EmotionParser 可能已经处理了一部分，这里确保干净)
            text = self.tool_executor.remove_tool_calls(text).strip()
            
            if not text:
                continue
                
            # 3. 智能分段 (控制单句长度，避免 VoxCPM 长句崩坏)
            # 使用之前实现的 _split_into_chunks (60字阈值 + 句子结束符切分)
            sub_chunks = self._split_into_chunks(text)
            
            # 4. 提交分段
            for chunk in sub_chunks:
                if chunk:
                    self.audio_queue.submit(chunk, emotion)
                    total_chunks += 1
        
        if total_chunks > 0:
            logger.info(f"💾 TTS: 共提交 {total_chunks} 个片段 (支持动态表情)")
        else:
            logger.warning("清理后无有效文本可读")
        
        
        # 记录对话历史（带时间戳）
        if append_history:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.conversation_history.append({
                "role": "user", 
                "content": user_text,
                "timestamp": timestamp
            })
            self.conversation_history.append({
                "role": "assistant", 
                "content": response,
                "timestamp": timestamp
            })

        if len(self.conversation_history) > 30:  # 触发摘要
            # 🔥 使用 ConversationSummarizer 摘要旧消息
            try:
                from core.conversation_summarizer import get_conversation_summarizer
                summarizer = get_conversation_summarizer(self.llm_client)
                if summarizer:
                    # 异步摘要并截断
                    asyncio.create_task(self._summarize_and_truncate())
                else:
                    # 没有摘要器时直接截断
                    self.conversation_history = self.conversation_history[-30:]
            except Exception as e:
                logger.debug(f"摘要器调用失败: {e}")
                self.conversation_history = self.conversation_history[-30:]

        # 🔥 检查是否被取消（打断）
        if self._cancelled:
            logger.debug("🔇 _speak_response: 处理已被取消，跳过后续执行")
            return
        
        if not self.state_machine.is_speaking:
            self.state_machine.start_speaking()
        
        # 🔥 并行处理：在播放音频的同时启动追问判断
        # 追问内容生成后会直接追加到音频队列
        follow_up_task = None
        clean_text = re.sub(r'\[\w+\]', '', response)
        clean_text = self.tool_executor.remove_tool_calls(clean_text)
        if "[IGNORE]" not in response:
            try:
                from core.proactive_chat import get_proactive_chat_manager
                manager = get_proactive_chat_manager()
                if manager.llm_client:
                    # 🔥 启动追问判断（并行），传入 response_handler 以便追加到队列
                    follow_up_task = asyncio.create_task(
                        self._handle_follow_up(user_text, clean_text)
                    )
            except Exception as e:
                logger.debug(f"Follow-up 分析跳过: {e}")
        
        # 播放音频队列
        await self._play_audio_queue()
        
        # 🔥 等待追问任务完成（如果有的话）
        if follow_up_task:
            try:
                await follow_up_task
            except asyncio.CancelledError:
                pass

        # 通知知识监控器（后台小祥）
        if self.knowledge_monitor:
            # 🔥 检索当前对话相关的原始记忆（包含 ID）
            # 🔥 检查 user_text 是否有效（不是占位符）
            if not self._last_retrieved_memories and user_text and user_text not in ["[语音输入]", ""]:
                self._last_retrieved_memories = self.memory_injector.search_raw_memories(user_text, n_results=5)
            
            asyncio.create_task(
                self.knowledge_monitor.analyze_conversation(
                    user_text, response, self._last_retrieved_memories
                )
            )
        
        # 🔥 后台整理工具调用结果（供下轮对话使用）
        if self._tool_results_this_turn:
            try:
                from core.context_manager import get_context_manager
                context_manager = get_context_manager(self.llm_client)
                
                # 构建对话摘要
                clean_response = re.sub(r'\[\w+\]', '', response).strip()
                conversation = f"主人: {user_text}\n小祥: {clean_response}"
                
                # 后台异步整理（不阻塞主流程）
                asyncio.create_task(
                    context_manager.prepare_context(conversation, self._tool_results_this_turn)
                )
                logger.debug(f"📋 启动工具结果整理 ({len(self._tool_results_this_turn)} 个结果)")
            except Exception as e:
                logger.debug(f"工具结果整理启动失败: {e}")
            finally:
                # 清空本轮结果
                self._tool_results_this_turn = {}
    
    async def _summarize_and_truncate(self):
        """摘要旧对话并截断历史"""
        try:
            from core.conversation_summarizer import get_conversation_summarizer
            summarizer = get_conversation_summarizer(self.llm_client)
            if summarizer:
                self.conversation_history = await summarizer.check_and_summarize(
                    self.conversation_history,
                    threshold=30,
                    keep_recent=10
                )
        except Exception as e:
            logger.error(f"对话摘要失败: {e}")
            # 失败时直接截断
            if len(self.conversation_history) > 30:
                self.conversation_history = self.conversation_history[-30:]
    
    def _split_by_emotion(self, text: str) -> list:
        """按情绪标签分段（委托给 EmotionParser）"""
        from core.emotion_parser import get_emotion_parser
        parser = get_emotion_parser(self.tool_executor)
        return parser.split_by_emotion(text)
    
    def _build_messages(self, user_text: str) -> List[dict]:
        """
        构建对话消息（新架构，参考 MaiBot）
        
        使用 PromptBuilder 构建：
        - System: 角色设定 + 记忆（带缓存，不每轮调用）
        - User: 简洁对话历史 + 当前输入
        """
        from llm.prompt_builder import get_prompt_builder
        
        builder = get_prompt_builder()
        
        # 使用新架构：只返回 system + user 两条消息
        # 记忆在 system prompt 中一次性注入，不每轮调用
        messages = builder.build_messages(
            current_input=user_text,
            conversation_history=self.conversation_history
        )
        
        # 🔍 Debug: 打印完整 Prompt (修改为 info 级别以便查看)
        logger.info("="*30 + " Prompt Debug " + "="*30)
        logger.info(f"【System Prompt】:\n{messages[0]['content']}")
        logger.info(f"【User Prompt】:\n{messages[1]['content']}")
        logger.info("="*74)
        
        return messages
    
    def _get_system_context(self) -> str:
        """获取系统上下文"""
        return self.memory_injector.get_system_context()
    
    def _get_recent_memories(self, n: int = 5) -> str:
        """获取最近记忆（自动注入到对话中）"""
        return self.memory_injector.get_recent_memories(n=n)
    
    def _get_important_memories(self) -> str:
        """获取核心层记忆（高重要性，始终注入）"""
        return self.memory_injector.get_important_memories()
    
    async def _handle_follow_up(self, user_text: str, ai_response: str) -> None:
        """🔥 处理追问：委托给 FollowUpHandler"""
        if self.follow_up_handler:
            self.follow_up_handler._cancelled = self._cancelled
            await self.follow_up_handler.handle_follow_up(user_text, ai_response)
    
    def _search_related_memories(self, query: str) -> str:
        """搜索相关记忆"""
        return self.memory_injector.search_related_memories(query)
    
    def _split_into_chunks(self, text: str) -> List[str]:
        """
        将文本分割为适合 TTS 的小段
        
        策略：
        1. 优先保持整段（连贯性最好）
        2. 如果超过 60 字，尝试在句子结束符（。.！？!?）处分割（避免长句导致的语速/音调问题）
        3. 如果必须分割，尽量保持语义完整
        """
        if not text:
            return []
            
        # 预处理：去除多余空白
        text = text.strip()
        length = len(text)
        
        # 1. 如果短于 60 字，直接整段返回
        if length <= 60:
            return [text]
            
        logger.info(f"文本较长 ({length} 字)，执行智能分段...")
        chunks = []
        current_chunk = ""
        
        # 使用正则表达式分割句子，保留分隔符
        # ([。.！？!?]+) 匹配一个或多个结束符
        import re
        parts = re.split(r'([。.！？!?]+)', text)
        
        # re.split 保留分隔符时，列表会是 [句1, 分隔符1, 句2, 分隔符2, ...]
        # 我们需要两两合并：句1+分隔符1
        sentences = []
        for i in range(0, len(parts) - 1, 2):
            sentences.append(parts[i] + parts[i+1])
        if len(parts) % 2 != 0 and parts[-1]: # 处理最后可能没有分隔符的部分
            sentences.append(parts[-1])
            
        for sentence in sentences:
            # 如果当前块加上新句子超过 60 字，且当前块不为空，则先提交当前块
            if len(current_chunk) + len(sentence) > 60 and current_chunk:
                chunks.append(current_chunk)
                current_chunk = sentence
            else:
                current_chunk += sentence
                
        if current_chunk:
            chunks.append(current_chunk)
            
        logger.info(f"分段结果: {len(chunks)} 段")
        return chunks
    
    async def _play_audio_queue(self) -> None:
        """播放 TTS 队列（支持打断）"""
        while self.audio_queue.has_pending():
            # 检查打断
            if self.audio_queue.is_interrupted or self._cancelled:
                logger.info("🔇 检测到打断，停止播放")
                return
            await asyncio.sleep(0.1)
            task = self.audio_queue.get_next_ready()
            if task and (task.audio_data or task.audio_path):
                source = task.audio_data if task.audio_data else task.audio_path
                self.player.add(task.id, source, task.text)
        
        # 等待播放完成
        while self.player.is_playing:
            if self.audio_queue.is_interrupted or self._cancelled:
                logger.info("🔇 检测到打断，停止播放")
                self.player.clear()
                return
            await asyncio.sleep(0.1)
    
    def _set_expression(self, emotion: str) -> None:
        """设置表情"""
        if self._on_expression_change:
            self._on_expression_change(emotion)
        logger.info(f"🎭 表情: {emotion}")
    
    def get_recent_context(self) -> str:
        """获取完整对话历史（用于后台小祥判断）"""
        if not self.conversation_history:
            return "（还没有对话）"
        
        # 🔥 直接返回完整对话历史，不做截取
        lines = []
        for msg in self.conversation_history:
            role = "主人" if msg["role"] == "user" else "你"
            lines.append(f"{role}: {msg['content']}")
        
        return "\n".join(lines)
