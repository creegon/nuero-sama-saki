# -*- coding: utf-8 -*-
"""
音频质量验证器 - 检测TTS生成的音频是否异常
"""

import numpy as np
from loguru import logger


class AudioValidator:
    """音频质量验证器"""
    
    @staticmethod
    def validate(audio: np.ndarray, sample_rate: int = 44100) -> tuple:
        """
        检测音频是否异常
        
        Args:
            audio: 音频数据 (numpy array, float32)
            sample_rate: 采样率
            
        Returns:
            (is_valid, reason): (是否有效, 问题原因)
        """
        try:
            # 1. 检查音量
            rms = np.sqrt(np.mean(audio**2))
            if rms < 0.001:
                return False, "音量过低（可能是静音）"
            if rms > 0.3:
                return False, "音量过高（可能爆音）"
            
            # 2. 检查时长
            duration = len(audio) / sample_rate
            if duration < 0.1:
                return False, "音频过短"
            if duration > 60:
                return False, "音频过长（异常）"
            
            # 3. 检测异常频率（尖锐啸叫）
            # 简单检测：高频能量异常
            if len(audio) > sample_rate:  # 至少1秒
                window = audio[:sample_rate]  # 取前1秒
                high_freq_energy = np.sum(np.abs(np.diff(window))) / len(window)
                if high_freq_energy > 0.5:
                    return False, "检测到高频噪音（可能啸叫）"

            
            return True, ""
            
        except Exception as e:
            logger.error(f"音频验证异常: {e}")
            return True, ""  # 验证失败时放行，避免阻塞
