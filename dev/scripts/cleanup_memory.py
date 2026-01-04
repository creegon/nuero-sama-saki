# -*- coding: utf-8 -*-
"""
显存/内存清理工具
定期清理 GPU 显存碎片和 Python 内存，避免 RTF 越跑越低

用法:
    # 作为模块导入，定期调用
    from scripts.cleanup_memory import cleanup_memory, cleanup_cuda
    
    # 或者作为独立脚本运行
    python scripts/cleanup_memory.py
"""

import gc
import sys
from loguru import logger

def cleanup_memory():
    """
    清理 Python 内存
    - 强制垃圾回收
    - 清理循环引用
    """
    # 多次 GC 以确保清理干净
    gc.collect()
    gc.collect()
    gc.collect()
    
    logger.debug("🧹 Python 内存已清理")


def cleanup_cuda(aggressive: bool = False):
    """
    清理 CUDA 显存
    - 清空缓存
    - 重置峰值统计
    - aggressive模式：多轮清理+碎片整理
    """
    try:
        import torch
        if torch.cuda.is_available():
            if aggressive:
                # 激进模式：多轮清理
                for i in range(3):
                    torch.cuda.synchronize()
                    torch.cuda.empty_cache()
                    if i < 2:
                        import time
                        time.sleep(0.1)

                logger.info(f"🎮 CUDA 激进清理完成 (3轮)")
            else:
                # 同步 CUDA 操作
                torch.cuda.synchronize()
                # 清空缓存
                torch.cuda.empty_cache()

            # 重置峰值统计
            torch.cuda.reset_peak_memory_stats()

            # 获取当前显存使用
            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3

            logger.debug(f"🎮 CUDA 显存已清理 (已分配: {allocated:.2f}GB, 已保留: {reserved:.2f}GB)")
            return True
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"CUDA 清理失败: {e}")
    return False


def cleanup_temp_files():
    """清理临时文件（TTS输出等）"""
    import shutil
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import config

    try:
        # 清理TTS输出目录
        tts_dir = config.TTS_OUTPUT_DIR
        if os.path.exists(tts_dir):
            file_count = 0
            for filename in os.listdir(tts_dir):
                file_path = os.path.join(tts_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                        file_count += 1
                except Exception as e:
                    logger.debug(f"删除文件失败: {file_path}, {e}")

            if file_count > 0:
                logger.info(f"🗑️ 清理临时TTS文件: {file_count}个")

        # 清理debug音频（可选，保留最近的）
        debug_dir = os.path.join(config.BASE_DIR, "debug_audio")
        if os.path.exists(debug_dir):
            files = [(os.path.join(debug_dir, f), os.path.getmtime(os.path.join(debug_dir, f)))
                     for f in os.listdir(debug_dir) if os.path.isfile(os.path.join(debug_dir, f))]
            files.sort(key=lambda x: x[1], reverse=True)

            # 保留最近50个，删除其他
            if len(files) > 50:
                for file_path, _ in files[50:]:
                    try:
                        os.unlink(file_path)
                    except Exception:
                        pass
                logger.debug(f"🗑️ 清理旧debug音频: {len(files) - 50}个")

    except Exception as e:
        logger.warning(f"临时文件清理失败: {e}")


def cleanup_all(aggressive: bool = False):
    """
    清理所有内存 (Python + CUDA + 临时文件)

    Args:
        aggressive: 是否使用激进模式（更彻底但更慢）
    """
    cleanup_memory()
    cleanup_cuda(aggressive=aggressive)
    if aggressive:
        cleanup_temp_files()


def get_memory_stats() -> dict:
    """获取内存统计信息"""
    stats = {
        "python": {},
        "cuda": {}
    }
    
    # Python 内存
    import psutil
    process = psutil.Process()
    mem_info = process.memory_info()
    stats["python"]["rss_mb"] = mem_info.rss / 1024**2
    stats["python"]["vms_mb"] = mem_info.vms / 1024**2
    
    # CUDA 内存
    try:
        import torch
        if torch.cuda.is_available():
            stats["cuda"]["allocated_gb"] = torch.cuda.memory_allocated() / 1024**3
            stats["cuda"]["reserved_gb"] = torch.cuda.memory_reserved() / 1024**3
            stats["cuda"]["max_allocated_gb"] = torch.cuda.max_memory_allocated() / 1024**3
    except ImportError:
        pass
    
    return stats


def start_periodic_cleanup(interval_seconds: int = 300, aggressive: bool = False):
    """
    启动定期清理

    Args:
        interval_seconds: 清理间隔 (秒)，默认 5 分钟
        aggressive: 是否使用激进清理模式
    """
    import threading
    import time

    def cleanup_loop():
        cleanup_count = 0
        while True:
            time.sleep(interval_seconds)
            cleanup_count += 1

            # 每3次做一次激进清理
            use_aggressive = aggressive or (cleanup_count % 3 == 0)
            cleanup_all(aggressive=use_aggressive)

            mode = "激进" if use_aggressive else "常规"
            logger.info(f"⏰ 定期内存清理完成 ({mode}模式, 间隔: {interval_seconds}s)")

    thread = threading.Thread(target=cleanup_loop, daemon=True)
    thread.start()
    logger.info(f"🔄 已启动定期内存清理 (间隔: {interval_seconds}s)")
    return thread


if __name__ == "__main__":
    # 测试
    print("🧹 显存/内存清理工具\n")
    
    # 显示清理前状态
    print("清理前:")
    stats = get_memory_stats()
    print(f"  Python: RSS={stats['python']['rss_mb']:.1f}MB")
    if stats["cuda"]:
        print(f"  CUDA: {stats['cuda']['allocated_gb']:.2f}GB / {stats['cuda']['reserved_gb']:.2f}GB")
    
    # 执行清理
    print("\n执行清理...")
    cleanup_all()
    
    # 显示清理后状态
    print("\n清理后:")
    stats = get_memory_stats()
    print(f"  Python: RSS={stats['python']['rss_mb']:.1f}MB")
    if stats["cuda"]:
        print(f"  CUDA: {stats['cuda']['allocated_gb']:.2f}GB / {stats['cuda']['reserved_gb']:.2f}GB")
    
    print("\n✅ 清理完成!")
