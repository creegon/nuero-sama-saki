# Live2D Integration Module
"""
Live2D 集成模块 - 使用官方 API

主要组件：
- Live2DController: PyQt5 透明窗口渲染控制器
- 口型同步: LipSyncAnalyzer / LipSyncController  
"""

from .lipsync import (
    LipSyncAnalyzer,
    LipSyncController,
    VOWEL_SHAPES,
    get_lip_sync_analyzer,
)


def get_live2d_controller():
    """获取全局 Live2D 控制器实例"""
    try:
        from .controller import get_live2d_controller as _get_controller
        return _get_controller()
    except ImportError:
        return None


def create_controller(model_path: str):
    """创建 Live2D 控制器"""
    from .controller import create_controller as _create
    return _create(model_path)


def set_live2d_controller(controller):
    """设置全局 Live2D 控制器实例"""
    from .controller import set_live2d_controller as _set
    _set(controller)


__all__ = [
    # Lip Sync
    "LipSyncAnalyzer",
    "LipSyncController",
    "VOWEL_SHAPES",
    "get_lip_sync_analyzer",
    # Controller
    "get_live2d_controller",
    "create_controller",
    "set_live2d_controller",
]
