# -*- coding: utf-8 -*-
"""
STT 对比基准测试脚本

比较 FireRedASR-AED-L 和 FunASR Paraformer-Large 的推理速度
"""

import os
import sys
import time
import wave
import numpy as np
from pathlib import Path

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# 测试音频路径
TEST_WAV_PATH = os.path.join(PROJECT_ROOT, "debug_audio", "tts_8_20260101_130716.wav")


def load_audio(wav_path: str) -> tuple:
    """加载 WAV 音频"""
    with wave.open(wav_path, 'rb') as wf:
        sample_rate = wf.getframerate()
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        n_frames = wf.getnframes()
        audio_bytes = wf.readframes(n_frames)
        
        # 转为 numpy array
        if sample_width == 2:
            audio = np.frombuffer(audio_bytes, dtype=np.int16)
        else:
            raise ValueError(f"Unsupported sample width: {sample_width}")
        
        # 如果是立体声，取第一个通道
        if n_channels == 2:
            audio = audio[::2]
        
        duration = len(audio) / sample_rate
        return audio, sample_rate, duration


def run_benchmark(name: str, transcribe_func, audio, num_warmup: int = 2, num_iterations: int = 5):
    """运行基准测试"""
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print("=" * 60)
    
    # Warmup
    print(f"[Warmup] {num_warmup} 次预热...")
    for i in range(num_warmup):
        print(f"  Warmup {i+1}/{num_warmup}...", end=" ", flush=True)
        start = time.time()
        text, _ = transcribe_func(audio)
        elapsed = time.time() - start
        print(f"{elapsed:.3f}s")
    
    # Benchmark
    print(f"\n[Benchmark] {num_iterations} 次测试...")
    times = []
    final_text = ""
    for i in range(num_iterations):
        print(f"  Iteration {i+1}/{num_iterations}...", end=" ", flush=True)
        start = time.time()
        text, _ = transcribe_func(audio)
        elapsed = time.time() - start
        times.append(elapsed)
        final_text = text
        
        preview = text[:40] + "..." if len(text) > 40 else text
        print(f"{elapsed:.3f}s (text: '{preview}')")
    
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    
    return {
        "name": name,
        "avg_time": avg_time,
        "min_time": min_time,
        "max_time": max_time,
        "text": final_text
    }


def test_paraformer():
    """测试 FunASR Paraformer-Large"""
    from stt.transcriber import Transcriber
    
    print("\n加载 FunASR Paraformer-Large 模型...")
    start = time.time()
    transcriber = Transcriber()
    transcriber.load_model()
    load_time = time.time() - start
    print(f"模型加载耗时: {load_time:.2f}s")
    
    def transcribe(audio):
        # Paraformer 需要 float32 输入
        audio_float = audio.astype(np.float32) / 32768.0
        return transcriber.transcribe(audio_float)
    
    return transcribe


def test_fireredasr():
    """测试 FireRedASR-AED-L"""
    # Windows 兼容性修复
    import sentencepiece as _spm_preload
    
    # FireRedASR 路径
    FIREREDASR_PATH = os.path.join(PROJECT_ROOT, "modules", "FireRedASR")
    if os.path.exists(FIREREDASR_PATH):
        sys.path.insert(0, FIREREDASR_PATH)
    
    MODEL_DIR = os.path.join(PROJECT_ROOT, "modules", "FireRedASR", "pretrained_models", "FireRedASR-AED-L")
    
    from fireredasr.models.fireredasr import FireRedAsr
    
    print("\n加载 FireRedASR-AED-L 模型...")
    start = time.time()
    model = FireRedAsr.from_pretrained("aed", MODEL_DIR)
    load_time = time.time() - start
    print(f"模型加载耗时: {load_time:.2f}s")
    
    # 创建临时 WAV 文件用于推理
    temp_wav = os.path.join(PROJECT_ROOT, "scripts", "_temp_firered_benchmark.wav")
    
    def transcribe(audio):
        # 保存临时 WAV
        with wave.open(temp_wav, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(audio.tobytes())
        
        # 推理
        results = model.transcribe(
            ["benchmark"],
            [temp_wav],
            {
                "use_gpu": 1,
                "beam_size": 1,
                "nbest": 1,
                "decode_max_len": 0,
                "softmax_smoothing": 1.0,
                "aed_length_penalty": 0.0,
                "eos_penalty": 1.0
            }
        )
        
        text = ""
        if results and len(results) > 0:
            text = results[0].get("text", "") if isinstance(results[0], dict) else str(results[0])
        
        return text, {}
    
    return transcribe, temp_wav


def main():
    print("=" * 60)
    print("STT 对比基准测试")
    print("FireRedASR-AED-L vs FunASR Paraformer-Large")
    print("=" * 60)
    
    # 检查测试音频
    if not os.path.exists(TEST_WAV_PATH):
        print(f"\n[ERROR] 测试音频不存在: {TEST_WAV_PATH}")
        return
    
    # 加载音频
    print(f"\n加载测试音频: {TEST_WAV_PATH}")
    audio, sample_rate, duration = load_audio(TEST_WAV_PATH)
    print(f"  采样率: {sample_rate} Hz")
    print(f"  时长: {duration:.2f}s")
    print(f"  样本数: {len(audio)}")
    
    results = []
    
    # ============================================
    # 测试 1: FunASR Paraformer-Large
    # ============================================
    try:
        paraformer_transcribe = test_paraformer()
        result = run_benchmark(
            "FunASR Paraformer-Large",
            paraformer_transcribe,
            audio,
            num_warmup=2,
            num_iterations=5
        )
        result["rtf"] = result["avg_time"] / duration
        results.append(result)
    except Exception as e:
        print(f"\n[ERROR] Paraformer 测试失败: {e}")
    
    # ============================================
    # 测试 2: FireRedASR-AED-L
    # ============================================
    try:
        firered_transcribe, temp_wav = test_fireredasr()
        result = run_benchmark(
            "FireRedASR-AED-L (FP16 + torch.compile)",
            firered_transcribe,
            audio,
            num_warmup=3,  # FireRedASR 需要更多 warmup 让 torch.compile 编译
            num_iterations=5
        )
        result["rtf"] = result["avg_time"] / duration
        results.append(result)
        
        # 清理临时文件
        if os.path.exists(temp_wav):
            os.remove(temp_wav)
    except Exception as e:
        print(f"\n[ERROR] FireRedASR 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # ============================================
    # 对比结果
    # ============================================
    if len(results) >= 2:
        print("\n" + "=" * 60)
        print("对比结果")
        print("=" * 60)
        print(f"{'模型':<45} {'平均时间':>10} {'RTF':>10}")
        print("-" * 60)
        
        for r in results:
            print(f"{r['name']:<45} {r['avg_time']:.3f}s     {r['rtf']:.4f}")
        
        # 计算速度差异
        if len(results) == 2:
            ratio = results[0]["avg_time"] / results[1]["avg_time"]
            if ratio > 1:
                faster = results[1]["name"]
                slower = results[0]["name"]
                speedup = ratio
            else:
                faster = results[0]["name"]
                slower = results[1]["name"]
                speedup = 1 / ratio
            
            print("-" * 60)
            print(f"\n{faster} 比 {slower} 快 {speedup:.2f}x")
        
        print("\n识别结果对比:")
        print("-" * 60)
        for r in results:
            print(f"\n[{r['name']}]:")
            print(f"  {r['text']}")
    
    print("\n测试完成!")


if __name__ == "__main__":
    main()
