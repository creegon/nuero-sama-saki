# -*- coding: utf-8 -*-
"""
知识库模块 - 基于 LanceDB 的语义搜索

使用 LanceDB 替代 ChromaDB，解决与 PyTorch/ONNX 的 DLL 冲突问题
LanceDB 是纯 Python 嵌入式向量数据库，类似 SQLite，无外部依赖

服务化架构：
    - 推荐使用 get_knowledge_client() 通过 RPC 访问知识库服务
    - 服务器: python knowledge/server.py
    - 客户端会自动启动服务器（如果未运行）
"""

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  ⚠️  CRITICAL WARNING - 勿删除此注释块 ⚠️                                    ║
# ║  ╠══════════════════════════════════════════════════════════════════════════════╣
# ║  下面的环境变量设置 **必须** 是整个模块最先执行的代码！                       ║
# ║                                                                              ║
# ║  ROOT CAUSE (2024-12-31 调试确认):                                           ║
# ║  - sentence_transformers 在导入时会加载 transformers 库                      ║
# ║  - transformers 库在导入时会尝试加载 TensorFlow 相关模块（即使你不使用 TF）   ║
# ║  - 如果环境中安装了 Keras 3，但 transformers 不支持 Keras 3，会导致：         ║
# ║    ValueError: Your currently installed version of Keras is Keras 3,        ║
# ║    but this is not yet supported in Transformers.                           ║
# ║                                                                              ║
# ║  SOLUTION:                                                                   ║
# ║  TRANSFORMERS_NO_TF 环境变量必须在 **任何可能触发 transformers 导入的**       ║
# ║  **代码执行之前** 设置，包括：                                               ║
# ║  - 直接 import transformers / sentence_transformers                          ║
# ║  - 导入任何可能间接导入上述库的模块（如 loguru 的某些插件）                   ║
# ║                                                                              ║
# ║  ❌ 错误做法：在 import os 之后、其他 import 之前设置                         ║
# ║  ✅ 正确做法：使用 import os as _os 作为第一行，立即设置环境变量              ║
# ║                                                                              ║
# ║  如果你需要修改这个模块的 import 顺序，请务必保持环境变量设置在最前面！       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
import os as _os
_os.environ["TRANSFORMERS_NO_TF"] = "1"  # 禁用 TensorFlow 后端
_os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"  # 抑制 TensorFlow 日志
_os.environ["USE_TF"] = "0"  # 额外保险
_os.environ["USE_TORCH"] = "1"  # 明确使用 PyTorch
# ═══════════════════════════════════════════════════════════════════════════════

# Core Implementation (直接访问，仅限 server.py 使用)
from .core import KnowledgeBase, get_knowledge_base

# Client (推荐使用，通过 RPC 访问)
from .client import (
    KnowledgeClient, 
    KnowledgeBaseProxy,
    get_knowledge_client,
    ensure_knowledge_server,
    start_knowledge_server
)

# Helpers (Explicitly exported)
from .retrieval import MemoryRetriever, create_memory_retriever
from .memory_manager import MemoryManager, create_memory_manager

__all__ = [
    # Direct access (仅限服务端)
    "KnowledgeBase",
    "get_knowledge_base",
    # Client access (推荐)
    "KnowledgeClient",
    "KnowledgeBaseProxy", 
    "get_knowledge_client",
    "ensure_knowledge_server",
    "start_knowledge_server",
    # Helpers
    "MemoryRetriever", 
    "create_memory_retriever",
    "MemoryManager",
    "create_memory_manager"
]

