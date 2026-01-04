# -*- coding: utf-8 -*-
"""
强制清理脚本 - 当自动清理无效时使用

这个脚本会执行最激进的清理操作：
1. 强制Python垃圾回收（多轮）
2. 清理所有CUDA缓存（多轮）
3. 重置CUDA上下文（如果可能）
4. 清理所有临时文件
"""

import sys
import os
import gc
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def force_cleanup():
    """执行最激进的清理"""
    print("=" * 60)
    print("🚨 强制清理 - 最激进模式")
    print("=" * 60)
    print()

    # 1. 多轮Python GC
    print("🧹 [1/4] 强制Python垃圾回收（5轮）...")
    for i in range(5):
        collected = gc.collect()
        print(f"   第{i+1}轮: 回收 {collected} 个对象")
        time.sleep(0.1)
    print()

    # 2. 多轮CUDA清理
    print("🎮 [2/4] 强制CUDA缓存清理（5轮）...")
    try:
        import torch
        if torch.cuda.is_available():
            for i in range(5):
                torch.cuda.synchronize()
                torch.cuda.empty_cache()

                # 获取状态
                allocated = torch.cuda.memory_allocated() / 1024**3
                reserved = torch.cuda.memory_reserved() / 1024**3

                print(f"   第{i+1}轮: 已分配={allocated:.2f}GB, 已保留={reserved:.2f}GB")

                if i < 4:
                    time.sleep(0.2)

            # 重置峰值统计
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.reset_accumulated_memory_stats()

            print(f"   ✓ CUDA清理完成")
        else:
            print("   警告: CUDA不可用")
    except Exception as e:
        print(f"   错误: {e}")
    print()

    # 3. 清理临时文件
    print("🗑️  [3/4] 清理临时文件...")
    try:
        import config

        # TTS输出
        tts_dir = config.TTS_OUTPUT_DIR
        if os.path.exists(tts_dir):
            count = 0
            for filename in os.listdir(tts_dir):
                file_path = os.path.join(tts_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                        count += 1
                except:
                    pass
            print(f"   TTS临时文件: 删除 {count} 个")

        # Debug音频（全部删除）
        debug_dir = os.path.join(config.BASE_DIR, "debug_audio")
        if os.path.exists(debug_dir):
            count = 0
            for filename in os.listdir(debug_dir):
                file_path = os.path.join(debug_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                        count += 1
                except:
                    pass
            print(f"   Debug音频: 删除 {count} 个")

    except Exception as e:
        print(f"   警告: {e}")
    print()

    # 4. 显示最终状态
    print("📊 [4/4] 最终状态...")
    try:
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            import re
            output = result.stdout.strip()
            match = re.search(r'(\d+),\s*(\d+)', output)
            if match:
                used_mb = int(match.group(1))
                total_mb = int(match.group(2))
                used_gb = used_mb / 1024
                total_gb = total_mb / 1024

                print(f"   GPU显存: {used_gb:.2f}GB / {total_gb:.2f}GB ({used_mb}/{total_mb}MB)")
                print(f"   使用率: {(used_mb/total_mb)*100:.1f}%")
    except:
        pass

    try:
        import psutil
        process = psutil.Process()
        mem = process.memory_info()
        print(f"   Python内存: {mem.rss/1024**3:.2f}GB")
    except:
        pass

    print()
    print("=" * 60)
    print("✅ 强制清理完成!")
    print()
    print("建议:")
    print("1. 如果是程序运行中清理，现在可以继续使用")
    print("2. 如果问题仍然存在，请重启程序")
    print("3. 如果重启程序无效，请重启计算机")
    print("=" * 60)
    print()


if __name__ == "__main__":
    force_cleanup()
