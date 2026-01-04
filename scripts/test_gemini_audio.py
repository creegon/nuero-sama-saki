# -*- coding: utf-8 -*-
"""
测试 Gemini API 音频输入功能 (使用正确的 input_audio 格式)
通过 Antigravity 代理调用 Gemini Flash 处理音频
"""

import base64
import httpx
import asyncio
import sys
import os

# 配置
API_BASE = "http://localhost:8045/v1"
API_KEY = "sk-text"
MODEL = "gemini-3-flash"

# 测试音频文件
TEST_AUDIO = r"D:\neruo\debug_audio\tts_1_20260101_185058.wav"


async def test_audio_input_format():
    """使用正确的 input_audio 格式测试"""
    print("=" * 50)
    print("测试 Gemini 音频理解 (input_audio 格式)")
    print("=" * 50)
    
    if not os.path.exists(TEST_AUDIO):
        print(f"[X] 测试文件不存在: {TEST_AUDIO}")
        return
    
    with open(TEST_AUDIO, "rb") as f:
        audio_bytes = f.read()
    
    base64_audio = base64.b64encode(audio_bytes).decode("utf-8")
    print(f"[OK] 音频文件: {TEST_AUDIO}")
    print(f"     大小: {len(audio_bytes) / 1024:.1f} KB")
    
    # 使用官方文档的 input_audio 格式
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "请转录这段音频中的中文内容。只输出转录文字，不要添加任何解释。"
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
    
    print("\n[...] 发送请求到 Antigravity...")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
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
                print(f"\n[OK] 转录结果:\n{content}")
                return True
            else:
                print(f"[X] 错误响应:\n{response.text[:500]}")
                return False
                
        except Exception as e:
            print(f"[X] 请求失败: {e}")
            return False


async def test_direct_gemini_api():
    """直接调用 Gemini API (不经过 Antigravity)"""
    print("\n" + "=" * 50)
    print("测试: 直接调用 Gemini API")
    print("=" * 50)
    
    try:
        from google import genai
        from google.genai import types
        
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("[X] 未设置 GEMINI_API_KEY 环境变量")
            return False
        
        client = genai.Client(api_key=api_key)
        
        with open(TEST_AUDIO, "rb") as f:
            audio_bytes = f.read()
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                "请转录这段音频中的中文内容。只输出转录文字。",
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")
            ]
        )
        
        print(f"\n[OK] 转录结果:\n{response.text}")
        return True
        
    except ImportError:
        print("[!] google-genai 未安装，跳过直接 API 测试")
        print("    安装命令: pip install google-genai")
        return False
    except Exception as e:
        print(f"[X] 失败: {e}")
        return False


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    
    print("[Audio] Gemini 音频理解测试")
    print(f"API: {API_BASE}")
    print(f"Model: {MODEL}")
    print()
    
    # 测试1: 通过 Antigravity 代理
    success = asyncio.run(test_audio_input_format())
    
    if not success:
        # 测试2: 直接调用 Gemini API (如果代理不支持)
        asyncio.run(test_direct_gemini_api())
