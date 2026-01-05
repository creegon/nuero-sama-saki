# -*- coding: utf-8 -*-
"""
知识库核心实现
"""

import os
import sys
import time
import uuid
import json
from typing import Optional, List, Dict
from loguru import logger

import config

import lancedb
import pyarrow as pa


class KnowledgeBase:
    """
    知识库
    
    使用 LanceDB 存储和检索知识
    支持语义搜索，延迟 < 10ms
    """
    
    # Embedding 模型配置
    EMBEDDING_MODEL = "BAAI/bge-base-zh-v1.5"  # 中文专用，768 维
    EMBEDDING_DIM = 768
    
    # 表结构
    SCHEMA = pa.schema([
        pa.field("id", pa.string()),
        pa.field("text", pa.string()),
        pa.field("metadata", pa.string()),  # JSON 字符串
        pa.field("vector", pa.list_(pa.float32(), 768)),  # BGE 输出 768 维
    ])
    
    def __init__(
        self,
        persist_directory: str = None,
        collection_name: str = None
    ):
        """初始化知识库"""
        self._json = json
        self.collection_name = collection_name or config.KNOWLEDGE_COLLECTION_NAME
        
        if persist_directory is None:
            persist_directory = config.KNOWLEDGE_LANCEDB_PATH
        
        init_start = time.time()
        logger.info(f"📚 知识库初始化开始: {persist_directory}")
        os.makedirs(persist_directory, exist_ok=True)
        
        # ===== 加载 SentenceTransformer (主要耗时点) =====
        model_start = time.time()
        logger.info(f"🔧 加载 Embedding 模型: {self.EMBEDDING_MODEL}...")
        try:
            import torch
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            
            # 延迟导入，防止 TF 冲突
            from sentence_transformers import SentenceTransformer
            
            try:
                self._model = SentenceTransformer(
                    self.EMBEDDING_MODEL,
                    device=device,
                    local_files_only=True
                )
            except OSError:
                logger.warning("   模型不在本地缓存，首次下载中...")
                self._model = SentenceTransformer(
                    self.EMBEDDING_MODEL,
                    device=device
                )
            
            # 预热
            _ = self._model.encode("预热测试", show_progress_bar=False)
            
            model_elapsed = time.time() - model_start
            logger.info(f"✅ Embedding 模型加载完成 ({model_elapsed:.1f}s, device={device})")
        except Exception as e:
            logger.error(f"❌ Embedding 模型加载失败: {e}")
            raise
        
        # ===== 连接 LanceDB =====
        try:
            self._db = lancedb.connect(persist_directory)
            logger.debug("✅ LanceDB 连接成功")
        except Exception as e:
            logger.error(f"❌ LanceDB 连接失败: {e}")
            raise
        
        # ===== 获取或创建表 =====
        try:
            table_names = self._db.table_names()
            if self.collection_name in table_names:
                self._table = self._db.open_table(self.collection_name)
            else:
                self._table = self._db.create_table(
                    self.collection_name,
                    schema=self.SCHEMA,
                    mode="create"
                )
                logger.info(f"📝 创建新表: {self.collection_name}")
        except Exception as e:
            logger.error(f"❌ 表操作失败: {e}")
            raise
        
        total_elapsed = time.time() - init_start
        logger.info(f"📚 知识库就绪: {self.count()} 条记录 (总耗时 {total_elapsed:.1f}s)")
    
    def _embed(self, text: str) -> List[float]:
        """生成文本的向量表示"""
        return self._model.encode(
            text, 
            show_progress_bar=False,
            convert_to_numpy=True
        ).tolist()
    
    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量生成向量 (强制串行以避免 Windows 下的死锁问题)"""
        results = []
        for t in texts:
            vec = self._model.encode(
                t, 
                show_progress_bar=False,
                convert_to_numpy=True
            )
            results.append(vec.tolist())
        return results
    
    def add(
        self,
        text: str,
        metadata: Dict = None,
        doc_id: str = None,
        importance: float = 1.0
    ) -> str:
        """添加知识条目"""
        if doc_id is None:
            doc_id = str(uuid.uuid4())[:8]
        
        if metadata is None:
            metadata = {}
        
        metadata["importance"] = importance
        metadata["access_count"] = 0
        metadata["last_access"] = 0
        metadata["timestamp"] = time.time()
        metadata["consolidated"] = False
        
        vector = self._embed(text)
        
        self._table.add([{
            "id": doc_id,
            "text": text,
            "metadata": self._json.dumps(metadata, ensure_ascii=False),
            "vector": vector
        }])
        
        logger.debug(f"📝 添加知识: [{doc_id}] {text[:30]}...")
        return doc_id
    
    def add_batch(self, items: List[Dict]) -> List[str]:
        """批量添加知识"""
        if not items:
            return []
        
        texts = [item["text"] for item in items]
        vectors = self._embed_batch(texts)
        
        rows = []
        ids = []
        for i, item in enumerate(items):
            doc_id = item.get("id", str(uuid.uuid4())[:8])
            ids.append(doc_id)
            rows.append({
                "id": doc_id,
                "text": item["text"],
                "metadata": self._json.dumps(item.get("metadata", {}), ensure_ascii=False),
                "vector": vectors[i]
            })
        
        self._table.add(rows)
        logger.info(f"📝 批量添加 {len(items)} 条知识")
        return ids
    
    def search(
        self,
        query: str,
        n_results: int = 3,
        where: Dict = None
    ) -> List[Dict]:
        """语义搜索"""
        start = time.time()
        query_vector = self._embed(query)
        results = self._table.search(query_vector).limit(n_results).to_list()
        elapsed = (time.time() - start) * 1000
        
        formatted = []
        for row in results:
            try:
                metadata = self._json.loads(row.get("metadata", "{}"))
            except:
                metadata = {}
            
            if where:
                match = True
                for key, value in where.items():
                    if metadata.get(key) != value:
                        match = False
                        break
                if not match:
                    continue
            
            formatted.append({
                "id": row.get("id", ""),
                "text": row.get("text", ""),
                "metadata": metadata,
                "distance": row.get("_distance", 0)
            })
        
        if formatted:
            logger.info(f"🔍 搜索 '{query[:30]}' → {len(formatted)} 条匹配 ({elapsed:.0f}ms)")
        else:
            logger.debug(f"🔍 搜索 '{query[:30]}' → 无匹配 ({elapsed:.0f}ms)")
        
        return formatted
    
    def get_context_for_llm(
        self,
        query: str,
        n_results: int = 3,
        threshold: float = 1.5
    ) -> str:
        """获取用于 LLM 的上下文"""
        results = self.search(query, n_results)
        relevant = [r for r in results if r["distance"] < threshold]
        
        if not relevant:
            return ""
        
        lines = ["[相关知识]"]
        for r in relevant:
            lines.append(f"- {r['text']}")
        
        return "\n".join(lines)
    
    # 委托给 Helper 的方法
    def get_recent_memories(self, n: int = 5, exclude_system: bool = True) -> str:
        from knowledge.retrieval import create_memory_retriever
        return create_memory_retriever(self).get_recent_memories(n, exclude_system)
    
    def get_important_memories(self, threshold: float = 2.5, n: int = 3) -> str:
        from knowledge.retrieval import create_memory_retriever
        return create_memory_retriever(self).get_important_memories(threshold, n)
    
    def search_by_text(self, query: str, n_results: int = 3) -> str:
        from knowledge.retrieval import create_memory_retriever
        return create_memory_retriever(self).search_by_text(query, n_results)
    
    def search_by_text_raw(self, query: str, n_results: int = 3) -> list:
        from knowledge.retrieval import create_memory_retriever
        return create_memory_retriever(self).search_by_text_raw(query, n_results)
    
    def update_importance(self, doc_id: str, delta: float = 0.5) -> bool:
        from knowledge.memory_manager import create_memory_manager
        return create_memory_manager(self).update_importance(doc_id, delta)
    
    def find_similar(self, text: str, threshold: float = 0.8) -> list:
        from knowledge.memory_manager import create_memory_manager
        return create_memory_manager(self).find_similar(text, threshold)
    
    def add_with_dedup(self, text: str, metadata: Dict = None, similarity_threshold: float = 0.85) -> str:
        from knowledge.memory_manager import create_memory_manager
        return create_memory_manager(self).add_with_dedup(text, metadata, similarity_threshold)
    
    def decay_old_memories(self, days_threshold: int = 7, decay_factor: float = 0.9) -> int:
        from knowledge.memory_manager import create_memory_manager
        return create_memory_manager(self).decay_old_memories(days_threshold, decay_factor)
    
    def delete(self, doc_id: str) -> bool:
        try:
            self._table.delete(f"id = '{doc_id}'")
            return True
        except:
            return False
    
    def count(self) -> int:
        try:
            return len(self._table.to_arrow())
        except:
            return 0
    
    def clear(self) -> None:
        try:
            self._db.drop_table(self.collection_name)
            self._table = self._db.create_table(
                self.collection_name,
                schema=self.SCHEMA,
                mode="create"
            )
            logger.warning("⚠️ 知识库已清空")
        except Exception as e:
            logger.error(f"清空知识库失败: {e}")


# 全局单例
_knowledge_base: Optional[KnowledgeBase] = None

def get_knowledge_base() -> KnowledgeBase:
    """获取全局知识库实例"""
    global _knowledge_base
    if _knowledge_base is None:
        logger.debug("📚 首次初始化知识库单例...")
        _knowledge_base = KnowledgeBase()
    return _knowledge_base
