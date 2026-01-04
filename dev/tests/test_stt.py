# -*- coding: utf-8 -*-
"""
STT Module Test
语音识别模块测试脚本
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from stt.audio_capture import AudioCapture, list_audio_devices
from stt.vad import SileroVAD
from stt.transcriber import Transcriber

# 配置 loguru
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")


def test_audio_capture():
    """测试音频采集"""
    print("\n" + "="*60)
    print("测试 1: 音频采集")
    print("="*60)
    
    list_audio_devices()
    
    capture = AudioCapture()
    if capture.start():
        print("\n录制 3 秒音频...")
        chunks = []
        start_time = time.time()
        
        while time.time() - start_time < 3:
            chunk = capture.read_chunk()
            if chunk is not None:
                chunks.append(chunk)
        
        capture.stop()
        
        total_samples = sum(len(c) for c in chunks)
        duration = total_samples / capture.sample_rate
        print(f"录制完成: {len(chunks)} 块, {total_samples} 样本, {duration:.2f} 秒")
        return True
    else:
        print("音频采集启动失败")
        return False


def test_vad():
    """测试 VAD"""
    print("\n" + "="*60)
    print("测试 2: Silero VAD")
    print("="*60)
    
    vad = SileroVAD()
    print("VAD 模型加载成功")
    
    print("\n请对着麦克风说一句话（5秒内）...")
    
    capture = AudioCapture()
    if not capture.start():
        print("音频采集启动失败")
        return False
    
    start_time = time.time()
    speech_detected = False
    
    while time.time() - start_time < 10:
        chunk = capture.read_chunk()
        if chunk is None:
            continue
        
        is_end, audio = vad.process_chunk(chunk)
        
        if vad.is_speaking and not speech_detected:
            print("  检测到语音开始...")
            speech_detected = True
        
        if is_end:
            capture.stop()
            duration = len(audio) / capture.sample_rate
            print(f"  检测到语音结束，时长: {duration:.2f} 秒")
            return audio
    
    capture.stop()
    print("超时，未检测到完整语音")
    return None


def test_transcriber(audio=None):
    """测试语音识别"""
    print("\n" + "="*60)
    print("测试 3: Faster-Whisper 语音识别")
    print("="*60)
    
    transcriber = Transcriber()
    
    print("加载 Whisper 模型...")
    transcriber.load_model()
    
    if audio is None:
        print("\n请对着麦克风说一句话...")
        audio = test_vad()
    
    if audio is None:
        print("没有音频可识别")
        return None
    
    print("\n正在识别...")
    text, stats = transcriber.transcribe(audio)
    
    print(f"\n识别结果: '{text}'")
    print(f"统计信息:")
    print(f"  - 音频时长: {stats['audio_duration']:.2f}s")
    print(f"  - 识别耗时: {stats['transcribe_time']:.2f}s")
    print(f"  - RTF (实时系数): {stats['rtf']:.2f}")
    print(f"  - 检测语言: {stats['language']} (置信度: {stats['language_probability']:.2f})")
    
    return text, stats


def test_full_pipeline():
    """完整 STT 流程测试"""
    print("\n" + "="*60)
    print("测试 4: 完整 STT 流程（实时）")
    print("="*60)
    
    print("\n初始化组件...")
    capture = AudioCapture()
    vad = SileroVAD()
    transcriber = Transcriber()
    transcriber.load_model()
    
    print("\n开始实时语音识别，按 Ctrl+C 退出...")
    print("-"*60)
    
    if not capture.start():
        print("音频采集启动失败")
        return
    
    try:
        while True:
            chunk = capture.read_chunk()
            if chunk is None:
                continue
            
            is_end, audio = vad.process_chunk(chunk)
            
            if is_end:
                print("\n[检测到语音结束，正在识别...]")
                stt_start = time.time()
                
                text, stats = transcriber.transcribe(audio)
                
                stt_time = time.time() - stt_start
                print(f"识别结果: {text}")
                print(f"  耗时: {stt_time:.2f}s | RTF: {stats['rtf']:.2f}")
                print("-"*60)
                
                vad.reset()
    
    except KeyboardInterrupt:
        print("\n\n已停止")
    finally:
        capture.stop()


def main():
    print("="*60)
    print("STT 模块测试")
    print("="*60)
    
    print("\n选择测试项目:")
    print("  1. 测试音频采集")
    print("  2. 测试 VAD")
    print("  3. 测试语音识别")
    print("  4. 完整实时测试（推荐）")
    print("  0. 全部测试")
    
    choice = input("\n请输入选项 (默认 4): ").strip() or "4"
    
    if choice == "1":
        test_audio_capture()
    elif choice == "2":
        test_vad()
    elif choice == "3":
        test_transcriber()
    elif choice == "4":
        test_full_pipeline()
    elif choice == "0":
        test_audio_capture()
        audio = test_vad()
        if audio is not None:
            test_transcriber(audio)
    else:
        print("无效选项")


if __name__ == "__main__":
    main()
