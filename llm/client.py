# -*- coding: utf-8 -*-
"""
LLM Client Module
OpenAI 格式 API 客户端，支持流式输出和音频输入
"""

import httpx
import base64
from typing import AsyncGenerator, Optional, Dict, Any, Union
from loguru import logger
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class LLMClient:
    """LLM API 客户端"""
    
    def __init__(
        self,
        api_base: str = config.LLM_API_BASE,
        api_key: str = config.LLM_API_KEY,
        model: str = config.LLM_MODEL,
        timeout: float = 60.0
    ):
        self.api_base = api_base.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    async def chat_stream(
        self,
        messages: list,
        system_prompt: Optional[str] = None,
        temperature: float = 1.2,
        max_tokens: int = 2048
    ) -> AsyncGenerator[str, None]:
        """
        流式对话
        
        Args:
            messages: 对话历史
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大输出 token 数
            
        Yields:
            流式输出的文本片段
        """
        # 构建请求消息
        request_messages = []
        if system_prompt:
            request_messages.append({"role": "system", "content": system_prompt})
        request_messages.extend(messages)
        
        payload = {
            "model": self.model,
            "messages": request_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        
        url = f"{self.api_base}/chat/completions"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                url,
                json=payload,
                headers=self.headers
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    logger.error(f"LLM API 错误: {response.status_code} - {error_text}")
                    raise Exception(f"LLM API 错误: {response.status_code}")
                
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            if "choices" in chunk and len(chunk["choices"]) > 0:
                                delta = chunk["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
    
    async def chat_with_audio_stream(
        self,
        audio_data: bytes,
        audio_format: str = "wav",
        system_prompt: Optional[str] = None,
        conversation_history: Optional[list] = None,
        temperature: float = 1.2,
        max_tokens: int = 2048
    ) -> AsyncGenerator[str, None]:
        """
        语音直接输入的流式对话 (跳过 STT)
        
        Args:
            audio_data: 原始音频字节数据
            audio_format: 音频格式 (wav, mp3, etc.)
            system_prompt: 系统提示词
            conversation_history: 对话历史（可选）
            temperature: 温度参数
            max_tokens: 最大输出 token 数
            
        Yields:
            流式输出的文本片段
        """
        # Base64 编码音频
        base64_audio = base64.b64encode(audio_data).decode("utf-8")
        
        # 构建请求消息
        request_messages = []
        
        # 添加系统提示
        if system_prompt:
            request_messages.append({"role": "system", "content": system_prompt})
        
        # 添加对话历史
        if conversation_history:
            request_messages.extend(conversation_history)
        
        # 添加当前音频作为用户输入
        user_content = [
            {
                "type": "input_audio",
                "input_audio": {
                    "data": base64_audio,
                    "format": audio_format
                }
            }
        ]
        request_messages.append({"role": "user", "content": user_content})
        
        payload = {
            "model": self.model,
            "messages": request_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        
        url = f"{self.api_base}/chat/completions"
        
        logger.debug(f"🎤 发送音频到 LLM ({len(audio_data)//1024}KB)")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                url,
                json=payload,
                headers=self.headers
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    logger.error(f"LLM API 错误: {response.status_code} - {error_text}")
                    raise Exception(f"LLM API 错误: {response.status_code}")
                
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            if "choices" in chunk and len(chunk["choices"]) > 0:
                                delta = chunk["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
    
    async def chat(
        self,
        messages: list,
        system_prompt: Optional[str] = None,
        temperature: float = 1.2,
        max_tokens: int = 2048
    ) -> str:
        """
        非流式对话（收集完整响应）
        """
        full_response = ""
        async for chunk in self.chat_stream(messages, system_prompt, temperature, max_tokens):
            full_response += chunk
        return full_response
    
    async def chat_with_audio(
        self,
        audio_data: bytes,
        audio_format: str = "wav",
        system_prompt: Optional[str] = None,
        conversation_history: Optional[list] = None,
        temperature: float = 1.2,
        max_tokens: int = 2048
    ) -> str:
        """
        语音直接输入的非流式对话
        """
        full_response = ""
        async for chunk in self.chat_with_audio_stream(
            audio_data, audio_format, system_prompt, 
            conversation_history, temperature, max_tokens
        ):
            full_response += chunk
        return full_response


# 全局单例
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取全局 LLMClient 实例"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


if __name__ == "__main__":
    import asyncio
    
    async def test():
        client = LLMClient()
        messages = [{"role": "user", "content": "你好，请用一句话介绍自己"}]
        
        print("测试流式输出:")
        async for chunk in client.chat_stream(messages, system_prompt=config.SYSTEM_PROMPT):
            print(chunk, end="", flush=True)
        print("\n")
    
    asyncio.run(test())
