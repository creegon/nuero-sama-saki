# -*- coding: utf-8 -*-
"""
健康监控系统 - 实时监控性能并自动恢复
"""

import asyncio
import time
from typing import Optional, Callable
from loguru import logger
from collections import deque

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class HealthMonitor:
    """
    健康监控器

    监控系统性能指标，自动触发清理和恢复操作
    """

    def __init__(self):
        self._enabled = True
        self._monitor_task = None

        # 性能指标
        self._rtf_history = deque(maxlen=20)  # 最近20次RTF
        self._generation_time_history = deque(maxlen=20)  # 最近20次生成时间
        self._last_cleanup_time = time.time()
        self._degradation_count = 0  # 性能退化计数

        # 回调
        self._on_cleanup_needed: Optional[Callable] = None
        self._on_critical_degradation: Optional[Callable] = None

        # 阈值配置
        self.RTF_WARNING_THRESHOLD = 1.2  # RTF超过此值警告
        self.RTF_CRITICAL_THRESHOLD = 2.0  # RTF超过此值严重
        self.DEGRADATION_TRIGGER_COUNT = 3  # 连续N次退化触发清理
        self.MIN_CLEANUP_INTERVAL = 60  # 最小清理间隔（秒）
        self.AUTO_CLEANUP_INTERVAL = 180  # 自动清理间隔（秒）

    def start(self):
        """启动监控任务"""
        if self._monitor_task is None:
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            logger.info("🏥 健康监控器已启动")

    def stop(self):
        """停止监控任务"""
        self._enabled = False
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None
        logger.info("🏥 健康监控器已停止")

    def set_cleanup_callback(self, callback: Callable):
        """设置清理回调"""
        self._on_cleanup_needed = callback

    def set_critical_callback(self, callback: Callable):
        """设置严重退化回调（如重载模型）"""
        self._on_critical_degradation = callback

    def record_rtf(self, rtf: float):
        """记录RTF"""
        self._rtf_history.append(rtf)
        self._check_performance()

    def record_generation_time(self, duration: float, text_length: int):
        """记录生成时间"""
        self._generation_time_history.append((duration, text_length))

    def _check_performance(self):
        """检查性能指标"""
        if len(self._rtf_history) < 3:
            return

        recent_rtf = list(self._rtf_history)[-3:]  # 最近3次
        avg_rtf = sum(recent_rtf) / len(recent_rtf)

        # 检查RTF异常
        if avg_rtf > self.RTF_CRITICAL_THRESHOLD:
            self._degradation_count += 1
            logger.warning(f"⚠️ 性能严重退化！平均RTF: {avg_rtf:.2f} (阈值: {self.RTF_CRITICAL_THRESHOLD})")

            if self._degradation_count >= self.DEGRADATION_TRIGGER_COUNT:
                logger.error(f"🚨 连续{self._degradation_count}次性能退化，触发紧急恢复！")
                self._trigger_critical_recovery()
                self._degradation_count = 0

        elif avg_rtf > self.RTF_WARNING_THRESHOLD:
            logger.warning(f"⚠️ RTF偏高: {avg_rtf:.2f} (警告阈值: {self.RTF_WARNING_THRESHOLD})")
            self._trigger_cleanup()

        else:
            # 性能正常，重置计数
            if self._degradation_count > 0:
                self._degradation_count = max(0, self._degradation_count - 1)

    def _trigger_cleanup(self):
        """触发常规清理"""
        now = time.time()
        if now - self._last_cleanup_time < self.MIN_CLEANUP_INTERVAL:
            logger.debug("⏳ 清理间隔未到，跳过")
            return

        logger.info("🧹 触发性能清理...")
        self._last_cleanup_time = now

        if self._on_cleanup_needed:
            self._on_cleanup_needed()
        else:
            # 默认清理
            from scripts.cleanup_memory import cleanup_all
            cleanup_all(aggressive=False)

    def _trigger_critical_recovery(self):
        """触发严重恢复（重载模型）"""
        logger.warning("🚨 触发严重恢复程序...")

        # 激进清理
        from scripts.cleanup_memory import cleanup_all
        cleanup_all(aggressive=True)

        # 调用严重退化回调（如重载模型）
        if self._on_critical_degradation:
            self._on_critical_degradation()

    async def _monitor_loop(self):
        """监控循环"""
        logger.info("🏥 健康监控循环已启动")

        while self._enabled:
            try:
                await asyncio.sleep(self.AUTO_CLEANUP_INTERVAL)

                # 定期自动清理
                if self._enabled:
                    logger.info(f"⏰ 定期健康检查（间隔: {self.AUTO_CLEANUP_INTERVAL}s）")
                    self._trigger_cleanup()

                    # 显示统计信息
                    self._log_stats()

            except asyncio.CancelledError:
                logger.info("🏥 健康监控循环被取消")
                break
            except Exception as e:
                logger.error(f"🏥 健康监控异常: {e}")
                await asyncio.sleep(10)

    def _log_stats(self):
        """记录统计信息"""
        if not self._rtf_history:
            return

        avg_rtf = sum(self._rtf_history) / len(self._rtf_history)
        max_rtf = max(self._rtf_history)
        min_rtf = min(self._rtf_history)

        logger.info(f"📊 性能统计: RTF平均={avg_rtf:.2f}, 最大={max_rtf:.2f}, 最小={min_rtf:.2f}")

        # GPU显存统计
        try:
            from scripts.cleanup_memory import get_memory_stats
            stats = get_memory_stats()
            if stats["cuda"]:
                allocated = stats["cuda"].get("allocated_gb", 0)
                reserved = stats["cuda"].get("reserved_gb", 0)
                logger.info(f"📊 显存: {allocated:.2f}GB / {reserved:.2f}GB (已分配/已保留)")
        except Exception:
            pass

    def get_health_status(self) -> dict:
        """获取健康状态"""
        if not self._rtf_history:
            return {"status": "unknown", "rtf_avg": 0}

        avg_rtf = sum(self._rtf_history) / len(self._rtf_history)

        if avg_rtf > self.RTF_CRITICAL_THRESHOLD:
            status = "critical"
        elif avg_rtf > self.RTF_WARNING_THRESHOLD:
            status = "warning"
        else:
            status = "healthy"

        return {
            "status": status,
            "rtf_avg": avg_rtf,
            "rtf_max": max(self._rtf_history),
            "degradation_count": self._degradation_count
        }


# 全局单例
_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """获取全局健康监控器实例"""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor()
    return _health_monitor
