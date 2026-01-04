# -*- coding: utf-8 -*-
"""
性能诊断工具

快速检查系统性能状态，提供诊断建议
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def diagnose():
    """执行性能诊断"""
    print("=" * 60)
    print("🏥 Neuro AI 桌宠 - 性能诊断工具")
    print("=" * 60)
    print()

    issues = []
    warnings = []

    # 1. 检查GPU显存（使用nvidia-smi，更准确）
    print("📊 [1/5] 检查GPU显存...")
    try:
        import subprocess
        import re

        # 使用nvidia-smi获取真实显存使用
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            output = result.stdout.strip()
            match = re.search(r'(\d+),\s*(\d+)', output)
            if match:
                used_mb = int(match.group(1))
                total_mb = int(match.group(2))

                used_gb = used_mb / 1024
                total_gb = total_mb / 1024
                usage_pct = (used_mb / total_mb) * 100

                print(f"   已使用: {used_gb:.2f}GB ({used_mb}MB)")
                print(f"   总容量: {total_gb:.2f}GB ({total_mb}MB)")
                print(f"   使用率: {usage_pct:.1f}%")

                if usage_pct > 85:
                    issues.append(f"显存使用率过高（{usage_pct:.1f}%），可能导致OOM")
                elif usage_pct > 70:
                    warnings.append(f"显存使用率较高（{usage_pct:.1f}%），建议重启程序")
                elif usage_pct > 50:
                    warnings.append(f"显存使用中等（{usage_pct:.1f}%），正常范围")
            else:
                warnings.append("无法解析nvidia-smi输出")
        else:
            # 回退到torch方法（仅当nvidia-smi不可用）
            import torch
            if torch.cuda.is_available():
                total = torch.cuda.get_device_properties(0).total_memory / 1024**3
                print(f"   警告: nvidia-smi不可用，使用torch检查（仅当前进程）")
                print(f"   显卡总量: {total:.2f}GB")
                warnings.append("nvidia-smi不可用，显存检查可能不准确")
            else:
                issues.append("未检测到CUDA，无法使用GPU加速")

    except subprocess.TimeoutExpired:
        warnings.append("nvidia-smi超时")
    except FileNotFoundError:
        warnings.append("nvidia-smi未找到（可能未安装NVIDIA驱动）")
    except Exception as e:
        warnings.append(f"GPU检查失败: {e}")

    print()

    # 2. 检查Python内存
    print("📊 [2/5] 检查Python内存...")
    try:
        import psutil
        process = psutil.Process()
        mem = process.memory_info()
        rss_gb = mem.rss / 1024**3
        vms_gb = mem.vms / 1024**3

        print(f"   RSS: {rss_gb:.2f}GB")
        print(f"   VMS: {vms_gb:.2f}GB")

        if rss_gb > 8:
            issues.append(f"Python内存使用过高（{rss_gb:.1f}GB），建议重启程序")
        elif rss_gb > 4:
            warnings.append(f"Python内存使用较高（{rss_gb:.1f}GB）")
    except Exception as e:
        warnings.append(f"内存检查失败: {e}")

    print()

    # 3. 检查临时文件
    print("📊 [3/5] 检查临时文件...")
    try:
        import config
        tts_dir = config.TTS_OUTPUT_DIR
        debug_dir = os.path.join(config.BASE_DIR, "debug_audio")

        tts_count = 0
        debug_count = 0

        if os.path.exists(tts_dir):
            tts_count = len([f for f in os.listdir(tts_dir) if os.path.isfile(os.path.join(tts_dir, f))])

        if os.path.exists(debug_dir):
            debug_count = len([f for f in os.listdir(debug_dir) if os.path.isfile(os.path.join(debug_dir, f))])

        print(f"   TTS临时文件: {tts_count}个")
        print(f"   Debug音频: {debug_count}个")

        if tts_count > 100:
            warnings.append(f"TTS临时文件过多（{tts_count}个），建议清理")
        if debug_count > 200:
            warnings.append(f"Debug音频过多（{debug_count}个），建议清理")

    except Exception as e:
        warnings.append(f"文件检查失败: {e}")

    print()

    # 4. 检查模型文件
    print("📊 [4/5] 检查模型文件...")
    try:
        import config

        # 检查合并权重
        merged_path = os.path.join(config.BASE_DIR, "checkpoints", "sakiko_merged", "tts_model_merged.pt")
        if os.path.exists(merged_path):
            print(f"   ✓ 合并权重存在 (推荐)")
        else:
            warnings.append("未找到合并权重，正在使用LoRA模式（性能较差）")
            print(f"   ✗ 合并权重不存在，使用LoRA模式")

        # 检查LoRA checkpoint
        lora_path = config.VOXCPM_LORA_PATH
        if os.path.exists(lora_path):
            print(f"   ✓ LoRA checkpoint存在")
        else:
            issues.append(f"LoRA checkpoint不存在: {lora_path}")

    except Exception as e:
        warnings.append(f"模型文件检查失败: {e}")

    print()

    # 5. 提供建议
    print("📊 [5/5] 诊断建议...")
    print()

    if not issues and not warnings:
        print("   ✅ 系统状态良好！")
    else:
        if issues:
            print(f"   🚨 发现 {len(issues)} 个严重问题:")
            for issue in issues:
                print(f"      - {issue}")
            print()

        if warnings:
            print(f"   ⚠️ 发现 {len(warnings)} 个警告:")
            for warning in warnings:
                print(f"      - {warning}")
            print()

    # 操作建议
    print("💡 操作建议:")
    print()

    if issues or warnings:
        print("   1. 立即执行清理命令:")
        print("      python scripts/cleanup_memory.py")
        print()
        print("   2. 如果问题持续，重启应用:")
        print("      关闭程序 → 等待10秒 → 重新启动")
        print()
        print("   3. 如果重启无效，重启计算机")
        print()

    print("   4. 性能优化建议:")
    print("      - 减少主动对话频率（修改config.py中的PROACTIVE_CHAT_INTERVAL）")
    print("      - 禁用情感参考音频（VOXCPM_USE_EMOTION_REF = False）")
    print("      - 降低Live2D帧率（LIVE2D_FPS = 30）")
    print()

    print("=" * 60)
    print()

    return len(issues) == 0


if __name__ == "__main__":
    diagnose()
