# -*- coding: utf-8 -*-
"""
身体呼吸模拟测试

由于模型没有原生身体呼吸，尝试用 ParamBodyAngleY 模拟轻微的起伏

使用方法：
    python scripts/test_body_breath.py
"""

import sys
import os
import math
import time
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QOpenGLWidget, QPushButton, 
                             QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
                             QCheckBox, QSlider, QGroupBox, QDoubleSpinBox)
import OpenGL.GL as GL

import live2d.v3 as live2d
from live2d.utils.canvas import Canvas


class BodyBreathController(QOpenGLWidget):
    """身体呼吸模拟控制器"""
    
    def __init__(self, model_path: str):
        super().__init__()
        
        self.model_path = model_path
        self.display_width = 450
        self.display_height = 550
        self.fps = 60
        
        self.model = None
        self.canvas = None
        
        self.last_time = time.time()
        self.start_time = time.time()
        
        self.param_indices = {}
        
        # === 头发物理 ===
        self.enable_physics = True
        
        # === 尾巴摆动 ===
        self.enable_tail = True
        self.tail_speed = 0.8
        self.tail_amplitude = 1.0
        
        # === 身体呼吸模拟 ===
        self.enable_body_breath = True
        self.body_breath_speed = 0.5      # 速度 (慢)
        self.body_breath_amplitude = 2.0  # 幅度 (ParamBodyAngleY)
        self.body_breath_offset = 0.0     # 偏移 (默认位置)
        
        # === 眨眼 ===
        self.enable_blink = True
        self.blink_value = 1.0
        self.next_blink_time = time.time() + random.uniform(2, 4)
        self.is_blinking = False
        self.blink_phase = 0
        
        # 窗口设置
        self.setWindowTitle("Body Breath Test")
        self.setFixedSize(self.display_width, self.display_height)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        
    def initializeGL(self):
        live2d.glInit()
        
        self.model = live2d.Model()
        self.model.LoadModelJson(self.model_path)
        self.model.CreateRenderer()
        self.model.Resize(self.display_width, self.display_height)
        
        self.canvas = Canvas()
        self.canvas.SetSize(self.display_width, self.display_height)
        
        param_ids = self.model.GetParameterIds()
        for i, pid in enumerate(param_ids):
            self.param_indices[pid] = i
        
        print("\n=== 身体呼吸模拟测试 ===")
        print("尝试用 ParamBodyAngleY 模拟身体呼吸起伏")
        
        self.startTimer(int(1000 / self.fps))
    
    def timerEvent(self, event):
        if not self.model:
            return
        
        current_time = time.time()
        delta_time = current_time - self.last_time
        self.last_time = current_time
        t = current_time - self.start_time
        
        # Physics
        if self.enable_physics:
            self.model.UpdatePhysics(delta_time)
        
        # 尾巴
        if self.enable_tail and "ParamBreath" in self.param_indices:
            breath = (math.sin(t * self.tail_speed * math.pi) + 1) / 2 * self.tail_amplitude
            self.model.SetParameterValue(self.param_indices["ParamBreath"], breath, 1.0)
        
        # 身体呼吸模拟
        if self.enable_body_breath:
            # 正弦波呼吸
            body_y = math.sin(t * self.body_breath_speed * math.pi * 2) * self.body_breath_amplitude
            body_y += self.body_breath_offset
            
            if "ParamBodyAngleY" in self.param_indices:
                self.model.SetParameterValue(
                    self.param_indices["ParamBodyAngleY"], 
                    body_y, 
                    1.0
                )
        
        # 眨眼
        if self.enable_blink:
            self._update_blink(current_time, delta_time)
        
        self.update()
    
    def _update_blink(self, current_time, delta_time):
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
                    self.next_blink_time = current_time + random.uniform(2, 5)
        
        if "ParamEyeLOpen" in self.param_indices:
            self.model.SetParameterValue(self.param_indices["ParamEyeLOpen"], self.blink_value, 1.0)
        if "ParamEyeROpen" in self.param_indices:
            self.model.SetParameterValue(self.param_indices["ParamEyeROpen"], self.blink_value, 1.0)
    
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
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, 'drag_position'):
            self.move(event.globalPos() - self.drag_position)


class ControlPanel(QWidget):
    """控制面板"""
    
    def __init__(self, controller: BodyBreathController):
        super().__init__()
        self.controller = controller
        
        self.setWindowTitle("Body Breath Control")
        self.setFixedSize(350, 550)
        
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        # 标题
        layout.addWidget(QLabel("<b>身体呼吸模拟测试</b>"))
        layout.addWidget(QLabel("用 ParamBodyAngleY 模拟身体起伏"))
        
        # === 身体呼吸 ===
        group1 = QGroupBox("身体呼吸 (ParamBodyAngleY)")
        g1 = QVBoxLayout()
        g1.setSpacing(5)
        
        cb_body = QCheckBox("启用身体呼吸")
        cb_body.setChecked(controller.enable_body_breath)
        cb_body.toggled.connect(lambda v: setattr(controller, 'enable_body_breath', v))
        g1.addWidget(cb_body)
        
        # 速度
        g1.addWidget(QLabel("速度 (越大越快):"))
        h1 = QHBoxLayout()
        speed_slider = QSlider(Qt.Orientation.Horizontal)
        speed_slider.setRange(1, 20)
        speed_slider.setValue(5)
        speed_slider.valueChanged.connect(lambda v: setattr(controller, 'body_breath_speed', v / 10.0))
        h1.addWidget(speed_slider)
        self.speed_label = QLabel("0.5")
        speed_slider.valueChanged.connect(lambda v: self.speed_label.setText(f"{v/10:.1f}"))
        h1.addWidget(self.speed_label)
        g1.addLayout(h1)
        
        # 幅度
        g1.addWidget(QLabel("幅度 (ParamBodyAngleY 范围 -10~10):"))
        h2 = QHBoxLayout()
        amp_slider = QSlider(Qt.Orientation.Horizontal)
        amp_slider.setRange(0, 100)
        amp_slider.setValue(20)
        amp_slider.valueChanged.connect(lambda v: setattr(controller, 'body_breath_amplitude', v / 10.0))
        h2.addWidget(amp_slider)
        self.amp_label = QLabel("2.0")
        amp_slider.valueChanged.connect(lambda v: self.amp_label.setText(f"{v/10:.1f}"))
        h2.addWidget(self.amp_label)
        g1.addLayout(h2)
        
        # 偏移
        g1.addWidget(QLabel("偏移 (默认位置):"))
        h3 = QHBoxLayout()
        offset_slider = QSlider(Qt.Orientation.Horizontal)
        offset_slider.setRange(-50, 50)
        offset_slider.setValue(0)
        offset_slider.valueChanged.connect(lambda v: setattr(controller, 'body_breath_offset', v / 10.0))
        h3.addWidget(offset_slider)
        self.offset_label = QLabel("0.0")
        offset_slider.valueChanged.connect(lambda v: self.offset_label.setText(f"{v/10:.1f}"))
        h3.addWidget(self.offset_label)
        g1.addLayout(h3)
        
        group1.setLayout(g1)
        layout.addWidget(group1)
        
        # === 尾巴 ===
        group2 = QGroupBox("尾巴 (ParamBreath)")
        g2 = QVBoxLayout()
        
        cb_tail = QCheckBox("启用尾巴摆动")
        cb_tail.setChecked(controller.enable_tail)
        cb_tail.toggled.connect(lambda v: setattr(controller, 'enable_tail', v))
        g2.addWidget(cb_tail)
        
        g2.addWidget(QLabel("速度:"))
        h4 = QHBoxLayout()
        tail_speed = QSlider(Qt.Orientation.Horizontal)
        tail_speed.setRange(2, 20)
        tail_speed.setValue(8)
        tail_speed.valueChanged.connect(lambda v: setattr(controller, 'tail_speed', v / 10.0))
        h4.addWidget(tail_speed)
        self.tail_speed_label = QLabel("0.8")
        tail_speed.valueChanged.connect(lambda v: self.tail_speed_label.setText(f"{v/10:.1f}"))
        h4.addWidget(self.tail_speed_label)
        g2.addLayout(h4)
        
        group2.setLayout(g2)
        layout.addWidget(group2)
        
        # === 其他 ===
        group3 = QGroupBox("其他")
        g3 = QVBoxLayout()
        
        cb_physics = QCheckBox("Physics (头发物理)")
        cb_physics.setChecked(controller.enable_physics)
        cb_physics.toggled.connect(lambda v: setattr(controller, 'enable_physics', v))
        g3.addWidget(cb_physics)
        
        cb_blink = QCheckBox("眨眼")
        cb_blink.setChecked(controller.enable_blink)
        cb_blink.toggled.connect(lambda v: setattr(controller, 'enable_blink', v))
        g3.addWidget(cb_blink)
        
        group3.setLayout(g3)
        layout.addWidget(group3)
        
        layout.addStretch()
        
        # 退出
        btn_quit = QPushButton("退出")
        btn_quit.clicked.connect(QApplication.quit)
        layout.addWidget(btn_quit)
        
        self.setLayout(layout)


def main():
    print("\n" + "=" * 50)
    print("身体呼吸模拟测试")
    print("=" * 50)
    print("\n模型没有原生身体呼吸，尝试用 ParamBodyAngleY 模拟")
    print("调整参数找到最自然的效果\n")
    
    live2d.init()
    
    app = QApplication(sys.argv)
    
    model_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "live2d_local",
        "models",
        "sakiko.model3.json"
    )
    
    controller = BodyBreathController(model_path)
    controller.show()
    controller.move(50, 50)
    
    panel = ControlPanel(controller)
    panel.show()
    panel.move(550, 50)
    
    print("程序启动完成")
    print("=" * 50 + "\n")
    
    app.exec()
    live2d.dispose()


if __name__ == "__main__":
    main()
