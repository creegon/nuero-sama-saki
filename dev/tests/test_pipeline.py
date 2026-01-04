# -*- coding: utf-8 -*-
"""
Pipeline Integration Test
完整 STT -> LLM -> TTS Pipeline 测试
实时指标统计
"""

import sys
import os
import asyncio
import time
from dataclasses import dataclass, field
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

# 模块导入
from stt.audio_capture import AudioCapture
from stt.vad import SileroVAD
from stt.transcriber import Transcriber
from llm.client import LLMClient
from llm.prompts import get_system_prompt, build_conversation_messages
from llm.stream_parser import StreamParser
from tts.synthesizer import TTSSynthesizer
from tts.audio_queue import AudioQueue
from tts.player import SequentialPlayer
from state_machine.states import State
from state_machine.transitions import StateMachine
import config

# 配置 loguru
logger.remove()
logger.add(
    sys.stderr, 
    level="INFO", 
    format="<green>{time:HH:mm:ss.SSS}</green> | <cyan>{name:>12}</cyan> | <level>{message}</level>"
)


@dataclass
class PipelineMetrics:
    """Pipeline 性能指标"""
    # 时间点
    speech_end_time: float = 0
    stt_start_time: float = 0
    stt_end_time: float = 0
    llm_start_time: float = 0
    llm_first_token_time: float = 0
    llm_end_time: float = 0
    tts_first_submit_time: float = 0
    tts_first_ready_time: float = 0
    first_audio_play_time: float = 0
    all_audio_done_time: float = 0
    
    # 句子级统计
    sentence_count: int = 0
    sentence_times: List[float] = field(default_factory=list)
    
    def calculate(self) -> dict:
        """计算各项指标"""
        return {
            "vad_to_stt": self.stt_start_time - self.speech_end_time,
            "stt_latency": self.stt_end_time - self.stt_start_time,
            "llm_ttft": self.llm_first_token_time - self.llm_start_time,
            "llm_total": self.llm_end_time - self.llm_start_time,
            "tts_first_latency": self.tts_first_ready_time - self.tts_first_submit_time,
            "speech_to_first_audio": self.first_audio_play_time - self.speech_end_time,
            "total_e2e": self.all_audio_done_time - self.speech_end_time,
            "sentence_count": self.sentence_count
        }
    
    def print_report(self):
        """打印性能报告"""
        metrics = self.calculate()
        
        print("\n" + "="*60)
        print("📊 性能指标报告")
        print("="*60)
        print(f"  VAD → STT 启动:      {metrics['vad_to_stt']*1000:>8.1f} ms")
        print(f"  STT 识别耗时:        {metrics['stt_latency']*1000:>8.1f} ms")
        print(f"  LLM 首 Token (TTFT): {metrics['llm_ttft']*1000:>8.1f} ms")
        print(f"  LLM 完整响应:        {metrics['llm_total']*1000:>8.1f} ms")
        print(f"  TTS 首句就绪:        {metrics['tts_first_latency']*1000:>8.1f} ms")
        print("-"*60)
        print(f"  🎯 说完 → 首次播放:   {metrics['speech_to_first_audio']*1000:>8.1f} ms")
        print(f"  📦 端到端总延迟:      {metrics['total_e2e']*1000:>8.1f} ms")
        print(f"  📝 句子数量:          {metrics['sentence_count']:>8}")
        print("="*60)


class PipelineTest:
    """完整 Pipeline 测试"""
    
    def __init__(self):
        self.log = logger.bind(module="Pipeline")
        
        # 组件
        self.audio_capture: Optional[AudioCapture] = None
        self.vad: Optional[SileroVAD] = None
        self.transcriber: Optional[Transcriber] = None
        self.llm_client: Optional[LLMClient] = None
        self.stream_parser: Optional[StreamParser] = None
        self.synthesizer: Optional[TTSSynthesizer] = None
        self.audio_queue: Optional[AudioQueue] = None
        self.player: Optional[SequentialPlayer] = None
        self.state_machine: Optional[StateMachine] = None
        
        # 状态
        self.conversation_history: List[dict] = []
        self.current_metrics: Optional[PipelineMetrics] = None
        self._is_running = False
    
    def initialize(self) -> bool:
        """初始化所有组件"""
        self.log.info("初始化组件...")
        
        try:
            # STT
            self.log.info("加载 VAD...")
            self.vad = SileroVAD()
            
            self.log.info("加载 Whisper...")
            self.transcriber = Transcriber()
            self.transcriber.load_model()
            
            self.audio_capture = AudioCapture()
            
            # LLM
            self.log.info("初始化 LLM 客户端...")
            self.llm_client = LLMClient()
            self.stream_parser = StreamParser()
            
            # TTS
            self.log.info("连接 TTS 服务...")
            self.synthesizer = TTSSynthesizer()
            if not self.synthesizer.connect():
                self.log.error("无法连接到 IndexTTS2 服务")
                return False
            
            self.audio_queue = AudioQueue()
            self.player = SequentialPlayer()
            
            # 状态机
            self.state_machine = StateMachine()
            
            self.log.info("所有组件初始化完成 ✓")
            return True
            
        except Exception as e:
            self.log.error(f"初始化失败: {e}")
            return False
    
    async def process_speech(self, audio: bytes) -> Optional[str]:
        """处理一次语音输入"""
        metrics = PipelineMetrics()
        metrics.speech_end_time = time.time()
        self.current_metrics = metrics
        
        # === STT ===
        self.state_machine.start_processing()
        metrics.stt_start_time = time.time()
        
        text, stats = self.transcriber.transcribe(audio)
        metrics.stt_end_time = time.time()
        
        if not text.strip():
            self.log.warning("识别结果为空")
            self.state_machine.reset()
            return None
        
        self.log.info(f"识别结果: {text}")
        
        # === LLM ===
        messages = build_conversation_messages(text, self.conversation_history)
        
        metrics.llm_start_time = time.time()
        first_token = True
        full_response = ""
        
        self.log.info("LLM 生成回复...")
        
        # 先收集完整 LLM 响应
        async for chunk in self.llm_client.chat_stream(messages, system_prompt=get_system_prompt()):
            if first_token:
                metrics.llm_first_token_time = time.time()
                first_token = False
            full_response += chunk
        
        metrics.llm_end_time = time.time()
        
        # 使用智能分割（收集完后再分割，支持合并短句和颜文字保护）
        from llm.stream_parser import split_text_to_sentences
        sentences = split_text_to_sentences(full_response)
        
        metrics.tts_first_submit_time = time.time()
        
        for sentence, emotion in sentences:
            metrics.sentence_count += 1
            self.log.info(f"句子 #{metrics.sentence_count}: [{emotion}] {sentence} ({len(sentence)}字)")
            self.audio_queue.submit(sentence, emotion)
        
        # 更新对话历史
        self.conversation_history.append({"role": "user", "content": text})
        self.conversation_history.append({"role": "assistant", "content": full_response})
        
        # 保持历史长度
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
        
        return full_response
    
    async def run_single_turn(self):
        """运行单轮对话"""
        self.log.info("请说话...")
        self.state_machine.start_listening()
        
        if not self.audio_capture.start():
            self.log.error("音频采集启动失败")
            return
        
        self.vad.reset()
        
        # 监听语音
        while True:
            chunk = self.audio_capture.read_chunk()
            if chunk is None:
                continue
            
            is_end, audio = self.vad.process_chunk(chunk)
            
            if is_end:
                self.audio_capture.stop()
                
                # 处理语音
                await self.process_speech(audio)
                
                # 等待 TTS 完成
                self.log.info("等待 TTS 生成...")
                first_ready = True
                
                while self.audio_queue.has_pending():
                    await asyncio.sleep(0.1)
                    
                    # 检查可播放的音频
                    task = self.audio_queue.get_next_ready()
                    if task:
                        if first_ready:
                            self.current_metrics.tts_first_ready_time = time.time()
                            first_ready = False
                        
                        if task.audio_path:
                            self.player.add(task.id, task.audio_path, task.text)
                
                # 开始播放
                self.state_machine.start_speaking()
                self.current_metrics.first_audio_play_time = time.time()
                
                # 等待播放完成
                while self.player.is_playing:
                    await asyncio.sleep(0.1)
                
                self.current_metrics.all_audio_done_time = time.time()
                self.state_machine.finish_speaking()
                
                # 打印性能报告
                self.current_metrics.print_report()
                
                break
    
    async def run_loop(self):
        """运行主循环"""
        self._is_running = True
        self.audio_queue.start()
        self.player.start()
        
        print("\n" + "="*60)
        print("🎤 Pipeline 测试已启动")
        print("   对着麦克风说话，按 Ctrl+C 退出")
        print("="*60)
        
        try:
            while self._is_running:
                await self.run_single_turn()
                print("\n" + "-"*60)
                await asyncio.sleep(0.5)
                
        except KeyboardInterrupt:
            print("\n\n正在退出...")
        finally:
            self._is_running = False
            self.audio_queue.stop()
            self.player.stop()
    
    def run(self):
        """启动测试"""
        if not self.initialize():
            print("初始化失败，请检查错误信息")
            return
        
        asyncio.run(self.run_loop())


def main():
    print("="*60)
    print("🚀 Neuro-like AI 桌宠 - Pipeline 集成测试")
    print("="*60)
    
    print("\n前置条件检查:")
    print(f"  ✓ LLM API: {config.LLM_API_BASE}")
    print(f"  ✓ TTS API: {config.TTS_GRADIO_URL}")
    print(f"  ✓ Whisper: {config.WHISPER_MODEL} ({config.WHISPER_DEVICE})")
    
    input("\n按 Enter 开始测试...")
    
    test = PipelineTest()
    test.run()


if __name__ == "__main__":
    main()
