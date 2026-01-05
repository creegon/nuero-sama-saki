# -*- coding: utf-8 -*-
"""
内存清理工具
"""

import gc
from loguru import logger


def cleanup_all(aggressive: bool = False):
    """
    执行内存清理
    
    Args:
        aggressive: 是否激进清理（多轮）
    """
    try:
        import torch
        
        gc.collect()
        
        if torch.cuda.is_available():
            if aggressive:
                # 激进模式：多轮清理
                for i in range(3):
                    torch.cuda.synchronize()
                    torch.cuda.empty_cache()
                    gc.collect()
                logger.info("🧹 CUDA 激进清理完成 (3轮)")
            else:
                torch.cuda.empty_cache()
                logger.debug("🧹 CUDA 缓存已清理")
            
            torch.cuda.reset_peak_memory_stats()
        else:
            gc.collect()
            logger.debug("🧹 Python GC 已执行")
            
    except Exception as e:
        logger.warning(f"清理异常: {e}")


def get_memory_stats() -> dict:
    """
    获取内存统计信息
    
    Returns:
        dict: {"cuda": {...}, "ram": {...}}
    """
    stats = {"cuda": None, "ram": None}
    
    try:
        import torch
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated() / (1024**3)
            reserved = torch.cuda.memory_reserved() / (1024**3)
            stats["cuda"] = {
                "allocated_gb": allocated,
                "reserved_gb": reserved
            }
    except Exception:
        pass
    
    try:
        import psutil
        mem = psutil.virtual_memory()
        stats["ram"] = {
            "used_gb": mem.used / (1024**3),
            "total_gb": mem.total / (1024**3),
            "percent": mem.percent
        }
    except Exception:
        pass
    
    return stats


# 定期清理任务
_cleanup_task = None


def start_periodic_cleanup(interval_seconds: int = 300):
    """
    启动定期内存清理任务
    
    Args:
        interval_seconds: 清理间隔（秒），默认 5 分钟
    """
    import asyncio
    import threading
    
    global _cleanup_task
    
    async def _cleanup_loop():
        while True:
            await asyncio.sleep(interval_seconds)
            cleanup_all(aggressive=False)
            logger.debug(f"🧹 定期清理完成 (间隔: {interval_seconds}s)")
    
    def _run_in_thread():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_cleanup_loop())
        except Exception as e:
            logger.debug(f"定期清理线程异常: {e}")
    
    if _cleanup_task is None:
        _cleanup_task = threading.Thread(target=_run_in_thread, daemon=True)
        _cleanup_task.start()
        logger.info(f"🧹 定期内存清理已启动 (间隔: {interval_seconds}s)")
