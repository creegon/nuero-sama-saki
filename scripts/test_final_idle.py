# -*- coding: utf-8 -*-
"""
最终版 Idle 控制器

基于测试发现:
- UpdatePhysics: 需要 (头发、尾巴物理)
- ParamBreath: 手动控制 (尾巴摆动)
- 眼睛: 手动控制 (眨眼)
- UpdateBreath: 不要调用 (会导致 ParamBodyAngleX 乱动)
- UpdateBlink: 不工作，用手动实现

使用方法：
    python scripts/test_final_idle.py
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


class FinalIdleController(QOpenGLWidget):
    """最终版 Idle 控制器"""
    
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
        
        # 参数索引
        self.param_indices = {}
        
        # === 开关 ===
        self.enable_physics = True      # 头发物理
        self.enable_tail = True         # 尾巴摆动
        self.enable_blink = True        # 眨眼
        
        # === 尾巴摆动 ===
        self.tail_speed = 0.8           # 尾巴摆动速度
        self.tail_amplitude = 1.0       # 尾巴摆动幅度 (0-1)
        
        # === 眨眼 ===
        self.blink_value = 1.0
        self.next_blink_time = time.time() + random.uniform(2, 4)
        self.is_blinking = False
        self.blink_phase = 0
        self.blink_interval_min = 2.0   # 最短眨眼间隔
        self.blink_interval_max = 5.0   # 最长眨眼间隔
        
        # 窗口设置
        self.setWindowTitle("Final Idle")
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
        
        print("\n=== 最终 Idle 控制器 ===")
        print("配置:")
        print("  - Physics: ON (头发物理)")
        print("  - 尾巴: 手动 ParamBreath 正弦波")
        print("  - 眨眼: 手动控制")
        print("  - UpdateBreath: OFF (避免身体乱动)")
        
        self.startTimer(int(1000 / self.fps))
    
    def timerEvent(self, event):
        if not self.model:
            return
        
        current_time = time.time()
        delta_time = current_time - self.last_time
        self.last_time = current_time
        
        # === 只调用 Physics ===
        if self.enable_physics:
            self.model.UpdatePhysics(delta_time)
        
        # === 尾巴摆动 (手动 ParamBreath) ===
        if self.enable_tail and "ParamBreath" in self.param_indices:
            t = (current_time - self.start_time) * self.tail_speed * math.pi
            breath_value = (math.sin(t) + 1) / 2 * self.tail_amplitude
            self.model.SetParameterValue(
                self.param_indices["ParamBreath"], 
                breath_value, 
                1.0
            )
        
        # === 眨眼 ===
        if self.enable_blink:
            self._update_blink(current_time, delta_time)
        
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
                    self.next_blink_time = current_time + random.uniform(
                        self.blink_interval_min, 
                        self.blink_interval_max
                    )
        
        if "ParamEyeLOpen" in self.param_indices:
            self.model.SetParameterValue(
                self.param_indices["ParamEyeLOpen"], 
                self.blink_value, 
                1.0
            )
        if "ParamEyeROpen" in self.param_indices:
            self.model.SetParameterValue(
                self.param_indices["ParamEyeROpen"], 
                self.blink_value, 
                1.0
            )
    
    def force_blink(self):
        """强制眨眼"""
        self.is_blinking = True
        self.blink_phase = 1
        self.blink_value = 1.0
    
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
    
    def __init__(self, controller: FinalIdleController):
        super().__init__()
        self.controller = controller
        
        self.setWindowTitle("Idle 控制")
        self.setFixedSize(300, 350)
        
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        # 标题
        title = QLabel("<b>最终版 Idle 控制器</b>")
        layout.addWidget(title)
        
        desc = QLabel("基于测试发现的最佳配置")
        desc.setStyleSheet("color: gray;")
        layout.addWidget(desc)
        
        # 物理
        group1 = QGroupBox("头发物理")
        g1 = QVBoxLayout()
        cb_physics = QCheckBox("启用 Physics")
        cb_physics.setChecked(controller.enable_physics)
        cb_physics.toggled.connect(lambda v: setattr(controller, 'enable_physics', v))
        g1.addWidget(cb_physics)
        group1.setLayout(g1)
        layout.addWidget(group1)
        
        # 尾巴
        group2 = QGroupBox("尾巴摆动 (ParamBreath)")
        g2 = QVBoxLayout()
        
        cb_tail = QCheckBox("启用尾巴摆动")
        cb_tail.setChecked(controller.enable_tail)
        cb_tail.toggled.connect(lambda v: setattr(controller, 'enable_tail', v))
        g2.addWidget(cb_tail)
        
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("速度:"))
        speed_slider = QSlider(Qt.Orientation.Horizontal)
        speed_slider.setRange(2, 20)
        speed_slider.setValue(8)
        speed_slider.valueChanged.connect(lambda v: setattr(controller, 'tail_speed', v / 10.0))
        h1.addWidget(speed_slider)
        g2.addLayout(h1)
        
        h2 = QHBoxLayout()
        h2.addWidget(QLabel("幅度:"))
        amp_slider = QSlider(Qt.Orientation.Horizontal)
        amp_slider.setRange(0, 100)
        amp_slider.setValue(100)
        amp_slider.valueChanged.connect(lambda v: setattr(controller, 'tail_amplitude', v / 100.0))
        h2.addWidget(amp_slider)
        g2.addLayout(h2)
        
        group2.setLayout(g2)
        layout.addWidget(group2)
        
        # 眨眼
        group3 = QGroupBox("眨眼")
        g3 = QVBoxLayout()
        
        cb_blink = QCheckBox("启用眨眼")
        cb_blink.setChecked(controller.enable_blink)
        cb_blink.toggled.connect(lambda v: setattr(controller, 'enable_blink', v))
        g3.addWidget(cb_blink)
        
        btn_blink = QPushButton("立即眨眼")
        btn_blink.clicked.connect(controller.force_blink)
        g3.addWidget(btn_blink)
        
        h3 = QHBoxLayout()
        h3.addWidget(QLabel("间隔 (秒):"))
        interval_slider = QSlider(Qt.Orientation.Horizontal)
        interval_slider.setRange(10, 80)
        interval_slider.setValue(35)
        interval_slider.valueChanged.connect(self.update_blink_interval)
        h3.addWidget(interval_slider)
        self.interval_label = QLabel("2-5s")
        h3.addWidget(self.interval_label)
        g3.addLayout(h3)
        
        group3.setLayout(g3)
        layout.addWidget(group3)
        
        layout.addStretch()
        
        # 退出
        btn_quit = QPushButton("退出")
        btn_quit.clicked.connect(QApplication.quit)
        layout.addWidget(btn_quit)
        
        self.setLayout(layout)
    
    def update_blink_interval(self, v):
        min_v = v / 10.0
        max_v = min_v + 3.0
        self.controller.blink_interval_min = min_v
        self.controller.blink_interval_max = max_v
        self.interval_label.setText(f"{min_v:.0f}-{max_v:.0f}s")


def main():
    print("\n" + "=" * 50)
    print("最终版 Idle 控制器")
    print("=" * 50)
    
    print("\n基于测试发现:")
    print("  - UpdateBreath 会导致身体乱动 -> 不调用")
    print("  - UpdateBlink 不工作 -> 手动实现")
    print("  - ParamBreath 控制尾巴 -> 手动正弦波")
    print("  - UpdatePhysics 控制头发 -> 保留")
    
    print("\n预期效果:")
    print("  - 头发自然飘动")
    print("  - 尾巴轻轻摆动")
    print("  - 自然眨眼")
    print("  - 头部身体保持静止\n")
    
    live2d.init()
    
    app = QApplication(sys.argv)
    
    model_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "live2d_local",
        "models",
        "sakiko.model3.json"
    )
    
    controller = FinalIdleController(model_path)
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
