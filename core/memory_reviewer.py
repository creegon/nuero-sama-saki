# -*- coding: utf-8 -*-
"""
记忆审核器 - 后台小祥的深度判断模块
当记忆达到临界值时，进行思维链判断是否升级/保留/删除
"""

import asyncio
import re
import time
from typing import List, Dict, Optional
from loguru import logger

from .background_prompt import MEMORY_MANAGER_PERSONA, BackgroundToolRegistry


class MemoryReviewer:
    """
    记忆审核器
    
    当记忆的 importance 达到临界值时触发：
    - 升级阈值 (2.5): 判断是否升级为 core
    - 衰减阈值 (0.5): 判断是删除还是保留
    
    使用思维链 + 工具调用进行深度判断
    """
    
    @classmethod
    def get_promote_review_prompt(cls) -> str:
        """动态生成升级审核 prompt"""
        tools_section = BackgroundToolRegistry.get_memory_reviewer_tools_section("promote")
        
        return f"""{MEMORY_MANAGER_PERSONA}

现在有一条记忆被频繁提及，需要你判断是否应该升级为「核心记忆」。

## 什么是核心记忆？
核心记忆是关于主人的**长期稳定的重要事实**，例如：
- 主人的姓名、生日、重要身份信息
- 主人长期稳定的喜好（不是一时兴起）
- 主人与小祥之间的重要约定
- 主人明确要求"一定要记住"的事情

## 什么不应该成为核心记忆？
- 临时状态（"主人今天很累"）
- 短期计划（"主人明天要开会"）
- 可能变化的偏好（"主人最近在追某部剧"）
- 只是最近话题多，但不是长期事实

## 待审核的记忆
{{memory_info}}

## 相关记忆（供参考）
{{related_memories}}

## 你的任务
1. 先分析这条记忆的性质（是长期事实还是临时状态？）
2. 检查是否有矛盾的记忆
3. 判断主人是否明确表示过这很重要
4. 给出最终决策

{tools_section}

## 输出格式
先写出你的思考过程（2-3句话），然后输出操作指令。

示例：
```
这条记忆是关于主人的食物偏好。虽然被提及多次，但"喜欢吃拉面"可能只是最近的口味，不一定是长期稳定的偏好。而且我没看到主人明确说"一定要记住"。
[KEEP]
```

现在开始你的分析："""

    @classmethod
    def get_decay_review_prompt(cls) -> str:
        """动态生成衰减审核 prompt"""
        tools_section = BackgroundToolRegistry.get_memory_reviewer_tools_section("decay")
        
        return f"""{MEMORY_MANAGER_PERSONA}

有一条记忆长时间没有被提及，重要性已经很低，需要你判断是否应该删除。

## 待审核的记忆
{{memory_info}}

## 相关记忆（供参考）
{{related_memories}}

## 判断标准
1. 这条记忆是否还有价值？
2. 是否有更新的记忆替代了它？
3. 删除它会不会让小祥"忘记"重要的事？

{tools_section}

## 输出格式
先写出你的思考过程（1-2句话），然后输出操作指令。

现在开始你的分析："""

    # 最大思维链轮数
    MAX_THINKING_ROUNDS = 3
    
    def __init__(self, llm_client, knowledge_base):
        self.llm_client = llm_client
        self.kb = knowledge_base
    
    async def review_for_promotion(self, memory: Dict) -> str:
        """
        审核是否应该升级为 core 记忆
        
        Args:
            memory: {"id": "...", "text": "...", "metadata": {...}}
            
        Returns:
            "PROMOTE" | "KEEP" | "DELETE"
        """
        return await self._run_review(memory, self.get_promote_review_prompt(), "升级")
    
    async def review_for_decay(self, memory: Dict) -> str:
        """
        审核是否应该删除衰减的记忆
        
        Args:
            memory: {"id": "...", "text": "...", "metadata": {...}}
            
        Returns:
            "KEEP" | "DELETE"
        """
        return await self._run_review(memory, self.get_decay_review_prompt(), "衰减")
    
    async def _run_review(self, memory: Dict, prompt_template: str, review_type: str) -> str:
        """
        运行审核流程（思维链 + 工具调用）
        
        Args:
            memory: 待审核的记忆
            prompt_template: prompt 模板
            review_type: 审核类型（用于日志）
            
        Returns:
            决策结果
        """
        mem_id = memory.get("id", "unknown")
        mem_text = memory.get("text", "")
        metadata = memory.get("metadata", {})
        
        # 格式化记忆信息
        memory_info = f"""ID: {mem_id}
内容: {mem_text}
重要性: {metadata.get('importance', 1.0):.2f}
创建时间: {self._format_time(metadata.get('timestamp', 0))}
最后访问: {self._format_time(metadata.get('last_access', 0))}
来源: {metadata.get('source', 'unknown')}
已验证: {metadata.get('verified', False)}"""
        
        # 获取相关记忆
        related = await self._get_related_memories(mem_text, exclude_id=mem_id)
        related_text = self._format_related_memories(related)
        
        # 构建初始 prompt
        prompt = prompt_template.format(
            memory_info=memory_info,
            related_memories=related_text
        )
        
        # 思维链循环
        messages = [{"role": "user", "content": prompt}]
        
        for round_num in range(self.MAX_THINKING_ROUNDS):
            try:
                # 调用 LLM
                full_response = ""
                async for chunk in self.llm_client.chat_stream(
                    messages,
                    system_prompt="你是小祥的后台记忆管理程序。请仔细思考后做出决策。"
                ):
                    full_response += chunk
                
                logger.debug(f"🧠 记忆{review_type}审核 Round {round_num + 1}: {full_response[:100]}...")
                
                # 检查是否有工具调用
                search_match = re.search(r'\[SEARCH:(.+?)\]', full_response)
                if search_match and round_num < self.MAX_THINKING_ROUNDS - 1:
                    # 执行搜索
                    query = search_match.group(1).strip()
                    search_results = await self._get_related_memories(query, exclude_id=mem_id, n=3)
                    search_text = self._format_related_memories(search_results)
                    
                    # 继续对话
                    messages.append({"role": "assistant", "content": full_response})
                    messages.append({"role": "user", "content": f"搜索结果:\n{search_text}\n\n请继续你的分析，并给出最终决策。"})
                    continue
                
                # 解析最终决策
                if "[PROMOTE]" in full_response:
                    logger.info(f"🧠 记忆审核决策: [{mem_id}] → PROMOTE (升级为核心)")
                    return "PROMOTE"
                elif "[DELETE]" in full_response:
                    logger.info(f"🧠 记忆审核决策: [{mem_id}] → DELETE (删除)")
                    return "DELETE"
                elif "[KEEP]" in full_response:
                    logger.info(f"🧠 记忆审核决策: [{mem_id}] → KEEP (保留)")
                    return "KEEP"
                else:
                    # 没有明确决策，继续追问
                    if round_num < self.MAX_THINKING_ROUNDS - 1:
                        messages.append({"role": "assistant", "content": full_response})
                        messages.append({"role": "user", "content": "请给出明确的决策：[PROMOTE]、[KEEP] 或 [DELETE]"})
                        continue
                    else:
                        # 最后一轮还没决策，默认 KEEP
                        logger.warning(f"🧠 记忆审核无明确决策，默认 KEEP: [{mem_id}]")
                        return "KEEP"
                        
            except Exception as e:
                logger.error(f"🧠 记忆审核失败: {e}")
                return "KEEP"
        
        return "KEEP"
    
    async def _get_related_memories(self, query: str, exclude_id: str = None, n: int = 5) -> List[Dict]:
        """获取相关记忆"""
        try:
            results = self.kb.search(query, n_results=n)
            if exclude_id:
                results = [r for r in results if r.get("id") != exclude_id]
            return results
        except Exception as e:
            logger.debug(f"获取相关记忆失败: {e}")
            return []
    
    def _format_related_memories(self, memories: List[Dict]) -> str:
        """格式化相关记忆列表"""
        if not memories:
            return "(无相关记忆)"
        
        lines = []
        for mem in memories[:5]:
            mem_id = mem.get("id", "?")
            text = mem.get("text", "")[:60]
            metadata = mem.get("metadata", {})
            importance = metadata.get("importance", 1.0) if isinstance(metadata, dict) else 1.0
            category = metadata.get("category", "fact") if isinstance(metadata, dict) else "fact"
            lines.append(f"- [{mem_id}] ({category}, imp={importance:.1f}) {text}...")
        
        return "\n".join(lines)
    
    def _format_time(self, timestamp: float) -> str:
        """格式化时间戳"""
        if not timestamp:
            return "未知"
        from datetime import datetime
        try:
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%Y-%m-%d %H:%M")
        except:
            return "未知"


# 全局单例
_memory_reviewer: Optional[MemoryReviewer] = None


def get_memory_reviewer(llm_client=None, knowledge_base=None) -> Optional[MemoryReviewer]:
    """获取全局记忆审核器实例"""
    global _memory_reviewer
    if _memory_reviewer is None:
        if llm_client is None or knowledge_base is None:
            return None
        _memory_reviewer = MemoryReviewer(llm_client, knowledge_base)
    return _memory_reviewer
