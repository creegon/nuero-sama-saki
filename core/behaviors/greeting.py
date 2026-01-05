# -*- coding: utf-8 -*-
"""
自动打招呼行为
"""

import asyncio
import re
from loguru import logger
import config

class AutoGreeter:
    """负责启动时的自动打招呼"""
    
    def __init__(self, llm_client, audio_queue, player, state_machine, expression_callback):
        self.llm_client = llm_client
        self.audio_queue = audio_queue
        self.player = player
        self.state_machine = state_machine
        self._set_expression = expression_callback
        self.log = logger.bind(module="AutoGreeter")
        
    async def run(self):
        """启动时自动打招呼 (调用时间感知 + LLM)"""
        try:
            self.log.info("🌅 正在生成打招呼...")
            
            # 获取时间信息
            from tools.time_aware_tool import get_time_info
            time_info = get_time_info()
            
            # 构建打招呼 prompt
            greeting_prompt = f"""[系统: 启动打招呼]

当前时间信息：
- 时间: {time_info['time']}
- 时段: {time_info['period']}
- 日期: {time_info['date']}，{time_info['weekday']}
- 是否周末: {'是' if time_info['is_weekend'] else '否'}
"""
            
            # 如果是特殊日期
            if time_info['special_date']:
                greeting_prompt += f"- 特殊日期: {time_info['special_date']}！{time_info['special_hint']}\n"
            
            greeting_prompt += f"""
建议情绪: {time_info['period_emotion']}
建议问候: {time_info['period_hint']}

请用符合当前时间的语气，自然地跟主人打个招呼。保持你的角色性格（温柔热情、元气满满的大小姐）。
不要太长，一两句话就好。记得用表情标签开头。"""
            
            # 调用 LLM
            # 使用 PromptBuilder 获取带有记忆的 System Prompt
            from llm.prompt_builder import get_prompt_builder
            builder = get_prompt_builder()
            system_prompt = builder.build_system_prompt()
            
            # 构建消息列表
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": greeting_prompt}
            ]
            
            full_response = ""
            print("🤖 [打招呼] AI: ", end="", flush=True)
            # 传递完整的 messages (包含 system prompt)
            async for chunk in self.llm_client.chat_stream(messages):
                full_response += chunk
                print(chunk, end="", flush=True)
            print()
            
            # 处理响应 (跳过工具调用检测，直接播放)
            emotion_match = re.match(r'^\[(\w+)\]', full_response)
            detected_emotion = emotion_match.group(1).lower() if emotion_match else time_info['period_emotion']
            
            # 设置表情
            if self._set_expression:
                self._set_expression(detected_emotion)
            
            # 清理文本 - 移除所有情绪标签
            clean_text = re.sub(r'\[\w+\]', '', full_response)  # 移除所有 [tag]
            clean_text = re.sub(r'\s+', '', clean_text)
            
            # 提交 TTS
            if clean_text:
                self.audio_queue.submit(clean_text, detected_emotion)
                
                # 启动状态机 (IDLE -> PROCESSING -> SPEAKING)
                if self.state_machine:
                    self.state_machine.transition_to(self.state_machine._state, force=True)  # 确保在 IDLE
                    # 使用 force=True 跳过状态检查，因为这是启动时的特殊流程
                    from core.state_machine import State
                    self.state_machine.transition_to(State.SPEAKING, force=True)
                
                # 播放
                while self.audio_queue.has_pending():
                    await asyncio.sleep(0.1)
                    task = self.audio_queue.get_next_ready()
                    if task and (task.audio_data or task.audio_path):
                        source = task.audio_data if task.audio_data else task.audio_path
                        self.player.add(task.id, source, task.text)
                
                if self.player:
                    while self.player.is_playing:
                        await asyncio.sleep(0.1)
                
                if self.state_machine:
                    self.state_machine.finish_speaking()
            
            self.log.info("✅ 打招呼完成")
            
        except Exception as e:
            self.log.error(f"打招呼失败: {e}")
            import traceback
            traceback.print_exc()
