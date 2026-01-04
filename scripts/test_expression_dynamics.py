# -*- coding: utf-8 -*-
"""
表情动态参数测试脚本

测试内容：
1. 情绪对 Idle 动画的调制（呼吸速度/幅度、尾巴、眨眼频率等）
2. 表情微动 (Micro-Movements) - 使用噪波让表情参数轻微抖动

使用方法：
    python scripts/test_expression_dynamics.py
"""

import sys
import os
import math
import time
import random

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication, QOpenGLWidget, QPushButton, QVBoxLayout, 
    QWidget, QLabel, QSlider, QHBoxLayout, QGroupBox, QComboBox,
    QCheckBox
)
import OpenGL.GL as GL

import live2d.v3 as live2d
from live2d.utils.canvas import Canvas

from live2d_local.expressions import Params, EXPRESSIONS


# ============================================================
# 情绪 Idle 调制参数定义
# ============================================================
# 每个情绪对 Idle 动画的影响：
# - breath_speed_mult: 呼吸速度倍率 (1.0 = 正常)
# - breath_amp_mult: 呼吸幅度倍率
# - tail_speed_mult: 尾巴速度倍率
# - tail_amp_mult: 尾巴幅度倍率
# - blink_interval_mult: 眨眼间隔倍率 (>1 = 更慢, <1 = 更快)
# - head_sway_amp: 头部轻微摆动幅度 (0 = 不摆)
# - head_sway_speed: 头部摆动速度

EMOTION_IDLE_MODIFIERS = {
    "neutral": {
        "breath_speed_mult": 1.0,
        "breath_amp_mult": 1.0,
        "tail_speed_mult": 1.0,
        "tail_amp_mult": 1.0,
        "blink_interval_mult": 1.0,
        "head_sway_amp": 0.0,
        "head_sway_speed": 0.3,
        # 表情参数偏移 (叠加到基础表情上)
        "eye_open_offset": 0.0,      # 眼睛张开程度偏移 (-0.5~0.5)
        "eye_smile_offset": 0.0,     # 笑眼程度偏移
        "brow_y_offset": 0.0,        # 眉毛高度偏移
        "cheek_offset": 0.0,         # 脸红偏移
        "mouth_form_offset": 0.0,    # 嘴巴形状偏移 (-1=嘟嘴, 1=微笑)
    },
    "happy": {
        "breath_speed_mult": 1.2,
        "breath_amp_mult": 1.1,
        "tail_speed_mult": 1.5,
        "tail_amp_mult": 1.3,
        "blink_interval_mult": 0.8,
        "head_sway_amp": 3.0,
        "head_sway_speed": 0.5,
        "eye_open_offset": 0.0,
        "eye_smile_offset": 0.15,    # 稍微眠起的笑眼
        "brow_y_offset": 0.1,
        "cheek_offset": 0.1,
        "mouth_form_offset": 0.2,
    },
    "excited": {
        "breath_speed_mult": 1.5,
        "breath_amp_mult": 1.3,
        "tail_speed_mult": 2.0,
        "tail_amp_mult": 1.5,
        "blink_interval_mult": 0.6,
        "head_sway_amp": 5.0,
        "head_sway_speed": 0.8,
        "eye_open_offset": 0.2,      # 眼睛稍微睁大
        "eye_smile_offset": 0.1,
        "brow_y_offset": 0.2,
        "cheek_offset": 0.15,
        "mouth_form_offset": 0.3,
    },
    "angry": {
        "breath_speed_mult": 1.4,
        "breath_amp_mult": 1.2,
        "tail_speed_mult": 1.3,
        "tail_amp_mult": 0.8,
        "blink_interval_mult": 1.5,
        "head_sway_amp": 1.0,
        "head_sway_speed": 0.2,
        "eye_open_offset": 0.2,      # 睁大眼睛
        "eye_smile_offset": -0.1,
        "brow_y_offset": -0.3,       # 眉毛压低
        "cheek_offset": 0.0,
        "mouth_form_offset": -0.2,
    },
    "sad": {
        "breath_speed_mult": 0.7,
        "breath_amp_mult": 0.8,
        "tail_speed_mult": 0.5,
        "tail_amp_mult": 0.5,
        "blink_interval_mult": 1.3,
        "head_sway_amp": 0.5,
        "head_sway_speed": 0.15,
        "eye_open_offset": -0.15,
        "eye_smile_offset": 0.0,
        "brow_y_offset": 0.2,        # 眉毛上扬 (哀伤)
        "cheek_offset": 0.0,
        "mouth_form_offset": -0.15,
    },
    "thinking": {
        "breath_speed_mult": 0.9,
        "breath_amp_mult": 0.9,
        "tail_speed_mult": 0.6,
        "tail_amp_mult": 0.7,
        "blink_interval_mult": 1.2,
        "head_sway_amp": 2.0,
        "head_sway_speed": 0.2,
        "eye_open_offset": 0.0,
        "eye_smile_offset": 0.0,
        "brow_y_offset": 0.15,
        "cheek_offset": 0.0,
        "mouth_form_offset": 0.0,
    },
    "shy": {
        "breath_speed_mult": 1.1,
        "breath_amp_mult": 1.2,
        "tail_speed_mult": 0.8,
        "tail_amp_mult": 0.6,
        "blink_interval_mult": 0.7,
        "head_sway_amp": 2.0,
        "head_sway_speed": 0.4,
        "eye_open_offset": -0.1,
        "eye_smile_offset": 0.2,
        "brow_y_offset": 0.0,
        "cheek_offset": 0.3,         # 脸红
        "mouth_form_offset": 0.1,
    },
    "sleepy": {
        "breath_speed_mult": 0.5,
        "breath_amp_mult": 1.4,
        "tail_speed_mult": 0.3,
        "tail_amp_mult": 0.3,
        "blink_interval_mult": 0.5,
        "head_sway_amp": 1.5,
        "head_sway_speed": 0.1,
        "eye_open_offset": -0.6,     # 眼睛半闭（更明显）
        "eye_smile_offset": 0.0,
        "brow_y_offset": -0.1,
        "cheek_offset": 0.0,
        "mouth_form_offset": 0.0,
    },
    "surprised": {
        "breath_speed_mult": 1.8,
        "breath_amp_mult": 0.7,
        "tail_speed_mult": 2.0,
        "tail_amp_mult": 1.8,
        "blink_interval_mult": 2.0,
        "head_sway_amp": 0.0,
        "head_sway_speed": 0.0,
        "eye_open_offset": 0.4,      # 眼睛睁大
        "eye_smile_offset": 0.0,
        "brow_y_offset": 0.3,        # 眉毛抬高
        "cheek_offset": 0.0,
        "mouth_form_offset": 0.0,
    },
    "curious": {
        "breath_speed_mult": 1.1,
        "breath_amp_mult": 1.0,
        "tail_speed_mult": 1.2,
        "tail_amp_mult": 1.2,
        "blink_interval_mult": 0.9,
        "head_sway_amp": 4.0,
        "head_sway_speed": 0.3,
        "eye_open_offset": 0.15,
        "eye_smile_offset": 0.0,
        "brow_y_offset": 0.2,
        "cheek_offset": 0.0,
        "mouth_form_offset": 0.0,
    },
    "pout": {
        "breath_speed_mult": 0.9,
        "breath_amp_mult": 1.1,
        "tail_speed_mult": 0.4,
        "tail_amp_mult": 0.5,
        "blink_interval_mult": 1.0,
        "head_sway_amp": 1.0,
        "head_sway_speed": 0.2,
        "eye_open_offset": -0.1,
        "eye_smile_offset": 0.0,
        "brow_y_offset": -0.15,
        "cheek_offset": 0.2,         # 脸鼓鼓
        "mouth_form_offset": -0.3,   # 嘟嘴
    },
    "smug": {
        "breath_speed_mult": 0.85,
        "breath_amp_mult": 1.0,
        "tail_speed_mult": 0.9,
        "tail_amp_mult": 1.0,
        "blink_interval_mult": 1.2,
        "head_sway_amp": 3.0,
        "head_sway_speed": 0.25,
        "eye_open_offset": 0.0,
        "eye_smile_offset": 0.25,    # 得意的笑眼
        "brow_y_offset": 0.1,
        "cheek_offset": 0.1,
        "mouth_form_offset": 0.25,
    },
}

# 默认值（当情绪没有定义时使用）
DEFAULT_MODIFIER = {
    "breath_speed_mult": 1.0,
    "breath_amp_mult": 1.0,
    "tail_speed_mult": 1.0,
    "tail_amp_mult": 1.0,
    "blink_interval_mult": 1.0,
    "head_sway_amp": 0.0,
    "head_sway_speed": 0.3,
    "eye_open_offset": 0.0,
    "eye_smile_offset": 0.0,
    "brow_y_offset": 0.0,
    "cheek_offset": 0.0,
    "mouth_form_offset": 0.0,
}


class TestExpressionController(QOpenGLWidget):
    """表情动态测试控制器"""
    
    def __init__(self, model_path: str):
        super().__init__()
        
        self.model_path = model_path
        self.display_width = 500
        self.display_height = 620
        self.fps = 60
        
        self.model = None
        self.canvas = None
        self.param_indices = {}
        
        # === 时间和状态 ===
        self.last_time = time.time()
        self.start_time = time.time()
        
        # === 基础 Idle 参数 ===
        self.base_breath_speed = 0.5
        self.base_breath_amp = 1.4
        self.base_tail_speed = 0.8
        self.base_tail_amp = 1.0
        self.base_blink_min = 2.0
        self.base_blink_max = 5.0
        
        # === 当前情绪和调制后的参数 ===
        self.current_emotion = "neutral"
        self.breath_speed = self.base_breath_speed
        self.breath_amp = self.base_breath_amp
        self.tail_speed = self.base_tail_speed
        self.tail_amp = self.base_tail_amp
        self.blink_min = self.base_blink_min
        self.blink_max = self.base_blink_max
        self.head_sway_amp = 0.0
        self.head_sway_speed = 0.3
        
        # === 眨眼状态 ===
        self.blink_value = 1.0
        self.next_blink_time = time.time() + random.uniform(2.0, 5.0)
        self.is_blinking = False
        self.blink_phase = 0
        
        # === 表情参数偏移 (由情绪调制) ===
        self.eye_open_offset = 0.0
        self.eye_smile_offset = 0.0
        self.brow_y_offset = 0.0
        self.cheek_offset = 0.0
        self.mouth_form_offset = 0.0
        
        # === 微动 (Micro-Movements) ===
        self.enable_micro_movements = False
        self.micro_amp = 0.05
        self.micro_speed = 2.0
        
        # === 表情系统 ===
        self.current_expression_values = {}
        self.target_expression_values = {}
        self.expression_lerp_speed = 0.08
        
        # 窗口设置
        self.setWindowTitle("表情动态测试")
        self.setFixedSize(self.display_width, self.display_height)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        
        self.drag_position = None
    
    def initializeGL(self):
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
        
        self.canvas = Canvas()
        self.canvas.SetSize(self.display_width, self.display_height)
        
        self.startTimer(int(1000 / self.fps))
        print("模型加载完成")
    
    def _set_param(self, name: str, value: float):
        if name in self.param_indices:
            self.model.SetParameterValue(self.param_indices[name], value, 1.0)
    
    def set_emotion(self, emotion: str):
        """设置情绪（更新表情 + Idle 调制）"""
        self.current_emotion = emotion
        
        # 获取情绪调制器
        modifier = EMOTION_IDLE_MODIFIERS.get(emotion, DEFAULT_MODIFIER)
        
        # 更新 Idle 参数
        self.breath_speed = self.base_breath_speed * modifier["breath_speed_mult"]
        self.breath_amp = self.base_breath_amp * modifier["breath_amp_mult"]
        self.tail_speed = self.base_tail_speed * modifier["tail_speed_mult"]
        self.tail_amp = self.base_tail_amp * modifier["tail_amp_mult"]
        
        blink_mult = modifier["blink_interval_mult"]
        self.blink_min = self.base_blink_min * blink_mult
        self.blink_max = self.base_blink_max * blink_mult
        
        self.head_sway_amp = modifier.get("head_sway_amp", 0.0)
        self.head_sway_speed = modifier.get("head_sway_speed", 0.3)
        
        # 更新表情参数偏移
        self.eye_open_offset = modifier.get("eye_open_offset", 0.0)
        self.eye_smile_offset = modifier.get("eye_smile_offset", 0.0)
        self.brow_y_offset = modifier.get("brow_y_offset", 0.0)
        self.cheek_offset = modifier.get("cheek_offset", 0.0)
        self.mouth_form_offset = modifier.get("mouth_form_offset", 0.0)
        
        # 更新表情目标值
        if emotion in EXPRESSIONS:
            self.target_expression_values = EXPRESSIONS[emotion].copy()
        else:
            self.target_expression_values = {}
        
        print(f"情绪切换: {emotion}")
        print(f"  呼吸: speed={self.breath_speed:.2f}, amp={self.breath_amp:.2f}")
        print(f"  尾巴: speed={self.tail_speed:.2f}, amp={self.tail_amp:.2f}")
        print(f"  眨眼间隔: {self.blink_min:.1f}-{self.blink_max:.1f}s")
        print(f"  头部摆动: amp={self.head_sway_amp:.1f}")
    
    def timerEvent(self, event):
        if not self.model:
            return
        
        current_time = time.time()
        delta_time = current_time - self.last_time
        self.last_time = current_time
        t = current_time - self.start_time
        
        # === 1. Physics ===
        self.model.UpdatePhysics(delta_time)
        
        # === 2. 呼吸 (身体上下摆动) ===
        body_y = math.sin(t * self.breath_speed * math.pi * 2) * self.breath_amp
        self._set_param("ParamBodyAngleY", body_y)
        
        # === 3. 尾巴 ===
        breath = (math.sin(t * self.tail_speed * math.pi) + 1) / 2 * self.tail_amp
        self._set_param("ParamBreath", breath)
        
        # === 4. 头部轻微摆动 ===
        if self.head_sway_amp > 0:
            head_z = math.sin(t * self.head_sway_speed * math.pi) * self.head_sway_amp
            self._set_param("ParamAngleZ", head_z)
        
        # === 5. 眨眼 ===
        self._update_blink(current_time, delta_time)
        
        # === 6. 表情参数 + 微动 ===
        self._update_expression(t)
        for param_name, value in self.current_expression_values.items():
            # 跳过眨眼控制的参数（单独处理）
            if param_name in (Params.EYE_L_OPEN, Params.EYE_R_OPEN):
                continue
            self._set_param(param_name, value)
        
        # === 7. 情绪参数偏移叠加（在表情参数之后！）===
        # 眼睛大小 = 眨眼值 + 表情值 + 偏移
        expr_eye_open = self.current_expression_values.get(Params.EYE_L_OPEN, 0.0)
        eye_open_final = self.blink_value + expr_eye_open + self.eye_open_offset
        self._set_param("ParamEyeLOpen", max(0, min(1.5, eye_open_final)))
        self._set_param("ParamEyeROpen", max(0, min(1.5, eye_open_final)))
        
        # 笑眼 = 表情值 + 偏移
        expr_eye_smile = self.current_expression_values.get(Params.EYE_L_SMILE, 0.0)
        eye_smile_final = expr_eye_smile + self.eye_smile_offset
        self._set_param("ParamEyeLSmile", max(0, min(1.0, eye_smile_final)))
        self._set_param("ParamEyeRSmile", max(0, min(1.0, eye_smile_final)))
        
        # 眉毛 = 表情值 + 偏移
        expr_brow_l = self.current_expression_values.get(Params.BROW_L_Y, 0.0)
        expr_brow_r = self.current_expression_values.get(Params.BROW_R_Y, 0.0)
        self._set_param("ParamBrowLY", expr_brow_l + self.brow_y_offset)
        self._set_param("ParamBrowRY", expr_brow_r + self.brow_y_offset)
        
        # 脸红 = 表情值 + 偏移（不限制上限，让模型决定）
        expr_cheek = self.current_expression_values.get(Params.CHEEK, 0.0)
        cheek_final = expr_cheek + self.cheek_offset
        self._set_param("ParamCheek", max(0, cheek_final))  # 只限制下限，不限制上限
        
        # 嘴巴形状 = 表情值 + 偏移
        expr_mouth_form = self.current_expression_values.get(Params.MOUTH_FORM, 0.0)
        mouth_form_final = expr_mouth_form + self.mouth_form_offset
        self._set_param("ParamMouthForm", max(-1.0, min(1.0, mouth_form_final)))
        
        self.update()
    
    def _update_blink(self, current_time: float, delta_time: float):
        """更新眨眼 (不直接设置参数，只更新 blink_value)"""
        if not self.is_blinking and current_time >= self.next_blink_time:
            self.is_blinking = True
            self.blink_phase = 1
        
        if self.is_blinking:
            if self.blink_phase == 1:
                self.blink_value -= delta_time * 15
                if self.blink_value <= 0:
                    self.blink_value = 0
                    self.blink_phase = 2
            elif self.blink_phase == 2:
                self.blink_value += delta_time * 10
                if self.blink_value >= 1.0:
                    self.blink_value = 1.0
                    self.is_blinking = False
                    self.next_blink_time = current_time + random.uniform(
                        self.blink_min, self.blink_max
                    )
    
    def _update_expression(self, t: float):
        """更新表情参数（带微动）"""
        all_params = set(self.current_expression_values.keys()) | set(self.target_expression_values.keys())
        
        for param_name in all_params:
            current = self.current_expression_values.get(param_name, 0.0)
            target = self.target_expression_values.get(param_name, 0.0)
            
            # Lerp 插值
            new_value = current + (target - current) * self.expression_lerp_speed
            
            # 微动叠加
            if self.enable_micro_movements and abs(target) > 0.01:
                # 使用多个正弦波叠加模拟噪波
                noise = (
                    math.sin(t * self.micro_speed + hash(param_name) % 100) * 0.5 +
                    math.sin(t * self.micro_speed * 1.7 + hash(param_name) % 50) * 0.3 +
                    math.sin(t * self.micro_speed * 2.3 + hash(param_name) % 25) * 0.2
                )
                new_value += target * self.micro_amp * noise
            
            if abs(new_value - target) < 0.01:
                new_value = target
            
            if new_value == 0.0 and target == 0.0:
                self.current_expression_values.pop(param_name, None)
            else:
                self.current_expression_values[param_name] = new_value
    
    def on_draw(self):
        live2d.clearBuffer()
        self.model.Draw()
    
    def paintGL(self):
        GL.glClearColor(0.0, 0.0, 0.0, 0.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        
        if self.model and self.canvas:
            self.canvas.Draw(self.on_draw)
    
    def resizeGL(self, width, height):
        if self.model:
            self.model.Resize(width, height)
        if self.canvas:
            self.canvas.SetSize(width, height)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
    
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            self.move(event.globalPos() - self.drag_position)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = None


class ControlPanel(QWidget):
    """控制面板"""
    
    def __init__(self, controller: TestExpressionController):
        super().__init__()
        self.controller = controller
        
        self.setWindowTitle("表情动态控制面板")
        self.setFixedSize(350, 650)
        
        layout = QVBoxLayout()
        
        # === 情绪选择 ===
        emotion_group = QGroupBox("情绪选择")
        emotion_layout = QVBoxLayout()
        
        self.emotion_combo = QComboBox()
        emotions = list(EMOTION_IDLE_MODIFIERS.keys())
        self.emotion_combo.addItems(emotions)
        self.emotion_combo.currentTextChanged.connect(self.controller.set_emotion)
        emotion_layout.addWidget(self.emotion_combo)
        
        emotion_group.setLayout(emotion_layout)
        layout.addWidget(emotion_group)
        
        # === 微动 (Micro-Movements) ===
        micro_group = QGroupBox("微动 (Micro-Movements)")
        micro_layout = QVBoxLayout()
        
        self.micro_checkbox = QCheckBox("启用微动")
        self.micro_checkbox.stateChanged.connect(
            lambda s: setattr(self.controller, 'enable_micro_movements', s == 2)  # 2 = Checked
        )
        micro_layout.addWidget(self.micro_checkbox)
        
        # 微动幅度
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("幅度:"))
        self.micro_amp_slider = QSlider(Qt.Orientation.Horizontal)
        self.micro_amp_slider.setRange(1, 30)
        self.micro_amp_slider.setValue(5)
        self.micro_amp_slider.valueChanged.connect(
            lambda v: setattr(self.controller, 'micro_amp', v / 100.0)
        )
        h1.addWidget(self.micro_amp_slider)
        self.micro_amp_label = QLabel("5%")
        self.micro_amp_slider.valueChanged.connect(lambda v: self.micro_amp_label.setText(f"{v}%"))
        h1.addWidget(self.micro_amp_label)
        micro_layout.addLayout(h1)
        
        # 微动速度
        h2 = QHBoxLayout()
        h2.addWidget(QLabel("速度:"))
        self.micro_speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.micro_speed_slider.setRange(5, 50)
        self.micro_speed_slider.setValue(20)
        self.micro_speed_slider.valueChanged.connect(
            lambda v: setattr(self.controller, 'micro_speed', v / 10.0)
        )
        h2.addWidget(self.micro_speed_slider)
        self.micro_speed_label = QLabel("2.0")
        self.micro_speed_slider.valueChanged.connect(lambda v: self.micro_speed_label.setText(f"{v/10:.1f}"))
        h2.addWidget(self.micro_speed_label)
        micro_layout.addLayout(h2)
        
        micro_group.setLayout(micro_layout)
        layout.addWidget(micro_group)
        
        # === Idle 调制参数调整 ===
        idle_group = QGroupBox("当前情绪的 Idle 调制")
        idle_layout = QVBoxLayout()
        
        self.idle_labels = {}
        params = [
            ("breath_speed_mult", "呼吸速度倍率", 50, 200, 100),
            ("breath_amp_mult", "呼吸幅度倍率", 30, 200, 100),
            ("tail_speed_mult", "尾巴速度倍率", 20, 250, 100),
            ("tail_amp_mult", "尾巴幅度倍率", 20, 200, 100),
            ("blink_interval_mult", "眨眼间隔倍率", 30, 250, 100),
            ("head_sway_amp", "头部摆动幅度", 0, 100, 0),
            ("head_sway_speed", "头部摆动速度", 5, 100, 30),
        ]
        
        for key, label, min_val, max_val, default in params:
            h = QHBoxLayout()
            h.addWidget(QLabel(f"{label}:"))
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(min_val, max_val)
            slider.setValue(default)
            slider.valueChanged.connect(lambda v, k=key: self._update_modifier(k, v))
            h.addWidget(slider)
            value_label = QLabel(f"{default/100:.2f}" if key != "head_sway_amp" else f"{default/10:.1f}")
            slider.valueChanged.connect(
                lambda v, l=value_label, k=key: l.setText(
                    f"{v/100:.2f}" if k != "head_sway_amp" else f"{v/10:.1f}"
                )
            )
            h.addWidget(value_label)
            idle_layout.addLayout(h)
            self.idle_labels[key] = (slider, value_label)
        
        idle_group.setLayout(idle_layout)
        layout.addWidget(idle_group)
        
        # === 表情参数偏移调整 ===
        expr_group = QGroupBox("表情参数偏移")
        expr_layout = QVBoxLayout()
        
        expr_params = [
            ("eye_open_offset", "眼睛大小偏移", -80, 80, 0),
            ("eye_smile_offset", "笑眼程度", 0, 80, 0),
            ("brow_y_offset", "眉毛高度偏移", -80, 80, 0),
            ("cheek_offset", "脸红程度", 0, 100, 0),
            ("mouth_form_offset", "嘴巴形状", -80, 80, 0),
        ]
        
        for key, label, min_val, max_val, default in expr_params:
            h = QHBoxLayout()
            h.addWidget(QLabel(f"{label}:"))
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(min_val, max_val)
            slider.setValue(default)
            slider.valueChanged.connect(lambda v, k=key: self._update_expr_param(k, v))
            h.addWidget(slider)
            value_label = QLabel(f"{default/100:.2f}")
            slider.valueChanged.connect(
                lambda v, l=value_label: l.setText(f"{v/100:.2f}")
            )
            h.addWidget(value_label)
            expr_layout.addLayout(h)
            self.idle_labels[key] = (slider, value_label)
        
        expr_group.setLayout(expr_layout)
        layout.addWidget(expr_group)
        
        # === 状态显示 ===
        self.status_label = QLabel("状态: neutral")
        layout.addWidget(self.status_label)
        
        # === 保存按钮 ===
        save_btn = QPushButton("打印当前参数到控制台")
        save_btn.clicked.connect(self._print_params)
        layout.addWidget(save_btn)
        
        # 退出按钮
        quit_btn = QPushButton("退出")
        quit_btn.clicked.connect(QApplication.quit)
        layout.addWidget(quit_btn)
        
        self.setLayout(layout)
        
        # 定时更新显示
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_status)
        self.timer.start(200)
    
    def _update_modifier(self, key: str, value: int):
        """更新调制参数"""
        emotion = self.controller.current_emotion
        
        if key == "head_sway_amp":
            real_value = value / 10.0  # 0-10
        else:
            real_value = value / 100.0  # 0.5-2.0
        
        # 更新全局定义
        if emotion in EMOTION_IDLE_MODIFIERS:
            EMOTION_IDLE_MODIFIERS[emotion][key] = real_value
        
        # 立即应用
        self.controller.set_emotion(emotion)
    
    def _update_expr_param(self, key: str, value: int):
        """更新表情参数偏移"""
        emotion = self.controller.current_emotion
        real_value = value / 100.0
        
        if emotion in EMOTION_IDLE_MODIFIERS:
            EMOTION_IDLE_MODIFIERS[emotion][key] = real_value
        
        # 立即应用
        self.controller.set_emotion(emotion)
    
    def _update_status(self):
        self.status_label.setText(f"当前情绪: {self.controller.current_emotion}")
        
        # 更新滑块显示为当前情绪的值
        emotion = self.controller.current_emotion
        modifier = EMOTION_IDLE_MODIFIERS.get(emotion, DEFAULT_MODIFIER)
        
        for key, (slider, label) in self.idle_labels.items():
            val = modifier.get(key, 0.0)
            if key == "head_sway_amp":
                slider.blockSignals(True)
                slider.setValue(int(val * 10))
                slider.blockSignals(False)
            elif key in ("eye_open_offset", "eye_smile_offset", "brow_y_offset", "cheek_offset", "mouth_form_offset"):
                slider.blockSignals(True)
                slider.setValue(int(val * 100))
                slider.blockSignals(False)
            else:
                slider.blockSignals(True)
                slider.setValue(int(val * 100))
                slider.blockSignals(False)
    
    def _print_params(self):
        """打印当前所有情绪的调制参数"""
        print("\n" + "=" * 60)
        print("当前 EMOTION_IDLE_MODIFIERS 配置:")
        print("=" * 60)
        
        for emotion, params in EMOTION_IDLE_MODIFIERS.items():
            print(f'\n    "{emotion}": {{')
            for key, val in params.items():
                print(f'        "{key}": {val:.2f},')
            print("    },")
        
        print("\n" + "=" * 60)


def main():
    print("\n" + "=" * 60)
    print("表情动态参数测试")
    print("=" * 60)
    print("\n功能：")
    print("  1. 测试不同情绪对 Idle 动画的影响")
    print("  2. 测试微动 (Micro-Movements) 效果")
    print("  3. 实时调整参数并观察效果")
    print("\n使用方法：")
    print("  - 选择情绪，观察呼吸/尾巴/眨眼的变化")
    print("  - 启用微动，观察表情参数的轻微抖动")
    print("  - 调整滑块，找到最佳参数")
    print("  - 点击 '打印参数' 将配置输出到控制台")
    
    live2d.init()
    
    app = QApplication(sys.argv)
    
    model_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "live2d_local",
        "models",
        "sakiko.model3.json"
    )
    
    print(f"\n加载模型: {model_path}")
    
    controller = TestExpressionController(model_path)
    controller.show()
    controller.move(100, 50)
    
    panel = ControlPanel(controller)
    panel.show()
    panel.move(650, 50)
    
    print("\n" + "=" * 60 + "\n")
    
    app.exec()
    live2d.dispose()


if __name__ == "__main__":
    main()
