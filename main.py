# -*- coding: utf-8 -*-
"""
Neuro-like AI Desktop Pet - Main Entry
主程序入口
"""

import sys
import os
import time
import socket
import subprocess
import argparse

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
import config


# 配置 loguru
logger.remove()
logger.add(
    sys.stderr, 
    level="DEBUG" if "--debug" in sys.argv or "-d" in sys.argv else "INFO", 
    format="<green>{time:HH:mm:ss}</green> | <cyan>{name:>12}</cyan> | <level>{message}</level>"
)
logger.add(
    "logs/neuro_{time:YYYY-MM-DD}.log",
    level="DEBUG",
    rotation="1 day",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}"
)


# ====================
# 服务管理
# ====================

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """检测端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.connect((host, port))
            return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False


def start_antigravity():
    """启动 Antigravity API 代理服务"""
    logger.info(f"   启动目录: {config.ANTIGRAVITY_DIR}")
    cmd = f'start "Antigravity API" cmd /k "cd /d {config.ANTIGRAVITY_DIR} && npm start"'
    subprocess.Popen(cmd, shell=True)
    
    logger.info("   等待 Antigravity 初始化 (5秒)...")
    time.sleep(5)


def ensure_services_running():
    """确保必要服务正在运行"""
    logger.info("🔍 检测服务状态...")
    
    if not is_port_in_use(config.ANTIGRAVITY_PORT):
        logger.info(f"📡 Antigravity 未检测到 (端口 {config.ANTIGRAVITY_PORT})，正在启动...")
        start_antigravity()
    else:
        logger.info(f"✓ Antigravity 已运行 (端口 {config.ANTIGRAVITY_PORT})")
    
    stt_name = "FireRedASR" if config.STT_ENGINE == "fireredasr" else "FunASR Paraformer"
    logger.info(f"📝 TTS/STT: VoxCPM + {stt_name}")
    logger.info("")


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="Neuro-like AI 桌宠")
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="启用 debug 模式"
    )
    parser.add_argument(
        "--skip-services", "-s",
        action="store_true",
        help="跳过服务检测和启动"
    )
    args = parser.parse_args()
    
    print("""
    ╔═══════════════════════════════════════════════╗
    ║                                               ║
    ║     🌟 Neuro-like AI 桌宠 - Phase 2 🌟        ║
    ║                                               ║
    ╚═══════════════════════════════════════════════╝
    """)
    
    # 🔥 后台预加载知识库 + Embedding 模型 (~17s)
    # 与其他组件并行加载，大幅减少总启动时间
    import threading
    knowledge_ready = threading.Event()
    
    def _preload_knowledge():
        try:
            # 这会触发 SentenceTransformer 加载（~17s）
            from knowledge import get_knowledge_base
            kb = get_knowledge_base()
            logger.info(f"✅ 知识库预加载完成: {kb.count()} 条记录")
            
            # 🔥 启动时执行记忆衰减（如果距上次衰减超过 24h）
            try:
                from knowledge.memory_manager import MemoryManager
                import os
                import json
                
                decay_state_file = "data/decay_state.json"
                last_decay = 0
                
                if os.path.exists(decay_state_file):
                    with open(decay_state_file, 'r') as f:
                        state = json.load(f)
                        last_decay = state.get("last_decay", 0)
                
                import time
                if time.time() - last_decay > 24 * 3600:  # 超过 24 小时
                    manager = MemoryManager(kb)
                    count = manager.decay_old_memories()
                    if count > 0:
                        logger.info(f"🧹 启动时记忆衰减: 处理 {count} 条")
                    
                    # 更新衰减状态
                    os.makedirs("data", exist_ok=True)
                    with open(decay_state_file, 'w') as f:
                        json.dump({"last_decay": time.time()}, f)
            except Exception as de:
                logger.debug(f"启动时衰减失败: {de}")
                
        except Exception as e:
            logger.error(f"❌ 知识库预加载失败: {e}")
        finally:
            knowledge_ready.set()
    
    preload_thread = threading.Thread(target=_preload_knowledge, daemon=True, name="KnowledgePreload")
    preload_thread.start()
    
    if args.debug:
        print("    🔧 Debug 模式已启用\n")
    
    # 创建日志目录
    os.makedirs("logs", exist_ok=True)
    
    # 检测服务
    if not args.skip_services:
        ensure_services_running()
    else:
        print("    ⏩ 跳过服务检测\n")
    
    # 启动桌宠
    from core import NeuroPet
    pet = NeuroPet(debug=args.debug)
    pet.start()


if __name__ == "__main__":
    main()
