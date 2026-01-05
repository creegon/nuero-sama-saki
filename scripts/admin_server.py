# -*- coding: utf-8 -*-
"""
NeuroPet 管理面板 - FastAPI 后端

提供知识库管理和配置管理的 API
"""

import os
import sys
import json
import re
from typing import Dict, List, Any, Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from loguru import logger

import config

# 知识库客户端
from knowledge import get_knowledge_client

app = FastAPI(title="NeuroPet Admin Panel", version="1.0.0")

# ============================================================
# 数据模型
# ============================================================

class MemoryCreate(BaseModel):
    text: str
    category: str = "fact"

class MemoryUpdate(BaseModel):
    doc_id: str
    new_text: str

class MemoryDelete(BaseModel):
    ids: List[str]

class ConfigUpdate(BaseModel):
    key: str
    value: Any

# ============================================================
# 知识库 API
# ============================================================

@app.get("/api/memories")
async def get_all_memories():
    """获取所有记忆"""
    try:
        client = get_knowledge_client()
        records = client.get_all()
        return {"success": True, "data": records, "count": len(records)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/memories/search")
async def search_memories(q: str, limit: int = 20):
    """搜索记忆"""
    try:
        client = get_knowledge_client()
        results = client.search(q, n_results=limit)
        # 处理 metadata
        for r in results:
            if isinstance(r.get('metadata'), str):
                try:
                    r['metadata'] = json.loads(r['metadata'])
                except:
                    r['metadata'] = {}
        return {"success": True, "data": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/memories")
async def add_memory(memory: MemoryCreate):
    """添加记忆"""
    try:
        client = get_knowledge_client()
        doc_id = client.add(
            text=memory.text,
            metadata={
                "category": memory.category,
                "source": "manual",
                "verified": True,
                "timestamp": datetime.now().timestamp()
            }
        )
        return {"success": True, "id": doc_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/memories")
async def update_memory(memory: MemoryUpdate):
    """更新记忆"""
    try:
        client = get_knowledge_client()
        success = client.update_text(memory.doc_id, memory.new_text)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/memories")
async def delete_memories(data: MemoryDelete):
    """批量删除记忆"""
    try:
        client = get_knowledge_client()
        deleted = []
        skipped = []
        
        # 获取所有记录检查 core
        all_records = client.get_all()
        core_ids = {r['id'] for r in all_records if r.get('metadata', {}).get('category') == 'core'}
        
        for doc_id in data.ids:
            if doc_id in core_ids:
                skipped.append(doc_id)
                continue
            try:
                client.delete(doc_id)
                deleted.append(doc_id)
            except:
                pass
        
        return {"success": True, "deleted": len(deleted), "skipped": len(skipped)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/memories/stats")
async def get_memory_stats():
    """获取统计信息"""
    try:
        client = get_knowledge_client()
        records = client.get_all()
        
        categories = {}
        for r in records:
            cat = r.get('metadata', {}).get('category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1
        
        return {
            "success": True,
            "total": len(records),
            "categories": categories
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 🔥 测试 API (三元组 + Hybrid 检索)
# ============================================================

@app.get("/api/triples")
async def get_all_triples():
    """获取所有三元组"""
    try:
        from knowledge.triple_store import get_triple_store
        store = get_triple_store()
        triples = [t.to_dict() for t in store.triples.values()]
        return {
            "success": True,
            "data": triples,
            "count": len(triples),
            "stats": store.get_stats()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/triples/search")
async def search_triples(entity: str):
    """按实体搜索三元组"""
    try:
        from knowledge.triple_store import get_triple_store
        store = get_triple_store()
        results = store.find_by_entity(entity)
        return {
            "success": True,
            "entity": entity,
            "data": [str(t) for t in results],
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hybrid/search")
async def hybrid_search(q: str, top_k: int = 5):
    """Hybrid 检索测试 (Vector + Graph)"""
    try:
        from knowledge import get_knowledge_base
        from knowledge.triple_store import get_triple_store
        from knowledge.hybrid_retriever import get_hybrid_retriever
        
        kb = get_knowledge_base()
        retriever = get_hybrid_retriever()
        retriever.set_stores(kb, get_triple_store())
        
        results = retriever.search(q, top_k=top_k)
        
        return {
            "success": True,
            "query": q,
            "data": [
                {
                    "memory_id": r.memory_id,
                    "text": r.text[:200] + "..." if len(r.text) > 200 else r.text,
                    "score": round(r.score, 3),
                    "vector_score": round(r.vector_score, 3),
                    "graph_score": round(r.graph_score, 3),
                    "triples": [str(t) for t in r.related_triples]
                }
                for r in results
            ],
            "count": len(results),
            "prompt_format": retriever.format_for_prompt(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/test/decay")
async def trigger_decay():
    """手动触发记忆衰减"""
    try:
        from knowledge import get_knowledge_base
        from knowledge.memory_manager import MemoryManager
        
        kb = get_knowledge_base()
        manager = MemoryManager(kb)
        count = manager.decay_old_memories()
        
        return {
            "success": True,
            "message": f"衰减完成，处理 {count} 条记忆"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ExtractTripleRequest(BaseModel):
    text: str


@app.post("/api/test/extract-triples")
async def test_extract_triples(data: ExtractTripleRequest):
    """测试三元组抽取"""
    try:
        from knowledge.entity_extractor import get_entity_extractor
        from llm import get_llm_client
        
        extractor = get_entity_extractor()
        if not extractor.llm_client:
            extractor.set_llm_client(get_llm_client())
        
        triples = await extractor.extract(data.text)
        
        return {
            "success": True,
            "input": data.text,
            "triples": [
                {
                    "subject": t.subject,
                    "predicate": t.predicate,
                    "object": t.object,
                    "metadata": t.metadata
                }
                for t in triples
            ],
            "count": len(triples)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 配置 API
# ============================================================

# 可编辑的配置项（分组）
CONFIG_GROUPS = {
    "llm": {
        "title": "🤖 LLM 配置",
        "items": ["LLM_API_BASE", "LLM_API_KEY", "LLM_MODEL"]
    },
    "vision": {
        "title": "👁️ 视觉配置",
        "items": ["VISION_ENABLED", "VISION_MODEL", "SCREENSHOT_MAX_SIZE"]
    },
    "knowledge": {
        "title": "📚 知识库配置",
        "items": ["ENABLE_KNOWLEDGE", "KNOWLEDGE_SERVER_PORT", "MEMORY_INJECTION_COUNT", 
                  "MEMORY_DECAY_DAYS", "MEMORY_SIMILARITY_THRESHOLD"]
    },
    "proactive": {
        "title": "💬 主动对话",
        "items": ["PROACTIVE_CHAT_ENABLED", "PROACTIVE_CHECK_INTERVAL_MIN", 
                  "PROACTIVE_CHECK_INTERVAL_MAX", "PROACTIVE_MIN_IDLE_TIME"]
    },
    "tts": {
        "title": "🔊 TTS 配置",
        "items": ["VOXCPM_USE_DYNAMIC_CFG", "VOXCPM_CFG_SHORT", "VOXCPM_CFG_MEDIUM", 
                  "VOXCPM_CFG_LONG", "VOXCPM_INFERENCE_STEPS"]
    },
    "live2d": {
        "title": "🎭 Live2D 配置",
        "items": ["LIVE2D_FPS", "LIVE2D_LIPSYNC_ENABLED", "LIVE2D_EXPRESSION_LERP_SPEED",
                  "LIVE2D_IDLE_BODY_BREATH_ENABLED", "LIVE2D_IDLE_TAIL_ENABLED"]
    },
    "stt": {
        "title": "🎤 语音识别",
        "items": ["VOICE_TO_LLM_ENABLED", "STT_ENGINE", "VAD_THRESHOLD", "VAD_MIN_SILENCE_MS"]
    }
}


@app.get("/api/config")
async def get_config():
    """获取所有配置"""
    result = {}
    
    for group_id, group_info in CONFIG_GROUPS.items():
        items = {}
        for key in group_info["items"]:
            if hasattr(config, key):
                value = getattr(config, key)
                # 过滤掉路径等敏感信息
                if isinstance(value, str) and (os.sep in value or value.startswith("/")):
                    continue
                items[key] = {
                    "value": value,
                    "type": type(value).__name__
                }
        result[group_id] = {
            "title": group_info["title"],
            "items": items
        }
    
    return {"success": True, "data": result}


@app.put("/api/config")
async def update_config(data: ConfigUpdate):
    """更新配置（仅运行时生效，不持久化）"""
    try:
        if not hasattr(config, data.key):
            raise HTTPException(status_code=404, detail=f"配置项 {data.key} 不存在")
        
        # 类型转换
        old_value = getattr(config, data.key)
        if isinstance(old_value, bool):
            new_value = data.value if isinstance(data.value, bool) else str(data.value).lower() in ('true', '1', 'yes')
        elif isinstance(old_value, int):
            new_value = int(data.value)
        elif isinstance(old_value, float):
            new_value = float(data.value)
        else:
            new_value = data.value
        
        setattr(config, data.key, new_value)
        logger.info(f"配置更新: {data.key} = {new_value}")
        
        return {"success": True, "key": data.key, "value": new_value}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 前端页面
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def index():
    """返回管理面板 HTML"""
    html_path = os.path.join(os.path.dirname(__file__), "admin_panel.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>admin_panel.html not found</h1>"


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    import uvicorn
    print("[*] Starting NeuroPet Admin Panel...")
    print("[*] Open http://127.0.0.1:7861")
    uvicorn.run(app, host="127.0.0.1", port=7861, log_level="info")
