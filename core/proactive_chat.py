# -*- coding: utf-8 -*-
"""
主动交互管理器

🔥 设计理念：
- 后台小祥：做轻量级 Yes/No 判断 + 可调用工具调整频率
- 主程序小祥：具体内容由她生成（有更全面的上下文）
- 定时检查：按配置的间隔检查，后台小祥可以动态调整

所有参数从 config.py 读取
"""

import asyncio
import time
import random
import re
from typing import Optional, Callable, Awaitable
from loguru import logger

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

from .background_prompt import PROACTIVE_CHAT_PERSONA, BackgroundToolRegistry


# ============================================================
# 判断 Prompt（判断 Yes/No + 可选工具调用）
# 🔥 工具描述从 BackgroundToolRegistry 动态获取
# ============================================================

def get_proactive_chat_prompt() -> str:
    """动态生成主动聊天判断 prompt"""
    tools_section = BackgroundToolRegistry.get_proactive_chat_tools_section()
    
    return f"""{PROACTIVE_CHAT_PERSONA}

现在你要判断一件事：**你想不想主动找主人说话？**

【当前状态】
主人已经 {{idle_minutes}} 分钟没理你了。
屏幕上显示：{{screen_context}}

【最近的对话】
{{recent_context}}

【当前检查频率】
当前间隔: {{current_interval}} 秒（每隔这么久检查一次要不要说话）
合理范围: 30~300 秒（30=很积极，300=很安静）

【怎么判断】
就像你平时会不会主动找朋友发微信一样：
- 看到屏幕上有什么想吐槽的？
- 突然想起什么想说的？
- 纯粹无聊想找人聊？
- 之前的话没说完？

但如果主人明显在忙（写代码、开会、专注工作），你应该不会去打扰。

{tools_section}

1. 判断是否说话（必选）：
   [YES] 或 [NO]

2. 调整检查频率（可选）：
   什么时候用：
   - 话题很有趣想多聊 → 调小（如 30~60）
   - 主人说"别吵我"/"安静点" → 调大（如 180~300）
   - 主人在专注工作 → 调大
   - 主人闲着/在摸鱼 → 调小

【输出格式】
先输出判断，再输出工具（如果需要）。例如：
[NO]
[ADJUST_INTERVAL:180]

或者只输出判断：
[YES]
"""

SHOULD_FOLLOW_UP_PROMPT = f"""{PROACTIVE_CHAT_PERSONA}

现在你要判断一件事：**你刚说完那句话，想不想再补一句？**

【最近的对话】
{{recent_context}}

【刚刚这轮】
主人说：{{user_text}}
你说：{{ai_response}}

【怎么判断】
就像发微信有时候会连发两条：
- 刚发完就想到还有别的没说
- 突然想到一个梗
- 想追问主人的反应
- 补充一个语气词或吐槽

但大多数时候你应该发一条就等回复，不用每句话都追。

只输出 [YES] 或 [NO]。"""


# ============================================================
# 发送给主程序的系统提示词
# ============================================================

PROACTIVE_CHAT_SYSTEM_PROMPT = """[系统提示: 你打算主动发起聊天]

你已经有一段时间没和主人说话了，现在你想主动找他聊天。

请根据以下信息发起话题：
- 之前聊天的话题（如果有的话）
- 你自己感兴趣的事情
- 主人的兴趣爱好
- 屏幕上正在显示的内容
- 或者任何你觉得能聊的东西

保持你的性格，简短自然，1-2句话。
不要说"好久没聊了"之类的开场白，直接切入话题。"""

FOLLOW_UP_SYSTEM_PROMPT = """[系统提示: 你打算追问/补充一句]

你刚刚说完一句话，觉得意犹未尽，想再补充一句。

可以是：
- 追问主人的看法
- 补充刚才没说完的细节
- 突然想到的相关事情
- 调侃或吐槽
- 其他你觉得可以补充的

必须非常简短（20字以内），就像发微信连发两条那样。"""


class ProactiveChatManager:
    """
    主动交互管理器
    
    工作流程：
    1. 定期调用后台小祥判断：是否想说话？(Yes/No)
    2. 后台小祥可以调用工具调整检查频率
    3. 如果 Yes → 发送系统提示词给主程序
    4. 主程序根据提示词生成具体内容
    """
    
    # 间隔范围限制
    INTERVAL_MIN = 30
    INTERVAL_MAX = 300
    
    def __init__(self, llm_client=None, enabled: bool = None):
        self.enabled = enabled if enabled is not None else config.PROACTIVE_CHAT_ENABLED
        self.llm_client = llm_client
        
        # 从 config 读取参数
        self.check_interval_min = getattr(config, 'PROACTIVE_CHECK_INTERVAL_MIN', 30)
        self.check_interval_max = getattr(config, 'PROACTIVE_CHECK_INTERVAL_MAX', 90)
        self.min_idle_time = getattr(config, 'PROACTIVE_MIN_IDLE_TIME', 20)
        self.follow_up_delay_min = getattr(config, 'FOLLOW_UP_DELAY_MIN', 2)
        self.follow_up_delay_max = getattr(config, 'FOLLOW_UP_DELAY_MAX', 4)
        
        # 🔥 动态检查间隔（后台小祥可以调整）
        self.current_interval = (self.check_interval_min + self.check_interval_max) // 2
        
        self._task: Optional[asyncio.Task] = None
        self._follow_up_task: Optional[asyncio.Task] = None
        self._is_running: bool = False
        self._state_machine = None
        
        # 静默模式
        self.silent_mode = False
        self.silent_until = 0
        
        # 最后活跃时间
        self.last_interaction_time = time.time()
        
        # 回调
        self._on_proactive_request: Optional[Callable[[str], Awaitable[None]]] = None
        self._get_recent_context: Optional[Callable[[], str]] = None
    
    def set_llm_client(self, llm_client):
        self.llm_client = llm_client
    
    def set_callbacks(
        self,
        on_proactive_request: Callable[[str], Awaitable[None]],
        get_recent_context: Callable[[], str] = None
    ):
        self._on_proactive_request = on_proactive_request
        self._get_recent_context = get_recent_context
    
    def update_interaction_time(self) -> None:
        self.last_interaction_time = time.time()
        if self._follow_up_task:
            self._follow_up_task.cancel()
            self._follow_up_task = None
    
    def set_silent_mode(self, duration_minutes: int = 0):
        self.silent_mode = True
        self.silent_until = time.time() + (duration_minutes * 60) if duration_minutes > 0 else 0
        logger.info(f"🤫 进入静默模式 (持续: {duration_minutes if duration_minutes else '无限期'}分钟)")
    
    def exit_silent_mode(self):
        self.silent_mode = False
        self.silent_until = 0
        logger.info("👋 退出静默模式")
    
    def adjust_interval(self, new_interval: int) -> None:
        """调整检查间隔（由后台小祥调用）"""
        old_interval = self.current_interval
        self.current_interval = max(self.INTERVAL_MIN, min(self.INTERVAL_MAX, new_interval))
        logger.info(f"⏱️ 后台小祥调整检查间隔: {old_interval}s → {self.current_interval}s")
    
    def start(self, state_machine=None) -> None:
        if not self.enabled:
            logger.info("💬 主动聊天已禁用")
            return
        
        self._is_running = True
        self._state_machine = state_machine
        self._task = asyncio.create_task(self._loop())
        logger.info(f"💬 主动交互系统已启动 (初始间隔={self.current_interval}s)")
    
    async def stop(self) -> None:
        self._is_running = False
        if self._task:
            self._task.cancel()
        if self._follow_up_task:
            self._follow_up_task.cancel()
    
    async def _loop(self) -> None:
        while self._is_running:
            try:
                # 🔥 使用动态间隔 + 随机抖动
                jitter = random.randint(-10, 10)
                wait_time = max(self.INTERVAL_MIN, self.current_interval + jitter)
                await asyncio.sleep(wait_time)
                
                if not self._is_running:
                    break
                
                # 静默模式检查
                if self.silent_mode:
                    if self.silent_until > 0 and time.time() > self.silent_until:
                        self.exit_silent_mode()
                    else:
                        logger.debug("🤫 静默模式中，跳过主动聊天检查")
                        continue
                
                # 状态检查 - 只在空闲时触发
                if self._state_machine and self._state_machine.is_busy:
                    logger.debug(f"💬 状态机忙碌中 (state={self._state_machine._state})，跳过主动聊天")
                    continue
                
                # 空闲时间检查
                idle_time = time.time() - self.last_interaction_time
                if idle_time < self.min_idle_time:
                    logger.debug(f"💬 空闲时间不足 ({idle_time:.0f}s < {self.min_idle_time}s)")
                    continue
                
                # 🔥 到达这里说明条件都满足了
                logger.info(f"💬 主动聊天检查: 空闲 {idle_time:.0f}s，开始判断...")
                
                # 判断是否要说话
                await self._check_and_maybe_request(idle_time)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"主动交互循环错误: {e}")
                await asyncio.sleep(10)
    
    async def _check_and_maybe_request(self, idle_time: float) -> None:
        """检查是否要主动说话（Yes/No 判断 + 工具调用）"""
        if not self.llm_client or not self._on_proactive_request:
            return
        
        try:
            # 获取上下文
            screen_context = "(无法获取)"
            try:
                from vision import get_vision_analyzer
                analyzer = get_vision_analyzer()
                screen_context = await analyzer.describe_for_chat("")
            except:
                pass
            
            recent_context = "(暂无)"
            if self._get_recent_context:
                recent_context = self._get_recent_context()
            
            # 构建判断 prompt (🔥 使用动态生成的 prompt 模板)
            prompt_template = get_proactive_chat_prompt()
            prompt = prompt_template.format(
                idle_minutes=int(idle_time / 60),
                screen_context=screen_context[:300],
                recent_context=recent_context,
                current_interval=self.current_interval
            )
            
            # 调用 LLM 判断
            response = ""
            async for chunk in self.llm_client.chat_stream(
                [{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0.7
            ):
                response += chunk
            
            logger.debug(f"🧠 后台小祥判断: {response}")
            
            # 🔥 解析工具调用
            interval_match = re.search(r'\[ADJUST_INTERVAL:(\d+)\]', response)
            if interval_match:
                new_interval = int(interval_match.group(1))
                self.adjust_interval(new_interval)
            
            # 判断结果
            response_upper = response.upper()
            if "[YES]" not in response_upper:
                logger.debug("🤫 后台小祥判断：不想说话")
                return
            
            logger.info("💬 后台小祥判断：想说话！发送给主程序")
            
            # 更新时间
            self.last_interaction_time = time.time()
            
            # 发送系统提示词给主程序，让主程序生成具体内容
            await self._on_proactive_request(PROACTIVE_CHAT_SYSTEM_PROMPT)
                
        except Exception as e:
            logger.error(f"主动聊天判断失败: {e}")
    
    async def analyze_follow_up(self, user_text: str, ai_response: str) -> None:
        """分析是否需要追问（Yes/No 判断）"""
        if not self.llm_client or not self._on_proactive_request:
            return
        
        if self.silent_mode:
            return
        
        try:
            # 清理响应文本
            clean_response = re.sub(r'\[\w+\]', '', ai_response).strip()
            clean_response = re.sub(r'\[CALL:\w+.*?\]', '', clean_response).strip()
            
            # 🔥 获取完整对话上下文
            recent_context = "(暂无)"
            if self._get_recent_context:
                recent_context = self._get_recent_context()
            
            prompt = SHOULD_FOLLOW_UP_PROMPT.format(
                recent_context=recent_context,
                user_text=user_text,
                ai_response=clean_response
            )
            
            response = ""
            async for chunk in self.llm_client.chat_stream(
                [{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.7
            ):
                response += chunk
            
            response = response.strip().upper()
            
            if "[YES]" not in response:
                logger.debug("🤫 后台小祥判断：不需要追问")
                return
            
            delay = random.randint(self.follow_up_delay_min, self.follow_up_delay_max)
            logger.info(f"⏳ 后台小祥判断：需要追问！{delay}s 后发送给主程序")
            
            self._follow_up_task = asyncio.create_task(
                self._delayed_follow_up(delay)
            )
                
        except Exception as e:
            logger.debug(f"追问判断失败: {e}")
    
    async def _delayed_follow_up(self, delay: float):
        """延迟发送追问请求给主程序"""
        try:
            await asyncio.sleep(delay)
            
            if not self._is_running:
                return
            
            if self._state_machine and self._state_machine.is_busy:
                return
            
            logger.info("💬 发送追问请求给主程序")
            
            # 发送系统提示词给主程序，让主程序生成具体内容
            await self._on_proactive_request(FOLLOW_UP_SYSTEM_PROMPT)
            
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"追问发送失败: {e}")
        finally:
            self._follow_up_task = None
            
    async def transcribe_audio(self, audio_bytes: bytes, history_context: list, target_entry: dict):
        """
        后台语音转录任务 (委托给 '后台小祥')
        
        Args:
            audio_bytes: 音频数据
            history_context: 历史上下文
            target_entry: 目标历史记录条目 (将被直接修改)
        """
        if not self.llm_client:
            logger.warning("后台转录失败: LLM Client 未初始化")
            target_entry["content"] = "(后台小祥无法连接)"
            return
            
        try:
            from llm.prompt_builder import get_prompt_builder
            builder = get_prompt_builder()
            
            # 构建简化的历史记录用于上下文参考
            context_str = ""
            for msg in history_context[-10:]: # 最近10条
                role = "主人" if msg["role"] == "user" else "小祥"
                content = msg.get("content", "")
                if len(content) > 50: content = content[:50] + "..."
                context_str += f"{role}: {content}\n"
            
            system_prompt = f"""[系统任务: 语音转录]
你是一个后台语音转录助手。你的唯一任务是将用户刚刚发送的语音消息准确转录为文字。

[参考上下文]
{context_str}

[要求]
1. 根据上下文纠正可能的同音字（特别是人名、专有名词）。
2. 只输出转录后的文本，不要包含任何标点符号以外的额外解释或回复。
3. 如果语音无法识别，输出 "(无法识别的语音)"。
"""
            # 手动 Base64 编码
            import base64
            base64_audio = base64.b64encode(audio_bytes).decode("utf-8")
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": "请转录这段语音。"},
                    {"type": "input_audio", "input_audio": {"data": base64_audio, "format": "wav"}}
                ]}
            ]
            
            transcribed_text = ""
            # 使用非流式调用或流式调用拼接
            async for chunk in self.llm_client.chat_stream(messages):
                transcribed_text += chunk
            
            transcribed_text = transcribed_text.strip()
            if transcribed_text:
                logger.info(f"📝 后台转录完成: {transcribed_text}")
                target_entry["content"] = transcribed_text
            else:
                logger.warning("📝 后台转录为空")
                target_entry["content"] = "(无法识别的语音)"
                
        except Exception as e:
            logger.error(f"后台转录失败: {e}")
            target_entry["content"] = "(语音转录失败)"


# 全局单例
_proactive_chat_manager: Optional[ProactiveChatManager] = None

def get_proactive_chat_manager(llm_client=None, enabled: bool = None) -> ProactiveChatManager:
    global _proactive_chat_manager
    if _proactive_chat_manager is None:
        _proactive_chat_manager = ProactiveChatManager(llm_client=llm_client, enabled=enabled)
    elif llm_client and _proactive_chat_manager.llm_client is None:
        _proactive_chat_manager.set_llm_client(llm_client)
    return _proactive_chat_manager
