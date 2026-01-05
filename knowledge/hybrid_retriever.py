# -*- coding: utf-8 -*-
"""
Hybrid 检索器

结合 Vector Store（语义检索）和 Triple Store（关系检索）的混合检索
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class HybridResult:
    """Hybrid 检索结果"""
    memory_id: str
    text: str
    metadata: Dict
    score: float               # 综合得分
    vector_score: float = 0.0  # Vector 得分
    graph_score: float = 0.0   # Graph 得分
    related_triples: List = None  # 相关三元组
    
    def __post_init__(self):
        if self.related_triples is None:
            self.related_triples = []


class HybridRetriever:
    """
    Hybrid 检索器
    
    检索流程：
    1. Vector Store 粗筛（语义相似）
    2. 提取查询实体
    3. Triple Store 关系遍历
    4. 融合排序
    """
    
    def __init__(self, knowledge_base=None, triple_store=None):
        self.kb = knowledge_base
        self.triple_store = triple_store
        
        # 权重配置
        self.vector_weight = 0.4
        self.graph_weight = 0.6
        self.overlap_bonus = 0.3  # 同时命中加分
    
    def set_stores(self, knowledge_base, triple_store):
        """设置存储"""
        self.kb = knowledge_base
        self.triple_store = triple_store
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        include_core: bool = True
    ) -> List[HybridResult]:
        """
        Hybrid 检索
        
        Args:
            query: 查询文本
            top_k: 返回数量
            include_core: 是否包含 core/system 记忆
        
        Returns:
            排序后的检索结果
        """
        if not self.kb:
            logger.warning("HybridRetriever: 知识库未设置")
            return []
        
        results = {}  # memory_id -> HybridResult
        
        # === 1. Core/System 记忆（始终注入） ===
        if include_core:
            core_memories = self._get_core_memories()
            for mem in core_memories:
                mid = mem.get("id")
                results[mid] = HybridResult(
                    memory_id=mid,
                    text=mem.get("text", ""),
                    metadata=mem.get("metadata", {}),
                    score=10.0,  # 高优先级
                    vector_score=1.0,
                    graph_score=1.0
                )
        
        # === 2. Vector 检索 ===
        vector_results = self._vector_search(query, top_k=top_k * 2)
        
        for rank, mem in enumerate(vector_results):
            mid = mem.get("id")
            if mid in results:
                continue  # 已在 core 中
            
            # 距离转相似度
            distance = mem.get("distance", 1.0)
            similarity = max(0, 1 - distance / 2)
            
            results[mid] = HybridResult(
                memory_id=mid,
                text=mem.get("text", ""),
                metadata=mem.get("metadata", {}),
                score=0.0,
                vector_score=similarity
            )
        
        # === 3. 实体提取 + Graph 检索 ===
        if self.triple_store:
            from .entity_extractor import get_entity_extractor
            extractor = get_entity_extractor()
            entities = extractor.extract_entities_simple(query)
            
            if entities:
                graph_triples = self.triple_store.search(entities)
                
                # 为相关记忆加分
                for triple in graph_triples:
                    for source_mid in triple.source_memory_ids:
                        if source_mid in results:
                            results[source_mid].graph_score += 0.3
                            results[source_mid].related_triples.append(triple)
                        else:
                            # Vector 中没有，但 Graph 找到了 → 补充
                            mem = self._get_memory_by_id(source_mid)
                            if mem:
                                results[source_mid] = HybridResult(
                                    memory_id=source_mid,
                                    text=mem.get("text", ""),
                                    metadata=mem.get("metadata", {}),
                                    score=0.0,
                                    vector_score=0.0,
                                    graph_score=0.5,
                                    related_triples=[triple]
                                )
        
        # === 4. 融合排序 ===
        for result in results.values():
            if result.score >= 10.0:
                continue  # core 记忆保持高分
            
            # 计算综合得分
            result.score = (
                result.vector_score * self.vector_weight +
                result.graph_score * self.graph_weight
            )
            
            # 同时命中加分
            if result.vector_score > 0 and result.graph_score > 0:
                result.score += self.overlap_bonus
        
        # 排序
        sorted_results = sorted(
            results.values(),
            key=lambda x: x.score,
            reverse=True
        )
        
        return sorted_results[:top_k]
    
    def _get_core_memories(self) -> List[Dict]:
        """获取 core/system 记忆"""
        try:
            all_rows = self.kb._table.to_pandas()
            core_memories = []
            
            for _, row in all_rows.iterrows():
                import json
                metadata = json.loads(row.get("metadata", "{}"))
                category = metadata.get("category", "fact")
                
                if category in ["core", "system"]:
                    core_memories.append({
                        "id": row["id"],
                        "text": row["text"],
                        "metadata": metadata
                    })
            
            return core_memories
        except Exception as e:
            logger.debug(f"获取 core 记忆失败: {e}")
            return []
    
    def _vector_search(self, query: str, top_k: int = 10) -> List[Dict]:
        """Vector 检索"""
        try:
            return self.kb.search(query, n_results=top_k)
        except Exception as e:
            logger.debug(f"Vector 检索失败: {e}")
            return []
    
    def _get_memory_by_id(self, memory_id: str) -> Optional[Dict]:
        """根据 ID 获取记忆"""
        try:
            all_rows = self.kb._table.to_pandas()
            for _, row in all_rows.iterrows():
                if row["id"] == memory_id:
                    import json
                    return {
                        "id": row["id"],
                        "text": row["text"],
                        "metadata": json.loads(row.get("metadata", "{}"))
                    }
            return None
        except Exception as e:
            logger.debug(f"获取记忆失败: {e}")
            return None
    
    def format_for_prompt(self, results: List[HybridResult]) -> str:
        """
        格式化为 Prompt 注入格式
        
        包含记忆文本和相关三元组
        """
        if not results:
            return ""
        
        lines = ["[相关记忆]"]
        
        for result in results:
            # 记忆文本
            text = result.text[:100] + "..." if len(result.text) > 100 else result.text
            lines.append(f"- {text}")
            
            # 相关三元组
            if result.related_triples:
                for triple in result.related_triples[:2]:  # 最多2条
                    lines.append(f"  → 你知道: {triple}")
        
        return "\n".join(lines)


# 全局单例
_hybrid_retriever: Optional[HybridRetriever] = None


def get_hybrid_retriever() -> HybridRetriever:
    """获取全局 Hybrid 检索器实例"""
    global _hybrid_retriever
    if _hybrid_retriever is None:
        _hybrid_retriever = HybridRetriever()
    return _hybrid_retriever
