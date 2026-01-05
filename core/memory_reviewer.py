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
核心记忆是**永远不会被遗忘**的重要事实。只有以下类型才适合：

| ✅ 适合 | ❌ 不适合 |
|--------|----------|
| 主人的身份信息（姓名、生日、职业） | 临时状态（"主人今天很累"） |
| 长期稳定的喜好（"主人喜欢猫"） | 短期计划（"主人明天要开会"） |
| 主人的环境/设备信息（"主人的麦克风质量不好"） | 只是最近聊得多但不是长期事实 |
| 主人与我的重要约定 | 一次性提到的信息 |
| 主人明确说"一定要记住"的事 | 推测或不确定的信息 |

## 待审核的记忆
{{memory_info}}

## 相关记忆（供参考）
{{related_memories}}

## 判断流程
1. 这条记忆描述的是**长期稳定事实**还是**临时状态**？
2. 主人是否**多次**提到过这件事？（不是"最近聊得多"，而是"跨越较长时间多次确认"）
3. 这条记忆是否包含**个人情感、偏好、或身份信息**？
4. 如果我忘记这条记忆，会不会显得不尊重主人？

{tools_section}

## 详细示例

### 示例 1: 应该升级（环境信息）
**待审核**: 我知道主人的麦克风质量不太好，语音识别经常出错。
**相关记忆**: 我知道主人用语音输入和我聊天。

**分析**: 这是主人的设备环境信息，是长期稳定的事实（不会每天换麦克风）。而且这影响我理解主人的话，很重要。

[PROMOTE]

---

### 示例 2: 不应该升级（临时状态）
**待审核**: 主人说他今天特别累。
**相关记忆**: （无）

**分析**: 这是临时状态，不是长期事实。明天主人可能就不累了。

[KEEP]

---

### 示例 3: 需要搜索更多信息
**待审核**: 我记得主人喜欢吃拉面。
**相关记忆**: 主人上周说想吃拉面。

**分析**: 只有一次记录，我不确定这是不是长期偏好。让我搜索更多。

[SEARCH:主人 食物 喜欢]

（收到搜索结果后继续分析...）

---

### 示例 4: 不应该升级（近期热点）
**待审核**: 我记得主人最近在玩原神。
**相关记忆**: 上周主人聊了很多原神剧情。

**分析**: 虽然最近聊得很多，但"在玩某个游戏"是容易变化的。除非主人明确说这是他一直最爱的游戏，否则只是最近的兴趣。

[KEEP]

---

### 示例 5: 应该升级（主人的约定）
**待审核**: 我记得主人说他每天晚上11点后就不想被打扰了。
**相关记忆**: （无）

**分析**: 这是主人明确表达的个人习惯和对我的要求。这影响我什么时候可以主动说话，是重要的约定。

[PROMOTE]

---

### 示例 6: 应该升级（跨时间多次确认的偏好）
**待审核**: 我知道主人喜欢吃拉面，尤其是味噌拉面。
**相关记忆**: 
- 半个月前主人说他喜欢拉面
- 昨天主人又提到想吃拉面

**分析**: 这是食物偏好，跨越较长时间多次确认，是稳定的个人喜好。

[PROMOTE]

---

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
