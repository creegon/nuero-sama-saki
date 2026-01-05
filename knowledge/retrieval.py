# -*- coding: utf-8 -*-
"""
记忆检索器
负责各种记忆检索和格式化
"""

from typing import Dict, List
from loguru import logger


class MemoryRetriever:
    """
    记忆检索器
    
    提供各种记忆检索功能：
    - 最近记忆
    - 重要记忆
    - 语义搜索
    - 系统上下文
    """
    
    def __init__(self, knowledge_base):
        self.kb = knowledge_base
    
    def get_recent_memories(self, n: int = 5, exclude_system: bool = True) -> str:
        """获取最近 N 条记忆（按重要性+时间排序）"""
        try:
            all_rows = self.kb._table.to_pandas()
            if all_rows.empty:
                return ""
            
            memories = []
            for _, row in all_rows.iterrows():
                try:
                    text = row.get("text", "")
                    metadata = self.kb._json.loads(row.get("metadata", "{}"))
                    
                    if exclude_system and metadata.get("category") == "system":
                        continue
                    
                    importance = metadata.get("importance", 1.0)
                    timestamp = metadata.get("timestamp", 0)
                    
                    # 🔥 确保类型一致（防止 str vs float 比较错误）
                    try:
                        importance = float(importance)
                    except (TypeError, ValueError):
                        importance = 1.0
                    try:
                        timestamp = float(timestamp)
                    except (TypeError, ValueError):
                        timestamp = 0.0
                    
                    memories.append({
                        "text": text,
                        "importance": importance,
                        "timestamp": timestamp
                    })
                except:
                    continue
            
            if not memories:
                return ""
            
            memories.sort(key=lambda x: (x["importance"], x["timestamp"]), reverse=True)
            recent = memories[:n]
            
            if not recent:
                return ""
            
            lines = ["[你记得的事情]"]
            for mem in recent:
                lines.append(f"- {mem['text']}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.debug(f"获取最近记忆失败: {e}")
            return ""
    
    def get_important_memories(self, threshold: float = 2.5, n: int = 3) -> str:
        """获取核心层记忆（高重要性记忆）"""
        try:
            all_rows = self.kb._table.to_pandas()
            if all_rows.empty:
                return ""
            
            important = []
            for _, row in all_rows.iterrows():
                try:
                    text = row.get("text", "")
                    metadata = self.kb._json.loads(row.get("metadata", "{}"))
                    
                    if metadata.get("category") == "system":
                        continue
                    
                    importance = metadata.get("importance", 1.0)
                    if importance >= threshold:
                        important.append({
                            "text": text,
                            "importance": importance
                        })
                except:
                    continue
            
            if not important:
                return ""
            
            important.sort(key=lambda x: x["importance"], reverse=True)
            top_memories = important[:n]
            
            lines = ["[你一定要记住的事]"]
            for mem in top_memories:
                lines.append(f"- {mem['text']}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.debug(f"获取重要记忆失败: {e}")
            return ""
    
    def search_by_text(self, query: str, n_results: int = 3) -> str:
        """根据文本语义搜索相关记忆"""
        try:
            results = self.kb.search(query, n_results=n_results)
            
            if not results:
                return ""
            
            filtered = []
            for r in results:
                metadata = r.get("metadata", {})
                if isinstance(metadata, str):
                    metadata = self.kb._json.loads(metadata)
                if metadata.get("category") != "system":
                    filtered.append(r)
            
            if not filtered:
                return ""
            
            lines = ["[与当前话题相关的记忆]"]
            for r in filtered[:n_results]:
                lines.append(f"- {r.get('text', '')}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.debug(f"搜索相关记忆失败: {e}")
            return ""
    
    def search_by_text_raw(self, query: str, n_results: int = 3) -> list:
        """
        根据文本语义搜索相关记忆（返回原始结果，包含 ID）
        
        Returns:
            [{"id": "...", "text": "...", "distance": 0.x, "metadata": {...}}]
        """
        try:
            results = self.kb.search(query, n_results=n_results)
            
            if not results:
                return []
            
            filtered = []
            for r in results:
                metadata = r.get("metadata", {})
                if isinstance(metadata, str):
                    metadata = self.kb._json.loads(metadata)
                if metadata.get("category") != "system":
                    filtered.append({
                        "id": r.get("id", "unknown"),
                        "text": r.get("text", ""),
                        "distance": r.get("distance", 1.0),
                        "metadata": metadata
                    })
            
            return filtered[:n_results]
            
        except Exception as e:
            logger.debug(f"搜索相关记忆失败(raw): {e}")
            return []


def create_memory_retriever(knowledge_base) -> MemoryRetriever:
    """创建记忆检索器"""
    return MemoryRetriever(knowledge_base)
