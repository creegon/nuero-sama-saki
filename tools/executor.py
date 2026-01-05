# -*- coding: utf-8 -*-
"""
工具执行器 - 支持并行执行（边说话边执行工具）
"""

import asyncio
import re
import sys
import os
from typing import Optional, Tuple, Callable, Any
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .base import BaseTool, ToolResult
from .registry import get_tool_registry, get_tool


class ToolExecutor:
    """
    工具执行器
    
    支持:
    - 解析 LLM 输出中的 [CALL:tool_name]
    - 并行执行: 边播放提示语边执行工具
    - 返回工具结果供 LLM 继续生成
    """
    
    # 工具调用正则: [CALL:tool_name] 或 [CALL:tool_name:args]
    TOOL_CALL_PATTERN = re.compile(r'\[CALL:(\w+)(?::([^\]]*))?\]')
    
    def __init__(self):
        # 确保工具已注册
        self._registry = get_tool_registry()
    
    def parse_tool_calls(self, text: str) -> list:
        """
        从文本中解析工具调用
        
        Args:
            text: LLM 输出文本
        
        Returns:
            [(tool_name, args, match_obj), ...]
        """
        calls = []
        for match in self.TOOL_CALL_PATTERN.finditer(text):
            tool_name = match.group(1)
            args = match.group(2) or ""
            calls.append((tool_name, args, match))
        return calls
    
    def has_tool_call(self, text: str) -> bool:
        """检查文本是否包含工具调用"""
        return bool(self.TOOL_CALL_PATTERN.search(text))
    
    def split_at_tool_call(self, text: str) -> Tuple[str, Optional[str], Optional[str], str]:
        """
        在第一个工具调用处分割文本
        
        Returns:
            (before_text, tool_name, tool_args, after_text)
            如果没有工具调用: (text, None, None, "")
        """
        match = self.TOOL_CALL_PATTERN.search(text)
        if not match:
            return (text, None, None, "")
        
        before = text[:match.start()].strip()
        tool_name = match.group(1)
        tool_args = match.group(2) or ""  # 可选参数
        after = text[match.end():].strip()
        
        return (before, tool_name, tool_args, after)
    
    def remove_tool_calls(self, text: str) -> str:
        """移除文本中的所有工具调用标记"""
        return self.TOOL_CALL_PATTERN.sub('', text).strip()
    
    def get_tool_hint(self, tool_name: str) -> str:
        """获取工具的并行提示语"""
        tool = get_tool(tool_name)
        if tool:
            return tool.parallel_hint
        return ""
    
    async def execute_tool(
        self,
        tool_name: str,
        context: str = "",
        args: str = "",
        **kwargs
    ) -> str:
        """
        执行工具
        
        Args:
            tool_name: 工具名称
            context: 对话上下文
            args: 工具参数（从 [CALL:tool:args] 提取）
            **kwargs: 额外参数
        
        Returns:
            工具执行结果 (字符串)
        """
        tool = get_tool(tool_name)
        if not tool:
            logger.warning(f"未知工具: {tool_name}")
            return f"[未知工具: {tool_name}]"
        
        logger.info(f"🔧 执行工具: {tool_name}" + (f" (args: {args})" if args else ""))
        
        try:
            result = await tool.execute(context=context, args=args, **kwargs)
            
            if result.success:
                logger.info(f"🔧 工具结果: {str(result.data)[:50]}...")
                return str(result.data)
            else:
                logger.error(f"工具执行失败: {result.error}")
                return f"[工具执行失败: {result.error}]"
                
        except Exception as e:
            logger.error(f"工具执行异常: {e}")
            return f"[工具执行异常: {e}]"
    
    async def execute_with_callback(
        self,
        tool_name: str,
        on_start: Optional[Callable[[], Any]] = None,
        context: str = ""
    ) -> str:
        """
        执行工具，支持开始时回调
        
        用于并行执行: 开始时触发 TTS 播放提示语
        
        Args:
            tool_name: 工具名称
            on_start: 开始执行时的回调
            context: 对话上下文
        
        Returns:
            工具执行结果
        """
        # 触发开始回调 (通常是播放提示语)
        if on_start:
            on_start()
        
        # 执行工具
        result = await self.execute_tool(tool_name, context)
        
        return result

    async def handle_tool_execution(
        self,
        response: str,
        user_text: str,
        conversation_history: list,
        # Callbacks
        on_speak: Callable[[str, str], None],
        on_play_audio: Callable[[], Any],
        on_expression: Callable[[str], None],
        is_speaking_check: Callable[[], bool],
        start_speaking_call: Callable[[], None],
        # Monitors
        knowledge_monitor=None,
        memory_helper=None,
        last_retrieved_memories=None,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        处理完整的工具调用流程 (拆分 -> 播放前置 -> 执行 -> 播放后置)
        
        Returns:
            (tool_result, tool_name, after_text)
            如果被取消或出错，可能返回 None
        """
        before_text, tool_name, tool_args, after_text = self.split_at_tool_call(response)
        
        if not tool_name:
            return None, None, None
            
        logger.info(f"🔧 检测到工具调用: {tool_name}" + (f" (args: {tool_args})" if tool_args else ""))
        
        # 情绪检测（取第一个情绪标签）
        emotion_match = re.match(r'^\[(\w+)\]', before_text)
        detected_emotion = emotion_match.group(1).lower() if emotion_match else "curious"
        
        # 🔥 清理文本：移除所有情绪标签（不仅仅是开头的）
        from llm.character_prompt import EMOTION_TAGS
        emotion_pattern = r'\[(' + '|'.join(EMOTION_TAGS) + r')\]'
        clean_before = re.sub(emotion_pattern, '', before_text, flags=re.IGNORECASE)
        clean_before = re.sub(r'\s+', ' ', clean_before).strip()  # 合并空格
        
        # 设置表情
        if on_expression:
            on_expression(detected_emotion)
        
        logger.info(f"⚡ 并行执行: TTS + {tool_name}")
        
        # 播放前置文本
        if clean_before:
            on_speak(clean_before, detected_emotion)
        
        # 创建工具任务
        tool_task = asyncio.create_task(
            self.execute_tool(
                tool_name,
                context=user_text,
                args=tool_args,
                conversation_history=conversation_history
            )
        )
        
        # 确保开始说话状态
        if start_speaking_call and is_speaking_check and not is_speaking_check():
            start_speaking_call()
            
        # 播放音频
        await on_play_audio()
        
        # 等待结果
        try:
            tool_result = await tool_task
        except asyncio.CancelledError:
            logger.warning("工具执行被取消")
            return None, tool_name, None
            
        # 避免打印巨大的 base64 图片数据
        if tool_result.startswith("IMAGE_RESULT:"):
            logger.info(f"🔧 工具结果: [图片数据]")
        else:
            logger.info(f"🔧 工具结果: {tool_result[:50]}...")

        # 添加到历史
        conversation_history.append({"role": "user", "content": user_text})
        conversation_history.append({"role": "assistant", "content": response})

        # 知识库监控
        if knowledge_monitor and before_text:
            # 检索原始记忆（如果还没有检索过）
            memories = last_retrieved_memories
            if not memories and user_text and user_text not in ["[语音输入]", ""] and memory_helper:
                try:
                    memories = memory_helper.search_raw_memories(user_text, n_results=5)
                except Exception as e:
                    logger.warning(f"记忆检索失败: {e}")
            
            asyncio.create_task(
                knowledge_monitor.analyze_conversation(
                    user_text, before_text, memories
                )
            )

        # 处理后置文本
        if after_text:
            clean_after = re.sub(r'\s+', '', after_text.strip())
            if clean_after:
                logger.info(f"📢 播放工具调用后的文本: {clean_after[:30]}...")
                # 解析情绪并分段 (简单处理，假设调用者处理具体分段逻辑，或者这里不做分段直接返回让调用者处理)
                # 为了简化，这里我们通过回调让调用者处理"分段+提交"
                # 但 on_speak 签名是 (text, emotion)，所以需要一点逻辑
                # 或者我们假设 after_text 也包含情绪标签
                pass # 这里不做处理，返回 after_text 让 ResponseHandler 处理

        return tool_result, tool_name, after_text


# 全局单例
_tool_executor: Optional[ToolExecutor] = None


def get_tool_executor() -> ToolExecutor:
    """获取全局 ToolExecutor 实例"""
    global _tool_executor
    if _tool_executor is None:
        _tool_executor = ToolExecutor()
    return _tool_executor


# 测试入口
if __name__ == "__main__":
    import asyncio
    
    async def test():
        print("=" * 50)
        print("工具执行器测试 (重构版)")
        print("=" * 50)
        
        executor = ToolExecutor()
        
        # 测试解析
        print("\n[1] 解析工具调用...")
        test_texts = [
            "[curious] 让我看看...[CALL:screenshot]",
            "[happy] 好的！[CALL:screenshot] 我来看看",
            "没有工具调用的文本",
            "[CALL:unknown_tool]"
        ]
        
        for text in test_texts:
            calls = executor.parse_tool_calls(text)
            has_call = executor.has_tool_call(text)
            print(f"    '{text[:40]}...'")
            print(f"      has_call={has_call}, calls={[c[0] for c in calls]}")
        
        # 测试分割
        print("\n[2] 分割测试...")
        text = "[curious] 唔...让我看看。[CALL:screenshot]然后告诉你"
        before, tool, after = executor.split_at_tool_call(text)
        print(f"    原文: {text}")
        print(f"    before: '{before}'")
        print(f"    tool: {tool}")
        print(f"    after: '{after}'")
        
        # 测试执行
        print("\n[3] 执行 screenshot 工具...")
        result = await executor.execute_tool("screenshot", "测试上下文")
        print(f"    结果: {result[:80]}...")
        
        print("\n" + "=" * 50)
        print("测试完成!")
    
    asyncio.run(test())
