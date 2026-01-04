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
