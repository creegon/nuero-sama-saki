# -*- coding: utf-8 -*-
"""
Voice Activity Detection Module
使用 Silero VAD 进行实时语音检测
"""

import torch
import numpy as np
from typing import Optional, List, Tuple
from collections import deque
from loguru import logger
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class SileroVAD:
    """Silero VAD 语音活动检测器"""
    
    def __init__(
        self,
        threshold: float = config.VAD_THRESHOLD,
        min_speech_ms: int = config.VAD_MIN_SPEECH_MS,
        min_silence_ms: int = config.VAD_MIN_SILENCE_MS,
        speech_pad_ms: int = config.VAD_SPEECH_PAD_MS,
        sample_rate: int = config.AUDIO_SAMPLE_RATE
    ):
        self.threshold = threshold
        self.min_speech_ms = min_speech_ms
        self.min_silence_ms = min_silence_ms
        self.speech_pad_ms = speech_pad_ms
        self.sample_rate = sample_rate
        
        # 状态
        self._is_speaking = False
        self._speech_start_time: Optional[float] = None
        self._silence_start_time: Optional[float] = None
        self._speech_buffer: List[np.ndarray] = []
        self._padding_buffer: deque = deque(maxlen=int(speech_pad_ms / config.AUDIO_CHUNK_MS))
        
        # 加载 Silero VAD 模型
        self.model = None
        self._load_model()
        
    def _load_model(self):
        """加载 Silero VAD 模型"""
        try:
            logger.info("正在加载 Silero VAD 模型...")
            self.model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False
            )
            self.model.eval()
            logger.info("Silero VAD 模型加载完成")
        except Exception as e:
            logger.error(f"加载 Silero VAD 模型失败: {e}")
            raise
    
    def reset(self):
        """重置状态"""
        self._is_speaking = False
        self._speech_start_time = None
        self._silence_start_time = None
        self._speech_buffer.clear()
        self._padding_buffer.clear()
        if self.model:
            self.model.reset_states()
    
    def process_chunk(self, audio_chunk: np.ndarray) -> Tuple[bool, Optional[np.ndarray]]:
        """
        处理一个音频块
        
        Args:
            audio_chunk: float32 音频数据 (-1.0 到 1.0)
            
        Returns:
            (is_speech_end, speech_audio)
            - is_speech_end: 是否检测到一段完整语音的结束
            - speech_audio: 如果 is_speech_end=True，返回完整语音音频
        """
        if self.model is None:
            return False, None
            
        current_time = time.time()
        
        # 转换为 tensor
        audio_tensor = torch.from_numpy(audio_chunk).float()
        
        # 获取语音概率
        with torch.no_grad():
            speech_prob = self.model(audio_tensor, self.sample_rate).item()
        
        is_speech = speech_prob >= self.threshold
        
        # 状态机逻辑
        if not self._is_speaking:
            # 当前静音状态
            self._padding_buffer.append(audio_chunk)
            
            if is_speech:
                speech_duration = 0
                if self._speech_start_time is None:
                    self._speech_start_time = current_time
                else:
                    speech_duration = (current_time - self._speech_start_time) * 1000
                
                if speech_duration >= self.min_speech_ms:
                    # 确认开始说话
                    self._is_speaking = True
                    self._silence_start_time = None
                    # 添加前置填充
                    self._speech_buffer.extend(list(self._padding_buffer))
                    self._speech_buffer.append(audio_chunk)
                    logger.debug(f"检测到语音开始 (概率: {speech_prob:.2f})")
            else:
                self._speech_start_time = None
                
        else:
            # 当前说话状态
            self._speech_buffer.append(audio_chunk)
            
            if not is_speech:
                if self._silence_start_time is None:
                    self._silence_start_time = current_time
                else:
                    silence_duration = (current_time - self._silence_start_time) * 1000
                    
                    if silence_duration >= self.min_silence_ms:
                        # 确认结束说话
                        self._is_speaking = False
                        self._speech_start_time = None
                        self._silence_start_time = None
                        
                        # 返回完整语音
                        speech_audio = np.concatenate(self._speech_buffer)
                        self._speech_buffer.clear()
                        self._padding_buffer.clear()
                        self.model.reset_states()
                        
                        logger.debug(f"检测到语音结束 (时长: {len(speech_audio) / self.sample_rate:.2f}s)")
                        return True, speech_audio
            else:
                self._silence_start_time = None
        
        return False, None
    
    @property
    def is_speaking(self) -> bool:
        """当前是否在说话"""
        return self._is_speaking
    
    def get_speech_probability(self, audio_chunk: np.ndarray) -> float:
        """获取语音概率（用于调试）"""
        if self.model is None:
            return 0.0
        audio_tensor = torch.from_numpy(audio_chunk).float()
        with torch.no_grad():
            return self.model(audio_tensor, self.sample_rate).item()


if __name__ == "__main__":
    # 简单测试
    vad = SileroVAD()
    print("Silero VAD 加载成功！")
    print(f"阈值: {vad.threshold}")
    print(f"最小语音时长: {vad.min_speech_ms}ms")
    print(f"最小静音时长: {vad.min_silence_ms}ms")
