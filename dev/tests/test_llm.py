# -*- coding: utf-8 -*-
"""
LLM Module Test
LLM 模块测试脚本
"""

import sys
import os
import asyncio
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from llm.client import LLMClient
from llm.prompts import get_system_prompt, build_conversation_messages
from llm.stream_parser import StreamParser, split_text_to_sentences
import config

# 配置 loguru
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")


async def test_basic_chat():
    """测试基础对话"""
    print("\n" + "="*60)
    print("测试 1: 基础对话")
    print("="*60)
    
    client = LLMClient()
    messages = [{"role": "user", "content": "你好，请用一句话介绍自己"}]
    
    print(f"\nAPI: {config.LLM_API_BASE}")
    print(f"模型: {config.LLM_MODEL}")
    print(f"\n用户: {messages[0]['content']}")
    print("\n助手: ", end="", flush=True)
    
    start_time = time.time()
    first_token_time = None
    
    async for chunk in client.chat_stream(messages, system_prompt=get_system_prompt()):
        if first_token_time is None:
            first_token_time = time.time()
        print(chunk, end="", flush=True)
    
    total_time = time.time() - start_time
    ttft = first_token_time - start_time if first_token_time else 0
    
    print(f"\n\n统计:")
    print(f"  - 首 Token 延迟 (TTFT): {ttft:.2f}s")
    print(f"  - 总耗时: {total_time:.2f}s")


async def test_stream_parsing():
    """测试流式解析"""
    print("\n" + "="*60)
    print("测试 2: 流式解析 + 句子分割")
    print("="*60)
    
    client = LLMClient()
    parser = StreamParser()
    
    messages = [{"role": "user", "content": "给我讲个两句话的笑话"}]
    
    print(f"\n用户: {messages[0]['content']}")
    print("\n原始流式输出:")
    
    sentences = []
    start_time = time.time()
    
    async for chunk in client.chat_stream(messages, system_prompt=get_system_prompt()):
        print(chunk, end="", flush=True)
        
        for sentence, emotion in parser.feed(chunk):
            sentences.append((sentence, emotion, time.time() - start_time))
    
    final = parser.flush()
    if final:
        sentences.append((final[0], final[1], time.time() - start_time))
    
    print("\n\n分割后的句子:")
    for i, (sentence, emotion, t) in enumerate(sentences, 1):
        print(f"  [{t:.2f}s] {i}. [{emotion or 'None'}] {sentence}")
    
    print(f"\n检测到的情感: {parser.get_emotion()}")


async def test_conversation():
    """测试多轮对话"""
    print("\n" + "="*60)
    print("测试 3: 多轮对话")
    print("="*60)
    
    client = LLMClient()
    history = []
    
    test_inputs = [
        "你叫什么名字？",
        "你喜欢什么颜色？",
        "你刚才说的颜色，为什么喜欢它？"
    ]
    
    for user_input in test_inputs:
        print(f"\n用户: {user_input}")
        
        messages = build_conversation_messages(user_input, history)
        
        print("助手: ", end="", flush=True)
        response = ""
        async for chunk in client.chat_stream(messages, system_prompt=get_system_prompt()):
            print(chunk, end="", flush=True)
            response += chunk
        print()
        
        # 更新历史
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": response})


async def test_interactive():
    """交互式测试"""
    print("\n" + "="*60)
    print("测试 4: 交互式对话")
    print("="*60)
    
    client = LLMClient()
    parser = StreamParser()
    history = []
    
    print("\n输入消息与 AI 对话，输入 'quit' 退出")
    print("-"*60)
    
    while True:
        try:
            user_input = input("\n你: ").strip()
            if not user_input:
                continue
            if user_input.lower() == 'quit':
                break
            
            messages = build_conversation_messages(user_input, history)
            parser.reset()
            
            print("AI: ", end="", flush=True)
            
            start_time = time.time()
            first_token_time = None
            response = ""
            sentence_times = []
            
            async for chunk in client.chat_stream(messages, system_prompt=get_system_prompt()):
                if first_token_time is None:
                    first_token_time = time.time()
                print(chunk, end="", flush=True)
                response += chunk
                
                for sentence, emotion in parser.feed(chunk):
                    sentence_times.append((sentence, time.time() - start_time))
            
            final = parser.flush()
            if final:
                sentence_times.append((final[0], time.time() - start_time))
            
            total_time = time.time() - start_time
            ttft = first_token_time - start_time if first_token_time else 0
            
            print(f"\n  [TTFT: {ttft:.2f}s | 总耗时: {total_time:.2f}s | 情感: {parser.get_emotion()}]")
            
            if sentence_times:
                print("  句子时间节点:", end=" ")
                for s, t in sentence_times:
                    print(f"[{t:.2f}s]", end=" ")
                print()
            
            # 更新历史
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})
            
        except KeyboardInterrupt:
            print("\n\n已退出")
            break


async def main():
    print("="*60)
    print("LLM 模块测试")
    print("="*60)
    
    print("\n选择测试项目:")
    print("  1. 基础对话")
    print("  2. 流式解析 + 句子分割")
    print("  3. 多轮对话")
    print("  4. 交互式对话（推荐）")
    print("  0. 全部测试")
    
    choice = input("\n请输入选项 (默认 4): ").strip() or "4"
    
    if choice == "1":
        await test_basic_chat()
    elif choice == "2":
        await test_stream_parsing()
    elif choice == "3":
        await test_conversation()
    elif choice == "4":
        await test_interactive()
    elif choice == "0":
        await test_basic_chat()
        await test_stream_parsing()
        await test_conversation()
    else:
        print("无效选项")


if __name__ == "__main__":
    asyncio.run(main())
