# -*- coding: utf-8 -*-
"""
FireRedASR-AED 测试脚本

FireRedASR-AED-L (~1.1B 参数) 在中文 benchmark 上达到 ~3.18% CER
超过 FunASR/Paraformer 传统模型

使用前请先:
1. git clone https://github.com/FireRedTeam/FireRedASR.git modules/FireRedASR
2. pip install -r requirements.txt (从 FireRedASR 目录)
3. 下载模型: huggingface-cli download FireRedTeam/FireRedASR-AED-L --local-dir modules/FireRedASR/pretrained_models/FireRedASR-AED-L
"""

# ============================================================
# Windows 兼容性修复: 必须在 PyTorch 之前先导入 sentencepiece
# 否则会发生 DLL 冲突导致 access violation 崩溃
# ============================================================
import sentencepiece as _spm_preload
print("[DEBUG] sentencepiece 预加载完成 (避免 DLL 冲突)")

import os
import sys
import time
import wave
import threading
import numpy as np
import sounddevice as sd
from pathlib import Path
from queue import Queue

# 注意: 不启用 faulthandler，它可能干扰 C 扩展的内存操作
# import faulthandler
# faulthandler.enable()

# 注册退出处理器，捕获意外退出
import atexit
def on_exit():
    print("\n[DEBUG] atexit: 脚本正在退出...")
    sys.stdout.flush()
atexit.register(on_exit)

# 配置
SAMPLE_RATE = 16000
CHUNK_SECONDS = 0.5  # 每个分段长度 (从 2.0 降到 0.5 秒，更快响应)
SILENCE_THRESHOLD = 100  # 静音阈值 (根据实际麦克风调整)
SILENCE_CHUNKS = 2  # 连续静音块数认为说话结束 (0.5s * 2 = 1秒静音触发)

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# FireRedASR 路径 (必须在 import fireredasr 之前添加)
FIREREDASR_PATH = os.path.join(PROJECT_ROOT, "modules", "FireRedASR")
if os.path.exists(FIREREDASR_PATH):
    sys.path.insert(0, FIREREDASR_PATH)
    print(f"已添加 FireRedASR 路径: {FIREREDASR_PATH}")

# 模型目录 (在 FireRedASR 模块内)
MODEL_DIR = os.path.join(PROJECT_ROOT, "modules", "FireRedASR", "pretrained_models", "FireRedASR-AED-L")


def check_dependencies():
    """检查依赖是否安装"""
    print("检查依赖...")
    
    try:
        from fireredasr.models.fireredasr import FireRedAsr
        print("✓ FireRedASR 已安装")
        return True
    except ImportError as e:
        print(f"✗ FireRedASR 未安装: {e}")
        print("\n安装步骤:")
        print("1. git clone https://github.com/FireRedTeam/FireRedASR.git modules/FireRedASR")
        print("2. cd modules/FireRedASR && pip install -r requirements.txt")
        print("3. huggingface-cli download FireRedTeam/FireRedASR-AED-L --local-dir modules/FireRedASR/pretrained_models/FireRedASR-AED-L")
        return False


def save_temp_wav(audio: np.ndarray, path: str = "temp_test.wav"):
    """保存临时 WAV 文件"""
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())
    
    return path


def is_silence(audio: np.ndarray, threshold: int = SILENCE_THRESHOLD) -> bool:
    """判断是否为静音"""
    return np.abs(audio).mean() < threshold


class StreamingRecognizer:
    """流式语音识别器 - 说完一句就输出一句"""
    
    def __init__(self, model):
        self.model = model
        self.audio_queue = Queue()
        self.is_running = False
        self.current_audio = []
        self.silence_count = 0
        
    def audio_callback(self, indata, frames, time_info, status):
        """音频回调 - 实时获取麦克风数据"""
        if status:
            print(f"状态: {status}")
        audio_chunk = indata[:, 0].copy().astype(np.int16)
        self.audio_queue.put(audio_chunk)
    
    def process_audio(self):
        """处理音频流"""
        chunk_samples = int(CHUNK_SECONDS * SAMPLE_RATE)
        buffer = np.array([], dtype=np.int16)
        
        while self.is_running:
            # 获取音频数据
            try:
                chunk = self.audio_queue.get(timeout=0.1)
                buffer = np.concatenate([buffer, chunk])
            except:
                continue
            
            # 当缓冲区足够大时处理
            if len(buffer) >= chunk_samples:
                audio_segment = buffer[:chunk_samples]
                buffer = buffer[chunk_samples:]
                
                # 检查是否静音
                avg_volume = np.abs(audio_segment).mean()
                # 调试：显示实际音量
                print(f"\r[DEBUG] 音量: {avg_volume:.0f} (阈值: {SILENCE_THRESHOLD})", end="", flush=True)
                
                if is_silence(audio_segment):
                    self.silence_count += 1
                    
                    # 如果之前有积累的音频且连续静音，则识别
                    if len(self.current_audio) > 0 and self.silence_count >= SILENCE_CHUNKS:
                        self._recognize_and_output()
                        self.silence_count = 0
                else:
                    # 有声音，累积音频
                    self.silence_count = 0
                    self.current_audio.append(audio_segment)
                    
                    # 显示音量指示
                    volume = int(avg_volume / 100)
                    print(f"\r🎤 {'█' * min(volume, 30):<30} ({avg_volume:.0f})", end="", flush=True)
    
    def _recognize_and_output(self):
        """识别并输出结果"""
        if not self.current_audio:
            return
            
        # 合并音频
        full_audio = np.concatenate(self.current_audio)
        self.current_audio = []
        
        # 保存临时文件
        temp_path = save_temp_wav(full_audio)
        
        # 识别
        try:
            print("\n\n🔄 识别中...", end=" ", flush=True)
            start_time = time.time()
            
            results = self.model.transcribe(
                ["stream_utterance"],
                [temp_path],
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
            
            infer_time = time.time() - start_time
            
            if results and len(results) > 0:
                text = results[0].get("text", "") if isinstance(results[0], dict) else str(results[0])
                if text.strip():
                    print(f"\n{'='*50}")
                    print(f"📝 识别结果: {text}")
                    print(f"⏱️  耗时: {infer_time:.2f}s")
                    print(f"{'='*50}\n")
        except Exception as e:
            print(f"\n识别错误: {e}")
        finally:
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    def start(self):
        """开始流式识别"""
        self.is_running = True
        
        # 启动处理线程
        process_thread = threading.Thread(target=self.process_audio)
        process_thread.start()
        
        print("\n🎤 开始录音 (按 Ctrl+C 停止)...")
        print("说话时会实时显示音量，停顿后自动识别\n")
        
        # 开始录音
        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype='int16',
                blocksize=1024,  # 每 1024 样本触发一次回调 (~64ms)
                callback=self.audio_callback
            ):
                while self.is_running:
                    time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\n停止录音...")
        finally:
            self.is_running = False
            process_thread.join()
            
            # 处理剩余音频
            if self.current_audio:
                self._recognize_and_output()


def test_file(model, audio_path: str):
    """测试文件识别"""
    print(f"\n识别音频: {audio_path}")
    start_infer = time.time()
    
    results = model.transcribe(
        ["test_utterance"],
        [audio_path],
        {
            "use_gpu": 1,
            "beam_size": 3,
            "nbest": 1,
            "decode_max_len": 0,
            "softmax_smoothing": 1.0,
            "aed_length_penalty": 0.0,
            "eos_penalty": 1.0
        }
    )
    
    infer_time = time.time() - start_infer
    
    if results and len(results) > 0:
        text = results[0].get("text", "") if isinstance(results[0], dict) else str(results[0])
    else:
        text = ""
    
    print(f"\n{'='*50}")
    print(f"识别结果: {text}")
    print(f"推理耗时: {infer_time:.2f}s")
    print(f"{'='*50}")
    
    return text, infer_time


def main():
    print("=" * 60)
    print("FireRedASR-AED-L 测试脚本")
    print("=" * 60)
    
    # 检查依赖
    if not check_dependencies():
        return
    
    # 检查模型
    if not os.path.exists(MODEL_DIR):
        print(f"\n模型目录不存在: {MODEL_DIR}")
        print("请先下载模型:")
        print(f"huggingface-cli download FireRedTeam/FireRedASR-AED-L --local-dir {MODEL_DIR}")
        return
    
    # 加载模型
    print(f"\n[DEBUG] 开始加载模型...")
    print(f"[DEBUG] 模型目录: {MODEL_DIR}")
    
    try:
        print("[DEBUG] 正在导入 FireRedAsr...")
        from fireredasr.models.fireredasr import FireRedAsr
        print("[DEBUG] ✓ FireRedAsr 导入成功")
        
        print(f"\n加载 FireRedASR-AED-L 模型...")
        start_load = time.time()
        
        # 分步加载以定位问题
        import torch
        model_path = os.path.join(MODEL_DIR, "model.pth.tar")
        print(f"[DEBUG] 模型文件路径: {model_path}")
        print(f"[DEBUG] 文件存在: {os.path.exists(model_path)}")
        
        if os.path.exists(model_path):
            file_size = os.path.getsize(model_path) / (1024 * 1024 * 1024)
            print(f"[DEBUG] 模型文件大小: {file_size:.2f} GB")
        
        print("[DEBUG] 正在调用 FireRedAsr.from_pretrained()...")
        print("[DEBUG] 如果卡在这里，请等待模型加载完成...")
        sys.stdout.flush()  # 强制刷新输出缓冲区
        
        model = FireRedAsr.from_pretrained("aed", MODEL_DIR)
        
        load_time = time.time() - start_load
        print(f"[DEBUG] ✓ 模型加载成功")
        print(f"模型加载完成 (耗时: {load_time:.2f}s)")
        sys.stdout.flush()
        
    except Exception as e:
        print(f"\n[ERROR] 模型加载失败!")
        print(f"[ERROR] 异常类型: {type(e).__name__}")
        print(f"[ERROR] 异常信息: {e}")
        import traceback
        print("[ERROR] 完整堆栈:")
        traceback.print_exc()
        sys.stdout.flush()
        return
    
    # 选择测试模式
    while True:
        print("\n选择测试模式:")
        print("1. 流式录音测试 (说完一句输出一句)")
        print("2. 使用已有 WAV 文件")
        print("q. 退出")
        
        choice = input("请选择 (1/2/q): ").strip().lower()
        
        if choice == "1":
            recognizer = StreamingRecognizer(model)
            recognizer.start()
            break
        elif choice == "2":
            audio_path = input("请输入 WAV 文件路径: ").strip()
            if not audio_path:
                print("路径不能为空，请重新输入")
                continue
            if not os.path.exists(audio_path):
                print(f"文件不存在: {audio_path}")
                continue
            test_file(model, audio_path)
            break
        elif choice == "q":
            print("退出测试")
            return
        else:
            print("无效选择，请输入 1、2 或 q")
    
    print("\n测试完成!")


if __name__ == "__main__":
    main()
