# -*- coding: utf-8 -*-
"""
Neuro Service Launcher (preload.py)
启动所有 API 服务 (STT, TTS, LLM, RVC)
"""

import sys
import os
import time
import socket
import subprocess
from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

logger.remove()
logger.add(
    sys.stderr, 
    level="INFO", 
    format="<green>{time:HH:mm:ss}</green> | <cyan>{name}</cyan> | <level>{message}</level>"
)

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """检测端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.connect((host, port))
            return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

def start_service(name: str, port: int, cmd: str, work_dir: str = None, wait_seconds: int = 5):
    """启动单个服务"""
    if is_port_in_use(port):
        logger.info(f"✅ {name} 已在运行 (端口 {port})")
        return

    logger.info(f"🚀 正在启动 {name} (端口 {port})...")
    
    # 构造命令
    if work_dir:
        # 如果指定了目录，先切目录
        full_cmd = f'start "{name}" cmd /k "cd /d {work_dir} && {cmd}"'
    else:
        full_cmd = f'start "{name}" cmd /k "{cmd}"'
    
    try:
        subprocess.Popen(full_cmd, shell=True)
        
        # 等待服务初始化
        if wait_seconds > 0:
            logger.info(f"⏳ 等待 {name} 初始化 ({wait_seconds}秒)...")
            time.sleep(wait_seconds)
            
    except Exception as e:
        logger.error(f"❌ 启动 {name} 失败: {e}")

def main():
    print("""
    ╔═══════════════════════════════════════════════╗
    ║      🌟 Neuro Service Launcher 🌟             ║
    ║   启动所有后台 API 服务 (STT, TTS, LLM)       ║
    ╚═══════════════════════════════════════════════╝
    """)
    
    # 1. Antigravity LLM API
    start_service(
        name="Antigravity API",
        port=config.ANTIGRAVITY_PORT,
        cmd="npm start",
        work_dir=config.ANTIGRAVITY_DIR,
        wait_seconds=5
    )
    
    # 2. STT Service
    stt_script = os.path.join(config.SERVICES_DIR, "stt_service.py")
    start_service(
        name="STT Service",
        port=config.STT_SERVICE_PORT,
        cmd=f"python {stt_script}",
        wait_seconds=5
    )
    
    # 3. TTS Service
    tts_script = os.path.join(config.SERVICES_DIR, "tts_service.py")
    start_service(
        name="TTS Service",
        port=config.TTS_SERVICE_PORT,
        cmd=f"python {tts_script}",
        wait_seconds=5
    )
    
    # 4. RVC API (仅当配置使用 kokoro_rvc 时)
    if config.TTS_ENGINE == "kokoro_rvc":
        rvc_dir = getattr(config, 'RVC_API_DIR', '')
        if rvc_dir and os.path.exists(rvc_dir):
            python_exe = os.path.join(rvc_dir, "runtime", "python.exe")
            api_script = os.path.join(rvc_dir, "rvc_api_server.py")
            model_name = getattr(config, 'RVC_MODEL_NAME', 'xiangzi.pth')
            
            if os.path.exists(python_exe) and os.path.exists(api_script):
                cmd = f"{python_exe} {api_script} --port {config.RVC_API_PORT} --model {model_name}"
                start_service(
                    name="RVC API",
                    port=config.RVC_API_PORT,
                    cmd=cmd,
                    work_dir=rvc_dir,
                    wait_seconds=15
                )
    
    print("\n✅ 所有服务检测/启动完成！")
    print("现在可以运行 main.py (它会连接到这些服务)")
    
    # Keep window open if run directly
    # input("\n按 Enter 退出 Launcher...")
    time.sleep(2)

if __name__ == "__main__":
    main()
