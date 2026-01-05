# -*- coding: utf-8 -*-
"""
实体与关系抽取器

使用 LLM 从文本中抽取三元组 (Subject, Predicate, Object)
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class ExtractedTriple:
    """抽取的三元组"""
    subject: str
    predicate: str
    object: str
    metadata: Dict = None  # 扩展信息
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


# 抽取提示词
EXTRACTION_PROMPT = """从以下文本中提取关键的事实三元组（主语-关系-宾语）。

规则：
1. 只提取明确的事实，不要推测
2. 主语和宾语应该是具体的实体（人名、物品、地点等）
3. 关系应该简洁（如：喜欢、是、有、住在、叫做、认识）
4. 如果有否定，在关系前加"不"
5. 如果有程度副词（很、非常、有时），放在 metadata 中

输出格式（每行一条）：
[TRIPLE] 主语 | 关系 | 宾语 | metadata_json

示例输入：
主人说他很喜欢吃拉面，但不喜欢放香菜

示例输出：
[TRIPLE] 主人 | 喜欢 | 拉面 | {"frequency": "很"}
[TRIPLE] 主人 | 不喜欢 | 香菜 | {}

如果没有可提取的事实，输出：
[SKIP]

待提取文本：
{text}
"""


class EntityExtractor:
    """实体与关系抽取器"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    def set_llm_client(self, llm_client):
        """设置 LLM 客户端"""
        self.llm_client = llm_client
    
    async def extract(self, text: str) -> List[ExtractedTriple]:
        """
        从文本中抽取三元组
        
        Args:
            text: 输入文本
        
        Returns:
            抽取的三元组列表
        """
        if not self.llm_client:
            logger.warning("EntityExtractor: LLM 客户端未设置")
            return []
        
        if not text or len(text.strip()) < 5:
            return []
        
        try:
            prompt = EXTRACTION_PROMPT.format(text=text)
            
            response = ""
            async for chunk in self.llm_client.chat_stream(
                [{"role": "user", "content": prompt}],
                system_prompt="你是一个精确的信息抽取助手。只输出格式化结果，不要解释。"
            ):
                response += chunk
            
            return self._parse_response(response)
            
        except Exception as e:
            logger.error(f"实体抽取失败: {e}")
            return []
    
    def _parse_response(self, response: str) -> List[ExtractedTriple]:
        """解析 LLM 响应"""
        triples = []
        
        for line in response.strip().split('\n'):
            line = line.strip()
            
            if line == "[SKIP]":
                continue
            
            if not line.startswith("[TRIPLE]"):
                continue
            
            # 解析: [TRIPLE] 主语 | 关系 | 宾语 | metadata
            content = line[8:].strip()  # 移除 [TRIPLE]
            parts = [p.strip() for p in content.split('|')]
            
            if len(parts) < 3:
                continue
            
            subject = parts[0]
            predicate = parts[1]
            obj = parts[2]
            
            # 解析 metadata
            metadata = {}
            if len(parts) >= 4:
                try:
                    import json
                    metadata = json.loads(parts[3])
                except:
                    pass
            
            # 验证
            if not subject or not predicate or not obj:
                continue
            
            # 处理否定
            if predicate.startswith("不"):
                metadata["negation"] = True
                predicate = predicate[1:]  # 移除"不"
            
            triples.append(ExtractedTriple(
                subject=subject,
                predicate=predicate,
                object=obj,
                metadata=metadata
            ))
        
        return triples
    
    def extract_entities_simple(self, text: str) -> List[str]:
        """
        简单实体抽取（无需 LLM，基于规则）
        
        用于检索时快速提取关键词
        """
        entities = []
        
        # 常见实体模式
        patterns = [
            r"主人",
            r"小祥",
            r"([A-Za-z]+)",  # 英文名
            r"([\u4e00-\u9fa5]{2,4}(?:先生|女士|同学|老师|朋友))",  # 中文人名+称呼
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if match and len(match) >= 2:
                    entities.append(match)
        
        # 去重
        return list(set(entities))


# 全局单例
_entity_extractor: Optional[EntityExtractor] = None


def get_entity_extractor() -> EntityExtractor:
    """获取全局实体抽取器实例"""
    global _entity_extractor
    if _entity_extractor is None:
        _entity_extractor = EntityExtractor()
    return _entity_extractor
