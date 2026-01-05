# -*- coding: utf-8 -*-
"""
VoxCPM RTF 性能测试脚本
测试不同配置下的 RTF，找到最优参数组合
"""

import os
import sys
import time

# 设置环境变量（在 import torch 之前）
# 测试不同的 CUDA 内存配置
CUDA_ALLOC_CONFIGS = {
    "default": "",
    "max_split_128": "max_split_size_mb:128",
    "expandable": "expandable_segments:True",
}

# 选择要测试的配置
CUDA_CONFIG = "expandable"  # 改这里测试不同配置
if CUDA_ALLOC_CONFIGS[CUDA_CONFIG]:
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = CUDA_ALLOC_CONFIGS[CUDA_CONFIG]
    print(f"✓ CUDA 内存配置: {CUDA_ALLOC_CONFIGS[CUDA_CONFIG]}")

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import numpy as np
from voxcpm.core import VoxCPM

# ============ 测试配置 ============
TEST_TEXT = "你好呀，今天天气真不错，我们出去散散步吧？"  # ~20字
TEST_STEPS_LIST = [15, 20, 25, 30, 35]  # 测试不同 steps
TEST_CFG_LIST = [2.5, 3.0, 3.5]  # 测试不同 CFG
NUM_WARMUP = 1  # 预热次数
NUM_RUNS = 3    # 每组测试次数


def load_model():
    """加载模型（不加载 LoRA，纯测试基础性能）"""
    print("\n📦 加载 VoxCPM 1.5...")
    
    voxcpm = VoxCPM.from_pretrained(
        hf_model_id="openbmb/VoxCPM1.5",
        load_denoiser=False,  # 关闭降噪
        optimize=False,       # 关闭 torch.compile（避免首次编译延迟）
        lora_config=None,
        lora_weights_path=None,
    )
    
    # 打印模型信息
    print(f"✓ 模型加载完成")
    print(f"  - 采样率: {voxcpm.tts_model.sample_rate} Hz")
    print(f"  - 设备: {next(voxcpm.tts_model.parameters()).device}")
    print(f"  - dtype: {next(voxcpm.tts_model.parameters()).dtype}")
    
    return voxcpm


def test_rtf(model, text: str, steps: int, cfg: float, sample_rate: int) -> dict:
    """测试单次生成的 RTF"""
    torch.cuda.synchronize()
    start = time.perf_counter()
    
    # 收集所有 chunks
    chunks = []
    first_chunk_time = None
    
    for i, chunk in enumerate(model.generate_streaming(
        text=text,
        prompt_wav_path=None,
        prompt_text=None,
        cfg_value=cfg,
        inference_timesteps=steps,
        max_len=2048,
    )):
        if i == 0:
            torch.cuda.synchronize()
            first_chunk_time = time.perf_counter() - start
        chunks.append(chunk)
    
    torch.cuda.synchronize()
    total_time = time.perf_counter() - start
    
    # 计算音频时长
    full_wav = np.concatenate(chunks)
    audio_duration = len(full_wav) / sample_rate
    
    rtf = total_time / audio_duration if audio_duration > 0 else 0
    
    return {
        "rtf": rtf,
        "first_chunk_ms": first_chunk_time * 1000 if first_chunk_time else 0,
        "total_time": total_time,
        "audio_duration": audio_duration,
        "num_chunks": len(chunks),
    }


def run_benchmark():
    """运行完整基准测试"""
    print("=" * 60)
    print("VoxCPM RTF 性能基准测试")
    print("=" * 60)
    
    # 打印环境信息
    print(f"\n📊 环境信息:")
    print(f"  - PyTorch: {torch.__version__}")
    print(f"  - CUDA: {torch.version.cuda}")
    print(f"  - GPU: {torch.cuda.get_device_name(0)}")
    print(f"  - CUDA 内存配置: {os.environ.get('PYTORCH_CUDA_ALLOC_CONF', '默认')}")
    
    # 加载模型
    model = load_model()
    sample_rate = model.tts_model.sample_rate
    
    # 预热
    print(f"\n🔥 预热 ({NUM_WARMUP} 次)...")
    for _ in range(NUM_WARMUP):
        test_rtf(model, TEST_TEXT, steps=20, cfg=3.0, sample_rate=sample_rate)
    print("✓ 预热完成")
    
    # 清理 CUDA 缓存
    torch.cuda.empty_cache()
    
    # 运行测试
    print(f"\n📈 开始测试 (每组 {NUM_RUNS} 次)...")
    print(f"测试文本: '{TEST_TEXT}' ({len(TEST_TEXT)} 字)")
    print("-" * 60)
    
    results = []
    
    for steps in TEST_STEPS_LIST:
        for cfg in TEST_CFG_LIST:
            rtfs = []
            first_chunks = []
            
            for run in range(NUM_RUNS):
                result = test_rtf(model, TEST_TEXT, steps, cfg, sample_rate)
                rtfs.append(result["rtf"])
                first_chunks.append(result["first_chunk_ms"])
                
                # 清理缓存
                torch.cuda.empty_cache()
            
            avg_rtf = sum(rtfs) / len(rtfs)
            avg_first_chunk = sum(first_chunks) / len(first_chunks)
            
            status = "✅" if avg_rtf < 1.0 else ("⚠️" if avg_rtf < 1.5 else "❌")
            
            print(f"{status} Steps={steps:2d}, CFG={cfg:.1f} → RTF={avg_rtf:.2f}, 首包={avg_first_chunk:.0f}ms")
            
            results.append({
                "steps": steps,
                "cfg": cfg,
                "avg_rtf": avg_rtf,
                "avg_first_chunk_ms": avg_first_chunk,
            })
    
    # 找到最优组合
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    # 按 RTF 排序
    results.sort(key=lambda x: x["avg_rtf"])
    
    print("\n🏆 RTF 最优 Top 3:")
    for i, r in enumerate(results[:3]):
        print(f"  {i+1}. Steps={r['steps']}, CFG={r['cfg']:.1f} → RTF={r['avg_rtf']:.2f}")
    
    # 实时可用的配置
    realtime = [r for r in results if r["avg_rtf"] < 1.0]
    if realtime:
        print(f"\n✅ 可实时的配置 (RTF < 1.0):")
        for r in realtime:
            print(f"  - Steps={r['steps']}, CFG={r['cfg']:.1f} → RTF={r['avg_rtf']:.2f}")
    else:
        print("\n⚠️ 没有配置能达到实时 (RTF < 1.0)")
        print("建议：考虑安装 triton 或使用 torch.compile 加速")
    
    print("\n✓ 测试完成")


if __name__ == "__main__":
    run_benchmark()
