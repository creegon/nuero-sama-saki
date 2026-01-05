# -*- coding: utf-8 -*-
"""
知识库客户端 - 进程隔离版

与 KnowledgeServer 通信，提供与 KnowledgeBase 相同的接口
"""

import os
import sys
import json
import socket
import subprocess
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
# 知识库客户端
# ============================================================

class KnowledgeClient:
    """
    知识库 RPC 客户端
    
    提供与 KnowledgeBase 相同的接口，但实际调用远程服务
    """
    
    def __init__(self, host: str = None, port: int = None):
        self.host = host or config.KNOWLEDGE_SERVER_HOST
        self.port = port or config.KNOWLEDGE_SERVER_PORT
        self._server_process = None
        self._req_id = 0
    
    def _send_request(self, method: str, params: Dict = None) -> any:
        """发送 JSON-RPC 请求"""
        if params is None:
            params = {}
        
        self._req_id += 1
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._req_id
        }
        
        MAX_RETRIES = 3
        RETRY_DELAY = 0.5
        for attempt in range(MAX_RETRIES):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(config.KNOWLEDGE_SOCKET_TIMEOUT)
                sock.connect((self.host, self.port))
                
                sock.sendall((json.dumps(request) + "\n").encode("utf-8"))
                
                # 接收响应
                data = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                    if b"\n" in data:
                        break
                
                sock.close()
                
                if not data:
                    raise ConnectionError("Empty response")
                
                response = json.loads(data.decode("utf-8").strip())
                
                if "error" in response:
                    raise RuntimeError(response["error"].get("message", "Unknown error"))
                
                return response.get("result")
                
            except ConnectionRefusedError:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"知识库服务未响应，重试 {attempt + 1}/{MAX_RETRIES}...")
                    time.sleep(RETRY_DELAY)
                else:
                    raise RuntimeError(
                        "无法连接到知识库服务！\n"
                        "请先启动服务: python knowledge/server.py\n"
                        "或设置 DISABLE_KNOWLEDGE=true 禁用知识库"
                    )
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    raise
    
    def ping(self) -> bool:
        """检查服务是否可用"""
        try:
            result = self._send_request("ping")
            return result == "pong"
        except:
            return False
    
    def add(self, text: str, metadata: Dict = None, doc_id: str = None) -> str:
        """添加知识条目"""
        return self._send_request("add", {
            "text": text,
            "metadata": metadata,
            "doc_id": doc_id
        })
    
    def search(self, query: str, n_results: int = 3, where: Dict = None) -> List[Dict]:
        """语义搜索"""
        return self._send_request("search", {
            "query": query,
            "n_results": n_results,
            "where": where
        })
    
    def get_context_for_llm(self, query: str, n_results: int = 3, threshold: float = 1.5) -> str:
        """获取用于 LLM 的上下文"""
        return self._send_request("get_context_for_llm", {
            "query": query,
            "n_results": n_results,
            "threshold": threshold
        })
    
    def delete(self, doc_id: str) -> bool:
        """删除知识条目"""
        return self._send_request("delete", {"doc_id": doc_id})
    
    def count(self) -> int:
        """返回知识条目数量"""
        return self._send_request("count")
    
    def add_with_dedup(self, text: str, metadata: Dict = None, similarity_threshold: float = 0.85) -> str:
        """去重添加知识条目"""
        return self._send_request("add_with_dedup", {
            "text": text,
            "metadata": metadata,
            "similarity_threshold": similarity_threshold
        })
    
    def update_importance(self, doc_id: str, delta: float = 0.5) -> bool:
        """更新记忆重要性"""
        return self._send_request("update_importance", {
            "doc_id": doc_id,
            "delta": delta
        })
    
    def update_text(self, doc_id: str, new_text: str) -> bool:
        """更新记忆文本内容"""
        return self._send_request("update_text", {
            "doc_id": doc_id,
            "new_text": new_text
        })
    
    def get_all(self) -> List[Dict]:
        """获取所有记录"""
        return self._send_request("get_all")


# ============================================================
# 服务启动器
# ============================================================

def start_knowledge_server() -> subprocess.Popen:
    """
    在独立进程中启动知识库服务
    
    Returns:
        服务进程对象
    """
    server_script = os.path.join(os.path.dirname(__file__), "server.py")
    
    # 使用当前 Python 解释器
    python_exe = sys.executable
    
    logger.info("📚 正在启动知识库服务进程...")
    
    # 启动进程（不继承主进程的 stdout/stderr）
    process = subprocess.Popen(
        [python_exe, server_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    )
    
    # 等待服务启动
    client = KnowledgeClient()
    for i in range(20):  # 最多等 10 秒
        time.sleep(0.5)
        if client.ping():
            logger.info("📚 知识库服务已就绪")
            return process
    
    # 启动失败
    process.terminate()
    raise RuntimeError("知识库服务启动超时")


def ensure_knowledge_server() -> KnowledgeClient:
    """
    确保知识库服务正在运行，返回客户端
    
    如果服务未运行，自动启动
    """
    client = KnowledgeClient()
    
    if client.ping():
        logger.debug("📚 知识库服务已在运行")
        return client
    
    # 尝试启动服务
    try:
        start_knowledge_server()
        return client
    except Exception as e:
        logger.error(f"📚 知识库服务启动失败: {e}")
        raise


# ============================================================
# 全局单例
# ============================================================

_knowledge_client: Optional[KnowledgeClient] = None


def get_knowledge_client() -> KnowledgeClient:
    """获取全局知识库客户端实例"""
    global _knowledge_client
    if _knowledge_client is None:
        _knowledge_client = ensure_knowledge_server()
    return _knowledge_client


# ============================================================
# 兼容性包装器
# ============================================================

class KnowledgeBaseProxy:
    """
    KnowledgeBase 兼容代理
    
    提供与原 KnowledgeBase 完全相同的接口
    内部使用 KnowledgeClient 与服务通信
    """
    
    def __init__(self):
        self._client = None
    
    def _ensure_client(self):
        if self._client is None:
            self._client = get_knowledge_client()
    
    def add(self, text: str, metadata: Dict = None, doc_id: str = None) -> str:
        self._ensure_client()
        return self._client.add(text, metadata, doc_id)
    
    def add_with_dedup(self, text: str, metadata: Dict = None, similarity_threshold: float = 0.85) -> str:
        self._ensure_client()
        return self._client.add_with_dedup(text, metadata, similarity_threshold)
    
    def search(self, query: str, n_results: int = 3, where: Dict = None) -> List[Dict]:
        self._ensure_client()
        return self._client.search(query, n_results, where)
    
    def get_context_for_llm(self, query: str, n_results: int = 3, threshold: float = 1.5) -> str:
        self._ensure_client()
        return self._client.get_context_for_llm(query, n_results, threshold)
    
    def delete(self, doc_id: str) -> bool:
        self._ensure_client()
        return self._client.delete(doc_id)
    
    def count(self) -> int:
        self._ensure_client()
        return self._client.count()
    
    def update_importance(self, doc_id: str, delta: float = 0.5) -> bool:
        self._ensure_client()
        return self._client.update_importance(doc_id, delta)
    
    def update_text(self, doc_id: str, new_text: str) -> bool:
        self._ensure_client()
        return self._client.update_text(doc_id, new_text)
    
    def get_all(self) -> List[Dict]:
        self._ensure_client()
        return self._client.get_all()


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("知识库客户端测试")
    print("=" * 50)
    
    client = KnowledgeClient()
    
    print("\n[1] Ping 测试...")
    if client.ping():
        print("   ✓ 服务已连接")
    else:
        print("   ✗ 服务未响应，尝试启动...")
        start_knowledge_server()
        if client.ping():
            print("   ✓ 服务已启动")
        else:
            print("   ✗ 启动失败")
            sys.exit(1)
    
    print("\n[2] 知识库条目数...")
    count = client.count()
    print(f"   条目数: {count}")
    
    print("\n[3] 搜索测试...")
    results = client.search("祥子喜欢什么", n_results=2)
    for r in results:
        print(f"   [{r['distance']:.3f}] {r['text'][:40]}...")
    
    print("\n" + "=" * 50)
    print("测试完成!")
