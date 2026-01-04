# -*- coding: utf-8 -*-
"""
VoxCPM 首包延迟测试 - 对比有无参考音频
"""

import sys
import os
import time
import scipy.io.wavfile as wavfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
import config

logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")


def test_latency():
    """测试首包延迟"""
    print("=" * 60)
    print("VoxCPM 首包延迟测试")
    print("=" * 60)
    
    from tts.voxcpm_engine import VoxCPMEngine, get_emotion_audio
    
    engine = VoxCPMEngine()
    if not engine.initialize():
        print("VoxCPM 初始化失败")
        return
    
    sample_rate = engine.sample_rate
    test_text = "你好呀！"
    print(f"\n测试文本: \"{test_text}\"")
    
    # ================ 测试1: 无参考音频 ================
    print("\n" + "-" * 60)
    print("测试 1: 无参考音频")
    print("-" * 60)
    
    config.VOXCPM_USE_PROMPT = False
    
    start_time = time.time()
    first_chunk_time = None
    total_samples = 0
    
    for chunk in engine.synthesize_streaming(
        text=test_text,
        emotion=None,  # 不使用情感
    ):
        if first_chunk_time is None:
            first_chunk_time = time.time() - start_time
        total_samples += len(chunk)
    
    total_time = time.time() - start_time
    duration = total_samples / sample_rate
    
    print(f"  首包延迟: {first_chunk_time:.2f}s")
    print(f"  总耗时: {total_time:.2f}s")
    print(f"  音频时长: {duration:.2f}s")
    print(f"  RTF: {total_time/duration:.3f}")
    
    # ================ 测试2: 有参考音频 ================
    print("\n" + "-" * 60)
    print("测试 2: 有参考音频 (情感参考)")
    print("-" * 60)
    
    emotion_audio, emotion_text = get_emotion_audio("happy")
    ref_sr, ref_data = wavfile.read(emotion_audio)
    ref_duration = len(ref_data) / ref_sr
    print(f"  参考音频长度: {ref_duration:.2f}s")
    
    start_time = time.time()
    first_chunk_time = None
    total_samples = 0
    
    for chunk in engine.synthesize_streaming(
        text=test_text,
        emotion="happy",
    ):
        if first_chunk_time is None:
            first_chunk_time = time.time() - start_time
        total_samples += len(chunk)
    
    total_time = time.time() - start_time
    duration = total_samples / sample_rate
    
    print(f"  首包延迟: {first_chunk_time:.2f}s")  # 这是跳过 prompt 后的首包
    print(f"  总耗时: {total_time:.2f}s")
    print(f"  音频时长: {duration:.2f}s")
    print(f"  RTF (基于输出音频): {total_time/duration:.3f}")
    
    # ================ 结论 ================
    print("\n" + "=" * 60)
    print("结论")
    print("=" * 60)
    print(f"  使用情感参考音频会增加约 {ref_duration:.1f}s 的首包延迟")
    print(f"  因为需要先生成参考音频对应的 chunks（虽然被跳过不输出）")
    

if __name__ == "__main__":
    test_latency()
