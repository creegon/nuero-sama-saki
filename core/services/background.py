# -*- coding: utf-8 -*-
"""
后台服务管理器 (Knowledge, Live2D)
"""

import os
import time
import threading
from loguru import logger
import config

class BackgroundServices:
    """管理后台服务的启动和停止"""
    
    def __init__(self, pet_instance):
        self.pet = pet_instance
        self.log = logger.bind(module="BackgroundServices")
        self._knowledge_thread = None
        self._live2d_thread = None

    def start_knowledge_service(self):
        """预加载知识库 (通过客户端连接服务)"""
        # 优先读取 config，其次环境变量
        enable_knowledge = getattr(config, "ENABLE_KNOWLEDGE", False) or \
                           (os.getenv("ENABLE_KNOWLEDGE", "").lower() == "true")
        
        if not enable_knowledge:
            self.log.warning("⚠️ 知识库已禁用 (config.ENABLE_KNOWLEDGE=False)")
            return

        # 🔥 使用客户端连接知识库服务（自动启动服务）
        self.log.info("📚 正在连接知识库服务...")
        try:
            from knowledge import get_knowledge_client, KnowledgeBaseProxy
            client = get_knowledge_client()  # 自动启动服务
            kb_proxy = KnowledgeBaseProxy()  # 兼容 KnowledgeBase 接口
            self.log.info(f"✅ 知识库服务已连接: {client.count()} 条记录")
        except Exception as e:
            self.log.error(f"❌ 知识库服务连接失败: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # 后续的知识监控器初始化放到后台线程
        def init_monitor():
            try:
                # 等待 LLM Client 初始化完成
                self._wait_for_llm_client()
                
                if self.pet.llm_client:
                    from core.knowledge_monitor import KnowledgeMonitor
                    self.log.info("🧠 初始化知识监控器...")
                    
                    self.pet.knowledge_monitor = KnowledgeMonitor(self.pet.llm_client, kb_proxy)
                    self.pet.knowledge_monitor.start()
                    
                    # 动态更新 ResponseHandler
                    if self.pet.response_handler:
                        self.pet.response_handler.knowledge_monitor = self.pet.knowledge_monitor
                        self.log.info("✅ 知识库已集成到响应处理器")
                else:
                    self.log.error("❌ LLM Client 等待超时，无法启动知识监控器")
            except Exception as e:
                self.log.error(f"❌ 知识监控器初始化失败: {e}")
        
        # 后台初始化监控器（不阻塞主线程）
        self._knowledge_thread = threading.Thread(target=init_monitor, daemon=True, name="KnowledgeMonitorThread")
        self._knowledge_thread.start()

    def _wait_for_llm_client(self, timeout=30):
        """等待 LLM 客户端初始化"""
        wait_interval = 0.5
        waited = 0
        while not self.pet.llm_client and waited < timeout:
            time.sleep(wait_interval)
            waited += wait_interval

    def start_live2d(self):
        """启动 Live2D (异步)"""
        def run_live2d():
            try:
                from PyQt5.QtWidgets import QApplication
                import live2d.v3 as live2d
                from live2d_local.controller import Live2DController, set_live2d_controller
                
                live2d.init()
                # 检查是否已有 app 实例（在某些环境中防止冲突）
                if QApplication.instance():
                    app = QApplication.instance()
                else:
                    app = QApplication([])
                
                self.pet._qt_app = app
                
                model_path = config.LIVE2D_MODEL_PATH
                controller = Live2DController(
                    model_path, width=540, height=672, fps=config.LIVE2D_FPS
                )
                controller.move_to_bottom_right()
                controller.show()
                
                set_live2d_controller(controller)
                self.pet._live2d_controller = controller
                
                # 🎯 连接交互信号
                controller._sig_text_input.connect(self._on_text_input)
                controller._sig_interaction.connect(self._on_interaction)
                controller._sig_exit_program.connect(self._on_exit_program)
                
                if self.pet.audio_queue:
                    self.pet.audio_queue.set_live2d_controller(controller)
                
                self.log.info("🎭 Live2D 控制器已启动 (右下角)")
                
                app.exec()
                live2d.dispose()
                
            except ImportError as e:
                self.log.warning(f"Live2D 依赖未安装: {e}")
            except Exception as e:
                self.log.error(f"Live2D 启动失败: {e}")
        
        self._live2d_thread = threading.Thread(target=run_live2d, daemon=True)
        self._live2d_thread.start()
        time.sleep(1.0)

    def stop_live2d(self):
        """停止 Live2D"""
        if self.pet._qt_app:
            try:
                from PyQt5.QtCore import QMetaObject, Qt
                QMetaObject.invokeMethod(self.pet._qt_app, "quit", Qt.QueuedConnection)
            except:
                try:
                    self.pet._qt_app.quit()
                except:
                    pass
    
    # ==================== 🎯 交互信号处理 ====================
    
    def _on_text_input(self, text: str):
        """处理文字输入 (从 Qt 线程调用)"""
        import asyncio
        
        self.log.info(f"💬 收到文字输入: {text}")
        
        # 在异步线程中处理
        def run_async():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._handle_text_input(text))
                loop.close()
            except Exception as e:
                self.log.error(f"文字输入处理失败: {e}")
        
        threading.Thread(target=run_async, daemon=True).start()
    
    async def _handle_text_input(self, text: str):
        """异步处理文字输入"""
        if not self.pet.response_handler:
            self.log.warning("ResponseHandler 未初始化")
            return
        
        # 更新交互时间
        if self.pet.proactive_chat:
            self.pet.proactive_chat.update_interaction_time()
        
        # 处理文字输入
        await self.pet.response_handler.process_user_input(text, was_interrupted=False)
    
    def _on_interaction(self, prompt: str):
        """处理触摸/拖动交互 (从 Qt 线程调用)"""
        import asyncio
        
        self.log.info(f"🎯 收到交互: {prompt}")
        
        # 在异步线程中处理
        def run_async():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._handle_interaction(prompt))
                loop.close()
            except Exception as e:
                self.log.error(f"交互处理失败: {e}")
        
        threading.Thread(target=run_async, daemon=True).start()
    
    async def _handle_interaction(self, prompt: str):
        """异步处理交互"""
        if not self.pet.response_handler:
            self.log.warning("ResponseHandler 未初始化")
            return
        
        # 更新交互时间
        if self.pet.proactive_chat:
            self.pet.proactive_chat.update_interaction_time()
        
        # 将交互 prompt 作为用户输入处理
        await self.pet.response_handler.process_user_input(prompt, was_interrupted=False)
    
    def _on_exit_program(self):
        """处理退出程序请求"""
        self.log.info("🚪 收到退出程序请求")
        
        # 设置退出标志
        self.pet._is_running = False
        
        # 触发优雅退出
        if self.pet._qt_app:
            try:
                from PyQt5.QtCore import QMetaObject, Qt
                QMetaObject.invokeMethod(self.pet._qt_app, "quit", Qt.QueuedConnection)
            except:
                pass
        
        # 发送 KeyboardInterrupt 信号给主线程
        import signal
        import os as _os
        try:
            _os.kill(_os.getpid(), signal.SIGINT)
        except:
            pass

