# -*- coding: utf-8 -*-
"""
测试截图直接发送给 LLM
验证多模态图片消息是否正常工作
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

async def test_screenshot_to_llm():
    print("=" * 50)
    print("[TEST] Screenshot to LLM")
    print("=" * 50)
    
    # 1. 截取屏幕
    print("\n[1/3] Capturing screen...")
    from vision.screenshot import get_screen_capture
    screen_capture = get_screen_capture()
    screenshot = screen_capture.capture(mode="full")
    
    print(f"   OK - Screenshot: {screenshot.width}x{screenshot.height}")
    print(f"   Format: {screenshot.format}")
    print(f"   Base64 size: {len(screenshot.base64_data) / 1024:.1f} KB")
    
    print("\n[2/3] Building multimodal message...")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Please briefly describe what you see in this screenshot."},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/{screenshot.format};base64,{screenshot.base64_data}"
                    }
                }
            ]
        }
    ]
    print(f"   OK - Message built")
    
    print("\n[3/3] Sending to LLM...")
    from llm.client import LLMClient
    client = LLMClient()
    
    print(f"   API: {config.LLM_API_BASE}")
    print(f"   Model: {config.LLM_MODEL}")
    print()
    
    print("LLM Response: ", end="", flush=True)
    full_response = ""
    try:
        async for chunk in client.chat_stream(messages, temperature=0.7):
            print(chunk, end="", flush=True)
            full_response += chunk
        print("\n")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        return False
    
    if full_response:
        print("=" * 50)
        print("[SUCCESS] LLM can receive and analyze images!")
        print("=" * 50)
        return True
    else:
        print("[FAIL] Empty response")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_screenshot_to_llm())
    sys.exit(0 if success else 1)
