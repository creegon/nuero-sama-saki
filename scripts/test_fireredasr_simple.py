# -*- coding: utf-8 -*-
"""
FireRedASR-AED 简单基准测试脚本

测试纯推理速度，不涉及麦克风输入。
用于验证 FP16 + torch.compile 优化效果。
"""

# ============================================================
# Windows 兼容性修复: 必须在 PyTorch 之前先导入 sentencepiece
# ============================================================
import sentencepiece as _spm_preload
print("[DEBUG] sentencepiece 预加载完成")

import os
import sys
import time
import wave
import struct
import numpy as np
from pathlib import Path

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# FireRedASR 路径
FIREREDASR_PATH = os.path.join(PROJECT_ROOT, "modules", "FireRedASR")
if os.path.exists(FIREREDASR_PATH):
    sys.path.insert(0, FIREREDASR_PATH)

# 模型目录
MODEL_DIR = os.path.join(PROJECT_ROOT, "modules", "FireRedASR", "pretrained_models", "FireRedASR-AED-L")

# 测试用音频文件路径
# 如果指定的文件存在，则直接使用；否则会生成临时测试音频
TEST_WAV_PATH = os.path.join(PROJECT_ROOT, "debug_audio", "tts_8_20260101_130716.wav")

# 临时生成的测试音频 (不会覆盖真实音频)
GENERATED_TEST_WAV = os.path.join(PROJECT_ROOT, "scripts", "_temp_benchmark_audio.wav")


def generate_test_audio(duration_sec: float = 3.0, sample_rate: int = 16000) -> str:
    """
    生成测试用的噪声音频文件（用于基准测试）
    
    注意：只会写入 GENERATED_TEST_WAV，不会覆盖 TEST_WAV_PATH
    
    Args:
        duration_sec: 音频时长（秒）
        sample_rate: 采样率
    
    Returns:
        生成的 WAV 文件路径
    """
    # 生成低噪声音频
    num_samples = int(duration_sec * sample_rate)
    audio_data = np.random.randint(-100, 100, num_samples, dtype=np.int16)
    
    with wave.open(GENERATED_TEST_WAV, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())
    
    return GENERATED_TEST_WAV


def run_benchmark(model, audio_path: str, num_warmup: int = 2, num_iterations: int = 5):
    """
    运行推理基准测试
    
    Args:
        model: FireRedAsr 模型实例
        audio_path: 测试音频文件路径
        num_warmup: Warmup 次数（不计入统计）
        num_iterations: 正式测试次数
    
    Returns:
        (平均推理时间, 最小时间, 最大时间)
    """
    args = {
        "use_gpu": 1,
        "beam_size": 1,  # Greedy decoding 最快
        "nbest": 1,
        "decode_max_len": 0,
        "softmax_smoothing": 1.0,
        "aed_length_penalty": 0.0,
        "eos_penalty": 1.0
    }
    
    # Warmup: 预热 torch.compile 的 JIT 编译
    print(f"\n[Warmup] 执行 {num_warmup} 次预热...")
    for i in range(num_warmup):
        print(f"  Warmup {i+1}/{num_warmup}...", end=" ", flush=True)
        start = time.time()
        model.transcribe(["warmup"], [audio_path], args)
        elapsed = time.time() - start
        print(f"{elapsed:.3f}s")
    
    # Benchmark
    print(f"\n[Benchmark] 执行 {num_iterations} 次正式测试...")
    times = []
    for i in range(num_iterations):
        print(f"  Iteration {i+1}/{num_iterations}...", end=" ", flush=True)
        start = time.time()
        results = model.transcribe(["benchmark"], [audio_path], args)
        elapsed = time.time() - start
        times.append(elapsed)
        
        # 显示识别结果
        text = ""
        if results and len(results) > 0:
            text = results[0].get("text", "") if isinstance(results[0], dict) else str(results[0])
        print(f"{elapsed:.3f}s (text: '{text[:30]}...' )" if len(text) > 30 else f"{elapsed:.3f}s (text: '{text}')")
    
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    
    return avg_time, min_time, max_time


def main():
    print("=" * 60)
    print("FireRedASR-AED-L 基准测试")
    print("=" * 60)
    
    # 检查模型目录
    if not os.path.exists(MODEL_DIR):
        print(f"\n[ERROR] 模型目录不存在: {MODEL_DIR}")
        print("请先下载模型")
        return
    
    # 导入并加载模型
    print("\n[1/4] 导入 FireRedAsr...")
    from fireredasr.models.fireredasr import FireRedAsr
    
    print("\n[2/4] 加载模型 (包含 FP16 + torch.compile 优化)...")
    print("       注意: 首次加载可能需要较长时间进行 torch.compile 编译")
    print("       torch.compile 会自动缓存编译结果，后续启动会更快\n")
    
    load_start = time.time()
    model = FireRedAsr.from_pretrained("aed", MODEL_DIR)
    load_time = time.time() - load_start
    print(f"\n模型加载耗时: {load_time:.2f}s")
    
    # 准备测试音频
    is_generated = False
    if os.path.exists(TEST_WAV_PATH):
        # 使用用户指定的真实音频
        print(f"\n[3/4] 使用真实音频文件进行测试...")
        audio_path = TEST_WAV_PATH
        print(f"       音频路径: {audio_path}")
    else:
        # 生成临时测试音频
        print("\n[3/4] 生成临时测试音频 (3秒噪声)...")
        audio_path = generate_test_audio(duration_sec=3.0)
        is_generated = True
        print(f"       临时音频: {audio_path}")
    
    # 运行基准测试
    print("\n[4/4] 运行推理基准测试...")
    avg_time, min_time, max_time = run_benchmark(
        model, 
        audio_path,
        num_warmup=3,  # 3 次预热让 torch.compile 充分编译
        num_iterations=5
    )
    
    # 打印结果
    print("\n" + "=" * 60)
    print("基准测试结果")
    print("=" * 60)
    print(f"  平均推理时间: {avg_time:.3f}s")
    print(f"  最小推理时间: {min_time:.3f}s")
    print(f"  最大推理时间: {max_time:.3f}s")
    print(f"  RTF (Real-Time Factor): {avg_time / 3.0:.4f}")
    print("=" * 60)
    
    # 判断是否达标
    if avg_time < 0.2:
        print("\n✅ 推理速度优秀 (< 0.2s)")
    elif avg_time < 0.5:
        print("\n✅ 推理速度良好 (< 0.5s)")
    else:
        print("\n⚠️ 推理速度较慢，建议检查 GPU 状态或优化配置")
    
    # 清理临时生成的测试文件 (不删除用户的真实音频)
    if is_generated and os.path.exists(GENERATED_TEST_WAV):
        os.remove(GENERATED_TEST_WAV)
        print(f"\n已清理临时测试音频")
    
    print("\n测试完成!")


if __name__ == "__main__":
    main()
