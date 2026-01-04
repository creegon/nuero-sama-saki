# -*- coding: utf-8 -*-
"""
Minimal Idle 测试 v3

根据真人皮套观察：
1. 头部基本不动
2. 主要靠呼吸带来上下起伏
3. 眨眼带来动感
4. 偶尔非常轻微的调整

这个版本重点：
- 调试眨眼功能
- 极简的头部动画
- 查找身体摆动来源

使用方法：
    python scripts/test_minimal_idle.py
"""

import sys
import os
import math
import time
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QApplication, QOpenGLWidget, QPushButton, 
                             QVBoxLayout, QWidget, QLabel, QCheckBox, 
                             QSlider, QHBoxLayout, QGroupBox, QScrollArea)
import OpenGL.GL as GL

import live2d.v3 as live2d
from live2d.utils.canvas import Canvas


class MinimalIdleController(QOpenGLWidget):
    """极简 Idle 控制器"""
    
    def __init__(self, model_path: str):
        super().__init__()
        
        self.model_path = model_path
        self.display_width = 450
        self.display_height = 550
        self.fps = 60
        
        self.model = None
        self.canvas = None
        
        self.last_time = time.time()
        
        # 控制开关
        self.enable_motion = False     # Motion 可能是身体摆动的来源
        self.enable_breath = True
        self.enable_blink = True
        self.enable_physics = True
        self.enable_expression = False
        self.enable_pose = False
        self.enable_drag = False
        
        # 手动眨眼控制
        self.manual_blink = False
        self.blink_value = 1.0  # 1.0 = 眼睛完全睁开, 0.0 = 完全闭上
        self.blink_interval = 3.0  # 眨眼间隔
        self.next_blink_time = time.time() + random.uniform(2, 4)
        self.is_blinking = False
        self.blink_phase = 0  # 0=睁眼, 1=闭眼中, 2=睁眼中
        
        # 调试信息
        self.debug_params = {}
        
        # 窗口设置
        self.setWindowTitle("Minimal Idle")
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
        
        # 打印所有参数
        print("\n=== 全部模型参数 ===")
        param_ids = self.model.GetParameterIds()
        self.all_params = param_ids
        for i, pid in enumerate(param_ids):
            min_val = self.model.GetParameterMinimumValue(i)
            max_val = self.model.GetParameterMaximumValue(i)
            default_val = self.model.GetParameterDefaultValue(i)
            print(f"  [{i:2d}] {pid:30s} range: {min_val:.1f} ~ {max_val:.1f}, default: {default_val:.1f}")
        
        # 找眨眼参数
        self.eye_l_index = None
        self.eye_r_index = None
        for i, pid in enumerate(param_ids):
            if pid == "ParamEyeLOpen":
                self.eye_l_index = i
                print(f"\n[FOUND] ParamEyeLOpen at index {i}")
            elif pid == "ParamEyeROpen":
                self.eye_r_index = i
                print(f"[FOUND] ParamEyeROpen at index {i}")
        
        self.startTimer(int(1000 / self.fps))
        print("\n模型加载完成")
    
    def timerEvent(self, event):
        if not self.model:
            return
        
        current_time = time.time()
        delta_time = current_time - self.last_time
        self.last_time = current_time
        
        # === 选择性更新 ===
        if self.enable_motion:
            self.model.UpdateMotion(delta_time)
        
        if self.enable_drag:
            self.model.UpdateDrag(delta_time)
        
        if self.enable_breath:
            self.model.UpdateBreath(delta_time)
        
        if self.enable_blink and not self.manual_blink:
            self.model.UpdateBlink(delta_time)
        
        if self.enable_physics:
            self.model.UpdatePhysics(delta_time)
        
        if self.enable_expression:
            self.model.UpdateExpression(delta_time)
        
        if self.enable_pose:
            self.model.UpdatePose(delta_time)
        
        # === 手动眨眼 ===
        if self.manual_blink:
            self._update_manual_blink(current_time, delta_time)
        
        self.update()
    
    def _update_manual_blink(self, current_time, delta_time):
        """手动实现眨眼"""
        # 检查是否该眨眼了
        if not self.is_blinking and current_time >= self.next_blink_time:
            self.is_blinking = True
            self.blink_phase = 1  # 开始闭眼
        
        if self.is_blinking:
            if self.blink_phase == 1:  # 闭眼中
                self.blink_value -= delta_time * 15  # 快速闭眼
                if self.blink_value <= 0:
                    self.blink_value = 0
                    self.blink_phase = 2  # 开始睁眼
            elif self.blink_phase == 2:  # 睁眼中
                self.blink_value += delta_time * 10  # 稍慢睁眼
                if self.blink_value >= 1.0:
                    self.blink_value = 1.0
                    self.is_blinking = False
                    self.blink_phase = 0
                    self.next_blink_time = current_time + random.uniform(2, 5)
        
        # 设置眼睛参数
        if self.eye_l_index is not None:
            self.model.SetParameterValue(self.eye_l_index, self.blink_value, 1.0)
        if self.eye_r_index is not None:
            self.model.SetParameterValue(self.eye_r_index, self.blink_value, 1.0)
    
    def force_blink(self):
        """强制立即眨眼"""
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
    """控制面板 - 更紧凑的布局"""
    
    def __init__(self, controller: MinimalIdleController):
        super().__init__()
        self.controller = controller
        
        self.setWindowTitle("Control")
        self.setFixedSize(280, 450)
        
        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # === Update 组件 ===
        group1 = QGroupBox("Update 组件")
        g1_layout = QVBoxLayout()
        g1_layout.setSpacing(2)
        
        self.cb_motion = QCheckBox("Motion (可能是摆动来源!)")
        self.cb_motion.setChecked(controller.enable_motion)
        self.cb_motion.toggled.connect(lambda v: setattr(controller, 'enable_motion', v))
        g1_layout.addWidget(self.cb_motion)
        
        self.cb_breath = QCheckBox("Breath (呼吸)")
        self.cb_breath.setChecked(controller.enable_breath)
        self.cb_breath.toggled.connect(lambda v: setattr(controller, 'enable_breath', v))
        g1_layout.addWidget(self.cb_breath)
        
        self.cb_physics = QCheckBox("Physics (物理)")
        self.cb_physics.setChecked(controller.enable_physics)
        self.cb_physics.toggled.connect(lambda v: setattr(controller, 'enable_physics', v))
        g1_layout.addWidget(self.cb_physics)
        
        self.cb_pose = QCheckBox("Pose (姿势)")
        self.cb_pose.setChecked(controller.enable_pose)
        self.cb_pose.toggled.connect(lambda v: setattr(controller, 'enable_pose', v))
        g1_layout.addWidget(self.cb_pose)
        
        self.cb_expression = QCheckBox("Expression (表情)")
        self.cb_expression.setChecked(controller.enable_expression)
        self.cb_expression.toggled.connect(lambda v: setattr(controller, 'enable_expression', v))
        g1_layout.addWidget(self.cb_expression)
        
        self.cb_drag = QCheckBox("Drag (视线追踪)")
        self.cb_drag.setChecked(controller.enable_drag)
        self.cb_drag.toggled.connect(lambda v: setattr(controller, 'enable_drag', v))
        g1_layout.addWidget(self.cb_drag)
        
        group1.setLayout(g1_layout)
        layout.addWidget(group1)
        
        # === 眨眼控制 ===
        group2 = QGroupBox("眨眼控制")
        g2_layout = QVBoxLayout()
        g2_layout.setSpacing(2)
        
        self.cb_blink_auto = QCheckBox("自动眨眼 (UpdateBlink)")
        self.cb_blink_auto.setChecked(controller.enable_blink)
        self.cb_blink_auto.toggled.connect(self.toggle_auto_blink)
        g2_layout.addWidget(self.cb_blink_auto)
        
        self.cb_blink_manual = QCheckBox("手动眨眼 (我们实现)")
        self.cb_blink_manual.setChecked(controller.manual_blink)
        self.cb_blink_manual.toggled.connect(self.toggle_manual_blink)
        g2_layout.addWidget(self.cb_blink_manual)
        
        btn_blink = QPushButton("立即眨眼")
        btn_blink.clicked.connect(controller.force_blink)
        g2_layout.addWidget(btn_blink)
        
        # 眼睛值滑块（调试用）
        h = QHBoxLayout()
        h.addWidget(QLabel("眼睛值:"))
        self.eye_slider = QSlider(Qt.Orientation.Horizontal)
        self.eye_slider.setRange(0, 100)
        self.eye_slider.setValue(100)
        self.eye_slider.valueChanged.connect(self.set_eye_manual)
        h.addWidget(self.eye_slider)
        self.eye_label = QLabel("1.0")
        h.addWidget(self.eye_label)
        g2_layout.addLayout(h)
        
        group2.setLayout(g2_layout)
        layout.addWidget(group2)
        
        # === 调试 ===
        group3 = QGroupBox("调试")
        g3_layout = QVBoxLayout()
        
        btn_print_params = QPushButton("打印当前参数值")
        btn_print_params.clicked.connect(self.print_current_params)
        g3_layout.addWidget(btn_print_params)
        
        group3.setLayout(g3_layout)
        layout.addWidget(group3)
        
        # 退出
        btn_quit = QPushButton("退出")
        btn_quit.clicked.connect(QApplication.quit)
        layout.addWidget(btn_quit)
        
        self.setLayout(layout)
    
    def toggle_auto_blink(self, v):
        self.controller.enable_blink = v
        if v:
            self.cb_blink_manual.setChecked(False)
    
    def toggle_manual_blink(self, v):
        self.controller.manual_blink = v
        if v:
            self.cb_blink_auto.setChecked(False)
            self.controller.enable_blink = False
    
    def set_eye_manual(self, v):
        val = v / 100.0
        self.eye_label.setText(f"{val:.2f}")
        # 直接设置眼睛参数
        if self.controller.model and self.controller.manual_blink:
            self.controller.blink_value = val
            if self.controller.eye_l_index is not None:
                self.controller.model.SetParameterValue(
                    self.controller.eye_l_index, val, 1.0)
            if self.controller.eye_r_index is not None:
                self.controller.model.SetParameterValue(
                    self.controller.eye_r_index, val, 1.0)
    
    def print_current_params(self):
        """打印当前所有参数值"""
        if not self.controller.model:
            return
        print("\n=== 当前参数值 ===")
        for i, pid in enumerate(self.controller.all_params):
            val = self.controller.model.GetParameterValue(i)
            if abs(val) > 0.01:  # 只打印非零值
                print(f"  {pid}: {val:.3f}")


def main():
    print("\n" + "=" * 50)
    print("Minimal Idle 测试 v3")
    print("=" * 50)
    print("\n目标: 只有呼吸 + 眨眼，没有头部摆动")
    print("调试: 找到身体摆动的来源\n")
    
    live2d.init()
    
    app = QApplication(sys.argv)
    
    model_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "live2d_local",
        "models",
        "sakiko.model3.json"
    )
    
    print(f"加载模型: {model_path}")
    
    controller = MinimalIdleController(model_path)
    controller.show()
    controller.move(50, 50)
    
    panel = ControlPanel(controller)
    panel.show()
    panel.move(550, 50)
    
    print("\n使用说明:")
    print("1. 默认 Motion 关闭，观察身体是否还会摆动")
    print("2. 如果还摆动，尝试关闭 Physics")
    print("3. 测试眨眼：勾选'手动眨眼'然后拖动滑块")
    print("4. 或者点击'立即眨眼'")
    print("\n" + "=" * 50 + "\n")
    
    app.exec()
    live2d.dispose()


if __name__ == "__main__":
    main()
