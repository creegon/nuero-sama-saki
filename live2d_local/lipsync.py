# -*- coding: utf-8 -*-
"""
Lip Sync Module - 实时口型同步
基于音频频谱分析检测元音，驱动 Live2D 口型动画

实现原理:
1. 对音频块进行 FFT 频谱分析
2. 根据低频/高频能量比推断元音类型 (A/I/U/E/O)
3. 输出口型参数用于驱动 Live2D 模型
"""

import numpy as np
from typing import Tuple, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class VowelShape:
    """元音对应的口型参数"""
    mouth_open: float    # 嘴巴张开程度 (0-1)
    mouth_form: float    # 嘴巴形状 (-1=圆形, 0=中性, 1=横拉)
    
# 元音口型定义 (参考日语发音)
VOWEL_SHAPES = {
    "A": VowelShape(mouth_open=1.0, mouth_form=0.0),    # あ - 大张嘴
    "I": VowelShape(mouth_open=0.3, mouth_form=1.0),    # い - 横拉微张
    "U": VowelShape(mouth_open=0.4, mouth_form=-0.6),   # う - 圆形微张
    "E": VowelShape(mouth_open=0.5, mouth_form=0.3),    # え - 中等张开
    "O": VowelShape(mouth_open=0.7, mouth_form=-0.8),   # お - 圆形大张
    "N": VowelShape(mouth_open=0.15, mouth_form=0.0),   # ん - 闭嘴鼻音
    "silence": VowelShape(mouth_open=0.0, mouth_form=0.0),  # 静音
}


class LipSyncAnalyzer:
    """
    实时口型分析器
    基于音频频谱分析推断元音
    """
    
    def __init__(self, sample_rate: int = 44100, smoothing: float = 0.3):
        """
        Args:
            sample_rate: 采样率
            smoothing: 平滑系数 (0-1, 越大变化越平滑)
        """
        self.sample_rate = sample_rate
        self.smoothing = smoothing
        
        # 当前状态
        self._current_vowel = "silence"
        self._current_mouth_open = 0.0
        self._current_mouth_form = 0.0
        self._energy_history = []
        
        # 频率范围定义 (Hz)
        self.LOW_FREQ_RANGE = (100, 500)     # 低频 (A, O 主要区域)
        self.MID_FREQ_RANGE = (500, 1500)    # 中频 (U, E 主要区域)
        self.HIGH_FREQ_RANGE = (1500, 4000)  # 高频 (I 主要区域)
        
        # 能量阈值
        self.SILENCE_THRESHOLD = 0.01
        self.VOWEL_THRESHOLD = 0.05
    
    def analyze(self, audio_chunk: np.ndarray) -> Tuple[str, float, float]:
        """
        分析音频块，返回当前口型
        
        Args:
            audio_chunk: 音频数据 (float32, -1 到 1)
            
        Returns:
            (vowel, mouth_open, mouth_form)
            - vowel: 元音类型 (A/I/U/E/O/N/silence)
            - mouth_open: 嘴巴张开程度 (0-1)
            - mouth_form: 嘴巴形状 (-1 到 1)
        """
        if len(audio_chunk) == 0:
            return self._apply_smoothing("silence", 0.0, 0.0)
        
        # 确保是 1D 数组
        if audio_chunk.ndim > 1:
            audio_chunk = audio_chunk.flatten()
        
        # 计算总能量 (RMS)
        rms = np.sqrt(np.mean(audio_chunk ** 2))
        
        # 静音检测
        if rms < self.SILENCE_THRESHOLD:
            return self._apply_smoothing("silence", 0.0, 0.0)
        
        # FFT 频谱分析
        fft = np.fft.rfft(audio_chunk)
        magnitude = np.abs(fft)
        freqs = np.fft.rfftfreq(len(audio_chunk), 1.0 / self.sample_rate)
        
        # 计算各频段能量
        low_energy = self._get_band_energy(magnitude, freqs, *self.LOW_FREQ_RANGE)
        mid_energy = self._get_band_energy(magnitude, freqs, *self.MID_FREQ_RANGE)
        high_energy = self._get_band_energy(magnitude, freqs, *self.HIGH_FREQ_RANGE)
        
        total_energy = low_energy + mid_energy + high_energy + 1e-8
        
        # 频率能量比例
        low_ratio = low_energy / total_energy
        mid_ratio = mid_energy / total_energy
        high_ratio = high_energy / total_energy
        
        # 根据频谱特征推断元音
        vowel = self._classify_vowel(low_ratio, mid_ratio, high_ratio, rms)
        
        # 获取口型参数
        shape = VOWEL_SHAPES.get(vowel, VOWEL_SHAPES["silence"])
        
        # 根据能量调整张嘴幅度
        intensity = min(rms / 0.15, 1.0)  # 归一化
        mouth_open = shape.mouth_open * intensity
        mouth_form = shape.mouth_form
        
        return self._apply_smoothing(vowel, mouth_open, mouth_form)
    
    def _get_band_energy(self, magnitude: np.ndarray, freqs: np.ndarray, 
                         low: float, high: float) -> float:
        """计算指定频段的能量"""
        mask = (freqs >= low) & (freqs <= high)
        if not np.any(mask):
            return 0.0
        return np.sum(magnitude[mask] ** 2)
    
    def _classify_vowel(self, low_ratio: float, mid_ratio: float, 
                        high_ratio: float, rms: float) -> str:
        """根据频谱比例分类元音"""
        
        # I: 高频占主导
        if high_ratio > 0.4:
            return "I"
        
        # A: 低频强，中高频也有
        if low_ratio > 0.5 and mid_ratio > 0.2:
            return "A"
        
        # O: 低频占主导，高频弱
        if low_ratio > 0.6 and high_ratio < 0.15:
            return "O"
        
        # U: 中频占主导，低频也有
        if mid_ratio > 0.4 and low_ratio > 0.3 and high_ratio < 0.2:
            return "U"
        
        # E: 中高频，低频适中
        if mid_ratio > 0.35 and high_ratio > 0.2:
            return "E"
        
        # 低能量时可能是鼻音或辅音
        if rms < self.VOWEL_THRESHOLD:
            return "N"
        
        # 默认返回 A
        return "A"
    
    def _apply_smoothing(self, vowel: str, mouth_open: float, 
                         mouth_form: float) -> Tuple[str, float, float]:
        """应用平滑过渡"""
        # 嘴巴张开度平滑
        self._current_mouth_open += (mouth_open - self._current_mouth_open) * (1 - self.smoothing)
        
        # 嘴巴形状平滑
        self._current_mouth_form += (mouth_form - self._current_mouth_form) * (1 - self.smoothing)
        
        # 元音优先使用检测到的
        self._current_vowel = vowel
        
        return (self._current_vowel, self._current_mouth_open, self._current_mouth_form)
    
    def reset(self):
        """重置状态"""
        self._current_vowel = "silence"
        self._current_mouth_open = 0.0
        self._current_mouth_form = 0.0
        self._energy_history.clear()


class LipSyncController:
    """
    口型控制器 - 连接分析器与 Live2D 控制器
    """
    
    def __init__(self, live2d_controller=None, sample_rate: int = 44100):
        self.analyzer = LipSyncAnalyzer(sample_rate)
        self.controller = live2d_controller
        self.is_speaking = False
    
    def set_controller(self, controller):
        """设置 Live2D 控制器"""
        self.controller = controller
    
    def start_speaking(self):
        """开始说话"""
        self.is_speaking = True
    
    def stop_speaking(self):
        """停止说话"""
        self.is_speaking = False
        self.analyzer.reset()
        if self.controller:
            self.controller.set_mouth_open(0.0)
    
    def process_audio(self, audio_chunk: np.ndarray):
        """处理音频块并更新口型"""
        if not self.is_speaking:
            return
        
        vowel, mouth_open, mouth_form = self.analyzer.analyze(audio_chunk)
        
        if self.controller:
            self.controller.set_vowel(vowel, mouth_open, mouth_form)


# 全局单例
_lip_sync: Optional[LipSyncAnalyzer] = None


def get_lip_sync_analyzer(sample_rate: int = 44100) -> LipSyncAnalyzer:
    """获取全局 LipSyncAnalyzer 实例"""
    global _lip_sync
    if _lip_sync is None:
        _lip_sync = LipSyncAnalyzer(sample_rate)
    return _lip_sync


if __name__ == "__main__":
    # 测试
    import sounddevice as sd
    
    print("🎤 测试口型分析器 - 对着麦克风说 A/I/U/E/O")
    print("按 Ctrl+C 退出\n")
    
    analyzer = LipSyncAnalyzer(sample_rate=16000)
    
    def audio_callback(indata, frames, time, status):
        if status:
            print(f"Status: {status}")
        
        vowel, mouth_open, mouth_form = analyzer.analyze(indata[:, 0])
        
        # 可视化
        bar_len = int(mouth_open * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        form_indicator = "<" if mouth_form < -0.3 else (">" if mouth_form > 0.3 else "o")
        
        print(f"\r  {vowel:7} [{bar}] {form_indicator}", end="", flush=True)
    
    try:
        with sd.InputStream(channels=1, samplerate=16000, blocksize=512, 
                           callback=audio_callback):
            print("录音中...")
            while True:
                sd.sleep(100)
    except KeyboardInterrupt:
        print("\n\n结束")
