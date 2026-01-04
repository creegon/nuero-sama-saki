# -*- coding: utf-8 -*-
"""
参数调试工具 v5

完整的参数控制面板，可以单独测试每个参数的效果

使用方法：
    python scripts/test_param_debug.py
"""

import sys
import os
import math
import time
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QApplication, QOpenGLWidget, QPushButton, 
                             QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
                             QCheckBox, QSlider, QGroupBox, QScrollArea,
                             QMainWindow, QSplitter, QFrame, QSpinBox,
                             QDoubleSpinBox, QTabWidget)
import OpenGL.GL as GL

import live2d.v3 as live2d
from live2d.utils.canvas import Canvas


class Live2DWidget(QOpenGLWidget):
    """Live2D 显示组件"""
    
    def __init__(self, model_path: str):
        super().__init__()
        
        self.model_path = model_path
        self.display_width = 400
        self.display_height = 500
        self.fps = 60
        
        self.model = None
        self.canvas = None
        
        self.last_time = time.time()
        self.start_time = time.time()
        
        # 参数存储
        self.param_indices = {}
        self.all_params = []
        
        # Update 开关
        self.update_flags = {
            "motion": False,
            "drag": False,
            "breath": False,
            "blink": False,
            "physics": True,
            "expression": False,
            "pose": False,
        }
        
        # 手动参数控制
        self.manual_params = {}  # {param_name: value}
        
        # 手动眨眼
        self.manual_blink_enabled = True
        self.blink_value = 1.0
        self.next_blink_time = time.time() + random.uniform(2, 4)
        self.is_blinking = False
        self.blink_phase = 0
        
        # 窗口设置
        self.setMinimumSize(self.display_width, self.display_height)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
    def initializeGL(self):
        live2d.glInit()
        
        self.model = live2d.Model()
        self.model.LoadModelJson(self.model_path)
        self.model.CreateRenderer()
        self.model.Resize(self.display_width, self.display_height)
        
        self.canvas = Canvas()
        self.canvas.SetSize(self.display_width, self.display_height)
        
        # 获取所有参数
        self.all_params = self.model.GetParameterIds()
        for i, pid in enumerate(self.all_params):
            self.param_indices[pid] = i
        
        self.startTimer(int(1000 / self.fps))
    
    def timerEvent(self, event):
        if not self.model:
            return
        
        current_time = time.time()
        delta_time = current_time - self.last_time
        self.last_time = current_time
        
        # Update 函数
        if self.update_flags["motion"]:
            self.model.UpdateMotion(delta_time)
        if self.update_flags["drag"]:
            self.model.UpdateDrag(delta_time)
        if self.update_flags["breath"]:
            self.model.UpdateBreath(delta_time)
        if self.update_flags["blink"]:
            self.model.UpdateBlink(delta_time)
        if self.update_flags["physics"]:
            self.model.UpdatePhysics(delta_time)
        if self.update_flags["expression"]:
            self.model.UpdateExpression(delta_time)
        if self.update_flags["pose"]:
            self.model.UpdatePose(delta_time)
        
        # 手动眨眼
        if self.manual_blink_enabled and not self.update_flags["blink"]:
            self._update_manual_blink(current_time, delta_time)
        
        # 应用手动参数
        for param_name, value in self.manual_params.items():
            if param_name in self.param_indices:
                self.model.SetParameterValue(self.param_indices[param_name], value, 1.0)
        
        self.update()
    
    def _update_manual_blink(self, current_time, delta_time):
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
    
    def set_param(self, name, value):
        self.manual_params[name] = value
    
    def clear_param(self, name):
        if name in self.manual_params:
            del self.manual_params[name]
    
    def get_param_value(self, name):
        if name in self.param_indices and self.model:
            return self.model.GetParameterValue(self.param_indices[name])
        return 0.0
    
    def on_draw(self):
        live2d.clearBuffer()
        self.model.Draw()
    
    def paintGL(self):
        GL.glClearColor(0.2, 0.2, 0.2, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        
        if self.model and self.canvas:
            self.canvas.Draw(self.on_draw)
    
    def resizeGL(self, width, height):
        if self.model:
            self.model.Resize(width, height)
        if self.canvas:
            self.canvas.SetSize(width, height)


class ParamSlider(QWidget):
    """单个参数控制器"""
    
    def __init__(self, param_name, min_val, max_val, default_val, live2d_widget):
        super().__init__()
        self.param_name = param_name
        self.live2d = live2d_widget
        self.min_val = min_val
        self.max_val = max_val
        self.default_val = default_val
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 启用复选框
        self.cb = QCheckBox()
        self.cb.setFixedWidth(20)
        self.cb.toggled.connect(self.on_toggle)
        layout.addWidget(self.cb)
        
        # 参数名
        self.label = QLabel(param_name)
        self.label.setFixedWidth(150)
        self.label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self.label)
        
        # 滑块
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(int((default_val - min_val) / (max_val - min_val) * 100) if max_val != min_val else 50)
        self.slider.valueChanged.connect(self.on_slider)
        self.slider.setEnabled(False)
        layout.addWidget(self.slider)
        
        # 当前值
        self.value_label = QLabel(f"{default_val:.2f}")
        self.value_label.setFixedWidth(50)
        layout.addWidget(self.value_label)
        
        self.setLayout(layout)
    
    def on_toggle(self, checked):
        self.slider.setEnabled(checked)
        if checked:
            self.on_slider(self.slider.value())
        else:
            self.live2d.clear_param(self.param_name)
    
    def on_slider(self, v):
        value = self.min_val + (self.max_val - self.min_val) * v / 100.0
        self.value_label.setText(f"{value:.2f}")
        if self.cb.isChecked():
            self.live2d.set_param(self.param_name, value)


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self, model_path):
        super().__init__()
        
        self.setWindowTitle("Live2D 参数调试工具")
        self.setGeometry(50, 50, 1100, 700)
        
        # 创建 Live2D 组件
        self.live2d = Live2DWidget(model_path)
        
        # 主布局
        central = QWidget()
        main_layout = QHBoxLayout()
        main_layout.setSpacing(10)
        
        # 左侧：Live2D 显示
        left_frame = QFrame()
        left_frame.setFrameStyle(QFrame.StyledPanel)
        left_frame.setFixedWidth(420)
        left_layout = QVBoxLayout()
        left_layout.addWidget(self.live2d)
        left_frame.setLayout(left_layout)
        main_layout.addWidget(left_frame)
        
        # 右侧：控制面板（使用 Tab）
        self.tabs = QTabWidget()
        
        # Tab 1: Update 函数开关
        tab1 = self._create_update_tab()
        self.tabs.addTab(tab1, "Update 函数")
        
        # Tab 2: 常用参数
        tab2 = self._create_common_params_tab()
        self.tabs.addTab(tab2, "常用参数")
        
        # Tab 3: 全部参数
        tab3 = self._create_all_params_tab()
        self.tabs.addTab(tab3, "全部参数")
        
        main_layout.addWidget(self.tabs)
        
        central.setLayout(main_layout)
        self.setCentralWidget(central)
        
        # 定时更新参数显示
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_param_display)
        self.update_timer.start(100)
    
    def _create_update_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        layout.addWidget(QLabel("<b>Update 函数开关</b>"))
        layout.addWidget(QLabel("勾选后会调用对应的 Update 函数"))
        layout.addWidget(QLabel(""))
        
        updates = [
            ("motion", "UpdateMotion (动作)", "可能导致身体乱转"),
            ("drag", "UpdateDrag (拖拽追踪)", ""),
            ("breath", "UpdateBreath (呼吸)", "会影响尾巴和其他部位!"),
            ("blink", "UpdateBlink (官方眨眼)", ""),
            ("physics", "UpdatePhysics (物理)", "控制头发衣服"),
            ("expression", "UpdateExpression (表情)", ""),
            ("pose", "UpdatePose (姿势)", ""),
        ]
        
        for key, name, note in updates:
            h = QHBoxLayout()
            cb = QCheckBox(name)
            cb.setChecked(self.live2d.update_flags[key])
            cb.toggled.connect(lambda v, k=key: self._set_update_flag(k, v))
            h.addWidget(cb)
            if note:
                lbl = QLabel(f"<font color='orange'>{note}</font>")
                h.addWidget(lbl)
            h.addStretch()
            layout.addLayout(h)
        
        layout.addWidget(QLabel(""))
        layout.addWidget(QLabel("<b>手动控制</b>"))
        
        cb_manual_blink = QCheckBox("手动眨眼 (我们实现)")
        cb_manual_blink.setChecked(self.live2d.manual_blink_enabled)
        cb_manual_blink.toggled.connect(lambda v: setattr(self.live2d, 'manual_blink_enabled', v))
        layout.addWidget(cb_manual_blink)
        
        layout.addStretch()
        
        # 退出按钮
        btn_quit = QPushButton("退出")
        btn_quit.clicked.connect(QApplication.quit)
        layout.addWidget(btn_quit)
        
        widget.setLayout(layout)
        return widget
    
    def _set_update_flag(self, key, value):
        self.live2d.update_flags[key] = value
    
    def _create_common_params_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("<b>常用参数控制</b>"))
        layout.addWidget(QLabel("勾选后可以手动控制该参数"))
        
        # 常用参数分组
        groups = {
            "头部": ["ParamAngleX", "ParamAngleY", "ParamAngleZ"],
            "身体": ["ParamBodyAngleX", "ParamBodyAngleY", "ParamBodyAngleZ"],
            "眼睛": ["ParamEyeLOpen", "ParamEyeROpen", "ParamEyeBallX", "ParamEyeBallY"],
            "嘴巴": ["ParamMouthForm", "ParamMouthOpenY"],
            "其他": ["ParamBreath", "ParamCheek"],
        }
        
        self.common_sliders = {}
        
        for group_name, params in groups.items():
            group = QGroupBox(group_name)
            g_layout = QVBoxLayout()
            g_layout.setSpacing(3)
            
            for param in params:
                if param in self.live2d.param_indices:
                    idx = self.live2d.param_indices[param]
                    min_v = self.live2d.model.GetParameterMinimumValue(idx) if self.live2d.model else -1
                    max_v = self.live2d.model.GetParameterMaximumValue(idx) if self.live2d.model else 1
                    def_v = self.live2d.model.GetParameterDefaultValue(idx) if self.live2d.model else 0
                    
                    slider = ParamSlider(param, min_v, max_v, def_v, self.live2d)
                    self.common_sliders[param] = slider
                    g_layout.addWidget(slider)
            
            group.setLayout(g_layout)
            layout.addWidget(group)
        
        layout.addStretch()
        widget.setLayout(layout)
        
        scroll = QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        return scroll
    
    def _create_all_params_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("<b>全部参数</b>"))
        layout.addWidget(QLabel("模型共有 {} 个参数".format(len(self.live2d.all_params) if self.live2d.all_params else "?")))
        
        self.all_sliders = {}
        
        # 等模型加载完
        QTimer.singleShot(500, lambda: self._populate_all_params(layout, widget))
        
        widget.setLayout(layout)
        
        scroll = QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        return scroll
    
    def _populate_all_params(self, layout, widget):
        if not self.live2d.model or not self.live2d.all_params:
            return
        
        for param in self.live2d.all_params:
            idx = self.live2d.param_indices[param]
            min_v = self.live2d.model.GetParameterMinimumValue(idx)
            max_v = self.live2d.model.GetParameterMaximumValue(idx)
            def_v = self.live2d.model.GetParameterDefaultValue(idx)
            
            slider = ParamSlider(param, min_v, max_v, def_v, self.live2d)
            self.all_sliders[param] = slider
            layout.addWidget(slider)
        
        layout.addStretch()
    
    def update_param_display(self):
        # 可以在这里更新实时参数显示
        pass


def main():
    print("\n" + "=" * 50)
    print("Live2D 参数调试工具 v5")
    print("=" * 50)
    print("\n这是一个完整的参数调试工具")
    print("你可以:")
    print("  - 开关各个 Update 函数")
    print("  - 手动控制任意参数")
    print("  - 观察每个参数的效果\n")
    
    live2d.init()
    
    app = QApplication(sys.argv)
    
    model_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "live2d_local",
        "models",
        "sakiko.model3.json"
    )
    
    window = MainWindow(model_path)
    window.show()
    
    print("程序启动完成\n" + "=" * 50 + "\n")
    
    app.exec()
    live2d.dispose()


if __name__ == "__main__":
    main()
