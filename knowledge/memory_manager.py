# -*- coding: utf-8 -*-
"""
记忆管理器
负责记忆的重要性评分、去重合并、衰减遗忘等
"""

import time
from typing import Dict, List, Optional
from loguru import logger


class MemoryManager:
    """
    记忆管理器
    
    提供记忆的高级管理功能：
    - 重要性评分动态调整
    - 相似记忆去重合并
    - 长期未访问记忆衰减
    """
    
    def __init__(self, knowledge_base):
        self.kb = knowledge_base
    
    # 临界值
    PROMOTE_THRESHOLD = 2.5  # 达到此值触发升级审核
    DECAY_THRESHOLD = 0.2    # 低于此值触发删除审核（更激进）
    DELETE_COOLDOWN_HOURS = 24  # 删除审核冷却期（小时）
    
    # 🔥 BOOST 防刷参数
    BOOST_VALUE = 0.5           # 单次 BOOST 增量
    BOOST_COOLDOWN_HOURS = 2    # 2小时内只算1次
    BOOST_DAILY_CAP = 1.0       # 每天每条记忆最多涨 1.0
    
    # 🔥 衰减参数（更激进）
    DECAY_DAYS_FACT = 5         # fact 类型 5 天后开始衰减
    DECAY_FACTOR_FACT = 0.85    # fact 每次衰减 15%
    DECAY_DAYS_EPISODE = 3      # episode 类型 3 天后开始衰减
    DECAY_FACTOR_EPISODE = 0.6  # episode 每次衰减 40%
    DELETE_DAYS_EPISODE = 7     # episode 7 天后强制删除
    
    def update_importance(self, doc_id: str, delta: float = 0.5, trigger_review: bool = True) -> bool:
        """
        更新记忆重要性评分
        
        Args:
            doc_id: 文档 ID
            delta: 评分变化量 (正数增加，负数减少)
            trigger_review: 是否在达到临界值时触发审核
        
        Returns:
            是否成功
        """
        try:
            all_rows = self.kb._table.to_pandas()
            for idx, row in all_rows.iterrows():
                if row["id"] == doc_id:
                    metadata = self.kb._json.loads(row.get("metadata", "{}"))
                    old_importance = metadata.get("importance", 1.0)
                    new_importance = max(0, old_importance + delta)
                    metadata["importance"] = new_importance
                    metadata["access_count"] = metadata.get("access_count", 0) + 1
                    metadata["last_access"] = time.time()
                    
                    # 更新记录
                    self.kb._table.delete(f"id = '{doc_id}'")
                    self.kb._table.add([{
                        "id": doc_id,
                        "text": row["text"],
                        "metadata": self.kb._json.dumps(metadata, ensure_ascii=False),
                        "vector": row["vector"]
                    }])
                    
                    logger.debug(f"📊 更新重要性: [{doc_id}] {old_importance:.1f} -> {new_importance:.1f}")
                    
                    # 🔥 检查是否需要触发升级审核
                    if trigger_review and new_importance >= self.PROMOTE_THRESHOLD:
                        category = metadata.get("category", "fact")
                        promotion_rejected = metadata.get("promotion_rejected", False)
                        
                        # 🔥 如果之前已经被拒绝升级，不再触发
                        if promotion_rejected:
                            logger.debug(f"⛔ 跳过升级审核（已被淘汰）: [{doc_id}]")
                        elif category not in ["core", "system"]:
                            # 异步触发升级审核
                            self._schedule_promotion_review({
                                "id": doc_id,
                                "text": row["text"],
                                "metadata": metadata
                            })
                    
                    return True
            return False
        except Exception as e:
            logger.error(f"更新重要性失败: {e}")
            return False
    
    def boost_with_cooldown(self, doc_id: str) -> bool:
        """
        🔥 带冷却和每日上限的 BOOST
        
        - 2小时内多次使用只算1次
        - 每天每条记忆最多涨 1.0
        
        Returns:
            是否成功执行 BOOST
        """
        try:
            from datetime import datetime
            
            all_rows = self.kb._table.to_pandas()
            for idx, row in all_rows.iterrows():
                if row["id"] == doc_id:
                    metadata = self.kb._json.loads(row.get("metadata", "{}"))
                    now = time.time()
                    today = datetime.now().strftime("%Y-%m-%d")
                    
                    # 检查冷却期
                    last_boost_time = metadata.get("last_boost_time", 0)
                    if now - last_boost_time < self.BOOST_COOLDOWN_HOURS * 3600:
                        logger.debug(f"⏳ BOOST 冷却中: [{doc_id}]")
                        return False
                    
                    # 检查每日上限
                    boost_date = metadata.get("boost_date", "")
                    if boost_date == today:
                        daily_boost = metadata.get("daily_boost_total", 0)
                        if daily_boost >= self.BOOST_DAILY_CAP:
                            logger.debug(f"📊 BOOST 达到每日上限: [{doc_id}]")
                            return False
                    else:
                        # 新的一天，重置计数
                        metadata["boost_date"] = today
                        metadata["daily_boost_total"] = 0
                    
                    # 执行 BOOST
                    old_importance = metadata.get("importance", 1.0)
                    new_importance = old_importance + self.BOOST_VALUE
                    
                    metadata["importance"] = new_importance
                    metadata["last_boost_time"] = now
                    metadata["daily_boost_total"] = metadata.get("daily_boost_total", 0) + self.BOOST_VALUE
                    metadata["access_count"] = metadata.get("access_count", 0) + 1
                    metadata["last_access"] = now
                    
                    # 更新记录
                    self.kb._table.delete(f"id = '{doc_id}'")
                    self.kb._table.add([{
                        "id": doc_id,
                        "text": row["text"],
                        "metadata": self.kb._json.dumps(metadata, ensure_ascii=False),
                        "vector": row["vector"]
                    }])
                    
                    logger.debug(f"📊 BOOST: [{doc_id}] {old_importance:.1f} -> {new_importance:.1f}")
                    
                    # 检查是否触发升级审核
                    if new_importance >= self.PROMOTE_THRESHOLD:
                        category = metadata.get("category", "fact")
                        promotion_rejected = metadata.get("promotion_rejected", False)
                        
                        if not promotion_rejected and category not in ["core", "system"]:
                            self._schedule_promotion_review({
                                "id": doc_id,
                                "text": row["text"],
                                "metadata": metadata
                            })
                    
                    return True
            return False
        except Exception as e:
            logger.error(f"BOOST 失败: {e}")
            return False
    
    def _schedule_promotion_review(self, memory: dict):
        """调度升级审核（异步）"""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._run_promotion_review(memory))
        except RuntimeError:
            # 没有运行中的事件循环，跳过
            logger.debug(f"⏳ 升级审核已跳过（无事件循环）: [{memory['id']}]")
    
    async def _run_promotion_review(self, memory: dict):
        """执行升级审核"""
        try:
            from core.memory_reviewer import get_memory_reviewer
            reviewer = get_memory_reviewer()
            if reviewer:
                decision = await reviewer.review_for_promotion(memory)
                if decision == "PROMOTE":
                    self._promote_to_core(memory["id"])
                elif decision == "DELETE":
                    self.kb.delete(memory["id"])
                elif decision == "KEEP":
                    # 🔥 升级被拒绝，设置标记，永不再触发升级审核
                    self._set_promotion_rejected(memory["id"])
        except Exception as e:
            logger.error(f"升级审核执行失败: {e}")
    
    def _promote_to_core(self, doc_id: str):
        """将记忆升级为 core"""
        try:
            all_rows = self.kb._table.to_pandas()
            for _, row in all_rows.iterrows():
                if row["id"] == doc_id:
                    metadata = self.kb._json.loads(row.get("metadata", "{}"))
                    metadata["category"] = "core"
                    
                    self.kb._table.delete(f"id = '{doc_id}'")
                    self.kb._table.add([{
                        "id": doc_id,
                        "text": row["text"],
                        "metadata": self.kb._json.dumps(metadata, ensure_ascii=False),
                        "vector": row["vector"]
                    }])
                    
                    logger.info(f"⭐ 记忆升级为核心: [{doc_id}]")
                    return True
            return False
        except Exception as e:
            logger.error(f"升级为核心失败: {e}")
            return False
    
    def update_text(self, doc_id: str, new_text: str) -> bool:
        """
        更新记忆的文本内容（保留 metadata 和重新计算 vector）
        
        🔥 特别用于 core 记忆的更新（core 不允许删除，但允许修改）
        
        Args:
            doc_id: 文档 ID
            new_text: 新的文本内容
        
        Returns:
            是否成功
        """
        try:
            all_rows = self.kb._table.to_pandas()
            for _, row in all_rows.iterrows():
                if row["id"] == doc_id:
                    metadata = self.kb._json.loads(row.get("metadata", "{}"))
                    
                    # 重新计算向量
                    new_vector = self.kb._embed(new_text)
                    
                    # 更新记录
                    self.kb._table.delete(f"id = '{doc_id}'")
                    self.kb._table.add([{
                        "id": doc_id,
                        "text": new_text,
                        "metadata": self.kb._json.dumps(metadata, ensure_ascii=False),
                        "vector": new_vector
                    }])
                    
                    logger.info(f"📝 更新记忆内容: [{doc_id}] → {new_text[:50]}...")
                    return True
            
            logger.warning(f"⚠️ 记忆不存在: [{doc_id}]")
            return False
        except Exception as e:
            logger.error(f"更新记忆内容失败: {e}")
            return False
    
    def find_similar(self, text: str, threshold: float = 0.8) -> list:
        """
        查找相似记忆
        
        Args:
            text: 要比较的文本
            threshold: 相似度阈值 (1.0 = 完全相同, 0.8 = 很相似)
        
        Returns:
            相似记忆列表 [{"id": ..., "text": ..., "similarity": ...}]
        """
        try:
            results = self.kb.search(text, n_results=5)
            
            similar = []
            for r in results:
                distance = r.get("distance", 2.0)
                similarity = max(0, 1 - distance / 2)
                if similarity >= threshold:
                    similar.append({
                        "id": r["id"],
                        "text": r.get("text", ""),
                        "similarity": similarity,
                        "metadata": r.get("metadata", {})
                    })
            
            return similar
        except Exception as e:
            logger.debug(f"查找相似记忆失败: {e}")
            return []
    
    def add_with_dedup(self, text: str, metadata: Dict = None, similarity_threshold: float = 0.85) -> str:
        """
        添加记忆（自动去重和合并）
        
        如果已有非常相似的记忆，则增加其重要性而非重复添加
        
        Returns:
            文档 ID（新建或已存在的）
        """
        similar = self.find_similar(text, threshold=similarity_threshold)
        
        if similar:
            best_match = similar[0]
            self.update_importance(best_match["id"], delta=0.5)
            logger.info(f"🔗 记忆合并: 增强现有记忆 [{best_match['id']}] (相似度: {best_match['similarity']:.2f})")
            return best_match["id"]
        else:
            return self.kb.add(text, metadata)
    
    def decay_old_memories(self, days_threshold: int = 7, decay_factor: float = 0.9) -> int:
        """
        衰减长期未访问的记忆
        
        三层架构衰减规则：
        - system: 永不衰减（系统设定）
        - core: 永不衰减（核心事实，importance >= 3.0）
        - episode: 7天后快速衰减(0.8)，14天后删除
        - fact: 7天后正常衰减(0.95)，importance < 0.3 时删除
        
        Returns:
            衰减的记忆数量
        """
        try:
            all_rows = self.kb._table.to_pandas()
            now = time.time()
            
            # 🔥 使用类属性参数
            fact_threshold = self.DECAY_DAYS_FACT * 24 * 3600
            episode_threshold = self.DECAY_DAYS_EPISODE * 24 * 3600
            episode_delete_threshold = self.DELETE_DAYS_EPISODE * 24 * 3600
            
            decayed_count = 0
            deleted_count = 0
            deleted_memory_ids = []  # 用于级联删除三元组
            
            for _, row in all_rows.iterrows():
                metadata = self.kb._json.loads(row.get("metadata", "{}"))
                last_access = metadata.get("last_access", metadata.get("timestamp", 0))
                category = metadata.get("category", "fact")
                importance = metadata.get("importance", 1.0)
                
                # system/core 永不衰减
                if category in ["core", "system"]:
                    continue
                
                elapsed = now - last_access
                
                # episode 类型：快速衰减
                if category == "episode":
                    if elapsed > episode_delete_threshold:
                        self.kb.delete(row["id"])
                        deleted_memory_ids.append(row["id"])
                        logger.debug(f"🗑 删除过期情境: [{row['id']}]")
                        deleted_count += 1
                    elif elapsed > episode_threshold:
                        new_importance = importance * self.DECAY_FACTOR_EPISODE
                        if new_importance < self.DECAY_THRESHOLD:
                            self.kb.delete(row["id"])
                            deleted_memory_ids.append(row["id"])
                            logger.debug(f"🗑 遗忘情境: [{row['id']}]")
                            deleted_count += 1
                        else:
                            metadata["importance"] = new_importance
                            self._update_memory_metadata(row, metadata)
                            decayed_count += 1
                    continue
                
                # fact 类型：正常衰减
                if elapsed > fact_threshold:
                    new_importance = importance * self.DECAY_FACTOR_FACT
                    metadata["importance"] = new_importance
                    self._update_memory_metadata(row, metadata)
                    decayed_count += 1
                    
                    # 🔥 低于阈值时触发删除审核
                    if new_importance < self.DECAY_THRESHOLD:
                        cooldown_until = metadata.get("delete_cooldown_until", 0)
                        if cooldown_until > time.time():
                            logger.debug(f"⛔ 跳过删除审核（冷却中）: [{row['id']}]")
                        else:
                            self._schedule_decay_review({
                                "id": row["id"],
                                "text": row["text"],
                                "metadata": metadata
                            })
            
            # 🔥 级联删除三元组
            if deleted_memory_ids:
                try:
                    from .triple_store import get_triple_store
                    triple_store = get_triple_store()
                    for mid in deleted_memory_ids:
                        triple_store.remove_source(mid)
                except Exception as e:
                    logger.debug(f"级联删除三元组失败: {e}")
            
            if decayed_count > 0 or deleted_count > 0:
                logger.info(f"🧹 记忆衰减: 衰减 {decayed_count} 条，删除 {deleted_count} 条")
            return decayed_count + deleted_count
            
        except Exception as e:
            logger.error(f"记忆衰减失败: {e}")
            return 0
    
    def _schedule_decay_review(self, memory: dict):
        """调度衰减审核（异步）"""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._run_decay_review(memory))
        except RuntimeError:
            logger.debug(f"⏳ 衰减审核已跳过（无事件循环）: [{memory['id']}]")
    
    async def _run_decay_review(self, memory: dict):
        """执行衰减审核"""
        try:
            from core.memory_reviewer import get_memory_reviewer
            reviewer = get_memory_reviewer()
            if reviewer:
                decision = await reviewer.review_for_decay(memory)
                if decision == "DELETE":
                    self.kb.delete(memory["id"])
                    logger.info(f"🗑 审核后删除: [{memory['id']}]")
                elif decision == "KEEP":
                    # 🔥 保留：重置 importance 并设置 24h 冷却期
                    self._reset_importance_with_cooldown(memory["id"], 0.5)
        except Exception as e:
            logger.error(f"衰减审核执行失败: {e}")
    
    def _reset_importance(self, doc_id: str, new_importance: float):
        """重置记忆的 importance"""
        try:
            all_rows = self.kb._table.to_pandas()
            for _, row in all_rows.iterrows():
                if row["id"] == doc_id:
                    metadata = self.kb._json.loads(row.get("metadata", "{}"))
                    metadata["importance"] = new_importance
                    metadata["last_access"] = time.time()
                    
                    self.kb._table.delete(f"id = '{doc_id}'")
                    self.kb._table.add([{
                        "id": doc_id,
                        "text": row["text"],
                        "metadata": self.kb._json.dumps(metadata, ensure_ascii=False),
                        "vector": row["vector"]
                    }])
                    logger.debug(f"📊 重置重要性: [{doc_id}] -> {new_importance}")
                    return True
            return False
        except Exception as e:
            logger.error(f"重置重要性失败: {e}")
            return False
    
    def _set_promotion_rejected(self, doc_id: str):
        """🔥 设置升级被拒绝标记（永不再触发升级审核）"""
        try:
            all_rows = self.kb._table.to_pandas()
            for _, row in all_rows.iterrows():
                if row["id"] == doc_id:
                    metadata = self.kb._json.loads(row.get("metadata", "{}"))
                    metadata["promotion_rejected"] = True
                    
                    self.kb._table.delete(f"id = '{doc_id}'")
                    self.kb._table.add([{
                        "id": doc_id,
                        "text": row["text"],
                        "metadata": self.kb._json.dumps(metadata, ensure_ascii=False),
                        "vector": row["vector"]
                    }])
                    logger.info(f"⛔ 设置升级淘汰标记: [{doc_id}]")
                    return True
            return False
        except Exception as e:
            logger.error(f"设置淘汰标记失败: {e}")
            return False
    
    def _reset_importance_with_cooldown(self, doc_id: str, new_importance: float):
        """🔥 重置 importance 并设置删除审核冷却期"""
        try:
            all_rows = self.kb._table.to_pandas()
            for _, row in all_rows.iterrows():
                if row["id"] == doc_id:
                    metadata = self.kb._json.loads(row.get("metadata", "{}"))
                    metadata["importance"] = new_importance
                    metadata["last_access"] = time.time()
                    # 🔥 设置冷却期
                    cooldown_seconds = self.DELETE_COOLDOWN_HOURS * 3600
                    metadata["delete_cooldown_until"] = time.time() + cooldown_seconds
                    
                    self.kb._table.delete(f"id = '{doc_id}'")
                    self.kb._table.add([{
                        "id": doc_id,
                        "text": row["text"],
                        "metadata": self.kb._json.dumps(metadata, ensure_ascii=False),
                        "vector": row["vector"]
                    }])
                    logger.info(f"⏳ 设置删除冷却期: [{doc_id}] ({self.DELETE_COOLDOWN_HOURS}h)")
                    return True
            return False
        except Exception as e:
            logger.error(f"设置冷却期失败: {e}")
            return False
    
    def _update_memory_metadata(self, row, metadata):
        """更新记忆的 metadata"""
        self.kb._table.delete(f"id = '{row['id']}'")
        self.kb._table.add([{
            "id": row["id"],
            "text": row["text"],
            "metadata": self.kb._json.dumps(metadata, ensure_ascii=False),
            "vector": row["vector"]
        }])


def create_memory_manager(knowledge_base) -> MemoryManager:
    """创建记忆管理器"""
    return MemoryManager(knowledge_base)
