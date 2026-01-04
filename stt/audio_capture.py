# -*- coding: utf-8 -*-
"""
Audio Capture Module
使用 PyAudio 采集麦克风音频流
"""

import pyaudio
import numpy as np
from typing import Generator, Optional
from loguru import logger
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class AudioCapture:
    """麦克风音频采集器"""
    
    def __init__(
        self,
        sample_rate: int = config.AUDIO_SAMPLE_RATE,
        channels: int = config.AUDIO_CHANNELS,
        chunk_ms: int = config.AUDIO_CHUNK_MS
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_ms = chunk_ms
        self.chunk_size = int(sample_rate * chunk_ms / 1000)
        
        self.pyaudio = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None
        self._is_running = False
        
    def _get_input_device_index(self) -> Optional[int]:
        """获取默认输入设备索引"""
        try:
            default_device = self.pyaudio.get_default_input_device_info()
            logger.info(f"使用默认输入设备: {default_device['name']}")
            return default_device['index']
        except Exception as e:
            logger.warning(f"无法获取默认输入设备: {e}")
            # 尝试找到任何可用的输入设备
            for i in range(self.pyaudio.get_device_count()):
                device_info = self.pyaudio.get_device_info_by_index(i)
                if device_info['maxInputChannels'] > 0:
                    logger.info(f"使用备选输入设备: {device_info['name']}")
                    return i
            return None
    
    def start(self) -> bool:
        """开始采集"""
        if self._is_running:
            return True
            
        device_index = self._get_input_device_index()
        if device_index is None:
            logger.error("没有找到可用的输入设备")
            return False
            
        try:
            self.stream = self.pyaudio.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk_size
            )
            self._is_running = True
            logger.info(f"音频采集已启动 (采样率: {self.sample_rate}, 块大小: {self.chunk_size})")
            return True
        except Exception as e:
            logger.error(f"启动音频采集失败: {e}")
            return False
    
    def stop(self):
        """停止采集"""
        self._is_running = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        logger.info("音频采集已停止")
    
    def read_chunk(self) -> Optional[np.ndarray]:
        """读取一个音频块"""
        if not self._is_running or not self.stream:
            return None
            
        try:
            data = self.stream.read(self.chunk_size, exception_on_overflow=False)
            audio_chunk = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            return audio_chunk
        except Exception as e:
            logger.error(f"读取音频块失败: {e}")
            return None
    
    def stream_chunks(self) -> Generator[np.ndarray, None, None]:
        """生成器：持续产出音频块"""
        if not self.start():
            return
            
        try:
            while self._is_running:
                chunk = self.read_chunk()
                if chunk is not None:
                    yield chunk
        finally:
            self.stop()
    
    @property
    def is_running(self) -> bool:
        return self._is_running
    
    def __del__(self):
        self.stop()
        if self.pyaudio:
            self.pyaudio.terminate()


def list_audio_devices():
    """列出所有音频设备"""
    p = pyaudio.PyAudio()
    print("\n可用音频设备:")
    print("-" * 60)
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        device_type = []
        if info['maxInputChannels'] > 0:
            device_type.append("输入")
        if info['maxOutputChannels'] > 0:
            device_type.append("输出")
        print(f"[{i}] {info['name']} ({', '.join(device_type)})")
    print("-" * 60)
    p.terminate()


if __name__ == "__main__":
    list_audio_devices()
