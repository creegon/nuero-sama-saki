# -*- coding: utf-8 -*-
"""
记忆注入器
负责将记忆注入到对话上下文中
"""

from loguru import logger

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class MemoryInjector:
    """
    记忆注入器
    
    实现多层记忆注入：
    - 系统层：背景设定（始终存在）
    - 核心层：高重要性记忆（始终存在）
    - 时间层：最近情境记忆（从知识库 episode 检索）
    - 刷新层：语义相关记忆（每 N 轮刷新）
    - 一般层：最近记忆（首轮注入）
    """
    
    def __init__(self):
        self._kb = None
    
    def _get_kb(self):
        """懒加载知识库"""
        if self._kb is None:
            from knowledge import get_knowledge_base
            self._kb = get_knowledge_base()
        return self._kb
    
    def get_system_context(self) -> str:
        """获取系统上下文"""
        try:
            return self._get_kb().get_system_context()
        except Exception as e:
            logger.debug(f"获取系统上下文失败: {e}")
            return ""
    
    def get_recent_memories(self, n: int = 5) -> str:
        """获取最近记忆（一般层）"""
        try:
            return self._get_kb().get_recent_memories(n=n)
        except Exception as e:
            logger.debug(f"获取最近记忆失败: {e}")
            return ""
    
    def get_important_memories(self) -> str:
        """获取核心层记忆（高重要性，始终注入）"""
        try:
            threshold = getattr(config, 'MEMORY_IMPORTANT_THRESHOLD', 2.5)
            return self._get_kb().get_important_memories(threshold=threshold, n=3)
        except Exception as e:
            logger.debug(f"获取重要记忆失败: {e}")
            return ""
    
    def search_related_memories(self, query: str) -> str:
        """搜索刷新层记忆（语义相关）"""
        try:
            return self._get_kb().search_by_text(query, n_results=3)
        except Exception as e:
            logger.debug(f"搜索相关记忆失败: {e}")
            return ""

    def search_raw_memories(self, query: str, n_results: int = 5) -> list:
        """检索原始记忆数据（包含 ID，用于记忆分析）"""
        try:
            return self._get_kb().search_by_text_raw(query, n_results=n_results)
        except Exception as e:
            logger.debug(f"检索原始记忆失败: {e}")
            return []
    
    def get_time_context(self) -> str:
        """
        🔥 获取时间感知上下文
        - 当前时间
        - 最近的情境记忆（episode）
        """
        import time
        from datetime import datetime
        
        context_parts = []
        
        # 当前时间
        now = datetime.now()
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%Y年%m月%d日")
        weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
        
        context_parts.append(f"现在是 {date_str} {weekday} {time_str}")
        
        # 🔥 从知识库检索最近的 episode 记忆
        try:
            kb = self._get_kb()
            # 搜索最近的 episode
            all_rows = kb._table.to_pandas()
            if not all_rows.empty:
                import json
                episodes = []
                for _, row in all_rows.iterrows():
                    try:
                        metadata = json.loads(row.get("metadata", "{}"))
                        if metadata.get("category") == "episode":
                            timestamp = metadata.get("timestamp", 0)
                            text = row.get("text", "")
                            episodes.append({"text": text, "timestamp": timestamp})
                    except:
                        continue
                
                # 按时间排序，取最近的
                if episodes:
                    episodes.sort(key=lambda x: x["timestamp"], reverse=True)
                    recent_episode = episodes[0]
                    
                    # 计算时间差
                    elapsed = time.time() - recent_episode["timestamp"]
                    if elapsed < 60:
                        time_ago = "刚刚"
                    elif elapsed < 3600:
                        time_ago = f"{int(elapsed / 60)} 分钟前"
                    elif elapsed < 86400:
                        time_ago = f"{int(elapsed / 3600)} 小时前"
                    else:
                        days = int(elapsed / 86400)
                        time_ago = f"{days} 天前"
                    
                    # 只有 7 天内的才提及
                    if elapsed < 86400 * 7:
                        episode_text = recent_episode["text"]
                        # 去除时间戳前缀（如果有）
                        import re
                        episode_text = re.sub(r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}\]\s*', '', episode_text)
                        context_parts.append(f"你{time_ago}和主人聊过：{episode_text[:80]}")
        except Exception as e:
            logger.debug(f"检索 episode 失败: {e}")
        
        return "[时间信息]\n" + "\n".join(context_parts) if context_parts else ""
    
    def inject_memories(self, system_prompt: str, conversation_history: list) -> str:
        """
        多层记忆注入（增强版）
        
        Args:
            system_prompt: 原始系统提示
            conversation_history: 对话历史
        
        Returns:
            增强后的系统提示
        """
        conversation_len = len(conversation_history)
        
        # ===== 始终注入的内容 =====
        
        # 1. 时间感知上下文（始终注入）
        time_context = self.get_time_context()
        if time_context:
            system_prompt += f"\n\n{time_context}"
        
        # 2. 系统上下文/背景设定（始终注入）
        system_context = self.get_system_context()
        if system_context:
            system_prompt += f"\n\n{system_context}"
        
        # 3. 核心层：高重要性记忆（始终注入）
        important_memories = self.get_important_memories()
        if important_memories:
            system_prompt += f"\n\n{important_memories}"
        
        # ===== 动态注入的内容 =====
        
        # 4. 一般层：最近记忆（首轮时注入）
        if conversation_len == 0:
            recent_memories = self.get_recent_memories()
            if recent_memories:
                system_prompt += f"\n\n{recent_memories}"
        
        # 5. 刷新层：每 N 轮从对话中提取关键词搜索相关记忆
        refresh_interval = getattr(config, 'MEMORY_REFRESH_INTERVAL', 5)
        if conversation_len > 0 and conversation_len % refresh_interval == 0:
            recent_user_msgs = [
                m["content"] for m in conversation_history[-3:]
                if m.get("role") == "user" and m["content"] not in ["[语音输入]", ""]
            ]
            if recent_user_msgs:
                query = " ".join(recent_user_msgs)[:200]
                related_memories = self.search_related_memories(query)
                if related_memories:
                    system_prompt += f"\n\n{related_memories}"
        
        return system_prompt


# 全局单例
_memory_injector = None


def get_memory_injector() -> MemoryInjector:
    """获取全局记忆注入器实例"""
    global _memory_injector
    if _memory_injector is None:
        _memory_injector = MemoryInjector()
    return _memory_injector
