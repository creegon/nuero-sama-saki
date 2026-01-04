# -*- coding: utf-8 -*-
"""
Live2D 控制器 - 丰川祥子专用

==============================================================================
重要经验教训 (2026-01-02 完全重写)
==============================================================================

1. 【使用底层 Model 类】
   - LAppModel 的 Update() 会导致身体乱动 (UpdateBreath bug)
   - 使用 Model 类可以精确控制每个 Update 步骤
   
2. 【Idle 动画配方】
   - Physics: 只调用 UpdatePhysics (头发物理)
   - 尾巴: 手动 ParamBreath 正弦波 (速度 0.8)
   - 身体呼吸: 手动 ParamBodyAngleY 正弦波 (速度 0.5, 幅度 1.4)
   - 眨眼: 手动控制 ParamEyeLOpen/ROpen (官方 UpdateBlink 不工作)
   
3. 【禁用的 Update 函数】
   - UpdateBreath: 会导致 ParamBodyAngleX 乱动!
   - UpdateBlink: 对这个模型无效
   - UpdateMotion: 无效

4. 【参数对照表】
   - ParamBreath: 尾巴 (0~1)
   - ParamBodyAngleY: 身体上下 (-10~10)
   - ParamEyeLOpen/ROpen: 眼睛 (0~1)
==============================================================================
"""

import sys
import os
import math
import random
import time
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, QOpenGLWidget
import OpenGL.GL as GL

import live2d.v3 as live2d
from live2d.utils.canvas import Canvas

from .lipsync import VOWEL_SHAPES
from .expressions import Params, EXPRESSIONS
from .emotion_modifiers import get_emotion_modifier, EmotionModifier

# 导入配置
try:
    import config
except ImportError:
    config = None


class Live2DController(QOpenGLWidget):
    """Live2D 桌宠控制器 - 使用底层 Model 类
    
    使用底层 Model 类获得完全控制，避免 LAppModel 的 bug。
    
    动画系统：
    - 头发: UpdatePhysics
    - 尾巴: 手动 ParamBreath
    - 身体呼吸: 手动 ParamBodyAngleY
    - 眨眼: 手动控制
    - 口型: 外部输入
    
    🔥 线程安全：外部调用应使用 request_* 方法，它们通过 signal 调度到 Qt 主线程
    """
    
    # 🔥 线程安全 Signals
    _sig_move_to_corner = pyqtSignal(str)
    _sig_set_scale = pyqtSignal(float)
    _sig_scale_change = pyqtSignal(float)
    _sig_toggle_side = pyqtSignal()
    _sig_random_corner = pyqtSignal()
    
    def __init__(
        self,
        model_path: str,
        width: int = 450,
        height: int = 560,
        fps: int = 60,
    ):
        super().__init__()
        
        self.model_path = model_path
        self.display_width = width
        self.display_height = height
        self.fps = fps
        
        # 使用底层 Model 类
        self.model: Optional[live2d.Model] = None
        self.canvas: Optional[Canvas] = None
        
        # 参数索引缓存
        self.param_indices = {}
        
        # 时间追踪
        self.last_time = time.time()
        self.start_time = time.time()
        
        # === Idle 参数 (从 config 读取，带默认值回退) ===
        self.enable_physics = getattr(config, 'LIVE2D_IDLE_PHYSICS_ENABLED', True) if config else True
        self.enable_tail = getattr(config, 'LIVE2D_IDLE_TAIL_ENABLED', True) if config else True
        self.enable_body_breath = getattr(config, 'LIVE2D_IDLE_BODY_BREATH_ENABLED', True) if config else True
        self.enable_blink = getattr(config, 'LIVE2D_IDLE_BLINK_ENABLED', True) if config else True
        
        # Idle 动画参数
        self.body_breath_speed = getattr(config, 'LIVE2D_IDLE_BODY_BREATH_SPEED', 0.5) if config else 0.5
        self.body_breath_amplitude = getattr(config, 'LIVE2D_IDLE_BODY_BREATH_AMPLITUDE', 1.4) if config else 1.4
        self.tail_speed = getattr(config, 'LIVE2D_IDLE_TAIL_SPEED', 0.8) if config else 0.8
        self.tail_amplitude = getattr(config, 'LIVE2D_IDLE_TAIL_AMPLITUDE', 1.0) if config else 1.0
        self.blink_interval_min = getattr(config, 'LIVE2D_IDLE_BLINK_INTERVAL_MIN', 2.0) if config else 2.0
        self.blink_interval_max = getattr(config, 'LIVE2D_IDLE_BLINK_INTERVAL_MAX', 5.0) if config else 5.0
        
        # 眨眼状态
        self.blink_value = 1.0
        self.next_blink_time = time.time() + random.uniform(self.blink_interval_min, self.blink_interval_max)
        self.is_blinking = False
        self.blink_phase = 0
        
        # === 口型同步 ===
        self.target_mouth_open = 0.0
        self.target_mouth_form = 0.0
        self.current_mouth_open = 0.0
        self.current_mouth_form = 0.0
        self.mouth_smoothing = 0.25
        self.is_speaking = False
        
        # === 表情系统 (带过渡) ===
        self.current_expression = "neutral"
        self.current_expression_values = {}   # 当前插值中的表情参数
        self.target_expression_values = {}    # 目标表情参数
        self.expression_lerp_speed = getattr(config, 'LIVE2D_EXPRESSION_LERP_SPEED', 0.08) if config else 0.08
        
        # === 情绪调制系统 ===
        self._base_breath_speed = self.body_breath_speed
        self._base_breath_amp = self.body_breath_amplitude
        self._base_tail_speed = self.tail_speed
        self._base_tail_amp = self.tail_amplitude
        self._base_blink_min = self.blink_interval_min
        self._base_blink_max = self.blink_interval_max
        
        # 头部摆动
        self.head_sway_amp = 0.0
        self.head_sway_speed = 0.3
        
        # 表情参数偏移 (由情绪调制)
        self.eye_open_offset = 0.0
        self.eye_smile_offset = 0.0
        self.brow_y_offset = 0.0
        self.cheek_offset = 0.0
        self.mouth_form_offset = 0.0
        
        # === 表情内循环动画 (Expression Loops) ===
        self.enable_expression_loops = True
        # thinking: 眼球缓慢移动
        self.thinking_eye_speed = 0.3
        self.thinking_eye_amp_x = 0.4
        self.thinking_eye_amp_y = 0.2
        # happy: 笑眼微微波动
        self.happy_smile_speed = 1.5
        self.happy_smile_amp = 0.1
        # shy: 眼球周期性躲避 + 脸红闪烁
        self.shy_eye_speed = 0.5
        self.shy_eye_amp = 0.3
        self.shy_cheek_speed = 0.8
        self.shy_cheek_amp = 0.15
        # curious: 头微微倾斜循环
        self.curious_head_speed = 0.4
        self.curious_head_amp = 3.0
        
        # === 说话时表情增强 ===
        self.enable_speaking_enhancement = True
        self.speaking_brow_mult = 0.15      # 眉毛随音量变化幅度
        self.speaking_eye_open_mult = 0.1   # 大声时眼睛稍微睁大
        self.speaking_blink_chance = 0.003  # 说话时偶尔眨眼的概率
        self.last_speaking_blink_time = 0
        
        # 窗口拖动
        self.drag_position = None
        
        # 窗口设置
        self.setWindowTitle("Sakiko")
        self.setFixedSize(width, height)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        
        # 🔥 连接 signals 到 slots (确保 Qt 操作在主线程执行)
        self._sig_move_to_corner.connect(self._slot_move_to_corner)
        self._sig_set_scale.connect(self._slot_set_scale)
        self._sig_scale_change.connect(self._slot_scale_change)
        self._sig_toggle_side.connect(self._slot_toggle_side)
        self._sig_random_corner.connect(self._slot_random_corner)
    
    def move_to_bottom_right(self):
        """移动窗口到屏幕右下角"""
        screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.availableGeometry()
            x = geometry.width() - self.display_width - 20
            y = geometry.height() - self.display_height - 20
            self.move(x, y)
    
    def initializeGL(self):
        """OpenGL 初始化"""
        live2d.glInit()
        
        # 使用底层 Model 类
        self.model = live2d.Model()
        self.model.LoadModelJson(self.model_path)
        self.model.CreateRenderer()
        self.model.Resize(self.display_width, self.display_height)
        
        # 缓存参数索引
        param_ids = self.model.GetParameterIds()
        for i, pid in enumerate(param_ids):
            self.param_indices[pid] = i
        
        # 创建 Canvas
        self.canvas = Canvas()
        self.canvas.SetSize(self.display_width, self.display_height)
        
        self.startTimer(int(1000 / self.fps))
        print("Live2D Controller initialized (using low-level Model class)")
    
    def timerEvent(self, event):
        """定时器回调 - 更新动画"""
        if not self.model:
            return
        
        current_time = time.time()
        delta_time = current_time - self.last_time
        self.last_time = current_time
        t = current_time - self.start_time
        
        # === 1. Physics (头发物理) ===
        if self.enable_physics:
            self.model.UpdatePhysics(delta_time)
        
        # === 2. 尾巴摆动 ===
        if self.enable_tail:
            breath = (math.sin(t * self.tail_speed * math.pi) + 1) / 2 * self.tail_amplitude
            self._set_param("ParamBreath", breath)
        
        # === 3. 身体呼吸模拟 ===
        if self.enable_body_breath:
            body_y = math.sin(t * self.body_breath_speed * math.pi * 2) * self.body_breath_amplitude
            self._set_param("ParamBodyAngleY", body_y)
        
        # === 4. 头部轻微摆动 ===
        if self.head_sway_amp > 0:
            head_z = math.sin(t * self.head_sway_speed * math.pi) * self.head_sway_amp
            self._set_param("ParamAngleZ", head_z)
        
        # === 5. 眨眼 ===
        if self.enable_blink:
            self._update_blink(current_time, delta_time)
        
        # === 6. 口型 ===
        self._update_mouth()
        if self.is_speaking or self.current_mouth_open > 0.01:
            self._set_param("ParamMouthOpenY", self.current_mouth_open)
            # 嘴巴形状 = 说话形状 + 偏移
            mouth_form = self.current_mouth_form + self.mouth_form_offset
            self._set_param("ParamMouthForm", max(-1.0, min(1.0, mouth_form)))
        elif self.mouth_form_offset != 0:
            # 不说话时也应用偏移
            self._set_param("ParamMouthForm", max(-1.0, min(1.0, self.mouth_form_offset)))
        
        # === 7. 表情参数 (平滑过渡) ===
        self._update_expression()
        for param_name, value in self.current_expression_values.items():
            # 跳过由偏移系统处理的参数
            if param_name in (Params.EYE_L_OPEN, Params.EYE_R_OPEN, 
                             Params.EYE_L_SMILE, Params.EYE_R_SMILE,
                             Params.BROW_L_Y, Params.BROW_R_Y,
                             Params.CHEEK, Params.MOUTH_FORM):
                continue
            if param_name in ("ParamMouthOpenY", "ParamMouthForm") and self.is_speaking:
                continue
            self._set_param(param_name, value)
        
        # === 8. 情绪参数偏移叠加 ===
        # 眼睛 = 眨眼值 + 表情值 + 偏移 + 说话增强
        expr_eye_open = self.current_expression_values.get(Params.EYE_L_OPEN, 0.0)
        speaking_eye_bonus = self.current_mouth_open * self.speaking_eye_open_mult if self.enable_speaking_enhancement and self.is_speaking else 0
        eye_open_final = self.blink_value + expr_eye_open + self.eye_open_offset + speaking_eye_bonus
        self._set_param("ParamEyeLOpen", max(0, min(1.5, eye_open_final)))
        self._set_param("ParamEyeROpen", max(0, min(1.5, eye_open_final)))
        
        # 笑眼 = 表情值 + 偏移 + 表情循环
        expr_eye_smile = self.current_expression_values.get(Params.EYE_L_SMILE, 0.0)
        smile_loop = self._get_expression_loop_smile(t)
        eye_smile_final = expr_eye_smile + self.eye_smile_offset + smile_loop
        self._set_param("ParamEyeLSmile", max(0, min(1.0, eye_smile_final)))
        self._set_param("ParamEyeRSmile", max(0, min(1.0, eye_smile_final)))
        
        # 眉毛 = 表情值 + 偏移 + 说话增强
        expr_brow_l = self.current_expression_values.get(Params.BROW_L_Y, 0.0)
        expr_brow_r = self.current_expression_values.get(Params.BROW_R_Y, 0.0)
        speaking_brow_bonus = self.current_mouth_open * self.speaking_brow_mult if self.enable_speaking_enhancement and self.is_speaking else 0
        self._set_param("ParamBrowLY", expr_brow_l + self.brow_y_offset + speaking_brow_bonus)
        self._set_param("ParamBrowRY", expr_brow_r + self.brow_y_offset + speaking_brow_bonus)
        
        # 脸红 = 表情值 + 偏移 + 表情循环
        expr_cheek = self.current_expression_values.get(Params.CHEEK, 0.0)
        cheek_loop = self._get_expression_loop_cheek(t)
        cheek_final = expr_cheek + self.cheek_offset + cheek_loop
        self._set_param("ParamCheek", max(0, cheek_final))
        
        # === 9. 表情内循环动画 ===
        if self.enable_expression_loops:
            self._apply_expression_loops(t)
        
        # === 10. 说话时偶尔眨眼 ===
        if self.enable_speaking_enhancement and self.is_speaking:
            if not self.is_blinking and random.random() < self.speaking_blink_chance:
                if current_time - self.last_speaking_blink_time > 1.0:  # 至少间隔1秒
                    self.is_blinking = True
                    self.blink_phase = 1
                    self.last_speaking_blink_time = current_time
        
        self.update()
    
    def _set_param(self, name: str, value: float):
        """设置参数值"""
        if name in self.param_indices:
            self.model.SetParameterValue(self.param_indices[name], value, 1.0)
    
    def _get_expression_loop_smile(self, t: float) -> float:
        """获取笑眼循环动画叠加值 (happy/excited/smug)"""
        if not self.enable_expression_loops:
            return 0.0
        
        if self.current_expression in ("happy", "excited", "smug", "mischievous"):
            # 轻微的笑眼波动
            return math.sin(t * self.happy_smile_speed * math.pi) * self.happy_smile_amp
        return 0.0
    
    def _get_expression_loop_cheek(self, t: float) -> float:
        """获取脸红循环动画叠加值 (shy/embarrassed)"""
        if not self.enable_expression_loops:
            return 0.0
        
        if self.current_expression in ("shy", "embarrassed"):
            # 脸红轻微闪烁
            return (math.sin(t * self.shy_cheek_speed * math.pi) + 1) * 0.5 * self.shy_cheek_amp
        return 0.0
    
    def _apply_expression_loops(self, t: float):
        """应用表情内循环动画"""
        # thinking: 眼球缓慢左右/上下移动（模拟思考）
        if self.current_expression == "thinking":
            eye_x = math.sin(t * self.thinking_eye_speed * math.pi) * self.thinking_eye_amp_x
            eye_y = math.sin(t * self.thinking_eye_speed * 0.7 * math.pi) * self.thinking_eye_amp_y
            self._set_param("ParamEyeBallX", eye_x)
            self._set_param("ParamEyeBallY", eye_y)
        
        # shy: 眼球周期性躲避
        elif self.current_expression in ("shy", "embarrassed"):
            # 眼球周期性向一侧移动
            phase = (math.sin(t * self.shy_eye_speed * math.pi) + 1) * 0.5
            eye_x = self.shy_eye_amp * phase
            self._set_param("ParamEyeBallX", eye_x)
        
        # curious: 头微微倾斜循环（叠加到已有的头部摆动）
        elif self.current_expression == "curious":
            # 好奇地歪头周期循环
            head_tilt = math.sin(t * self.curious_head_speed * math.pi) * self.curious_head_amp
            # 注意：这会叠加到 head_sway，所以效果更明显
            current_z = math.sin(t * self.head_sway_speed * math.pi) * self.head_sway_amp if self.head_sway_amp > 0 else 0
            self._set_param("ParamAngleZ", current_z + head_tilt * 0.5)
    
    def _update_blink(self, current_time: float, delta_time: float):
        """更新眨眼（只更新 blink_value，不直接设置参数）"""
        if not self.is_blinking and current_time >= self.next_blink_time:
            self.is_blinking = True
            self.blink_phase = 1
        
        if self.is_blinking:
            if self.blink_phase == 1:  # 闭眼
                self.blink_value -= delta_time * 15
                if self.blink_value <= 0:
                    self.blink_value = 0
                    self.blink_phase = 2
            elif self.blink_phase == 2:  # 睁眼
                self.blink_value += delta_time * 10
                if self.blink_value >= 1.0:
                    self.blink_value = 1.0
                    self.is_blinking = False
                    self.next_blink_time = current_time + random.uniform(
                        self.blink_interval_min,
                        self.blink_interval_max
                    )
    
    def _update_mouth(self):
        """平滑更新口型"""
        self.current_mouth_open += (self.target_mouth_open - self.current_mouth_open) * self.mouth_smoothing
        self.current_mouth_form += (self.target_mouth_form - self.current_mouth_form) * self.mouth_smoothing
    
    def on_draw(self):
        """绘制回调"""
        live2d.clearBuffer()
        self.model.Draw()
    
    def paintGL(self):
        """OpenGL 绘制"""
        GL.glClearColor(0.0, 0.0, 0.0, 0.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        
        if self.model and self.canvas:
            self.canvas.Draw(self.on_draw)
    
    def resizeGL(self, width: int, height: int):
        """窗口大小变化"""
        if self.model:
            self.model.Resize(width, height)
        if self.canvas:
            self.canvas.SetSize(width, height)
    
    # ==================== 公开 API ====================
    
    def set_expression(self, emotion: str):
        """设置表情 (通过情绪名称，带平滑过渡和 Idle 调制)"""
        if emotion == self.current_expression:
            return
        
        self.current_expression = emotion
        
        # 更新表情目标值
        if emotion in EXPRESSIONS:
            self.target_expression_values = EXPRESSIONS[emotion].copy()
        else:
            self.target_expression_values = {}
        
        # 获取并应用情绪调制器
        modifier = get_emotion_modifier(emotion)
        
        # 更新 Idle 参数
        self.body_breath_speed = self._base_breath_speed * modifier.breath_speed_mult
        self.body_breath_amplitude = self._base_breath_amp * modifier.breath_amp_mult
        self.tail_speed = self._base_tail_speed * modifier.tail_speed_mult
        self.tail_amplitude = self._base_tail_amp * modifier.tail_amp_mult
        self.blink_interval_min = self._base_blink_min * modifier.blink_interval_mult
        self.blink_interval_max = self._base_blink_max * modifier.blink_interval_mult
        
        # 更新头部摆动
        self.head_sway_amp = modifier.head_sway_amp
        self.head_sway_speed = modifier.head_sway_speed
        
        # 更新表情参数偏移
        self.eye_open_offset = modifier.eye_open_offset
        self.eye_smile_offset = modifier.eye_smile_offset
        self.brow_y_offset = modifier.brow_y_offset
        self.cheek_offset = modifier.cheek_offset
        self.mouth_form_offset = modifier.mouth_form_offset
        
        print(f"Expression: {emotion} (breath={self.body_breath_speed:.2f}, tail={self.tail_speed:.2f}, sway={self.head_sway_amp:.1f})")
    
    def _update_expression(self):
        """平滑更新表情参数 (lerp)"""
        # 获取所有需要处理的参数
        all_params = set(self.current_expression_values.keys()) | set(self.target_expression_values.keys())
        
        for param_name in all_params:
            current = self.current_expression_values.get(param_name, 0.0)
            target = self.target_expression_values.get(param_name, 0.0)
            
            # Lerp 插值
            new_value = current + (target - current) * self.expression_lerp_speed
            
            # 接近目标时直接到位（避免无限逼近）
            if abs(new_value - target) < 0.01:
                new_value = target
            
            # 更新当前值（如果为0且目标也为0，从字典中移除以节省内存）
            if new_value == 0.0 and target == 0.0:
                self.current_expression_values.pop(param_name, None)
            else:
                self.current_expression_values[param_name] = new_value
    
    def set_random_expression(self):
        """设置随机表情"""
        expressions = list(EXPRESSIONS.keys())
        expr = random.choice(expressions)
        self.set_expression(expr)
    
    def set_mouth_open(self, value: float):
        """设置嘴巴张开程度"""
        self.target_mouth_open = max(0.0, min(1.0, value))
        self.is_speaking = value > 0.05
    
    def set_vowel(self, vowel: str, intensity: float = 1.0, mouth_form: Optional[float] = None):
        """设置元音口型"""
        shape = VOWEL_SHAPES.get(vowel, VOWEL_SHAPES.get("silence"))
        
        if shape:
            self.target_mouth_open = shape.mouth_open * intensity
            self.target_mouth_form = mouth_form if mouth_form is not None else shape.mouth_form
        
        self.is_speaking = intensity > 0.05
    
    def set_lipsync(self, mouth_open: float, mouth_form: float):
        """直接设置口型参数"""
        self.target_mouth_open = max(0.0, min(1.0, mouth_open))
        self.target_mouth_form = max(-1.0, min(1.0, mouth_form))
        self.is_speaking = mouth_open > 0.05
    
    def start_speaking(self):
        """开始说话"""
        self.is_speaking = True
    
    def stop_speaking(self):
        """停止说话"""
        self.is_speaking = False
        self.target_mouth_open = 0.0
        self.target_mouth_form = 0.0
    
    # ==================== Idle 控制 ====================
    
    def set_idle_params(self, 
                        body_breath_speed: float = None,
                        body_breath_amplitude: float = None,
                        tail_speed: float = None,
                        tail_amplitude: float = None):
        """动态调整 Idle 参数（用于情绪变化）"""
        if body_breath_speed is not None:
            self.IDLE_BODY_BREATH_SPEED = body_breath_speed
        if body_breath_amplitude is not None:
            self.IDLE_BODY_BREATH_AMPLITUDE = body_breath_amplitude
        if tail_speed is not None:
            self.IDLE_TAIL_SPEED = tail_speed
        if tail_amplitude is not None:
            self.IDLE_TAIL_AMPLITUDE = tail_amplitude
    
    # ==================== 位置/大小控制 API ====================
    
    def move_to_position(self, x: int, y: int):
        """移动窗口到指定屏幕位置"""
        screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.availableGeometry()
            x = max(0, min(x, geometry.width() - self.width()))
            y = max(0, min(y, geometry.height() - self.height()))
        self.move(x, y)
    
    def move_by_offset(self, dx: int, dy: int):
        """相对移动窗口"""
        current_pos = self.pos()
        self.move_to_position(current_pos.x() + dx, current_pos.y() + dy)
    
    def set_scale(self, scale: float):
        """设置窗口缩放比例"""
        scale = max(0.0, min(2.0, scale))
        
        if scale == 0.0:
            self.hide()
            return
        
        if not self.isVisible():
            self.show()
        
        new_width = int(self.display_width * scale)
        new_height = int(self.display_height * scale)
        
        self.setFixedSize(new_width, new_height)
        
        if self.model:
            self.model.Resize(new_width, new_height)
        if self.canvas:
            self.canvas.SetSize(new_width, new_height)
    
    def get_position(self) -> tuple:
        """获取当前窗口位置"""
        pos = self.pos()
        return (pos.x(), pos.y())
    
    def get_current_scale(self) -> float:
        """获取当前缩放比例"""
        if not self.isVisible():
            return 0.0
        return self.width() / self.display_width
    
    def move_to_corner(self, corner: str):
        """移动到屏幕角落"""
        screen = QApplication.primaryScreen()
        if not screen:
            return
        
        geometry = screen.availableGeometry()
        margin = 20
        
        if corner == "top_left":
            x, y = margin, margin
        elif corner == "top_right":
            x = geometry.width() - self.width() - margin
            y = margin
        elif corner == "bottom_left":
            x = margin
            y = geometry.height() - self.height() - margin
        elif corner == "top_center":
            x = (geometry.width() - self.width()) // 2
            y = margin
        elif corner == "bottom_center":
            x = (geometry.width() - self.width()) // 2
            y = geometry.height() - self.height() - margin
        else:  # bottom_right (default)
            x = geometry.width() - self.width() - margin
            y = geometry.height() - self.height() - margin
        
        self.move(x, y)
    
    # ==================== 🔥 线程安全请求方法 (跨线程调用) ====================
    
    def request_move_to_corner(self, corner: str):
        """线程安全：请求移动到角落"""
        self._sig_move_to_corner.emit(corner)
    
    def request_set_scale(self, scale: float):
        """线程安全：请求设置缩放"""
        self._sig_set_scale.emit(scale)
    
    def request_scale_change(self, delta: float):
        """线程安全：请求调整缩放 (相对变化)"""
        self._sig_scale_change.emit(delta)
    
    def request_toggle_side(self):
        """线程安全：请求切换到对面"""
        self._sig_toggle_side.emit()
    
    def request_random_corner(self):
        """线程安全：请求移动到随机角落"""
        self._sig_random_corner.emit()
    
    # ==================== 🔥 Slot 方法 (在 Qt 主线程执行) ====================
    
    @pyqtSlot(str)
    def _slot_move_to_corner(self, corner: str):
        """Slot: 移动到角落"""
        self.move_to_corner(corner)
    
    @pyqtSlot(float)
    def _slot_set_scale(self, scale: float):
        """Slot: 设置缩放"""
        self.set_scale(scale)
    
    @pyqtSlot(float)
    def _slot_scale_change(self, delta: float):
        """Slot: 调整缩放"""
        current = self.get_current_scale()
        new_scale = max(0.3, min(2.0, current + delta))
        self.set_scale(new_scale)
    
    @pyqtSlot()
    def _slot_toggle_side(self):
        """Slot: 切换到对面"""
        screen = QApplication.primaryScreen()
        if not screen:
            return
        
        geometry = screen.availableGeometry()
        pos = self.pos()
        
        if pos.x() > geometry.width() / 2:
            self.move_to_corner("bottom_left")
        else:
            self.move_to_corner("bottom_right")
    
    @pyqtSlot()
    def _slot_random_corner(self):
        """Slot: 移动到随机角落"""
        corners = ["top_left", "top_right", "bottom_left", "bottom_right"]
        self.move_to_corner(random.choice(corners))
    
    # ==================== 鼠标事件 ====================
    
    def mousePressEvent(self, event):
        """鼠标按下 - 开始拖动"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """鼠标移动 - 拖动窗口"""
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        """鼠标释放 - 结束拖动"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = None
    
    def mouseDoubleClickEvent(self, event):
        """双击 - 切换随机表情"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_random_expression()


def create_controller(model_path: str) -> Live2DController:
    """创建并返回 Live2D 控制器"""
    controller = Live2DController(model_path)
    controller.move_to_bottom_right()
    return controller


# 全局单例
_controller: Optional[Live2DController] = None


def get_live2d_controller() -> Optional[Live2DController]:
    """获取全局 Live2D 控制器实例"""
    global _controller
    return _controller


def set_live2d_controller(controller: Live2DController):
    """设置全局 Live2D 控制器实例"""
    global _controller
    _controller = controller


def main():
    """测试入口"""
    live2d.init()
    
    app = QApplication(sys.argv)
    
    model_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "models",
        "sakiko.model3.json"
    )
    
    print(f"Loading model from: {model_path}")
    
    controller = create_controller(model_path)
    set_live2d_controller(controller)
    controller.show()
    
    print("\n=== Live2D Controller (Low-Level Model) ===")
    print("Using manual idle animations:")
    print(f"  - Body breath: speed={controller.body_breath_speed}, amp={controller.body_breath_amplitude}")
    print(f"  - Tail: speed={controller.tail_speed}")
    print(f"  - Blink: interval={controller.blink_interval_min}-{controller.blink_interval_max}s")
    print("Double-click to trigger random expression")
    
    app.exec()
    live2d.dispose()


if __name__ == "__main__":
    main()
