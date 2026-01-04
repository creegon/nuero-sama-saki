# -*- coding: utf-8 -*-
"""
Speech Transcriber Module - FunASR Paraformer
使用阿里巴巴 DAMO Academy 的 Paraformer 进行语音识别
集成 VAD (语音活动检测) + 标点恢复
"""

import numpy as np
from typing import Optional, Tuple
from loguru import logger
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

# 全局模型实例
_funasr_model = None


def get_funasr_model():
    """懒加载 FunASR 模型"""
    global _funasr_model
    if _funasr_model is None:
        from funasr import AutoModel
        
        logger.info("正在加载 FunASR Paraformer-Large 模型 (含 VAD + 标点)...")
        start_time = time.time()

        # 初始化模型：ASR + VAD + 标点恢复 完整链路
        # 升级到 Large 版本 - 准确率提升至 95%+
        _funasr_model = AutoModel(
            model="iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
            vad_model="fsmn-vad",
            vad_model_revision="v2.0.4",
            punc_model="ct-punc-c",
            punc_model_revision="v2.0.4",
            device="cuda:0"  # 使用 GPU
        )
        
        load_time = time.time() - start_time
        logger.info(f"FunASR Paraformer-Large 模型加载完成 (耗时: {load_time:.2f}s)")
    
    return _funasr_model


class ParaformerTranscriber:
    """语音识别器 - FunASR Paraformer 版"""
    
    def __init__(
        self,
        device: str = config.STT_DEVICE,
        language: str = config.STT_LANGUAGE
    ):
        self.device = device
        self.language = language
        self.model = None
        
    def load_model(self):
        """加载模型（可提前调用以预热）"""
        if self.model is None:
            self.model = get_funasr_model()
    
    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = config.AUDIO_SAMPLE_RATE,
        use_hotwords: bool = True
    ) -> Tuple[str, dict]:
        """
        识别语音

        Args:
            audio: float32 音频数据 (-1.0 到 1.0) 或 int16 音频数据
            sample_rate: 采样率
            use_hotwords: 是否使用热词（提升关键词准确率）

        Returns:
            (text, stats)
            - text: 识别结果文本（已带标点）
            - stats: 统计信息
        """
        if self.model is None:
            self.load_model()

        audio_duration = len(audio) / sample_rate

        start_time = time.time()

        # 确保音频格式正确
        if audio.dtype == np.float32:
            # FunASR 期望 float32 范围 [-1, 1]
            audio_input = audio
        elif audio.dtype == np.int16:
            # 如果是 int16，转换为 float32
            audio_input = audio.astype(np.float32) / 32768.0
        else:
            audio_input = audio.astype(np.float32)

        # 准备热词
        hotword = None
        if use_hotwords:
            try:
                from ..hotwords import get_hotwords_with_weights
                hotword = get_hotwords_with_weights()
            except ImportError:
                pass

        # 执行识别 (FunASR 会自动处理 VAD 和标点)
        generate_kwargs = {
            "input": audio_input,
            "batch_size_s": 300,  # 支持长音频
        }

        # 添加热词（如果启用）
        if hotword:
            generate_kwargs["hotword"] = hotword

        result = self.model.generate(**generate_kwargs)
        
        # 提取文本
        text = ""
        if result and len(result) > 0:
            # FunASR 返回的是列表，取第一个结果
            if isinstance(result[0], dict):
                text = result[0].get("text", "")
            elif isinstance(result[0], str):
                text = result[0]
            else:
                # 尝试其他格式
                text = str(result[0])
        
        transcribe_time = time.time() - start_time
        rtf = transcribe_time / audio_duration if audio_duration > 0 else 0
        
        stats = {
            "transcribe_time": transcribe_time,
            "audio_duration": audio_duration,
            "rtf": rtf,
            "language": "zh",
            "model": "paraformer-large-zh"
        }
        
        # 后处理
        from ..post_processor import post_process
        text = post_process(text)
        
        logger.info(f"识别结果: '{text}' (耗时: {transcribe_time:.2f}s, RTF: {rtf:.2f})")
        
        return text.strip(), stats


# 全局单例
_transcriber: Optional[Transcriber] = None


def get_transcriber() -> Transcriber:
    """获取全局 Transcriber 实例"""
    global _transcriber
    if _transcriber is None:
        _transcriber = Transcriber()
    return _transcriber


if __name__ == "__main__":
    # 测试模型加载
    print("测试 FunASR Paraformer 模型加载...")
    transcriber = Transcriber()
    transcriber.load_model()
    print("模型加载成功！")
    
    # 测试空音频
    empty_audio = np.zeros(16000, dtype=np.float32)  # 1秒静音
    text, stats = transcriber.transcribe(empty_audio)
    print(f"静音测试结果: '{text}'")
    print(f"统计: {stats}")
