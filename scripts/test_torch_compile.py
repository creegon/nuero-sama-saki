# -*- coding: utf-8 -*-
"""
VoxCPM torch.compile 加速测试脚本
隔离测试 torch.compile 对 VoxCPM 的加速效果和稳定性

⚠️ 注意：这是独立测试脚本，不会影响主程序
"""

import os
import sys
import time
import warnings
import io

# 修复 Windows 终端编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import numpy as np

# ============ 测试配置 ============
TEST_TEXT = "你好呀，今天天气真不错，我们出去散散步吧？"
TEST_STEPS = 15  # 使用已知能实时的 steps
TEST_CFG = 3.0
NUM_WARMUP = 2
NUM_RUNS = 3

# torch.compile 配置选项
COMPILE_BACKENDS = {
    "none": None,           # 不使用 compile（基准）
    "inductor": "inductor", # 默认后端，通常最快
    "eager": "eager",       # 不优化，用于对比
}


def load_model_vanilla():
    """加载原版模型（不使用 torch.compile）"""
    from voxcpm.core import VoxCPM
    
    print("\n📦 加载 VoxCPM 1.5 (原版)...")
    
    voxcpm = VoxCPM.from_pretrained(
        hf_model_id="openbmb/VoxCPM1.5",
        load_denoiser=False,
        optimize=False,  # 关闭内置优化
        lora_config=None,
        lora_weights_path=None,
    )
    
    return voxcpm


def apply_torch_compile(model, backend: str):
    """对模型应用 torch.compile"""
    if backend is None:
        return model
    
    print(f"🔧 应用 torch.compile (backend={backend})...")
    
    try:
        # 只编译 tts_model 的 forward 方法
        model.tts_model = torch.compile(
            model.tts_model,
            backend=backend,
            mode="reduce-overhead",  # 减少开销，适合实时推理
            fullgraph=False,  # 允许图断开，提高兼容性
        )
        print(f"✓ torch.compile 已应用 (backend={backend})")
    except Exception as e:
        print(f"❌ torch.compile 失败: {e}")
        return None
    
    return model


def test_rtf(model, text: str, steps: int, cfg: float, sample_rate: int) -> dict:
    """测试单次生成的 RTF"""
    torch.cuda.synchronize()
    start = time.perf_counter()
    
    chunks = []
    first_chunk_time = None
    
    try:
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
    except Exception as e:
        return {"error": str(e)}
    
    torch.cuda.synchronize()
    total_time = time.perf_counter() - start
    
    if not chunks:
        return {"error": "No audio generated"}
    
    full_wav = np.concatenate(chunks)
    audio_duration = len(full_wav) / sample_rate
    rtf = total_time / audio_duration if audio_duration > 0 else 0
    
    return {
        "rtf": rtf,
        "first_chunk_ms": first_chunk_time * 1000 if first_chunk_time else 0,
        "total_time": total_time,
        "audio_duration": audio_duration,
    }


def run_single_backend_test(backend_name: str, backend_value):
    """测试单个后端"""
    print(f"\n{'='*60}")
    print(f"📊 测试后端: {backend_name}")
    print(f"{'='*60}")
    
    # 每次测试都重新加载模型，确保隔离
    model = load_model_vanilla()
    sample_rate = model.tts_model.sample_rate
    
    # 应用 torch.compile（如果需要）
    if backend_value is not None:
        model = apply_torch_compile(model, backend_value)
        if model is None:
            print(f"❌ {backend_name} 后端失败，跳过")
            return None
    
    # 预热
    print(f"\n🔥 预热 ({NUM_WARMUP} 次)...")
    for i in range(NUM_WARMUP):
        result = test_rtf(model, TEST_TEXT, TEST_STEPS, TEST_CFG, sample_rate)
        if "error" in result:
            print(f"⚠️ 预热失败: {result['error']}")
            return None
        print(f"  预热 {i+1}: RTF={result['rtf']:.2f}")
    
    # 清理缓存
    torch.cuda.empty_cache()
    
    # 正式测试
    print(f"\n📈 正式测试 ({NUM_RUNS} 次)...")
    rtfs = []
    first_chunks = []
    
    for run in range(NUM_RUNS):
        result = test_rtf(model, TEST_TEXT, TEST_STEPS, TEST_CFG, sample_rate)
        if "error" in result:
            print(f"❌ 测试失败: {result['error']}")
            return None
        rtfs.append(result["rtf"])
        first_chunks.append(result["first_chunk_ms"])
        print(f"  Run {run+1}: RTF={result['rtf']:.2f}, 首包={result['first_chunk_ms']:.0f}ms")
        torch.cuda.empty_cache()
    
    avg_rtf = sum(rtfs) / len(rtfs)
    avg_first_chunk = sum(first_chunks) / len(first_chunks)
    
    # 清理模型
    del model
    torch.cuda.empty_cache()
    
    return {
        "backend": backend_name,
        "avg_rtf": avg_rtf,
        "avg_first_chunk_ms": avg_first_chunk,
        "rtfs": rtfs,
    }


def run_benchmark():
    """运行完整基准测试"""
    print("=" * 60)
    print("VoxCPM torch.compile 加速测试")
    print("=" * 60)
    
    # 打印环境信息
    print(f"\n📊 环境信息:")
    print(f"  - PyTorch: {torch.__version__}")
    print(f"  - CUDA: {torch.version.cuda}")
    print(f"  - GPU: {torch.cuda.get_device_name(0)}")
    
    # 检查 triton
    try:
        import triton
        print(f"  - Triton: {triton.__version__} ✓")
    except ImportError:
        print(f"  - Triton: ❌ 未安装")
        print("⚠️ 建议安装 triton-windows 以获得最佳 torch.compile 性能")
    
    print(f"\n📝 测试参数:")
    print(f"  - 文本: '{TEST_TEXT}'")
    print(f"  - Steps: {TEST_STEPS}")
    print(f"  - CFG: {TEST_CFG}")
    
    # 测试各后端
    results = []
    
    # 先测试基准（无 compile）
    result = run_single_backend_test("none", None)
    if result:
        results.append(result)
        baseline_rtf = result["avg_rtf"]
    else:
        print("❌ 基准测试失败，无法继续")
        return
    
    # 测试 inductor 后端
    result = run_single_backend_test("inductor", "inductor")
    if result:
        results.append(result)
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    for r in results:
        speedup = (baseline_rtf / r["avg_rtf"] - 1) * 100 if r["avg_rtf"] > 0 else 0
        status = "🚀" if speedup > 5 else ("✅" if r["avg_rtf"] < 1.0 else "⚠️")
        print(f"{status} {r['backend']:10s}: RTF={r['avg_rtf']:.2f}, 首包={r['avg_first_chunk_ms']:.0f}ms, 加速={speedup:+.1f}%")
    
    # 推荐
    print("\n📌 结论:")
    if len(results) >= 2:
        inductor = next((r for r in results if r["backend"] == "inductor"), None)
        if inductor:
            speedup = (baseline_rtf / inductor["avg_rtf"] - 1) * 100
            if speedup > 10:
                print(f"✅ torch.compile (inductor) 有效，加速 {speedup:.1f}%，建议启用")
            elif speedup > 0:
                print(f"⚠️ torch.compile (inductor) 略有提升 ({speedup:.1f}%)，可选择性启用")
            else:
                print(f"❌ torch.compile (inductor) 无效甚至变慢，不建议启用")
    else:
        print("⚠️ 部分测试失败，无法给出完整建议")
    
    print("\n✓ 测试完成")


if __name__ == "__main__":
    # 忽略一些警告
    warnings.filterwarnings("ignore", category=UserWarning)
    
    run_benchmark()
