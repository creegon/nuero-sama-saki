# -*- coding: utf-8 -*-
"""
Audio Queue Module
并行 TTS 生成 + 按序播放队列 + Live2D 口型同步
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass, field
from loguru import logger
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


@dataclass
class TTSTask:
    """TTS 任务"""
    id: int
    text: str
    emotion: Optional[str] = None
    audio_path: Optional[str] = None
    audio_data: Optional[bytes] = None
    is_ready: bool = False
    submit_time: float = field(default_factory=time.time)
    complete_time: Optional[float] = None


class AudioQueue:
    """
    音频队列管理器
    - 并行生成 TTS
    - 按序播放音频
    - Live2D 口型同步
    """
    
    def __init__(self, max_workers: int = 1):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=1)
        
        self._tasks: Dict[int, TTSTask] = {}
        self._task_counter = 0
        self._next_play_id = 1
        self._is_running = False
        self._interrupted = False  # 🔥 打断标志
        
        # 回调
        self.on_audio_ready: Optional[Callable[[TTSTask], None]] = None
        self.on_audio_played: Optional[Callable[[TTSTask], None]] = None
        
        # Live2D 口型同步
        self._lip_sync_analyzer = None
        self._live2d_controller = None
        self._lip_sync_enabled = True
        
    def start(self):
        """启动队列"""
        self._is_running = True
        self._task_counter = 0
        self._next_play_id = 1
        self._tasks.clear()
        
        # 初始化口型分析器
        self._init_lip_sync()
        
        logger.info("音频队列已启动")
    
    def _init_lip_sync(self):
        """初始化口型同步"""
        if not self._lip_sync_enabled:
            return
        
        try:
            from live2d_local.lipsync import LipSyncAnalyzer
            from live2d_local.controller import get_live2d_controller
            
            self._lip_sync_analyzer = LipSyncAnalyzer(sample_rate=44100)
            self._live2d_controller = get_live2d_controller()
            
            if self._live2d_controller:
                logger.info("🎭 Live2D 口型同步已启用")
            else:
                logger.debug("Live2D 控制器未初始化，口型同步将在控制器就绪后启用")
                
        except ImportError as e:
            logger.warning(f"Live2D 模块不可用，口型同步已禁用: {e}")
            self._lip_sync_enabled = False
    
    def set_live2d_controller(self, controller):
        """设置 Live2D 控制器"""
        self._live2d_controller = controller
        if controller:
            logger.info("🎭 Live2D 控制器已连接")
    
    def stop(self):
        """停止队列"""
        self._is_running = False
        self._tasks.clear()
        
        # 停止口型
        if self._live2d_controller:
            self._live2d_controller.stop_speaking()
        
        logger.info("音频队列已停止")
    
    def clear(self):
        """清空队列（用于打断）"""
        import sounddevice as sd
        
        self._interrupted = True  # 设置打断标志
        self._tasks.clear()
        self._next_play_id = self._task_counter + 1
        
        # 🔥 立即停止音频输出
        try:
            sd.stop()
        except:
            pass
        
        if self._live2d_controller:
            self._live2d_controller.stop_speaking()
        
        logger.info("🔇 音频队列已清空（打断）")
    
    def reset_interrupt(self):
        """重置打断标志（开始新一轮对话时调用）"""
        self._interrupted = False
    
    @property
    def is_interrupted(self) -> bool:
        """是否被打断"""
        return self._interrupted
    
    def submit(self, text: str, emotion: Optional[str] = None) -> int:
        """
        提交 TTS 任务
        
        Args:
            text: 要合成的文本
            emotion: 情感标签
            
        Returns:
            任务 ID，如果被打断返回 -1
        """
        # 🔥 如果已被打断，拒绝提交新任务
        if self._interrupted:
            logger.debug(f"TTS 任务被拒绝（打断中）: '{text[:20]}...'")
            return -1
        
        self._task_counter += 1
        task_id = self._task_counter
        
        task = TTSTask(
            id=task_id,
            text=text,
            emotion=emotion
        )
        self._tasks[task_id] = task
        
        # 提交到线程池
        future = self.executor.submit(self._synthesize_task, task)
        future.add_done_callback(lambda f: self._on_task_done(task_id))
        
        logger.debug(f"TTS 任务已提交: #{task_id} '{text[:20]}...'")
        return task_id
    
    def _synthesize_task(self, task: TTSTask):
        """执行 TTS 流式合成并直接播放（在线程池中运行）"""
        import queue
        import threading
        import sounddevice as sd
        import numpy as np
        
        from tts.voxcpm_engine import get_voxcpm_engine
        engine = get_voxcpm_engine()
        
        BUFFER_SIZE = 3
        RTF_WARNING_THRESHOLD = 0.95
        
        # 口型分析设置
        LIP_SYNC_CHUNK_SIZE = 1024  # 每 1024 样本分析一次口型
        
        audio_queue = queue.Queue()
        sample_rate = engine.sample_rate
        
        # 获取最新的 Live2D 控制器
        if self._lip_sync_enabled and self._live2d_controller is None:
            try:
                from live2d_local.controller import get_live2d_controller
                self._live2d_controller = get_live2d_controller()
            except:
                pass
        
        def fetch_stream():
            """后台生成音频流"""
            gen_start = time.time()
            total_samples = 0
            chunk_count = 0
            
            try:
                for chunk in engine.synthesize_streaming(task.text, emotion=task.emotion):
                    # 🔥 检查打断标志 - 立即停止生成
                    if self._interrupted:
                        logger.info(f"🔇 TTS 生成被打断 (任务 #{task.id})")
                        audio_queue.put(None)  # 发送结束信号
                        return
                    
                    total_samples += len(chunk)
                    chunk_count += 1
                    audio_queue.put(chunk)
                    
                    elapsed = time.time() - gen_start
                    audio_duration = total_samples / sample_rate
                    if audio_duration > 0:
                        rtf = elapsed / audio_duration
                        if rtf > RTF_WARNING_THRESHOLD and chunk_count % 5 == 0:
                            logger.warning(f"⚠️ RTF={rtf:.2f} > {RTF_WARNING_THRESHOLD} (Chunk #{chunk_count})")
                
                audio_queue.put(None)
                
                # 🔥 如果已被打断，不记录完成日志
                if self._interrupted:
                    return
                
                total_time = time.time() - gen_start
                audio_duration = total_samples / sample_rate
                final_rtf = total_time / audio_duration if audio_duration > 0 else 0
                logger.debug(f"TTS 生成完成: #{task.id} RTF={final_rtf:.2f} ({chunk_count} chunks)")
                
                engine.record_rtf(final_rtf)
                
            except Exception as e:
                logger.error(f"TTS 流式生成异常: {e}")
                audio_queue.put(None)
        
        try:
            fetch_thread = threading.Thread(target=fetch_stream)
            fetch_thread.start()
            
            buffer = []
            all_audio = []
            
            while len(buffer) < BUFFER_SIZE:
                item = audio_queue.get()
                if item is None:
                    break
                buffer.append(item)
                all_audio.append(item)
            
            if not buffer:
                logger.warning(f"TTS 任务 #{task.id} 没有生成音频")
                task.is_ready = True
                return
            
            # 通知开始说话 + 设置表情
            if self._live2d_controller:
                self._live2d_controller.start_speaking()
                # 动态表情切换：播放每段时设置对应表情
                if task.emotion:
                    self._live2d_controller.set_expression(task.emotion)
            
            # 流式播放 + 口型同步
            lip_buffer = np.array([], dtype=np.float32)
            
            with sd.OutputStream(samplerate=sample_rate, channels=1, dtype='float32') as stream:
                for chunk in buffer:
                    # 🔥 检查打断标志
                    if self._interrupted:
                        logger.info("🔇 TTS 播放被打断")
                        break
                    
                    # 口型同步
                    if self._lip_sync_analyzer and self._live2d_controller:
                        lip_buffer = np.concatenate([lip_buffer, chunk.flatten()])
                        while len(lip_buffer) >= LIP_SYNC_CHUNK_SIZE:
                            lip_chunk = lip_buffer[:LIP_SYNC_CHUNK_SIZE]
                            lip_buffer = lip_buffer[LIP_SYNC_CHUNK_SIZE:]
                            
                            vowel, mouth_open, mouth_form = self._lip_sync_analyzer.analyze(lip_chunk)
                            self._live2d_controller.set_lipsync(mouth_open, mouth_form)
                    
                    if chunk.ndim == 1:
                        chunk = chunk.reshape(-1, 1)
                    stream.write(chunk)
                
                while not self._interrupted:
                    try:
                        item = audio_queue.get(timeout=0.1)  # 添加超时以便检查打断
                    except queue.Empty:
                        continue  # 超时后继续检查打断标志
                    
                    if item is None:
                        break
                    all_audio.append(item)
                    
                    # 🔥 检查打断标志
                    if self._interrupted:
                        logger.info("🔇 TTS 播放被打断")
                        break
                    
                    # 口型同步
                    if self._lip_sync_analyzer and self._live2d_controller:
                        lip_buffer = np.concatenate([lip_buffer, item.flatten()])
                        while len(lip_buffer) >= LIP_SYNC_CHUNK_SIZE:
                            lip_chunk = lip_buffer[:LIP_SYNC_CHUNK_SIZE]
                            lip_buffer = lip_buffer[LIP_SYNC_CHUNK_SIZE:]
                            
                            vowel, mouth_open, mouth_form = self._lip_sync_analyzer.analyze(lip_chunk)
                            self._live2d_controller.set_lipsync(mouth_open, mouth_form)
                    
                    if item.ndim == 1:
                        item = item.reshape(-1, 1)
                    stream.write(item)
            
            fetch_thread.join()
            
            # 停止说话
            if self._live2d_controller:
                self._live2d_controller.stop_speaking()
            
            # 重置口型分析器
            if self._lip_sync_analyzer:
                self._lip_sync_analyzer.reset()
            
            # Debug: 保存音频到文件
            debug_save = getattr(config, 'DEBUG_SAVE_AUDIO', False)
            if debug_save and all_audio:
                import scipy.io.wavfile as wav
                from datetime import datetime
                
                full_audio = np.concatenate(all_audio)
                
                debug_dir = os.path.join(config.BASE_DIR, "debug_audio")
                os.makedirs(debug_dir, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"tts_{task.id}_{timestamp}.wav"
                filepath = os.path.join(debug_dir, filename)
                
                wav.write(filepath, sample_rate, (full_audio * 32767).astype(np.int16))
                logger.info(f"🔊 Debug: 音频已保存 -> {filename}")
            
            task.audio_data = b'streamed'
            task.is_ready = True
            task.complete_time = time.time()
            
        except Exception as e:
            logger.error(f"TTS 任务执行异常: {e}")
            import traceback
            traceback.print_exc()
            task.is_ready = True
            
            # 确保停止说话状态
            if self._live2d_controller:
                self._live2d_controller.stop_speaking()

    
    def _on_task_done(self, task_id: int):
        """任务完成回调"""
        if task_id not in self._tasks:
            return
            
        task = self._tasks[task_id]
        synth_time = task.complete_time - task.submit_time if task.complete_time else 0
        
        if task.audio_data or task.audio_path:
            logger.debug(f"TTS 任务完成: #{task_id} (耗时: {synth_time:.2f}s)")
            if self.on_audio_ready:
                self.on_audio_ready(task)
        else:
            logger.warning(f"TTS 任务失败: #{task_id}")
    
    def get_next_ready(self) -> Optional[TTSTask]:
        """获取下一个可播放的音频"""
        if self._next_play_id not in self._tasks:
            return None
            
        task = self._tasks[self._next_play_id]
        if task.is_ready:
            self._next_play_id += 1
            return task
        return None
    
    def get_all_ready(self) -> List[TTSTask]:
        """获取所有按顺序准备好的音频"""
        ready_tasks = []
        while True:
            task = self.get_next_ready()
            if task:
                ready_tasks.append(task)
            else:
                break
        return ready_tasks
    
    def has_pending(self) -> bool:
        """是否有待处理的任务"""
        for task in self._tasks.values():
            if not task.is_ready:
                return True
            if task.id >= self._next_play_id:
                return True
        return False
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        total = len(self._tasks)
        ready = sum(1 for t in self._tasks.values() if t.is_ready)
        pending = total - ready
        return {
            "total": total,
            "ready": ready,
            "pending": pending,
            "next_play_id": self._next_play_id,
            "lip_sync_enabled": self._lip_sync_enabled and self._live2d_controller is not None,
        }


# 全局单例
_audio_queue: Optional[AudioQueue] = None


def get_audio_queue() -> AudioQueue:
    """获取全局 AudioQueue 实例"""
    global _audio_queue
    if _audio_queue is None:
        _audio_queue = AudioQueue()
    return _audio_queue


if __name__ == "__main__":
    # 测试
    queue = AudioQueue()
    queue.start()
    
    sentences = [
        ("你好呀！", "happy"),
        ("今天天气真不错。", "neutral"),
        ("一起出去玩吧！", "excited"),
    ]
    
    for text, emotion in sentences:
        queue.submit(text, emotion)
    
    print("等待任务完成...")
    import time
    while queue.has_pending():
        time.sleep(0.5)
        stats = queue.get_stats()
        print(f"  进度: {stats['ready']}/{stats['total']} (口型同步: {stats['lip_sync_enabled']})")
    
    print("\n所有任务完成!")
    ready = queue.get_all_ready()
    for task in ready:
        print(f"  #{task.id}: {task.audio_path}")
    
    queue.stop()
