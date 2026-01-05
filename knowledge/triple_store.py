# -*- coding: utf-8 -*-
"""
三元组存储 (Triple Store)

存储结构化的 (Subject, Predicate, Object) 关系，用于 Hybrid GraphRAG 检索。
三元组作为记忆的"副产物"，本身不存储 importance，而是通过佐证记忆动态计算。
"""

import json
import os
import time
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from loguru import logger


@dataclass
class Triple:
    """三元组结构"""
    id: str                          # 唯一 ID
    subject: str                     # 主语
    predicate: str                   # 谓语/关系
    object: str                      # 宾语
    source_memory_ids: List[str]     # 佐证记忆 ID 列表
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    # 扩展字段 (N-Tuple 支持)
    metadata: Dict = field(default_factory=dict)
    # metadata 可包含:
    # - time_context: "2026-01"     时间上下文
    # - frequency: "经常/很/有时"   程度副词
    # - condition: "饿的时候"       条件
    # - negation: bool              是否否定
    # - confidence: float           置信度
    
    @property
    def support_count(self) -> int:
        """被多少条记忆佐证"""
        return len(self.source_memory_ids)
    
    def add_source(self, memory_id: str) -> bool:
        """添加佐证记忆"""
        if memory_id not in self.source_memory_ids:
            self.source_memory_ids.append(memory_id)
            self.updated_at = time.time()
            return True
        return False
    
    def remove_source(self, memory_id: str) -> bool:
        """移除佐证记忆"""
        if memory_id in self.source_memory_ids:
            self.source_memory_ids.remove(memory_id)
            self.updated_at = time.time()
            return True
        return False
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Triple":
        return cls(**data)
    
    def __str__(self) -> str:
        neg = "不" if self.metadata.get("negation") else ""
        freq = self.metadata.get("frequency", "")
        return f"({self.subject} {neg}{freq}{self.predicate} {self.object})"


class TripleStore:
    """
    三元组存储
    
    特性：
    - JSONL 持久化
    - 内存索引（按 subject/predicate/object）
    - 自动去重
    - 佐证记忆追踪
    """
    
    def __init__(self, data_path: str = None):
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import config
        
        self.data_path = data_path or getattr(config, 'TRIPLE_STORE_PATH', 'data/triples.jsonl')
        
        # 主存储
        self.triples: Dict[str, Triple] = {}
        
        # 索引
        self.subject_index: Dict[str, Set[str]] = {}   # subject -> triple_ids
        self.predicate_index: Dict[str, Set[str]] = {} # predicate -> triple_ids
        self.object_index: Dict[str, Set[str]] = {}    # object -> triple_ids
        self.memory_index: Dict[str, Set[str]] = {}    # memory_id -> triple_ids
        
        # 加载数据
        self._load()
    
    def _load(self):
        """从文件加载"""
        if not os.path.exists(self.data_path):
            logger.info(f"三元组存储文件不存在，将创建: {self.data_path}")
            return
        
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        triple = Triple.from_dict(data)
                        self.triples[triple.id] = triple
                        self._index_triple(triple)
            
            logger.info(f"加载三元组: {len(self.triples)} 条")
        except Exception as e:
            logger.error(f"加载三元组失败: {e}")
    
    def _save(self):
        """保存到文件"""
        os.makedirs(os.path.dirname(self.data_path) or '.', exist_ok=True)
        try:
            with open(self.data_path, 'w', encoding='utf-8') as f:
                for triple in self.triples.values():
                    f.write(json.dumps(triple.to_dict(), ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"保存三元组失败: {e}")
    
    def _index_triple(self, triple: Triple):
        """添加索引"""
        tid = triple.id
        
        # Subject 索引
        if triple.subject not in self.subject_index:
            self.subject_index[triple.subject] = set()
        self.subject_index[triple.subject].add(tid)
        
        # Predicate 索引
        if triple.predicate not in self.predicate_index:
            self.predicate_index[triple.predicate] = set()
        self.predicate_index[triple.predicate].add(tid)
        
        # Object 索引
        if triple.object not in self.object_index:
            self.object_index[triple.object] = set()
        self.object_index[triple.object].add(tid)
        
        # Memory 索引
        for mid in triple.source_memory_ids:
            if mid not in self.memory_index:
                self.memory_index[mid] = set()
            self.memory_index[mid].add(tid)
    
    def _remove_from_index(self, triple: Triple):
        """移除索引"""
        tid = triple.id
        
        if triple.subject in self.subject_index:
            self.subject_index[triple.subject].discard(tid)
        if triple.predicate in self.predicate_index:
            self.predicate_index[triple.predicate].discard(tid)
        if triple.object in self.object_index:
            self.object_index[triple.object].discard(tid)
        for mid in triple.source_memory_ids:
            if mid in self.memory_index:
                self.memory_index[mid].discard(tid)
    
    def _generate_id(self, subject: str, predicate: str, obj: str) -> str:
        """生成三元组 ID（用于去重）"""
        import hashlib
        key = f"{subject}|{predicate}|{obj}"
        return hashlib.md5(key.encode()).hexdigest()[:12]
    
    def add(
        self,
        subject: str,
        predicate: str,
        obj: str,
        source_memory_id: str,
        metadata: Dict = None
    ) -> Tuple[str, bool]:
        """
        添加三元组
        
        如果相同的 (S, P, O) 已存在，则追加佐证记忆
        
        Returns:
            (triple_id, is_new)
        """
        triple_id = self._generate_id(subject, predicate, obj)
        
        if triple_id in self.triples:
            # 已存在，追加佐证
            triple = self.triples[triple_id]
            is_new = triple.add_source(source_memory_id)
            
            # 更新 memory 索引
            if is_new and source_memory_id not in self.memory_index:
                self.memory_index[source_memory_id] = set()
            if is_new:
                self.memory_index[source_memory_id].add(triple_id)
            
            # 合并 metadata
            if metadata:
                triple.metadata.update(metadata)
                triple.updated_at = time.time()
            
            self._save()
            logger.debug(f"三元组追加佐证: {triple} ← {source_memory_id}")
            return triple_id, False
        else:
            # 新建
            triple = Triple(
                id=triple_id,
                subject=subject,
                predicate=predicate,
                object=obj,
                source_memory_ids=[source_memory_id],
                metadata=metadata or {}
            )
            self.triples[triple_id] = triple
            self._index_triple(triple)
            self._save()
            logger.info(f"新增三元组: {triple}")
            return triple_id, True
    
    def remove_source(self, memory_id: str) -> List[str]:
        """
        移除某条记忆的所有佐证
        
        如果三元组的 support_count 降为 0，则删除该三元组
        
        Returns:
            被删除的 triple_ids
        """
        deleted = []
        
        if memory_id not in self.memory_index:
            return deleted
        
        triple_ids = list(self.memory_index[memory_id])
        
        for tid in triple_ids:
            if tid not in self.triples:
                continue
            
            triple = self.triples[tid]
            triple.remove_source(memory_id)
            
            if triple.support_count == 0:
                # 无佐证，删除三元组
                self._remove_from_index(triple)
                del self.triples[tid]
                deleted.append(tid)
                logger.info(f"删除无佐证三元组: {triple}")
        
        # 清理 memory 索引
        if memory_id in self.memory_index:
            del self.memory_index[memory_id]
        
        if deleted:
            self._save()
        
        return deleted
    
    def find_by_entity(self, entity: str) -> List[Triple]:
        """根据实体查找（可能是 subject 或 object）"""
        results = []
        seen = set()
        
        for tid in self.subject_index.get(entity, set()):
            if tid not in seen and tid in self.triples:
                results.append(self.triples[tid])
                seen.add(tid)
        
        for tid in self.object_index.get(entity, set()):
            if tid not in seen and tid in self.triples:
                results.append(self.triples[tid])
                seen.add(tid)
        
        return results
    
    def find_by_subject(self, subject: str) -> List[Triple]:
        """根据 subject 查找"""
        return [
            self.triples[tid] 
            for tid in self.subject_index.get(subject, set())
            if tid in self.triples
        ]
    
    def find_by_predicate(self, predicate: str) -> List[Triple]:
        """根据 predicate 查找"""
        return [
            self.triples[tid]
            for tid in self.predicate_index.get(predicate, set())
            if tid in self.triples
        ]
    
    def find_by_memory(self, memory_id: str) -> List[Triple]:
        """根据佐证记忆查找"""
        return [
            self.triples[tid]
            for tid in self.memory_index.get(memory_id, set())
            if tid in self.triples
        ]
    
    def search(
        self,
        entities: List[str],
        predicates: List[str] = None
    ) -> List[Triple]:
        """
        搜索三元组
        
        Args:
            entities: 实体列表（匹配 subject 或 object）
            predicates: 关系列表（可选）
        
        Returns:
            匹配的三元组列表
        """
        results = []
        seen = set()
        
        for entity in entities:
            for triple in self.find_by_entity(entity):
                if triple.id in seen:
                    continue
                
                if predicates and triple.predicate not in predicates:
                    continue
                
                results.append(triple)
                seen.add(triple.id)
        
        return results
    
    def get_all_entities(self) -> Set[str]:
        """获取所有实体"""
        entities = set(self.subject_index.keys())
        entities.update(self.object_index.keys())
        return entities
    
    def get_all_predicates(self) -> Set[str]:
        """获取所有关系类型"""
        return set(self.predicate_index.keys())
    
    def count(self) -> int:
        """三元组总数"""
        return len(self.triples)
    
    def get_stats(self) -> Dict:
        """统计信息"""
        return {
            "total_triples": len(self.triples),
            "total_entities": len(self.get_all_entities()),
            "total_predicates": len(self.get_all_predicates()),
            "predicates": list(self.get_all_predicates())[:10]
        }


# 全局单例
_triple_store: Optional[TripleStore] = None


def get_triple_store() -> TripleStore:
    """获取全局三元组存储实例"""
    global _triple_store
    if _triple_store is None:
        _triple_store = TripleStore()
    return _triple_store
