# -*- coding: utf-8 -*-
"""
Pure Manual Idle 测试 v4

发现：UpdateBreath() 会导致头部和身体乱转！
解决：完全手动控制所有参数，不调用任何 Update 函数

使用方法：
    python scripts/test_pure_manual.py
"""

import sys
import os
import math
import time
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QOpenGLWidget, QPushButton, 
                             QVBoxLayout, QWidget, QLabel, QCheckBox, 
                             QSlider, QHBoxLayout, QGroupBox)
import OpenGL.GL as GL

import live2d.v3 as live2d
from live2d.utils.canvas import Canvas


class PureManualController(QOpenGLWidget):
    """完全手动控制的控制器 - 不调用任何 Update 函数"""
    
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
        
        # === 手动呼吸 ===
        self.enable_manual_breath = True
        self.breath_speed = 0.8  # 呼吸速度
        self.breath_value = 0.0
        
        # === 手动眨眼 ===
        self.enable_manual_blink = True
        self.blink_value = 1.0
        self.next_blink_time = time.time() + random.uniform(2, 4)
        self.is_blinking = False
        self.blink_phase = 0
        
        # === Physics（头发、衣服） ===
        self.enable_physics = True
        
        # 参数索引
        self.param_indices = {}
        
        # 窗口设置
        self.setWindowTitle("Pure Manual")
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
        
        # 获取参数索引
        param_ids = self.model.GetParameterIds()
        for i, pid in enumerate(param_ids):
            self.param_indices[pid] = i
        
        print("\n关键参数索引:")
        for key in ["ParamBreath", "ParamEyeLOpen", "ParamEyeROpen", 
                    "ParamAngleX", "ParamAngleY", "ParamAngleZ",
                    "ParamBodyAngleX", "ParamBodyAngleY", "ParamBodyAngleZ"]:
            if key in self.param_indices:
                print(f"  {key}: {self.param_indices[key]}")
        
        self.startTimer(int(1000 / self.fps))
        print("\n模型加载完成 - 完全手动控制模式")
    
    def timerEvent(self, event):
        if not self.model:
            return
        
        current_time = time.time()
        delta_time = current_time - self.last_time
        self.last_time = current_time
        
        # === 只调用 Physics（控制头发衣服，不影响头部身体） ===
        if self.enable_physics:
            self.model.UpdatePhysics(delta_time)
        
        # === 手动呼吸 ===
        if self.enable_manual_breath:
            # 简单的正弦波呼吸
            t = (current_time - self.start_time) * self.breath_speed * math.pi
            self.breath_value = (math.sin(t) + 1) / 2  # 0 到 1
            
            if "ParamBreath" in self.param_indices:
                self.model.SetParameterValue(
                    self.param_indices["ParamBreath"], 
                    self.breath_value, 
                    1.0
                )
        
        # === 手动眨眼 ===
        if self.enable_manual_blink:
            self._update_blink(current_time, delta_time)
        
        # === 确保头部和身体参数固定在 0 ===
        for param in ["ParamAngleX", "ParamAngleY", "ParamAngleZ",
                      "ParamBodyAngleX", "ParamBodyAngleY", "ParamBodyAngleZ"]:
            if param in self.param_indices:
                self.model.SetParameterValue(self.param_indices[param], 0.0, 1.0)
        
        self.update()
    
    def _update_blink(self, current_time, delta_time):
        """手动眨眼"""
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
                    self.blink_phase = 0
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
    
    def __init__(self, controller: PureManualController):
        super().__init__()
        self.controller = controller
        
        self.setWindowTitle("Control")
        self.setFixedSize(260, 300)
        
        layout = QVBoxLayout()
        layout.setSpacing(5)
        
        layout.addWidget(QLabel("=== 完全手动控制 ==="))
        layout.addWidget(QLabel("不调用任何 Update 函数"))
        layout.addWidget(QLabel("只手动设置参数"))
        
        # 呼吸
        group1 = QGroupBox("呼吸")
        g1 = QVBoxLayout()
        
        self.cb_breath = QCheckBox("启用手动呼吸")
        self.cb_breath.setChecked(controller.enable_manual_breath)
        self.cb_breath.toggled.connect(lambda v: setattr(controller, 'enable_manual_breath', v))
        g1.addWidget(self.cb_breath)
        
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("速度:"))
        self.breath_slider = QSlider(Qt.Orientation.Horizontal)
        self.breath_slider.setRange(2, 20)
        self.breath_slider.setValue(8)
        self.breath_slider.valueChanged.connect(lambda v: setattr(controller, 'breath_speed', v / 10.0))
        h1.addWidget(self.breath_slider)
        g1.addLayout(h1)
        
        group1.setLayout(g1)
        layout.addWidget(group1)
        
        # 眨眼
        group2 = QGroupBox("眨眼")
        g2 = QVBoxLayout()
        
        self.cb_blink = QCheckBox("启用手动眨眼")
        self.cb_blink.setChecked(controller.enable_manual_blink)
        self.cb_blink.toggled.connect(lambda v: setattr(controller, 'enable_manual_blink', v))
        g2.addWidget(self.cb_blink)
        
        group2.setLayout(g2)
        layout.addWidget(group2)
        
        # Physics
        group3 = QGroupBox("物理")
        g3 = QVBoxLayout()
        
        self.cb_physics = QCheckBox("启用 Physics (头发/衣服)")
        self.cb_physics.setChecked(controller.enable_physics)
        self.cb_physics.toggled.connect(lambda v: setattr(controller, 'enable_physics', v))
        g3.addWidget(self.cb_physics)
        
        group3.setLayout(g3)
        layout.addWidget(group3)
        
        # 退出
        btn_quit = QPushButton("退出")
        btn_quit.clicked.connect(QApplication.quit)
        layout.addWidget(btn_quit)
        
        self.setLayout(layout)


def main():
    print("\n" + "=" * 50)
    print("Pure Manual Idle 测试 v4")
    print("=" * 50)
    print("\n发现: UpdateBreath() 会导致头部身体乱转!")
    print("解决: 完全手动控制参数，不调用 Update 函数")
    print("\n预期效果:")
    print("  - 只有呼吸上下起伏")
    print("  - 自动眨眼")
    print("  - 头发衣服有物理效果")
    print("  - 头部身体完全不动\n")
    
    live2d.init()
    
    app = QApplication(sys.argv)
    
    model_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "live2d_local",
        "models",
        "sakiko.model3.json"
    )
    
    controller = PureManualController(model_path)
    controller.show()
    controller.move(50, 50)
    
    panel = ControlPanel(controller)
    panel.show()
    panel.move(550, 50)
    
    print("程序启动完成\n" + "=" * 50 + "\n")
    
    app.exec()
    live2d.dispose()


if __name__ == "__main__":
    main()
