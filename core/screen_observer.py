# -*- coding: utf-8 -*-
"""
静默屏幕观察器 - 后台小祥的"默默观察"功能

🔥 设计理念：
- 定期截屏观察主人在做什么
- 推断主人的日常活动和喜好
- 不打扰主程序小祥，只是默默记住
- 就像宠物默默观察主人一样
"""

import asyncio
import re
import time
from typing import Optional
from loguru import logger

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

from .background_prompt import KNOWLEDGE_MONITOR_PERSONA


# ============================================================
# 观察者 Prompt
# ============================================================

SCREEN_OBSERVER_PROMPT = f"""{KNOWLEDGE_MONITOR_PERSONA}

你的任务是默默观察主人的屏幕，了解主人在做什么、喜欢什么。

【当前屏幕】
（图片）

【我已经知道的关于主人的信息】
{{known_facts}}

请分析这张截图，思考：
1. 主人正在做什么？（具体描述活动）
2. 这能告诉我关于主人的什么？（兴趣/习惯/职业/偏好）
3. 有没有什么**新发现**是我之前不知道的？

**判断标准：**
- ✅ 值得记住：发现主人的兴趣爱好（如喜欢某类游戏/音乐/动漫）
- ✅ 值得记住：发现主人的工作/学习领域（如程序员/学生/设计师）
- ✅ 值得记住：发现主人常用的软件/网站
- ❌ 不需要记：普通的日常操作（打开文件夹、浏览网页）
- ❌ 不需要记：已经知道的信息（重复观察）
- ❌ 不需要记：临时状态（正在加载、正在下载）

**输出格式：**
如果有新发现，用以下格式输出（可以多条）：
[OBSERVE] 我观察到主人xxx（推断：主人可能喜欢/经常/擅长xxx）

如果没有新发现或只是普通活动，输出：
[SKIP] 原因（如：只是普通操作/已经知道了）
"""


class ScreenObserver:
    """
    静默屏幕观察器
    
    定期截屏让后台小祥分析，推断主人的行为偏好
    """
    
    # 默认配置
    DEFAULT_INTERVAL = 120  # 2 分钟
    
    def __init__(self, llm_client, knowledge_base):
        self.llm_client = llm_client
        self.kb = knowledge_base
        
        # 从配置读取参数
        self.enabled = getattr(config, 'SCREEN_OBSERVER_ENABLED', True)
        self.interval = getattr(config, 'SCREEN_OBSERVER_INTERVAL', self.DEFAULT_INTERVAL)
        
        self._task: Optional[asyncio.Task] = None
        self._is_running = False
        self._last_observation = ""  # 避免重复观察
        
        logger.info(f"👁️ 静默屏幕观察器已初始化 (间隔={self.interval}s)")
    
    def start(self):
        """启动观察器"""
        if not self.enabled:
            logger.info("👁️ 静默屏幕观察器已禁用")
            return
        
        if self._task is not None:
            return
        
        try:
            loop = asyncio.get_running_loop()
            self._is_running = True
            self._task = loop.create_task(self._observe_loop())
            logger.info(f"👁️ 静默屏幕观察器已启动 (每 {self.interval}s 观察一次)")
        except RuntimeError:
            logger.warning("⚠️ 事件循环未运行，观察器将延迟启动")
    
    async def stop(self):
        """停止观察器"""
        self._is_running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("👁️ 静默屏幕观察器已停止")
    
    async def _observe_loop(self):
        """观察循环"""
        # 首次等待一段时间再开始
        await asyncio.sleep(30)
        
        while self._is_running:
            try:
                await self._do_observation()
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"👁️ 观察失败: {e}")
                await asyncio.sleep(60)  # 出错后等待更久
    
    async def _do_observation(self):
        """执行一次观察"""
        try:
            # 1. 截屏
            from vision import get_screen_capture
            screen_capture = get_screen_capture()
            screenshot = screen_capture.capture(mode="full")
            
            logger.debug(f"👁️ 截屏完成: {screenshot.width}x{screenshot.height}")
            
            # 2. 获取已知信息（用于避免重复）
            known_facts = self._get_known_facts()
            
            # 3. 构建 prompt
            prompt = SCREEN_OBSERVER_PROMPT.format(known_facts=known_facts)
            
            # 4. 调用 LLM 分析（带图片）
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{screenshot.format};base64,{screenshot.base64_data}"
                        }
                    }
                ]
            }]
            
            response = ""
            async for chunk in self.llm_client.chat_stream(messages, max_tokens=200):
                response += chunk
            
            logger.debug(f"👁️ 观察结果: {response[:100]}...")
            
            # 5. 解析并存储
            await self._process_observation(response)
            
        except Exception as e:
            logger.error(f"👁️ 观察执行失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _get_known_facts(self) -> str:
        """获取已知的主人信息（用于避免重复观察）"""
        try:
            # 获取 observation 类型的记忆
            all_rows = self.kb._table.to_pandas()
            observations = []
            
            for _, row in all_rows.iterrows():
                import json
                metadata = json.loads(row.get("metadata", "{}"))
                if metadata.get("category") == "observation":
                    text = row.get("text", "")
                    if text:
                        observations.append(f"- {text[:80]}")
            
            # 最多显示最近 5 条
            if observations:
                recent = observations[-5:]
                return "\n".join(recent)
            return "(暂无)"
            
        except Exception as e:
            logger.debug(f"获取已知信息失败: {e}")
            return "(暂无)"
    
    async def _process_observation(self, response: str):
        """处理观察结果"""
        lines = response.strip().split("\n")
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # [SKIP] - 跳过
            if "[SKIP]" in line:
                reason = line.replace("[SKIP]", "").strip()
                logger.debug(f"👁️ 观察跳过: {reason[:50]}")
                continue
            
            # [OBSERVE] - 新发现
            if "[OBSERVE]" in line:
                content = line.replace("[OBSERVE]", "").strip()
                if content:
                    # 避免完全重复的观察
                    if content == self._last_observation:
                        logger.debug(f"👁️ 跳过重复观察: {content[:30]}...")
                        continue
                    
                    # 存入知识库（使用去重）
                    doc_id = self.kb.add_with_dedup(
                        text=content,
                        metadata={
                            "category": "observation",
                            "source": "screen_observer",
                            "importance": 0.8,  # 观察得到的信息初始重要性较低
                            "timestamp": time.time(),
                        },
                        similarity_threshold=0.85
                    )
                    
                    self._last_observation = content
                    logger.info(f"👁️ 屏幕观察器 [OBSERVE]: [{doc_id}]")
                    logger.debug(f"   📝 内容: {content}")


# 全局单例
_screen_observer: Optional[ScreenObserver] = None


def get_screen_observer(llm_client=None, knowledge_base=None) -> Optional[ScreenObserver]:
    """获取全局屏幕观察器实例"""
    global _screen_observer
    if _screen_observer is None:
        if llm_client is None or knowledge_base is None:
            return None
        _screen_observer = ScreenObserver(llm_client, knowledge_base)
    return _screen_observer
