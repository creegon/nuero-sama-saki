# -*- coding: utf-8 -*-
"""
Audio Player Module
使用 sounddevice 播放音频
"""

import sounddevice as sd
import numpy as np
from scipy.io import wavfile
from typing import Optional, Callable, Union
from loguru import logger
import threading
import time
import io


class AudioPlayer:
    """音频播放器"""
    
    def __init__(self):
        self._is_playing = False
        self._should_stop = False
        self._current_thread: Optional[threading.Thread] = None
        
        # 回调
        self.on_play_start: Optional[Callable[[str], None]] = None
        self.on_play_end: Optional[Callable[[str], None]] = None
    
    def play(self, audio_source: Union[str, bytes, np.ndarray], blocking: bool = False, sample_rate: int = 44100) -> bool:
        """
        播放音频
        
        Args:
            audio_source: 音频文件路径(str) 或 WAV数据(bytes) 或 音频数组(np.ndarray)
            blocking: 是否阻塞等待播放完成
            sample_rate: 如果输入是 numpy 数组，必须指定采样率
            
        Returns:
            是否成功开始播放
        """
        if blocking:
            return self._play_blocking(audio_source, sample_rate)
        else:
            return self._play_async(audio_source, sample_rate)
    
    def _play_blocking(self, audio_source: Union[str, bytes, np.ndarray], sample_rate: int = 44100) -> bool:
        """阻塞播放 (使用 soundfile + sleep 防止 sd.wait 卡死)"""
        try:
            # Local imports
            import soundfile as sf
            import librosa
            
            target_sr = sample_rate
            audio_data = None

            # Read audio data
            if isinstance(audio_source, str):
                audio_data, target_sr = sf.read(audio_source, dtype='float32')
            elif isinstance(audio_source, bytes):
                # 跳过已流式播放的任务 (标记为 b'streamed')
                if audio_source == b'streamed':
                    logger.debug("跳过已流式播放的音频")
                    return True  # 已播放，视为成功
                with io.BytesIO(audio_source) as bio:
                    audio_data, target_sr = sf.read(bio, dtype='float32')
            elif isinstance(audio_source, np.ndarray):
                audio_data = audio_source
                if audio_data.dtype == np.int16:
                    audio_data = audio_data.astype(np.float32) / 32768.0
                elif audio_data.dtype == np.int32:
                    audio_data = audio_data.astype(np.float32) / 2147483648.0
            else:
                 logger.error(f"不支持的音频源类型: {type(audio_source)}")
                 return False
            
            # Ensure audio_data is at least 1D
            if audio_data.ndim > 2:
                logger.error(f"无效的音频维度: {audio_data.ndim}")
                return False
            
            # FORCE Resample to 48000Hz (Standard) to avoid driver mismatch issues
            # If input is 24000Hz, this fixes "Chipmunk" effect on 48k-only devices
            if target_sr != 48000:
                # Transpose if needed (librosa expects (channels, samples) for multi-channel, 
                # but sf.read returns (samples, channels))
                # Logic: librosa.resample works on 1D or (C, N).
                # audio_data shape: (N,) or (N, C).
                # If stereo (N, 2), we need to transpose to (2, N) for librosa -> (2, N_new) -> transpose back
                
                is_stereo = audio_data.ndim == 2
                if is_stereo:
                    audio_data = audio_data.T
                
                # Resample
                audio_data = librosa.resample(audio_data, orig_sr=target_sr, target_sr=48000)
                target_sr = 48000
                
                if is_stereo:
                    audio_data = audio_data.T
                    
            self._is_playing = True
            self._should_stop = False
            
            if self.on_play_start:
                source_repr = audio_source if isinstance(audio_source, str) else "<memory-audio>"
                self.on_play_start(source_repr)
            
            # Calculate duration
            duration = len(audio_data) / target_sr
            logger.debug(f"开始播放... ({duration:.2f}s, SR={target_sr})")
            
            sd.play(audio_data, target_sr)
            
            # Sleep loop with interrupt check (safer than sd.wait)
            elapsed = 0
            while elapsed < duration + 0.3 and not self._should_stop:
                time.sleep(0.1)
                elapsed += 0.1
            
            sd.stop()
            self._is_playing = False
            
            if self.on_play_end:
                 source_repr = audio_source if isinstance(audio_source, str) else "<memory-audio>"
                 self.on_play_end(source_repr)
            
            logger.debug(f"播放完成")
            return True
            
        except Exception as e:
            logger.error(f"播放失败: {e}")
            import traceback
            traceback.print_exc()
            self._is_playing = False
            return False
    
    def _play_async(self, audio_source: Union[str, bytes, np.ndarray], sample_rate: int = 44100) -> bool:
        """异步播放"""
        if self._is_playing:
            logger.warning("正在播放中，跳过")
            return False
        
        self._current_thread = threading.Thread(
            target=self._play_blocking,
            args=(audio_source, sample_rate),
            daemon=True
        )
        self._current_thread.start()
        return True
    
    def stop(self):
        """停止播放"""
        self._should_stop = True
        sd.stop()
        self._is_playing = False
        logger.debug("播放已停止")
    
    def wait(self):
        """等待当前播放完成"""
        if self._current_thread and self._current_thread.is_alive():
            self._current_thread.join()
    
    @property
    def is_playing(self) -> bool:
        return self._is_playing


class SequentialPlayer:
    """顺序播放器，按序播放音频队列"""
    
    def __init__(self):
        self.player = AudioPlayer()
        self._play_queue: list = []
        self._is_running = False
        self._play_thread: Optional[threading.Thread] = None
        
        # 回调
        self.on_sentence_start: Optional[Callable[[int, str], None]] = None
        self.on_sentence_end: Optional[Callable[[int, str], None]] = None
        self.on_all_done: Optional[Callable[[], None]] = None
    
    def start(self):
        """启动播放器"""
        self._is_running = True
        self._play_queue.clear()
        self._play_thread = threading.Thread(target=self._play_loop, daemon=True)
        self._play_thread.start()
        logger.info("顺序播放器已启动")
    
    def stop(self):
        """停止播放器"""
        self._is_running = False
        self.player.stop()
        self._play_queue.clear()
        logger.info("顺序播放器已停止")
    
    def add(self, task_id: int, audio_source: Union[str, bytes], text: str):
        """添加音频到播放队列"""
        self._play_queue.append((task_id, audio_source, text))
    
    def clear(self):
        """清空队列"""
        self._play_queue.clear()
        self.player.stop()
    
    def _play_loop(self):
        """播放循环"""
        while self._is_running:
            if self._play_queue:
                task_id, audio_source, text = self._play_queue.pop(0)
                
                if self.on_sentence_start:
                    self.on_sentence_start(task_id, text)
                
                self.player.play(audio_source, blocking=True)
                
                if self.on_sentence_end:
                    self.on_sentence_end(task_id, text)
            else:
                time.sleep(0.05)
    
    @property
    def is_playing(self) -> bool:
        return self.player.is_playing or len(self._play_queue) > 0


# 全局单例
_player: Optional[SequentialPlayer] = None


def get_player() -> SequentialPlayer:
    """获取全局播放器实例"""
    global _player
    if _player is None:
        _player = SequentialPlayer()
    return _player


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python player.py <音频文件>")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    player = AudioPlayer()
    player.play(audio_file, blocking=True)
