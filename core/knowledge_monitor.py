# -*- coding: utf-8 -*-
"""
知识监控器 - 后台小祥
自动监控对话并管理知识库（添加/更新/删除/重要性调整）
使用 LLM 判断，而非机械规则
"""

import asyncio
import re
from typing import List, Dict, Optional
from loguru import logger
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

from .background_prompt import KNOWLEDGE_MONITOR_PERSONA, BackgroundToolRegistry


class KnowledgeMonitor:
    """
    知识监控器 - 后台小祥

    实时监控对话内容，自动管理知识库：
    - 判断是否需要记住新信息
    - 判断检索到的记忆是否真正相关
    - 更新记忆的重要性
    - 修正/删除过时的记忆
    
    核心理念：复杂的记忆判断交给 LLM，而非机械规则
    """
    
    @classmethod
    def get_system_prompt(cls) -> str:
        """动态生成 system prompt"""
        tools_section = BackgroundToolRegistry.get_knowledge_monitor_tools_section()
        
        return f"""{KNOWLEDGE_MONITOR_PERSONA}

你的任务是管理小祥的记忆：
1. 判断对话中是否有值得记住的新信息
2. 判断检索到的记忆是否真正被用到了
3. 判断是否需要更新/修正/删除某条记忆

{tools_section}

**记忆撰写规范：**
- ⚠️ **使用第三人称客观描述**（不要用"我知道"开头）
- 一条记忆只记录一个主题，不要杂糅多个无关信息
- 包含足够的上下文，让未来能理解这条信息的含义

**记忆分类（在 [ADD] 后用 [类型] 标注）：**
- `[fact]` - 客观事实：主人的偏好、习惯、环境信息等
- `[feeling]` - 小祥的主观感受/情绪反应（可以带有角色色彩）

**什么值得记住：**
✅ 长期事实/偏好："主人喜欢吃拉面" 
✅ 环境信息："主人的麦克风质量不太好"
✅ 角色情绪/看法："小祥觉得主人修改参数的行为是黑历史" → [feeling]
❌ 临时状态："主人现在在写代码"
❌ 单次事件："主人今天迟到了"
❌ 占位符文本："[语音输入]"
❌ 语音识别错误："被误听成xxx"
❌ 纯技术细节：文件名列表、代码片段

**判断原则：**
1. 记忆不是越多越好。只记住真正重要的、长期有用的信息。
2. 两条信息看似冲突不一定要删除，可能只是时间变化。
3. 如果检索到的记忆**真正影响了小祥的回复**，才算被使用。
4. 主人纠正了错误记忆时，用 UPDATE 修改（不要删除再添加）。
5. core 类型记忆不能删除，只能用 UPDATE 修改。

**输出格式：**
可以输出多个操作，每行一个。如果不需要任何操作，只输出 [SKIP]。

**示例：**

---
对话：
主人: 我最喜欢吃寿司，尤其是三文鱼寿司
小祥: 诶嘿嘿，我记住了呢～

检索到的记忆：(无)

你的操作：
[ADD][fact] 主人最喜欢吃寿司，尤其是三文鱼寿司

---
对话：
主人: 不对，我现在更喜欢豚骨拉面了
小祥: 欸？口味变了吗

检索到的记忆：
- [mem_123] 主人最喜欢吃寿司，尤其是三文鱼寿司

你的操作：
[UPDATE:mem_123] 主人现在更喜欢吃豚骨拉面（之前喜欢寿司，后来口味变了）

---
对话：
主人: 这个语音识别老是听错，麦克风太烂了
小祥: 唔...那确实有点困扰呢

检索到的记忆：(无)

你的操作：
[ADD][fact] 主人的麦克风质量不太好，语音识别经常出错

---
对话：
主人: 你看看这个参数改得像翻白眼...
小祥: 哼！这是我的黑历史！质疑主人的审美！

检索到的记忆：(无)

你的操作：
[ADD][feeling] 小祥认为主人修改眼神参数的效果是"黑历史"，对此感到尴尬和不满

---
对话：
小祥尝试调用视觉模块失败
小祥: 气死我了！为什么又报错！

检索到的记忆：(无)

你的操作：
[ADD][feeling] 小祥在调用视觉模块失败时会感到愤怒

---
对话：
主人: 今天好累，我在写代码呢
小祥: 辛苦了

检索到的记忆：(无)

你的操作：
[SKIP]
（"今天好累"和"在写代码"都是临时状态，不是长期事实）

---
对话：
主人: [语音输入]
小祥: 嗯？

检索到的记忆：(无)

你的操作：
[SKIP]
（"[语音输入]"是占位符，不是实际内容）

---
对话：
主人: 我最近在做一个桌宠项目，用的 Live2D
小祥: 听起来很有趣

检索到的记忆：
- [mem_456] 主人喜欢编程

你的操作：
[BOOST:mem_456]
[ADD][fact] 主人最近在开发一个桌宠项目，使用 Live2D 技术

---
现在，请分析以下对话和检索到的记忆，决定需要执行的操作。
"""

    def __init__(self, llm_client, knowledge_base):
        """
        初始化知识监控器

        Args:
            llm_client: LLM客户端（用于分析对话）
            knowledge_base: 知识库实例
        """
        self.llm_client = llm_client
        self.kb = knowledge_base

        self._enabled = True
        self._queue = None  # 延迟创建（需要事件循环）
        self._monitor_task = None

        logger.info("🧠 知识监控器已初始化（队列将在事件循环中创建）")

    def start(self):
        """启动后台监控任务（需要在事件循环中调用）"""
        if self._monitor_task is None:
            try:
                # 尝试获取当前事件循环
                loop = asyncio.get_running_loop()

                # 创建队列（如果还未创建）
                if self._queue is None:
                    self._queue = asyncio.Queue()

                self._monitor_task = loop.create_task(self._monitor_loop())
                logger.info("🧠 知识监控器后台任务已启动")
            except RuntimeError:
                # 如果没有运行中的事件循环，延迟启动
                logger.warning("⚠️ 事件循环未运行，知识监控器将延迟启动")
                self._monitor_task = "pending"  # 标记为待启动

    def stop(self):
        """停止后台监控任务"""
        self._enabled = False
        if self._monitor_task and self._monitor_task != "pending":
            self._monitor_task.cancel()
            self._monitor_task = None
        logger.info("🧠 知识监控器已停止")

    async def analyze_conversation(
        self,
        user_message: str,
        assistant_message: str,
        retrieved_memories: List[Dict] = None
    ) -> None:
        """
        分析一轮对话，判断如何管理记忆

        Args:
            user_message: 用户消息
            assistant_message: 助手消息
            retrieved_memories: 检索到的记忆列表 [{"id": "...", "text": "...", "distance": 0.x}]
        """
        if not self._enabled:
            return

        # 确保队列已创建
        if self._queue is None:
            logger.warning("⚠️ 知识监控器队列未创建，跳过分析")
            return

        # 🔥 调试日志
        logger.debug(f"🧠 后台小祥收到对话:")
        logger.debug(f"   主人: {user_message[:50]}...")
        logger.debug(f"   检索到 {len(retrieved_memories or [])} 条相关记忆")
        if retrieved_memories:
            for mem in retrieved_memories[:3]:
                logger.debug(f"      - [{mem.get('id')}] {mem.get('text', '')[:40]}...")

        # 加入队列异步处理
        await self._queue.put({
            "user": user_message,
            "assistant": assistant_message,
            "retrieved_memories": retrieved_memories or []
        })

    async def _monitor_loop(self):
        """后台监控循环"""
        logger.info("🧠 知识监控器循环已启动")

        while self._enabled:
            try:
                # 从队列获取对话
                conversation = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )

                # 分析对话
                await self._process_conversation(conversation)

            except asyncio.TimeoutError:
                # 队列空闲，继续等待
                continue
            except asyncio.CancelledError:
                logger.info("🧠 知识监控器任务被取消")
                break
            except Exception as e:
                logger.error(f"🧠 知识监控器异常: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(1)

    async def _process_conversation(self, conversation: Dict):
        """
        处理单轮对话

        Args:
            conversation: {"user": "...", "assistant": "...", "retrieved_memories": [...]}
        """
        user_msg = conversation["user"]
        assistant_msg = conversation["assistant"]
        retrieved_memories = conversation.get("retrieved_memories", [])

        # 清理消息（去除系统标记、情感标签等）
        user_msg = re.sub(r'\[系统:.*?\]', '', user_msg).strip()
        assistant_msg = re.sub(r'^\[\w+\]', '', assistant_msg).strip()
        assistant_msg = re.sub(r'\[CALL:\w+.*?\]', '', assistant_msg).strip()

        # 构建记忆上下文
        memory_context = "(无)"
        if retrieved_memories:
            memory_lines = []
            for mem in retrieved_memories:
                mem_id = mem.get("id", "unknown")
                mem_text = mem.get("text", "")
                memory_lines.append(f"- [{mem_id}] {mem_text}")
            memory_context = "\n".join(memory_lines)

        # 构建分析 prompt
        analysis_prompt = f"""对话：
主人: {user_msg}
小祥: {assistant_msg}

检索到的记忆：
{memory_context}

你的操作："""

        try:
            # 调用 LLM 分析
            messages = [{"role": "user", "content": analysis_prompt}]

            full_response = ""
            async for chunk in self.llm_client.chat_stream(
                messages,
                system_prompt=self.get_system_prompt()  # 🔥 使用动态生成的 prompt
            ):
                full_response += chunk

            # 解析并执行操作
            await self._execute_operations(full_response)

        except Exception as e:
            logger.error(f"🧠 对话分析失败: {e}")

    async def _execute_operations(self, response: str):
        """
        解析并执行后台小祥的操作指令

        Args:
            response: LLM 的响应文本
        """
        lines = response.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            try:
                # [SKIP]
                if "[SKIP]" in line:
                    reason = line.replace("[SKIP]", "").strip()
                    logger.debug(f"🧠 后台小祥 [SKIP]: {reason if reason else '无理由'}")
                    continue

                # [ADD] 内容  或  [ADD][类型] 内容
                add_match = re.match(r'\[ADD\](?:\[(fact|feeling)\])?\s*(.+)', line)
                if add_match:
                    category = add_match.group(1) or "fact"  # 默认 fact
                    content = add_match.group(2).strip()
                    if content:
                        doc_id = self.kb.add_with_dedup(
                            text=content,
                            metadata={
                                "category": category,  # 🔥 支持 fact/feeling
                                "source": "background_ai",
                                "verified": False,  # 后台小祥推断的，未经用户确认
                            },
                            similarity_threshold=0.85
                        )
                        logger.info(f"🧠 后台小祥 [ADD][{category}]: [{doc_id}]")
                        logger.debug(f"   📝 内容: {content}")
                        
                        # 🔥 异步抽取三元组
                        asyncio.create_task(self._extract_triples(doc_id, content))
                    continue


                # [UPDATE:mem_id] 新内容
                update_match = re.match(r'\[UPDATE:(\w+)\]\s*(.+)', line)
                if update_match:
                    mem_id = update_match.group(1)
                    new_content = update_match.group(2).strip()
                    if new_content:
                        # 获取旧内容用于对比（使用客户端 API）
                        old_content = ""
                        try:
                            records = self.kb.get_all()
                            for r in records:
                                if r["id"] == mem_id:
                                    old_content = r.get("text", "")
                                    break
                        except:
                            pass
                        
                        success = self.kb.update_text(mem_id, new_content)
                        if success:
                            logger.info(f"🧠 后台小祥 [UPDATE]: {mem_id}")
                            logger.debug(f"   📝 旧内容: {old_content}")
                            logger.debug(f"   📝 新内容: {new_content}")
                        else:
                            logger.warning(f"🧠 后台小祥 [UPDATE] 失败: {mem_id} 不存在")
                    continue

                # [BOOST:mem_id]
                boost_match = re.match(r'\[BOOST:(\w+)\]', line)
                if boost_match:
                    mem_id = boost_match.group(1)
                    # 获取内容用于日志（使用客户端 API）
                    mem_content = ""
                    try:
                        records = self.kb.get_all()
                        for r in records:
                            if r["id"] == mem_id:
                                mem_content = r.get("text", "")
                                break
                    except:
                        pass
                    
                    success = self.kb.update_importance(mem_id, delta=0.3)
                    if success:
                        logger.info(f"🧠 后台小祥 [BOOST]: {mem_id} 重要性 +0.3")
                        logger.debug(f"   📝 内容: {mem_content}")
                    continue

                # [DELETE:mem_id]
                delete_match = re.match(r'\[DELETE:(\w+)\]', line)
                if delete_match:
                    mem_id = delete_match.group(1)
                    
                    # 🔥 检查是否为 core 记忆，core 不允许删除（使用客户端 API）
                    is_core = False
                    delete_content = ""
                    try:
                        records = self.kb.get_all()
                        for r in records:
                            if r["id"] == mem_id:
                                meta = r.get("metadata", {})
                                if meta.get("category") == "core":
                                    is_core = True
                                delete_content = r.get("text", "")
                                break
                    except:
                        pass
                    
                    if is_core:
                        logger.warning(f"⛔ 后台小祥 [DELETE] 拒绝: {mem_id} 是 core 记忆，不允许删除")
                        logger.debug(f"   📝 内容: {delete_content}")
                    else:
                        self.kb.delete(mem_id)
                        logger.info(f"🧠 后台小祥 [DELETE]: {mem_id}")
                        logger.debug(f"   📝 已删除内容: {delete_content}")
                        
                        # 🔥 级联删除关联三元组
                        try:
                            from knowledge.triple_store import get_triple_store
                            triple_store = get_triple_store()
                            deleted_triples = triple_store.remove_source(mem_id)
                            if deleted_triples:
                                logger.info(f"🔗 级联删除 {len(deleted_triples)} 条三元组")
                        except Exception as te:
                            logger.debug(f"级联删除三元组失败: {te}")
                    continue

            except Exception as e:
                logger.error(f"🧠 执行操作失败 [{line}]: {e}")
    
    async def _extract_triples(self, memory_id: str, content: str):
        """
        🔥 异步从记忆内容中抽取三元组
        
        Args:
            memory_id: 记忆 ID（作为三元组的佐证来源）
            content: 记忆文本内容
        """
        try:
            from knowledge.entity_extractor import get_entity_extractor
            from knowledge.triple_store import get_triple_store
            
            extractor = get_entity_extractor()
            if not extractor.llm_client:
                extractor.set_llm_client(self.llm_client)
            
            # 抽取三元组
            triples = await extractor.extract(content)
            
            if triples:
                triple_store = get_triple_store()
                for t in triples:
                    triple_store.add(
                        subject=t.subject,
                        predicate=t.predicate,
                        obj=t.object,
                        source_memory_id=memory_id,
                        metadata=t.metadata
                    )
                logger.info(f"🔗 抽取三元组: {len(triples)} 条 ← [{memory_id}]")
                for t in triples:
                    logger.debug(f"   → {t}")
        except Exception as e:
            logger.debug(f"三元组抽取失败: {e}")

    def is_enabled(self) -> bool:
        """检查监控器是否启用"""
        return self._enabled

    def enable(self):
        """启用监控器"""
        self._enabled = True
        logger.info("🧠 知识监控器已启用")

    def disable(self):
        """禁用监控器"""
        self._enabled = False
        logger.info("🧠 知识监控器已禁用")


# 全局单例
_knowledge_monitor: Optional[KnowledgeMonitor] = None


def get_knowledge_monitor(llm_client=None, knowledge_base=None) -> KnowledgeMonitor:
    """获取全局知识监控器实例"""
    global _knowledge_monitor
    if _knowledge_monitor is None:
        if llm_client is None or knowledge_base is None:
            raise ValueError("首次初始化需要提供 llm_client 和 knowledge_base")
        _knowledge_monitor = KnowledgeMonitor(llm_client, knowledge_base)
    return _knowledge_monitor
