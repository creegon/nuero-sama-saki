# -*- coding: utf-8 -*-
"""
知识库服务 - 进程隔离版

将 LanceDB 知识库运行在独立进程中，通过 IPC 与主程序通信
彻底解决与 STT/TTS 库的 DLL 冲突问题

使用方法:
    # 启动服务（在主程序之前）
    python knowledge/server.py

    # 或者让主程序自动启动
    from knowledge.client import get_knowledge_client
    client = get_knowledge_client()  # 自动启动服务进程
"""

import os
import sys
import json
import socket
import threading
import time
from typing import Dict, List, Optional
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


# ============================================================
# 配置
# ============================================================
# 配置已移动到 config.py


# ============================================================
# 知识库服务器（运行在独立进程）
# ============================================================

class KnowledgeServer:
    """
    知识库 RPC 服务
    
    接收 JSON-RPC 请求，调用 LanceDB 知识库执行操作
    """
    
    def __init__(self, host: str = None, port: int = None):
        self.host = host or config.KNOWLEDGE_SERVER_HOST
        self.port = port or config.KNOWLEDGE_SERVER_PORT
        self.kb = None
        self._running = False
        self._server_socket = None
    
    def start(self):
        """启动知识库服务"""
        # 延迟导入 ChromaDB（只在此进程中加载）
        from knowledge import KnowledgeBase
        
        logger.info("📚 知识库服务正在初始化...")
        self.kb = KnowledgeBase()
        logger.info(f"📚 知识库已加载: {self.kb.count()} 条记录")
        
        # 启动 socket 服务
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen(5)
        
        self._running = True
        logger.info(f"📚 知识库服务已启动: {self.host}:{self.port}")
        
        while self._running:
            try:
                client_socket, addr = self._server_socket.accept()
                threading.Thread(
                    target=self._handle_client,
                    args=(client_socket,),
                    daemon=True
                ).start()
            except Exception as e:
                if self._running:
                    logger.error(f"服务器错误: {e}")
    
    def stop(self):
        """停止服务"""
        self._running = False
        if self._server_socket:
            self._server_socket.close()
    
    def _handle_client(self, client_socket: socket.socket):
        """处理客户端请求"""
        try:
            client_socket.settimeout(config.KNOWLEDGE_SOCKET_TIMEOUT)
            
            # 接收数据
            data = b""
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break
            
            if not data:
                return
            
            # 解析 JSON-RPC
            request = json.loads(data.decode("utf-8").strip())
            method = request.get("method", "")
            params = request.get("params", {})
            req_id = request.get("id", 0)
            
            # 执行方法
            result = self._dispatch(method, params)
            
            # 返回响应
            response = {
                "jsonrpc": "2.0",
                "result": result,
                "id": req_id
            }
            client_socket.sendall((json.dumps(response) + "\n").encode("utf-8"))
            
        except Exception as e:
            logger.error(f"处理请求失败: {e}")
            try:
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {"code": -1, "message": str(e)},
                    "id": req_id if 'req_id' in dir() else 0
                }
                client_socket.sendall((json.dumps(error_response) + "\n").encode("utf-8"))
            except:
                pass
        finally:
            client_socket.close()
    
    def _dispatch(self, method: str, params: Dict):
        """分发方法调用"""
        if method == "add":
            return self.kb.add(
                text=params["text"],
                metadata=params.get("metadata"),
                doc_id=params.get("doc_id")
            )
        
        elif method == "add_with_dedup":
            return self.kb.add_with_dedup(
                text=params["text"],
                metadata=params.get("metadata"),
                similarity_threshold=params.get("similarity_threshold", 0.85)
            )
        
        elif method == "search":
            return self.kb.search(
                query=params["query"],
                n_results=params.get("n_results", 3),
                where=params.get("where")
            )
        
        elif method == "get_context_for_llm":
            return self.kb.get_context_for_llm(
                query=params["query"],
                n_results=params.get("n_results", 3),
                threshold=params.get("threshold", 1.5)
            )
        
        elif method == "delete":
            return self.kb.delete(params["doc_id"])
        
        elif method == "count":
            return self.kb.count()
        
        elif method == "update_importance":
            return self.kb.update_importance(
                doc_id=params["doc_id"],
                delta=params.get("delta", 0.5)
            )
        
        elif method == "update_text":
            # 使用 MemoryManager 更新文本
            from knowledge.memory_manager import create_memory_manager
            manager = create_memory_manager(self.kb)
            return manager.update_text(
                doc_id=params["doc_id"],
                new_text=params["new_text"]
            )
        
        elif method == "get_all":
            # 获取所有记录（用于 GUI）
            import json
            all_data = self.kb._table.to_pandas()
            records = []
            for _, row in all_data.iterrows():
                metadata = row.get("metadata", "{}")
                try:
                    meta = json.loads(metadata) if isinstance(metadata, str) else metadata
                except:
                    meta = {}
                records.append({
                    "id": row["id"],
                    "text": row.get("text", ""),
                    "metadata": meta
                })
            return records
        
        elif method == "ping":
            return "pong"
        
        else:
            raise ValueError(f"Unknown method: {method}")


# ============================================================
# 主函数
# ============================================================

def main():
    """启动知识库服务"""
    import signal
    
    server = KnowledgeServer()
    
    def shutdown(sig, frame):
        logger.info("📚 正在关闭知识库服务...")
        server.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    try:
        server.start()
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
