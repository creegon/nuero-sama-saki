# -*- coding: utf-8 -*-
"""
FireRedASR Transcriber Wrapper

将 FireRedASR 封装为与 FunASR Paraformer 相同的接口，
使其可以作为可选的 STT 引擎使用。

FireRedASR-AED-L 特点：
- 1.1B 参数，CER ~3.18% (中文 benchmark)
- 比 Paraformer 准确率更高，但速度较慢 (~3x)
"""

import numpy as np
from typing import Tuple
from loguru import logger
import time
import sys
import os
import tempfile
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

# 全局模型实例
_fireredasr_model = None


def get_fireredasr_model():
    """懒加载 FireRedASR 模型"""
    global _fireredasr_model
    if _fireredasr_model is None:
        # Windows 兼容性修复: 必须在 PyTorch 之前先导入 sentencepiece
        import sentencepiece as _spm_preload
        
        # 添加 FireRedASR 到路径
        fireredasr_path = os.path.join(config.MODULES_DIR, "FireRedASR")
        if os.path.exists(fireredasr_path) and fireredasr_path not in sys.path:
            sys.path.insert(0, fireredasr_path)
        
        from fireredasr.models.fireredasr import FireRedAsr
        
        logger.info("正在加载 FireRedASR-AED-L 模型...")
        start_time = time.time()
        
        _fireredasr_model = FireRedAsr.from_pretrained("aed", config.FIREREDASR_MODEL_DIR)
        
        load_time = time.time() - start_time
        logger.info(f"FireRedASR-AED-L 加载完成 (耗时: {load_time:.2f}s)")
    
    return _fireredasr_model


class FireRedASRTranscriber:
    """FireRedASR 语音识别器 - 与 Paraformer Transcriber 接口兼容"""
    
    def __init__(self, device: str = "cuda"):
        self.device = device
        self.model = None
        self._temp_dir = tempfile.mkdtemp(prefix="fireredasr_")
        self._temp_wav_path = os.path.join(self._temp_dir, "temp_audio.wav")
    
    def load_model(self):
        """加载模型（可提前调用以预热）"""
        if self.model is None:
            self.model = get_fireredasr_model()
    
    def _save_temp_wav(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """将 numpy 音频保存为临时 WAV 文件"""
        # 确保是 int16 格式
        if audio.dtype == np.float32:
            audio_int16 = (audio * 32768).astype(np.int16)
        elif audio.dtype == np.int16:
            audio_int16 = audio
        else:
            audio_int16 = audio.astype(np.int16)
        
        with wave.open(self._temp_wav_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(audio_int16.tobytes())
        
        return self._temp_wav_path
    
    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        use_hotwords: bool = True  # 保持接口兼容，但 FireRedASR 不支持热词
    ) -> Tuple[str, dict]:
        """
        识别语音

        Args:
            audio: float32 音频数据 (-1.0 到 1.0) 或 int16 音频数据
            sample_rate: 采样率
            use_hotwords: 热词参数（保持接口兼容，FireRedASR 不支持）

        Returns:
            (text, stats)
            - text: 识别结果文本
            - stats: 统计信息
        """
        if self.model is None:
            self.load_model()
        
        audio_duration = len(audio) / sample_rate
        start_time = time.time()
        
        # FireRedASR 需要 WAV 文件路径作为输入
        wav_path = self._save_temp_wav(audio, sample_rate)
        
        # 调用 FireRedASR 推理
        results = self.model.transcribe(
            ["realtime_utterance"],
            [wav_path],
            {
                "use_gpu": 1 if self.device == "cuda" else 0,
                "beam_size": 1,  # Greedy decoding 最快
                "nbest": 1,
                "decode_max_len": 0,
                "softmax_smoothing": 1.0,
                "aed_length_penalty": 0.0,
                "eos_penalty": 1.0
            }
        )
        
        # 提取文本
        text = ""
        if results and len(results) > 0:
            if isinstance(results[0], dict):
                text = results[0].get("text", "")
            else:
                text = str(results[0])
        
        transcribe_time = time.time() - start_time
        rtf = transcribe_time / audio_duration if audio_duration > 0 else 0
        
        stats = {
            "transcribe_time": transcribe_time,
            "audio_duration": audio_duration,
            "rtf": rtf,
            "language": "zh",
            "model": "fireredasr-aed-l"
        }
        
        # 后处理
        from ..post_processor import post_process
        text = post_process(text)
        
        logger.info(f"识别结果: '{text}' (耗时: {transcribe_time:.2f}s, RTF: {rtf:.2f})")
        
        return text.strip(), stats
    
    def __del__(self):
        """清理临时文件"""
        try:
            if os.path.exists(self._temp_wav_path):
                os.remove(self._temp_wav_path)
            if os.path.exists(self._temp_dir):
                os.rmdir(self._temp_dir)
        except:
            pass


# 全局单例
_transcriber = None


def get_transcriber() -> FireRedASRTranscriber:
    """获取全局 FireRedASR Transcriber 实例"""
    global _transcriber
    if _transcriber is None:
        _transcriber = FireRedASRTranscriber()
    return _transcriber


if __name__ == "__main__":
    # 测试模型加载
    print("测试 FireRedASR 模型加载...")
    transcriber = FireRedASRTranscriber()
    transcriber.load_model()
    print("模型加载成功！")
    
    # 测试空音频
    empty_audio = np.zeros(16000, dtype=np.float32)  # 1秒静音
    text, stats = transcriber.transcribe(empty_audio)
    print(f"静音测试结果: '{text}'")
    print(f"统计: {stats}")
