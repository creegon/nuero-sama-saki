# -*- coding: utf-8 -*-
"""
NeuroPet - AI 桌宠主类
"""

import asyncio
import time
from typing import Optional, List
from loguru import logger

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config



from .response_handler import ResponseHandler
from .proactive_chat import ProactiveChatManager
from .state_machine import State, StateMachine



class NeuroPet:
    """Neuro-like AI 桌宠主类"""
    
    def __init__(self, debug: bool = False):
        self.log = logger.bind(module="NeuroPet")
        self.debug = debug
        
        # 组件
        self.audio_capture: Optional[AudioCapture] = None
        self.vad: Optional[SileroVAD] = None
        self.transcriber = None
        self.llm_client: Optional[LLMClient] = None
        self.audio_queue: Optional[AudioQueue] = None
        self.player: Optional[SequentialPlayer] = None
        self.state_machine: Optional[StateMachine] = None
        
        # 响应处理器
        self.response_handler: Optional[ResponseHandler] = None

        # 知识监控器
        self.knowledge_monitor = None

        # 健康监控器
        self.health_monitor = None

        # 主动聊天
        self.proactive_chat: Optional[ProactiveChatManager] = None
        
        # Live2D
        self._live2d_controller = None
        self._live2d_thread = None
        self._qt_app = None
        
        self._is_running = False
        self._was_interrupted = False  # 🔥 打断标志
        self._append_mode = False      # 🔥 追加模式 (在 PROCESSING 阶段打断时启用)
        self._pending_audio = None     # 🔥 待追加的音频 (上一次说话的内容)
        self._llm_lock = None          # 🔥 LLM 并发锁（在异步上下文中初始化）
        self.services = None
        self.greeter = None
    
    def initialize(self) -> bool:
        """初始化所有组件"""
        self.log.info("=" * 50)
        self.log.info("🚀 正在启动 Neuro-like AI 桌宠")
        self.log.info("=" * 50)
        
        try:
            # 初始化服务管理器
            from core.services.background import BackgroundServices
            self.services = BackgroundServices(self)

            # 🔥 首先启动知识库服务 (异步后台线程)
            # 这样可以与 STT/TTS 加载并行，节省启动时间
            self.services.start_knowledge_service()
            
            # STT 组件
            self.log.info("📢 加载语音活动检测 (Silero VAD)...")
            from stt.vad import SileroVAD
            self.vad = SileroVAD()
            
            # Voice-to-LLM 模式下跳过 STT 加载
            if config.VOICE_TO_LLM_ENABLED:
                self.log.info("🎤 Voice-to-LLM 模式启用 - 跳过 STT 加载")
                self.transcriber = None
            else:
                self.log.info(f"🎤 加载语音识别 ({config.STT_ENGINE})...")
                
                # 根据配置选择 STT 引擎
                # STT Factory Loading
                from stt import get_transcriber
                self.transcriber = get_transcriber()
                self.transcriber.load_model()
            
            from stt.audio_capture import AudioCapture
            self.audio_capture = AudioCapture()
            
            # LLM 组件
            self.log.info("🧠 初始化 LLM 客户端...")
            from llm.client import LLMClient
            self.llm_client = LLMClient()
            
            # 健康监控器（先初始化，后面TTS引擎会用到）
            self.log.info("🏥 初始化健康监控器...")
            from .health_monitor import HealthMonitor
            self.health_monitor = HealthMonitor()

            # TTS 组件
            self.log.info("🔊 预加载 VoxCPM TTS 引擎...")
            from tts.voxcpm_engine import get_voxcpm_engine
            tts_engine = get_voxcpm_engine()
            tts_engine.initialize()

            # 设置健康监控回调
            tts_engine.set_health_monitor(self.health_monitor)
            self.health_monitor.set_cleanup_callback(self._on_cleanup_needed)
            self.health_monitor.set_critical_callback(self._on_critical_degradation)

            self.log.info(f"   VoxCPM 加载完成，采样率: {tts_engine.sample_rate}Hz")
            
            from tts.audio_queue import AudioQueue
            from tts.player import SequentialPlayer
            self.audio_queue = AudioQueue()
            self.player = SequentialPlayer()
            
            self.player.on_sentence_start = self._on_sentence_start
            self.player.on_sentence_end = self._on_sentence_end
            
            # 状态机
            # from core.state_machine import StateMachine (already imported)
            self.state_machine = StateMachine()
            self.state_machine.on_state_change = self._on_state_change

            # 响应处理器
            self.log.info("🔧 初始化响应处理器...")
            self.response_handler = ResponseHandler(
                llm_client=self.llm_client,
                audio_queue=self.audio_queue,
                player=self.player,
                state_machine=self.state_machine,
                knowledge_monitor=self.knowledge_monitor,
            )
            self.response_handler.set_expression_callback(self._set_expression)
            
            # 主动聊天
            from core.proactive_chat import get_proactive_chat_manager
            self.proactive_chat = get_proactive_chat_manager(llm_client=self.llm_client)
            self.proactive_chat.set_callbacks(
                on_proactive_request=self._on_proactive_chat,
                get_recent_context=lambda: self.response_handler.get_recent_context() if self.response_handler else "(暂无)"
            )
            
            # 🔥 静默屏幕观察器 (后台小祥默默观察主人)
            from core.screen_observer import get_screen_observer
            try:
                from knowledge import get_knowledge_base
                kb = get_knowledge_base()
                self.screen_observer = get_screen_observer(
                    llm_client=self.llm_client,
                    knowledge_base=kb
                )
            except Exception as e:
                self.log.warning(f"⚠️ 屏幕观察器初始化跳过 (知识库未就绪): {e}")
                self.screen_observer = None
            
            # 初始化行为
            from core.behaviors.greeting import AutoGreeter
            self.greeter = AutoGreeter(
                self.llm_client,
                self.audio_queue,
                self.player,
                self.state_machine,
                self._set_expression
            )

            # Live2D (由 BackgroundServices 管理)
            try:
                self.services.start_live2d()
            except Exception as e:
                self.log.warning(f"⚠️ Live2D 加载失败 (可选功能): {e}")
            
            # 内存清理
            try:
                from scripts.cleanup_memory import start_periodic_cleanup
                start_periodic_cleanup(interval_seconds=300)
            except Exception as e:
                self.log.debug(f"定期清理未启用: {e}")
            
            self.log.info("=" * 50)
            self.log.info("✅ 所有组件初始化完成!")
            self.log.info("=" * 50)
            return True
            
        except Exception as e:
            self.log.error(f"❌ 初始化失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _on_proactive_chat(self, system_prompt: str) -> None:
        """主动聊天回调 - 接收来自 proactive_chat 的系统提示词"""
        # 🔥 确保锁已初始化
        if self._llm_lock is None:
            self._llm_lock = asyncio.Lock()
        
        # 🔥 检查是否正在处理其他请求
        if self._llm_lock.locked():
            self.log.info("⏳ 主动聊天被跳过：正在处理其他请求")
            return
        
        async with self._llm_lock:
            try:
                # 获取上下文
                recent_context = self.response_handler.get_recent_context()
                
                # 尝试获取屏幕内容
                screen_context = ""
                try:
                    from vision import get_vision_analyzer
                    analyzer = get_vision_analyzer()
                    screen_context = await analyzer.describe_for_chat("")
                except:
                    screen_context = "(无法获取屏幕)"
                
                # 构建完整 prompt
                full_prompt = f"""{system_prompt}

【参考信息】
屏幕内容：{screen_context[:200]}
最近对话：{recent_context}"""
                
                messages = [{"role": "user", "content": full_prompt}]
                
                full_response = ""
                print("🤖 [主动] AI: ", end="", flush=True)
                async for chunk in self.llm_client.chat_stream(
                    messages, system_prompt=config.SYSTEM_PROMPT
                ):
                    full_response += chunk
                    print(chunk, end="", flush=True)
                print()
                
                # 处理响应
                if self.response_handler.tool_executor.has_tool_call(full_response):
                    await self.response_handler._handle_tool_call("[主动聊天]", full_response)
                else:
                    await self.response_handler._speak_response(full_response, "[主动聊天]")
                
                self.response_handler.conversation_history.append({
                    "role": "assistant",
                    "content": f"[主动发起] {full_response}"
                })
                
            except Exception as e:
                self.log.error(f"主动聊天处理失败: {e}")
            
    def _set_expression(self, emotion: str) -> None:
        """设置 Live2D 表情"""
        try:
            from live2d_local import get_live2d_controller
            controller = get_live2d_controller()
            if controller:
                controller.set_expression(emotion)
        except:
            pass
    
    def _on_state_change(self, old_state: State, new_state: State):
        self.log.debug(f"状态: {old_state.name} -> {new_state.name}")
    
    def _on_sentence_start(self, task_id: int, text: str):
        self.log.info(f"🗣 说: {text}")
    
    def _on_sentence_end(self, task_id: int, text: str):
        pass

    def _on_cleanup_needed(self):
        """健康监控回调：需要清理"""
        self.log.info("🧹 健康监控触发清理")
        from scripts.cleanup_memory import cleanup_all
        cleanup_all(aggressive=False)

    def _on_critical_degradation(self):
        """健康监控回调：严重性能退化"""
        self.log.warning("🚨 健康监控检测到严重性能退化")

        # 激进清理
        from scripts.cleanup_memory import cleanup_all
        cleanup_all(aggressive=True)

        # 重载TTS模型
        from tts.voxcpm_engine import get_voxcpm_engine
        tts_engine = get_voxcpm_engine()
        tts_engine.reload_model()

    async def process_user_speech(self, audio):
        """处理用户语音（支持打断检测）
        
        Voice-to-LLM 模式：直接发送音频给 LLM
        传统模式：先 STT 转文字再发送
        
        在处理期间，后台持续监听用户的打断
        
        🔥 追加模式：如果在 PROCESSING 阶段被打断，会把之前说的和新说的拼接
        """
        import numpy as np
        
        # 🔥 确保锁已初始化
        if self._llm_lock is None:
            self._llm_lock = asyncio.Lock()
        
        # 🔥 追加模式检测
        if self._append_mode and self._pending_audio is not None:
            # 拼接之前的音频和新的音频
            self.log.debug(f"📎 追加模式：拼接音频 (之前 {len(self._pending_audio)/16000:.2f}s + 新 {len(audio)/16000:.2f}s)")
            audio = np.concatenate([self._pending_audio, audio])
            self._append_mode = False
            self._pending_audio = None
        
        # 🔥 保存当前音频用于可能的追加
        self._pending_audio = audio
        
        # 🔥 重置取消标志，确保新请求不受上一个被打断的请求影响
        if self.response_handler:
            self.response_handler.reset_cancellation()
        
        # 更新交互时间
        if self.proactive_chat:
            self.proactive_chat.update_interaction_time()
        
        # 启动后台打断检测任务
        interrupt_task = asyncio.create_task(self._background_interrupt_detection())
        
        # 🔥 使用锁保护 LLM 请求，确保不与主动聊天并发
        async with self._llm_lock:
            try:
                if config.VOICE_TO_LLM_ENABLED:
                    # Voice-to-LLM 模式：直接发送音频给 LLM
                    self.log.info("🎤 Voice-to-LLM: 发送语音到 LLM...")
                    self.state_machine.start_processing()
                    await self.response_handler.process_audio_input(audio, was_interrupted=self._was_interrupted)
                else:
                    # 传统模式：先转录
                    text, stats = self.transcriber.transcribe(audio)
                    
                    if not text.strip():
                        self.log.warning("识别结果为空，忽略")
                        self.state_machine.reset()
                        return
                    
                    self.log.info(f"👤 用户: {text}")
                    self.state_machine.start_processing()
                    await self.response_handler.process_user_input(text, was_interrupted=self._was_interrupted)
            finally:
                # 停止后台打断检测
                interrupt_task.cancel()
                try:
                    await interrupt_task
                except asyncio.CancelledError:
                    pass
                
                # 🔥 如果没有被打断，清除待追加的音频
                if not self._append_mode:
                    self._pending_audio = None
    
    async def _background_interrupt_detection(self):
        """🔇 后台打断检测任务
        
        在 AI 说话时持续监听麦克风，一旦检测到用户开始说话就立即打断
        
        🔥 打断模式：
        - SPEAKING 阶段打断：正常替换，用户新说的内容作为新输入
        - PROCESSING 阶段打断：追加模式，把之前说的和新说的拼接起来
        """
        # 等待 AI 开始说话
        await asyncio.sleep(0.3)  # 给 TTS 一点启动时间
        
        # 启动音频采集
        if not self.audio_capture.start():
            return
        
        # 用于检测语音开始的简单阈值计数
        speech_frames = 0
        # 🔥 提高阈值，降低敏感度
        SPEECH_THRESHOLD = 0.5   # 语音概率阈值 (原 0.35)
        MIN_SPEECH_FRAMES = 5    # 连续几帧超过阈值才认为开始说话 (原 3，约 160ms)
        
        # 收集打断时的音频
        interrupt_buffer = []
        
        try:
            while self.state_machine.is_speaking or self.state_machine.is_processing:
                chunk = self.audio_capture.read_chunk()
                if chunk is None:
                    await asyncio.sleep(0.01)
                    continue
                
                # 保存音频到缓冲区
                interrupt_buffer.append(chunk)
                # 只保留最近 2 秒的音频（避免内存无限增长）
                max_chunks = int(2.0 * 16000 / 512)  # 约 62 个 chunk
                if len(interrupt_buffer) > max_chunks:
                    interrupt_buffer.pop(0)
                
                # 使用主 VAD 检测语音概率
                speech_prob = self.vad.get_speech_probability(chunk)
                
                if speech_prob >= SPEECH_THRESHOLD:
                    speech_frames += 1
                    
                    # 🔥 连续检测到语音 → 立即打断！
                    if speech_frames >= MIN_SPEECH_FRAMES:
                        # 🔥 判断是否在 PROCESSING 阶段（追加模式）
                        is_processing_interrupt = self.state_machine.is_processing and not self.state_machine.is_speaking
                        
                        if is_processing_interrupt:
                            self.log.info(f"🔇 PROCESSING 阶段检测到用户继续说话 (概率: {speech_prob:.2f})，启用追加模式")
                        else:
                            self.log.info(f"🔇 检测到用户开始说话 (概率: {speech_prob:.2f})，立即打断 AI")
                        
                        self.interrupt()
                        
                        # 🔥 如果是 PROCESSING 阶段打断，设置追加标志
                        if is_processing_interrupt:
                            self._append_mode = True  # 追加模式
                        
                        # 不停止音频采集！让用户继续说
                        # 使用主 VAD 继续收集完整语音
                        self.vad.reset()
                        
                        # 把已收集的音频喂给 VAD
                        for buffered_chunk in interrupt_buffer:
                            self.vad.process_chunk(buffered_chunk)
                        
                        # 继续收集直到用户说完
                        while True:
                            chunk = self.audio_capture.read_chunk()
                            if chunk is None:
                                await asyncio.sleep(0.01)
                                continue
                            
                            is_end, interrupt_audio = self.vad.process_chunk(chunk)
                            
                            if is_end and interrupt_audio is not None and len(interrupt_audio) > 0:
                                self.audio_capture.stop()
                                self.log.info("🎤 处理打断后的用户输入...")
                                await self.process_user_speech(interrupt_audio)
                                return
                            
                            await asyncio.sleep(0.01)
                else:
                    speech_frames = 0  # 重置计数
                
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            pass
        finally:
            if self.audio_capture.is_running:
                self.audio_capture.stop()
    
    async def listen_and_respond(self):
        """监听一次并响应（支持打断）"""
        self.state_machine.start_listening()
        self.vad.reset()
        
        # 重置打断标志（但不重置追加模式相关状态，因为可能还需要追加）
        self._was_interrupted = False
        self.audio_queue.reset_interrupt()
        
        if not self.audio_capture.start():
            self.log.error("音频采集启动失败")
            return
        
        try:
            while self.state_machine.is_listening:
                chunk = self.audio_capture.read_chunk()
                if chunk is None:
                    continue
                
                is_end, audio = self.vad.process_chunk(chunk)
                
                if is_end:
                    self.audio_capture.stop()
                    await self.process_user_speech(audio)
                    break
                    
        except Exception as e:
            self.log.error(f"处理出错: {e}")
        finally:
            if self.audio_capture.is_running:
                self.audio_capture.stop()
    
    def interrupt(self):
        """
        🔇 打断当前说话
        
        立即停止 TTS 播放和生成，准备处理用户新输入
        """
        self.log.info("🔇 用户打断了 AI")
        
        # 清空音频队列（会停止播放）
        self.audio_queue.clear()
        
        # 清空播放器队列
        self.player.clear()
        
        # 🔥 通知 ResponseHandler 取消当前处理
        if self.response_handler:
            self.response_handler.cancel()
        
        # 设置打断标志
        self._was_interrupted = True
        
        # 转换状态
        self.state_machine.transition_to(State.LISTENING, force=True)
    
    async def run(self):
        """主运行循环"""
        self._is_running = True
        self.audio_queue.start()
        self.player.start()
        
        # 🌅 启动打招呼
        if self.greeter:
            await self.greeter.run()
        
        self.log.info("")
        self.log.info("🎤 开始监听... 对着麦克风说话吧!")
        self.log.info("   按 Ctrl+C 退出")
        self.log.info("")
        
        try:
            # 启动健康监控
            if self.health_monitor:
                self.health_monitor.start()

            # 启动知识监控器（在事件循环中真正启动）
            if self.knowledge_monitor and self.knowledge_monitor._monitor_task == "pending":
                self.knowledge_monitor._monitor_task = None
                self.knowledge_monitor.start()

            # 启动主动聊天
            if self.proactive_chat:
                self.proactive_chat.start(self.state_machine)

            # 🔥 启动静默屏幕观察器
            if self.screen_observer:
                self.screen_observer.start()

            while self._is_running:
                await self.listen_and_respond()
                await asyncio.sleep(0.3)
                
        except KeyboardInterrupt:
            self.log.info("\n👋 再见!")
        finally:
            self._is_running = False
            self.log.info("🛑 正在关闭...")
            
            # 🔥 保存对话摘要（用于下次启动时的记忆连续性）
            await self._save_chat_summary()

            if self.health_monitor:
                self.health_monitor.stop()
            if self.proactive_chat:
                await self.proactive_chat.stop()
            if self.knowledge_monitor:
                self.knowledge_monitor.stop()
            
            if self.services:
                self.services.stop_live2d()
            
            self.audio_queue.stop()
            self.player.stop()

            # 退出时强制清理，避免显存泄漏
            self.log.info("🧹 退出清理中...")
            from scripts.cleanup_memory import cleanup_all
            cleanup_all(aggressive=True)

            self.log.info("✅ 退出完成")
    
    async def _save_chat_summary(self):
        """保存本次对话摘要"""
        try:
            if not self.response_handler or not self.response_handler.conversation_history:
                return
            
            history = self.response_handler.conversation_history
            if len(history) < 2:
                return  # 对话太短，不保存
            
            # 提取最近的几轮对话
            recent = history[-6:]  # 最近 3 轮
            chat_text = []
            for msg in recent:
                role = "主人" if msg.get("role") == "user" else "你"
                content = msg.get("content", "")
                if content and content != "[语音输入]":
                    chat_text.append(f"{role}: {content[:50]}")
            
            if not chat_text:
                return
            
            # 生成简短摘要（直接用规则，不调用 LLM 避免延迟）
            # 找到最后一个有意义的用户消息
            summary = None
            for msg in reversed(history):
                if msg.get("role") == "user" and msg.get("content") not in ["[语音输入]", ""]:
                    content = msg.get("content", "")[:100]
                    summary = content
                    break
            
            if not summary:
                # 找最后一个 AI 回复
                for msg in reversed(history):
                    if msg.get("role") == "assistant":
                        content = msg.get("content", "")[:100]
                        # 清理情感标签
                        import re
                        content = re.sub(r'\[\w+\]\s*', '', content)
                        summary = content
                        break
            
            if summary:
                from core.memory_injector import get_memory_injector
                injector = get_memory_injector()
                injector.save_chat_summary(summary)
                self.log.info(f"📝 对话摘要已保存: {summary[:30]}...")
                
        except Exception as e:
            self.log.debug(f"保存对话摘要失败: {e}")
    
    def start(self):
        """启动"""
        if not self.initialize():
            return
        asyncio.run(self.run())

