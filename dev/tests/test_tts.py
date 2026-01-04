# -*- coding: utf-8 -*-
"""
TTS Module Test
TTS 模块测试脚本
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from tts.synthesizer import TTSSynthesizer
from tts.audio_queue import AudioQueue
from tts.player import AudioPlayer, SequentialPlayer
import config

# 配置 loguru
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")


def test_synthesizer():
    """测试语音合成器"""
    print("\n" + "="*60)
    print("测试 1: 语音合成器")
    print("="*60)
    
    synth = TTSSynthesizer()
    
    print(f"\nGradio URL: {config.TTS_GRADIO_URL}")
    print(f"参考音频: {config.TTS_PROMPT_AUDIO}")
    
    if not synth.connect():
        print("\n无法连接到 IndexTTS2 服务")
        print("请确保已启动: 雨落AI启动器.exe")
        return None
    
    test_text = "你好呀，这是一个语音合成测试。"
    print(f"\n合成文本: {test_text}")
    
    start_time = time.time()
    audio_path = synth.synthesize(test_text, "test_single")
    synth_time = time.time() - start_time
    
    if audio_path:
        print(f"\n合成成功: {audio_path}")
        print(f"耗时: {synth_time:.2f}s")
        return audio_path
    else:
        print("\n合成失败")
        return None


def test_player(audio_path=None):
    """测试音频播放器"""
    print("\n" + "="*60)
    print("测试 2: 音频播放器")
    print("="*60)
    
    if audio_path is None:
        audio_path = test_synthesizer()
    
    if audio_path is None:
        print("没有可播放的音频")
        return
    
    player = AudioPlayer()
    
    print(f"\n播放: {audio_path}")
    player.play(audio_path, blocking=True)
    print("播放完成")


def test_audio_queue():
    """测试音频队列"""
    print("\n" + "="*60)
    print("测试 3: 并行 TTS 队列")
    print("="*60)
    
    # 先测试连接
    synth = TTSSynthesizer()
    if not synth.connect():
        print("\n无法连接到 IndexTTS2 服务")
        return
    
    sentences = [
        ("你好呀！", "happy"),
        ("今天天气真不错。", "neutral"),
        ("一起出去玩吧！", "excited"),
    ]
    
    print(f"\n提交 {len(sentences)} 个句子到 TTS 队列:")
    for text, emotion in sentences:
        print(f"  - [{emotion}] {text}")
    
    queue = AudioQueue()
    queue.start()
    
    submit_start = time.time()
    for text, emotion in sentences:
        queue.submit(text, emotion)
    
    print("\n等待所有任务完成...")
    
    while queue.has_pending():
        time.sleep(0.5)
        stats = queue.get_stats()
        print(f"  进度: {stats['ready']}/{stats['total']}")
    
    total_time = time.time() - submit_start
    
    print(f"\n全部完成! 总耗时: {total_time:.2f}s")
    
    # 获取并播放
    ready_tasks = queue.get_all_ready()
    print(f"\n按序播放 {len(ready_tasks)} 个音频:")
    
    player = AudioPlayer()
    for task in ready_tasks:
        print(f"  播放: #{task.id} '{task.text}'")
        if task.audio_path:
            player.play(task.audio_path, blocking=True)
    
    queue.stop()
    print("\n播放完成")


def test_sequential_player():
    """测试顺序播放器"""
    print("\n" + "="*60)
    print("测试 4: 顺序播放器")
    print("="*60)
    
    synth = TTSSynthesizer()
    if not synth.connect():
        print("\n无法连接到 IndexTTS2 服务")
        return
    
    sentences = [
        "你好呀！",
        "我是咲希。",
        "很高兴认识你！",
    ]
    
    print("\n先合成所有句子...")
    audio_files = []
    for i, text in enumerate(sentences, 1):
        audio_path = synth.synthesize(text, f"seq_test_{i}")
        if audio_path:
            audio_files.append((i, audio_path, text))
            print(f"  #{i}: {text}")
    
    print("\n使用顺序播放器播放...")
    
    player = SequentialPlayer()
    
    def on_start(task_id, text):
        print(f"  ▶ 开始播放 #{task_id}: {text}")
    
    def on_end(task_id, text):
        print(f"  ■ 播放结束 #{task_id}")
    
    player.on_sentence_start = on_start
    player.on_sentence_end = on_end
    
    player.start()
    
    for task_id, audio_path, text in audio_files:
        player.add(task_id, audio_path, text)
    
    # 等待播放完成
    while player.is_playing:
        time.sleep(0.1)
    
    time.sleep(0.5)
    player.stop()
    
    print("\n全部播放完成")


def main():
    print("="*60)
    print("TTS 模块测试")
    print("="*60)
    
    print("\n前置条件:")
    print("  - IndexTTS2 服务已启动 (http://127.0.0.1:7860)")
    print("  - 参考音频存在: saki.WAV")
    
    print("\n选择测试项目:")
    print("  1. 语音合成器")
    print("  2. 音频播放器")
    print("  3. 并行 TTS 队列")
    print("  4. 顺序播放器")
    print("  0. 全部测试")
    
    choice = input("\n请输入选项 (默认 3): ").strip() or "3"
    
    if choice == "1":
        test_synthesizer()
    elif choice == "2":
        test_player()
    elif choice == "3":
        test_audio_queue()
    elif choice == "4":
        test_sequential_player()
    elif choice == "0":
        audio_path = test_synthesizer()
        if audio_path:
            test_player(audio_path)
        test_audio_queue()
        test_sequential_player()
    else:
        print("无效选项")


if __name__ == "__main__":
    main()
