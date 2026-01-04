# -*- coding: utf-8 -*-
"""
测试 Gemini 直接语音对话 - 跳过 STT
语音直接作为 LLM 输入，Gemini 理解并回复
"""

import base64
import httpx
import asyncio
import sys
import os

sys.path.insert(0, r"d:\neruo")
import config

# 配置
API_BASE = config.LLM_API_BASE
API_KEY = config.LLM_API_KEY
MODEL = config.LLM_MODEL

# 测试音频
TEST_AUDIO = r"D:\neruo\debug_audio\tts_1_20260101_185058.wav"


async def test_voice_to_response():
    """语音直接输入，获取对话回复（跳过 STT）"""
    print("=" * 50)
    print("测试: 语音直接对话 (跳过 STT)")
    print("=" * 50)
    
    with open(TEST_AUDIO, "rb") as f:
        audio_bytes = f.read()
    
    base64_audio = base64.b64encode(audio_bytes).decode("utf-8")
    print(f"[OK] 音频: {os.path.basename(TEST_AUDIO)} ({len(audio_bytes)//1024}KB)")
    
    # 直接以语音作为用户输入，让 LLM 回复
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": base64_audio,
                        "format": "wav"
                    }
                }
            ]
        }
    ]
    
    print("\n[...] 发送语音给 Gemini...")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{API_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL,
                "messages": messages,
                "max_tokens": 500
            }
        )
        
        print(f"[HTTP] 状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"\n[OK] Gemini 的回复:\n{content}")
        else:
            print(f"[X] 错误:\n{response.text[:300]}")


async def test_voice_with_context():
    """语音 + 上下文提示"""
    print("\n" + "=" * 50)
    print("测试: 语音 + 角色设定")
    print("=" * 50)
    
    with open(TEST_AUDIO, "rb") as f:
        audio_bytes = f.read()
    
    base64_audio = base64.b64encode(audio_bytes).decode("utf-8")
    
    # 加上系统角色设定
    system_prompt = """你是丰川祥子，一个住在主人电脑桌面的傲娇少女。
你自称"本神明"，说话带点傲娇但其实很关心主人。
请直接对音频中的内容做出回应，就像在和主人对话一样。"""
    
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": system_prompt
                },
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": base64_audio,
                        "format": "wav"
                    }
                }
            ]
        }
    ]
    
    print("[...] 发送语音 + 角色设定...")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{API_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL,
                "messages": messages,
                "max_tokens": 500
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"\n[OK] 小祥的回复:\n{content}")
        else:
            print(f"[X] 错误:\n{response.text[:300]}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    
    print("[Voice-to-LLM] 直接语音对话测试")
    print(f"API: {API_BASE}")
    print(f"Model: {MODEL}")
    print()
    
    asyncio.run(test_voice_to_response())
    asyncio.run(test_voice_with_context())
