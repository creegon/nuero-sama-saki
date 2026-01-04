# -*- coding: utf-8 -*-
"""
Live2D 控制工具 - 让小祥控制自己的位置和大小

🔥 线程安全机制 (2026-01-03 重写):
- 所有 Qt 方法调用都通过 signals/slots 机制实现跨线程通信
- 使用 pyqtSignal 确保在 Qt 主线程执行
- 工具只负责发送请求，不等待结果（fire-and-forget）
"""

import sys
import os
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .base import BaseTool, ToolResult


class Live2DControlTool(BaseTool):
    """
    Live2D 位置/大小控制工具
    
    让小祥可以移动自己的位置、调整大小、或者暂时消失
    
    🔥 所有操作都是 fire-and-forget（发了就返回），不等待 Qt 执行完成
    """
    
    name = "move_self"
    description = "移动或调整自己的位置和大小"
    usage_hint = "移动位置/调整大小。参数: left/right/top_left/top_right/top_center/bottom_left/bottom_right/bottom_center/hide/show/larger/smaller。"
    usage_example = (
        "你挡住我了",
        "[pout] 哼，那我换个地方。[CALL:move_self:bottom_left]"
    )
    parallel_hint = "让我动一下..."
    requires_context = True
    
    async def execute(self, context: str = "", args: str = "", **kwargs) -> ToolResult:
        """
        执行位置/大小控制
        
        Args:
            context: 用户说的话
            args: 控制命令 (参见 usage_hint)
        """
        try:
            from live2d_local.controller import get_live2d_controller
            
            controller = get_live2d_controller()
            if not controller:
                return ToolResult(success=False, error="Live2D 控制器未初始化")
            
            # 🔥 使用 controller 的线程安全方法
            # 这些方法内部会通过 signal 调度到 Qt 主线程
            
            # 合并 args 和 context 用于意图分析，优先查看 args
            intent_source = (args + " " + context).lower()
            result_msg = ""
            
            # --- 显式命令/意图分析 ---
            
            # 1. 隐藏/显示
            if any(k in intent_source for k in ["hide", "消失", "别挡", "走开", "隐藏"]):
                controller.request_set_scale(0.0)
                result_msg = "已隐藏。如果想让我回来，就说'回来'。"
                
            elif any(k in intent_source for k in ["show", "回来", "出来", "显示", "回到"]):
                controller.request_set_scale(1.0)
                controller.request_move_to_corner("bottom_right")
                result_msg = "我回来了！"
            
            # 2. 缩放
            elif any(k in intent_source for k in ["larger", "变大", "大一点", "看不清"]):
                controller.request_scale_change(0.3)
                result_msg = "变大了一点"
                
            elif any(k in intent_source for k in ["smaller", "变小", "小一点", "太大"]):
                controller.request_scale_change(-0.3)
                result_msg = "变小了一点"
            
            # 3. 指定位置移动
            elif any(k in intent_source for k in ["top_left", "左上"]):
                controller.request_move_to_corner("top_left")
                result_msg = "移动到左上角了。"
                
            elif any(k in intent_source for k in ["top_right", "右上"]):
                controller.request_move_to_corner("top_right")
                result_msg = "移动到右上角了。"
                
            elif any(k in intent_source for k in ["bottom_left", "左下"]):
                controller.request_move_to_corner("bottom_left")
                result_msg = "移动到左下角了。"
                
            elif any(k in intent_source for k in ["bottom_right", "右下"]):
                controller.request_move_to_corner("bottom_right")
                result_msg = "移动到右下角了。"
            
            elif any(k in intent_source for k in ["top_center", "上方中间", "top center"]):
                controller.request_move_to_corner("top_center")
                result_msg = "移动到上方中间了。"
                
            elif any(k in intent_source for k in ["bottom_center", "下方中间", "bottom center"]):
                controller.request_move_to_corner("bottom_center")
                result_msg = "移动到下方中间了。"
            
            # 4. 相对移动/自动移动
            elif any(k in intent_source for k in ["left", "左边"]):
                controller.request_move_to_corner("bottom_left")
                result_msg = "去左边了。"
            
            elif any(k in intent_source for k in ["right", "右边"]):
                controller.request_move_to_corner("bottom_right")
                result_msg = "去右边了。"

            elif any(k in intent_source for k in ["挡住", "让开", "换个位置", "移动", "move"]):
                # 智能切换到对面 (在 Qt 线程中处理)
                controller.request_toggle_side()
                result_msg = "换了个位置。"
            
            else:
                # 默认行为（如果参数无法识别，或是随机移动请求）
                if args:
                    logger.warning(f"Live2D 未知参数: {args}")
                
                controller.request_random_corner()
                result_msg = "换了个位置。"
            
            logger.info(f"🎮 Live2D 控制: {result_msg} (args={args})")
            
            return ToolResult(
                success=True,
                data=result_msg
            )
            
        except Exception as e:
            logger.error(f"Live2D 控制失败: {e}")
            import traceback
            traceback.print_exc()
            return ToolResult(
                success=False,
                data="",
                error=str(e)
            )
