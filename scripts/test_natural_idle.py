# -*- coding: utf-8 -*-
"""
自然 Idle 动画测试 v2

核心思路：真人直播时的头部行为
1. 大部分时间保持相对静止（只有极微小的抖动）
2. 偶尔会有小幅度的姿势调整（换个舒服的姿势）
3. 说话时可能会有更多动作

这不是"持续的 Perlin 摇摆"，而是"静止 + 偶尔微调"

使用方法：
    python scripts/test_natural_idle.py
"""

import sys
import os
import math
import time
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QOpenGLWidget, QPushButton, QVBoxLayout, QWidget, QLabel, QCheckBox, QSlider, QHBoxLayout, QComboBox
import OpenGL.GL as GL

import live2d.v3 as live2d
from live2d.utils.canvas import Canvas


class NaturalIdleAnimator:
    """自然的 Idle 动画控制器
    
    模拟真人直播时的头部行为：
    - 基础姿势：大部分时间保持在某个位置
    - 极微小抖动：模拟人不可能完全静止的特性
    - 偶尔调整：每隔一段时间换个姿势
    """
    
    def __init__(self):
        # 当前目标姿势
        self.target_x = 0.0
        self.target_y = 0.0
        self.target_z = 0.0
        
        # 当前实际值（平滑过渡用）
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_z = 0.0
        
        # 微小抖动（breathing noise）
        self.micro_noise_strength = 0.3  # 极小的抖动
        
        # 姿势调整设置
        self.adjust_interval_min = 3.0    # 最短间隔（秒）
        self.adjust_interval_max = 8.0    # 最长间隔（秒）
        self.next_adjust_time = time.time() + random.uniform(3, 6)
        
        # 调整幅度
        self.max_adjust_x = 5.0    # 左右看
        self.max_adjust_y = 3.0    # 上下看
        self.max_adjust_z = 3.0    # 歪头
        
        # 平滑系数（越小越平滑）
        self.smoothing = 0.03
        
        # 模式
        self.mode = "natural"  # natural, perlin, static
        
        # Perlin noise 时间偏移
        self.time_offset = random.random() * 1000
    
    def update(self, delta_time: float) -> dict:
        """更新并返回头部参数"""
        current_time = time.time()
        
        if self.mode == "static":
            # 完全静止
            return {
                "ParamAngleX": 0.0,
                "ParamAngleY": 0.0,
                "ParamAngleZ": 0.0,
            }
        
        elif self.mode == "perlin":
            # 持续 Perlin（原来的方式，作为对比）
            try:
                from noise import pnoise1
                t = current_time * 0.3 + self.time_offset
                return {
                    "ParamAngleX": pnoise1(t) * 8.0,
                    "ParamAngleY": pnoise1(t + 100) * 5.0,
                    "ParamAngleZ": pnoise1(t + 200) * 4.0,
                }
            except:
                return {"ParamAngleX": 0, "ParamAngleY": 0, "ParamAngleZ": 0}
        
        else:  # natural
            # === 1. 检查是否需要调整姿势 ===
            if current_time >= self.next_adjust_time:
                self._trigger_adjustment()
                self.next_adjust_time = current_time + random.uniform(
                    self.adjust_interval_min, 
                    self.adjust_interval_max
                )
            
            # === 2. 平滑过渡到目标姿势 ===
            self.current_x += (self.target_x - self.current_x) * self.smoothing
            self.current_y += (self.target_y - self.current_y) * self.smoothing
            self.current_z += (self.target_z - self.current_z) * self.smoothing
            
            # === 3. 添加极微小的抖动 ===
            try:
                from noise import pnoise1
                t = current_time * 2.0 + self.time_offset  # 快速的微小抖动
                micro_x = pnoise1(t) * self.micro_noise_strength
                micro_y = pnoise1(t + 50) * self.micro_noise_strength
                micro_z = pnoise1(t + 100) * self.micro_noise_strength * 0.5
            except:
                micro_x = micro_y = micro_z = 0.0
            
            return {
                "ParamAngleX": self.current_x + micro_x,
                "ParamAngleY": self.current_y + micro_y,
                "ParamAngleZ": self.current_z + micro_z,
            }
    
    def _trigger_adjustment(self):
        """触发一次姿势调整"""
        # 随机决定调整类型
        adjust_type = random.choice(["small", "small", "small", "medium", "return"])
        
        if adjust_type == "return":
            # 回到中心
            self.target_x = 0.0
            self.target_y = 0.0
            self.target_z = 0.0
        elif adjust_type == "small":
            # 小幅调整（从当前位置偏移一点）
            self.target_x += random.uniform(-2, 2)
            self.target_y += random.uniform(-1.5, 1.5)
            self.target_z += random.uniform(-1, 1)
            # 限制范围
            self.target_x = max(-self.max_adjust_x, min(self.max_adjust_x, self.target_x))
            self.target_y = max(-self.max_adjust_y, min(self.max_adjust_y, self.target_y))
            self.target_z = max(-self.max_adjust_z, min(self.max_adjust_z, self.target_z))
        else:  # medium
            # 较明显的调整（看向某个方向）
            self.target_x = random.uniform(-self.max_adjust_x, self.max_adjust_x) * 0.6
            self.target_y = random.uniform(-self.max_adjust_y, self.max_adjust_y) * 0.6
            self.target_z = random.uniform(-self.max_adjust_z, self.max_adjust_z) * 0.4


class NaturalIdleController(QOpenGLWidget):
    """自然 Idle 控制器"""
    
    def __init__(self, model_path: str):
        super().__init__()
        
        self.model_path = model_path
        self.display_width = 500
        self.display_height = 600
        self.fps = 60
        
        self.model = None
        self.canvas = None
        self.idle_animator = NaturalIdleAnimator()
        
        self.last_time = time.time()
        
        # 控制开关
        self.enable_breath = True
        self.enable_blink = True
        self.enable_physics = True
        self.enable_idle = True
        
        # 窗口设置
        self.setWindowTitle("Natural Idle Test")
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
        
        self.model.SetAutoBreath(True)
        self.model.SetAutoBlink(True)
        
        self.canvas = Canvas()
        self.canvas.SetSize(self.display_width, self.display_height)
        
        # 检查眨眼相关参数
        print("\n=== 检查眨眼参数 ===")
        param_ids = self.model.GetParameterIds()
        for i, pid in enumerate(param_ids):
            if "eye" in pid.lower() or "blink" in pid.lower():
                print(f"  {pid}")
        
        self.startTimer(int(1000 / self.fps))
        print("\n模型加载完成")
    
    def timerEvent(self, event):
        if not self.model:
            return
        
        current_time = time.time()
        delta_time = current_time - self.last_time
        self.last_time = current_time
        
        # 不调用 UpdateMotion，避免 idle 动作
        
        if self.enable_breath:
            self.model.UpdateBreath(delta_time)
        
        if self.enable_blink:
            self.model.UpdateBlink(delta_time)
        
        if self.enable_physics:
            self.model.UpdatePhysics(delta_time)
        
        # 自然 Idle 动画
        if self.enable_idle:
            params = self.idle_animator.update(delta_time)
            for param_id, value in params.items():
                self.model.SetParameterValueById(param_id, value, 1.0)
        
        self.update()
    
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
    
    def __init__(self, controller: NaturalIdleController):
        super().__init__()
        self.controller = controller
        self.animator = controller.idle_animator
        
        self.setWindowTitle("Natural Idle Control")
        self.setFixedSize(350, 550)
        
        layout = QVBoxLayout()
        
        # 模式选择
        layout.addWidget(QLabel("=== Idle 模式 ==="))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["natural (自然)", "perlin (持续摇摆)", "static (完全静止)"])
        self.mode_combo.currentIndexChanged.connect(self.change_mode)
        layout.addWidget(self.mode_combo)
        
        layout.addWidget(QLabel("\n=== 基础动画 ==="))
        
        cb_breath = QCheckBox("Breath (呼吸)")
        cb_breath.setChecked(True)
        cb_breath.toggled.connect(lambda v: setattr(controller, 'enable_breath', v))
        layout.addWidget(cb_breath)
        
        cb_blink = QCheckBox("Blink (眨眼)")
        cb_blink.setChecked(True)
        cb_blink.toggled.connect(lambda v: setattr(controller, 'enable_blink', v))
        layout.addWidget(cb_blink)
        
        cb_physics = QCheckBox("Physics (物理)")
        cb_physics.setChecked(True)
        cb_physics.toggled.connect(lambda v: setattr(controller, 'enable_physics', v))
        layout.addWidget(cb_physics)
        
        cb_idle = QCheckBox("Idle (头部动画)")
        cb_idle.setChecked(True)
        cb_idle.toggled.connect(lambda v: setattr(controller, 'enable_idle', v))
        layout.addWidget(cb_idle)
        
        layout.addWidget(QLabel("\n=== Natural 模式参数 ==="))
        
        # 调整间隔
        layout.addWidget(QLabel("调整间隔 (秒):"))
        h1 = QHBoxLayout()
        self.interval_slider = QSlider(Qt.Orientation.Horizontal)
        self.interval_slider.setRange(20, 150)  # 2.0 到 15.0 秒
        self.interval_slider.setValue(50)
        self.interval_slider.valueChanged.connect(self.update_interval)
        h1.addWidget(self.interval_slider)
        self.interval_label = QLabel("3-8s")
        h1.addWidget(self.interval_label)
        layout.addLayout(h1)
        
        # 微抖动强度
        layout.addWidget(QLabel("微抖动强度:"))
        h2 = QHBoxLayout()
        self.noise_slider = QSlider(Qt.Orientation.Horizontal)
        self.noise_slider.setRange(0, 20)
        self.noise_slider.setValue(3)
        self.noise_slider.valueChanged.connect(lambda v: setattr(self.animator, 'micro_noise_strength', v / 10.0))
        h2.addWidget(self.noise_slider)
        self.noise_label = QLabel("0.3")
        self.noise_slider.valueChanged.connect(lambda v: self.noise_label.setText(f"{v/10:.1f}"))
        h2.addWidget(self.noise_label)
        layout.addLayout(h2)
        
        # 最大调整幅度
        layout.addWidget(QLabel("最大调整幅度 X:"))
        slider_x = QSlider(Qt.Orientation.Horizontal)
        slider_x.setRange(0, 15)
        slider_x.setValue(5)
        slider_x.valueChanged.connect(lambda v: setattr(self.animator, 'max_adjust_x', float(v)))
        layout.addWidget(slider_x)
        
        layout.addWidget(QLabel("最大调整幅度 Y:"))
        slider_y = QSlider(Qt.Orientation.Horizontal)
        slider_y.setRange(0, 10)
        slider_y.setValue(3)
        slider_y.valueChanged.connect(lambda v: setattr(self.animator, 'max_adjust_y', float(v)))
        layout.addWidget(slider_y)
        
        layout.addWidget(QLabel("最大调整幅度 Z:"))
        slider_z = QSlider(Qt.Orientation.Horizontal)
        slider_z.setRange(0, 10)
        slider_z.setValue(3)
        slider_z.valueChanged.connect(lambda v: setattr(self.animator, 'max_adjust_z', float(v)))
        layout.addWidget(slider_z)
        
        # 平滑度
        layout.addWidget(QLabel("平滑度 (越大越快):"))
        h3 = QHBoxLayout()
        smooth_slider = QSlider(Qt.Orientation.Horizontal)
        smooth_slider.setRange(1, 20)
        smooth_slider.setValue(3)
        smooth_slider.valueChanged.connect(lambda v: setattr(self.animator, 'smoothing', v / 100.0))
        h3.addWidget(smooth_slider)
        self.smooth_label = QLabel("0.03")
        smooth_slider.valueChanged.connect(lambda v: self.smooth_label.setText(f"{v/100:.2f}"))
        h3.addWidget(self.smooth_label)
        layout.addLayout(h3)
        
        # 手动触发调整
        btn_adjust = QPushButton("手动触发姿势调整")
        btn_adjust.clicked.connect(self.animator._trigger_adjustment)
        layout.addWidget(btn_adjust)
        
        # 退出
        btn_quit = QPushButton("退出")
        btn_quit.clicked.connect(QApplication.quit)
        layout.addWidget(btn_quit)
        
        self.setLayout(layout)
    
    def change_mode(self, index):
        modes = ["natural", "perlin", "static"]
        self.animator.mode = modes[index]
        print(f"切换到模式: {modes[index]}")
    
    def update_interval(self, v):
        min_val = v / 10.0
        max_val = min_val + 5.0
        self.animator.adjust_interval_min = min_val
        self.animator.adjust_interval_max = max_val
        self.interval_label.setText(f"{min_val:.0f}-{max_val:.0f}s")


def main():
    print("\n" + "=" * 50)
    print("Natural Idle 动画测试 v2")
    print("=" * 50)
    print("\n核心思路: 真人直播时不会持续摇头")
    print("  - 大部分时间保持相对静止")
    print("  - 偶尔有小幅度的姿势调整")
    print("  - 始终有极微小的抖动（人无法完全静止）\n")
    
    live2d.init()
    
    app = QApplication(sys.argv)
    
    model_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "live2d_local",
        "models",
        "sakiko.model3.json"
    )
    
    print(f"加载模型: {model_path}")
    
    controller = NaturalIdleController(model_path)
    controller.show()
    controller.move(100, 100)
    
    panel = ControlPanel(controller)
    panel.show()
    panel.move(650, 100)
    
    print("\n使用说明:")
    print("1. 默认是 'natural' 模式，观察效果")
    print("2. 可以切换到 'perlin' 对比之前的效果")
    print("3. 调整参数找到最自然的配置")
    print("4. 点击 '手动触发' 立即触发一次姿势调整")
    print("\n" + "=" * 50 + "\n")
    
    app.exec()
    live2d.dispose()


if __name__ == "__main__":
    main()
