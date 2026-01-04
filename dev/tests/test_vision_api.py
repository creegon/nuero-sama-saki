# -*- coding: utf-8 -*-
"""
测试 Antigravity API 的视觉功能
检查是否支持图片上传和视觉理解
"""

import asyncio
import httpx
import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


async def test_vision_capability():
    """测试视觉 API 功能"""
    
    print("=" * 60)
    print("Antigravity API 视觉功能测试")
    print("=" * 60)
    print(f"\nAPI Base: {config.LLM_API_BASE}")
    print(f"Model: {config.LLM_MODEL}")
    print()
    
    # 1. 首先测试 /models 端点，查看支持的模型
    print("[1] 检查可用模型...")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{config.LLM_API_BASE}/models",
                headers={"Authorization": f"Bearer {config.LLM_API_KEY}"}
            )
            if response.status_code == 200:
                models = response.json()
                print(f"    可用模型列表:")
                for model in models.get("data", [])[:10]:  # 只显示前10个
                    model_id = model.get("id", "unknown")
                    print(f"      - {model_id}")
                if len(models.get("data", [])) > 10:
                    print(f"      ... 还有 {len(models.get('data', [])) - 10} 个模型")
            else:
                print(f"    ❌ 获取模型列表失败: {response.status_code}")
    except Exception as e:
        print(f"    ❌ 请求失败: {e}")
    
    print()
    
    # 2. 测试纯文本请求（确保 API 正常工作）
    print("[2] 测试纯文本请求...")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{config.LLM_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.LLM_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": config.LLM_MODEL,
                    "messages": [{"role": "user", "content": "说'视觉测试开始'"}],
                    "max_tokens": 50
                }
            )
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                print(f"    ✅ 纯文本请求成功: {content[:50]}...")
            else:
                print(f"    ❌ 请求失败: {response.status_code}")
                print(f"    Response: {response.text[:200]}")
    except Exception as e:
        print(f"    ❌ 请求失败: {e}")
    
    print()
    
    # 3. 测试带图片的视觉请求
    print("[3] 测试视觉请求 (带图片)...")
    
    # 创建一个简单的测试图片 (1x1 红色像素的 PNG)
    # 这是一个有效的最小 PNG 文件
    test_image_base64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    )
    
    # 也可以使用 URL 测试
    test_image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png"
    
    # 方法 A: 使用 base64 编码的图片
    print("    [3a] 使用 base64 编码图片...")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{config.LLM_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.LLM_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": config.LLM_MODEL,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "这张图片里有什么？用一句话描述。"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{test_image_base64}"
                                }
                            }
                        ]
                    }],
                    "max_tokens": 100
                }
            )
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                print(f"    ✅ Base64 图片请求成功!")
                print(f"       回复: {content[:100]}...")
            else:
                print(f"    ❌ 请求失败: {response.status_code}")
                error_detail = response.text[:300]
                print(f"       错误: {error_detail}")
    except Exception as e:
        print(f"    ❌ 请求失败: {e}")
    
    print()
    
    # 方法 B: 使用 URL 图片
    print("    [3b] 使用 URL 图片...")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{config.LLM_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.LLM_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": config.LLM_MODEL,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "描述这张图片的内容，用一句话。"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": test_image_url
                                }
                            }
                        ]
                    }],
                    "max_tokens": 100
                }
            )
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                print(f"    ✅ URL 图片请求成功!")
                print(f"       回复: {content[:100]}...")
            else:
                print(f"    ❌ 请求失败: {response.status_code}")
                error_detail = response.text[:300]
                print(f"       错误: {error_detail}")
    except Exception as e:
        print(f"    ❌ 请求失败: {e}")
    
    print()
    
    # 4. 测试带视觉模型的请求 (如果有专门的视觉模型)
    vision_models = ["gemini-2.0-flash", "gemini-1.5-pro", "gpt-4o", "claude-sonnet-4"]
    
    print("[4] 测试其他可能支持视觉的模型...")
    for model in vision_models:
        print(f"    测试 {model}...")
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{config.LLM_API_BASE}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.LLM_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "图片描述:"},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": test_image_url}
                                }
                            ]
                        }],
                        "max_tokens": 50
                    }
                )
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    print(f"    ✅ {model}: 支持视觉! -> {content[:50]}...")
                else:
                    print(f"    ❌ {model}: {response.status_code}")
        except Exception as e:
            print(f"    ❌ {model}: {e}")
    
    print()
    print("=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_vision_capability())
