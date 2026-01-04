# -*- coding: utf-8 -*-
"""
测试 live2d-py 底层 Model 类

目的：使用底层 Model 类代替 LAppModel，获得完全控制权
- 可以选择性调用 UpdateMotion/UpdateBreath/UpdateBlink/UpdatePhysics
- 禁用 idle 动作，只保留我们想要的动画

使用方法：
    python scripts/test_low_level_model.py
"""

import sys
import os
import math
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QOpenGLWidget, QPushButton, QVBoxLayout, QWidget, QLabel, QCheckBox, QSlider, QHBoxLayout
import OpenGL.GL as GL

import live2d.v3 as live2d
from live2d.utils.canvas import Canvas


class LowLevelModelController(QOpenGLWidget):
    """使用底层 Model 类的控制器"""
    
    def __init__(self, model_path: str):
        super().__init__()
        
        self.model_path = model_path
        self.display_width = 500
        self.display_height = 600
        self.fps = 60
        
        self.model = None  # 底层 Model 类
        self.canvas = None
        
        # 时间追踪
        self.last_time = time.time()
        self.start_time = time.time()
        
        # 控制开关
        self.enable_motion = False      # 是否播放 Motion（idle 动作）
        self.enable_breath = True       # 是否启用呼吸
        self.enable_blink = True        # 是否启用眨眼
        self.enable_physics = True      # 是否启用物理
        self.enable_drag = False        # 是否启用拖拽追踪（原生的）
        self.enable_perlin = False      # 是否启用 Perlin noise 头部动画
        
        # Perlin noise 参数
        self.amplitude_x = 8.0
        self.amplitude_y = 5.0
        self.amplitude_z = 4.0
        self.speed = 0.3
        
        # 窗口设置
        self.setWindowTitle("Low Level Model Test")
        self.setFixedSize(self.display_width, self.display_height)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        
    def initializeGL(self):
        live2d.glInit()
        
        # 使用底层 Model 类而非 LAppModel
        self.model = live2d.Model()
        self.model.LoadModelJson(self.model_path)
        self.model.CreateRenderer()  # 必须手动创建渲染器
        self.model.Resize(self.display_width, self.display_height)
        
        # 设置自动呼吸和眨眼的初始状态
        self.model.SetAutoBreath(self.enable_breath)
        self.model.SetAutoBlink(self.enable_blink)
        
        self.canvas = Canvas()
        self.canvas.SetSize(self.display_width, self.display_height)
        
        # 打印模型参数
        print("\n=== 模型参数列表 ===")
        param_ids = self.model.GetParameterIds()
        for i, pid in enumerate(param_ids[:20]):  # 只打印前 20 个
            print(f"  {i}: {pid}")
        if len(param_ids) > 20:
            print(f"  ... 还有 {len(param_ids) - 20} 个参数")
        
        # 打印 Motion 组
        print("\n=== Motion 组 ===")
        try:
            motions = self.model.GetMotions()
            for group, motion_list in motions.items():
                print(f"  {group}: {len(motion_list)} 个动作")
        except Exception as e:
            print(f"  无法获取 Motion: {e}")
        
        self.startTimer(int(1000 / self.fps))
        print("\n模型加载完成")
    
    def timerEvent(self, event):
        if not self.model:
            return
        
        current_time = time.time()
        delta_time = current_time - self.last_time
        self.last_time = current_time
        
        # === 选择性更新 ===
        
        # 1. Motion 更新（idle 动作来源！）
        if self.enable_motion:
            self.model.UpdateMotion(delta_time)
        
        # 2. 拖拽/视线追踪
        if self.enable_drag:
            self.model.UpdateDrag(delta_time)
        
        # 3. 呼吸
        if self.enable_breath:
            self.model.UpdateBreath(delta_time)
        
        # 4. 眨眼
        if self.enable_blink:
            self.model.UpdateBlink(delta_time)
        
        # 5. 物理（头发、衣服等）
        if self.enable_physics:
            self.model.UpdatePhysics(delta_time)
        
        # 6. Perlin noise 头部动画
        if self.enable_perlin:
            t = (current_time - self.start_time) * self.speed
            try:
                from noise import pnoise1
                angle_x = pnoise1(t) * self.amplitude_x
                angle_y = pnoise1(t + 100) * self.amplitude_y
                angle_z = pnoise1(t + 200) * self.amplitude_z
                
                # 使用底层 API 设置参数
                self.model.SetParameterValueById("ParamAngleX", angle_x, 1.0)
                self.model.SetParameterValueById("ParamAngleY", angle_y, 1.0)
                self.model.SetParameterValueById("ParamAngleZ", angle_z, 1.0)
            except ImportError:
                pass
        
        self.update()
    
    def on_draw(self):
        live2d.clearBuffer()
        self.model.Draw()
    
    def paintGL(self):
        GL.glClearColor(0.0, 0.0, 0.0, 0.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        
        if self.model and self.canvas:
            # 注意：底层 Model 的 Update 需要传入 deltaTime
            # 但我们已经在 timerEvent 中手动调用各个 Update 了
            # 这里不需要再调用 self.model.Update()
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
    
    def __init__(self, controller: LowLevelModelController):
        super().__init__()
        self.controller = controller
        
        self.setWindowTitle("Low Level Control")
        self.setFixedSize(350, 500)
        
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("=== Update 开关 ==="))
        
        # Motion 开关
        self.cb_motion = QCheckBox("Motion (idle 动作) - 关闭消除自发转头")
        self.cb_motion.setChecked(controller.enable_motion)
        self.cb_motion.toggled.connect(lambda v: setattr(controller, 'enable_motion', v))
        layout.addWidget(self.cb_motion)
        
        # Drag 开关
        self.cb_drag = QCheckBox("Drag (原生视线追踪)")
        self.cb_drag.setChecked(controller.enable_drag)
        self.cb_drag.toggled.connect(lambda v: setattr(controller, 'enable_drag', v))
        layout.addWidget(self.cb_drag)
        
        # Breath 开关
        self.cb_breath = QCheckBox("Breath (呼吸)")
        self.cb_breath.setChecked(controller.enable_breath)
        self.cb_breath.toggled.connect(self.toggle_breath)
        layout.addWidget(self.cb_breath)
        
        # Blink 开关
        self.cb_blink = QCheckBox("Blink (眨眼)")
        self.cb_blink.setChecked(controller.enable_blink)
        self.cb_blink.toggled.connect(self.toggle_blink)
        layout.addWidget(self.cb_blink)
        
        # Physics 开关
        self.cb_physics = QCheckBox("Physics (物理模拟)")
        self.cb_physics.setChecked(controller.enable_physics)
        self.cb_physics.toggled.connect(lambda v: setattr(controller, 'enable_physics', v))
        layout.addWidget(self.cb_physics)
        
        layout.addWidget(QLabel("\n=== 自定义动画 ==="))
        
        # Perlin 开关
        self.cb_perlin = QCheckBox("Perlin Noise 头部动画")
        self.cb_perlin.setChecked(controller.enable_perlin)
        self.cb_perlin.toggled.connect(lambda v: setattr(controller, 'enable_perlin', v))
        layout.addWidget(self.cb_perlin)
        
        # 幅度滑块
        layout.addWidget(QLabel("幅度 X:"))
        slider_x = QSlider(Qt.Orientation.Horizontal)
        slider_x.setRange(0, 30)
        slider_x.setValue(int(controller.amplitude_x))
        slider_x.valueChanged.connect(lambda v: setattr(controller, 'amplitude_x', float(v)))
        layout.addWidget(slider_x)
        
        layout.addWidget(QLabel("幅度 Y:"))
        slider_y = QSlider(Qt.Orientation.Horizontal)
        slider_y.setRange(0, 30)
        slider_y.setValue(int(controller.amplitude_y))
        slider_y.valueChanged.connect(lambda v: setattr(controller, 'amplitude_y', float(v)))
        layout.addWidget(slider_y)
        
        layout.addWidget(QLabel("幅度 Z:"))
        slider_z = QSlider(Qt.Orientation.Horizontal)
        slider_z.setRange(0, 30)
        slider_z.setValue(int(controller.amplitude_z))
        slider_z.valueChanged.connect(lambda v: setattr(controller, 'amplitude_z', float(v)))
        layout.addWidget(slider_z)
        
        layout.addWidget(QLabel("速度:"))
        slider_speed = QSlider(Qt.Orientation.Horizontal)
        slider_speed.setRange(1, 20)
        slider_speed.setValue(int(controller.speed * 10))
        slider_speed.valueChanged.connect(lambda v: setattr(controller, 'speed', v / 10.0))
        layout.addWidget(slider_speed)
        
        # 退出
        btn_quit = QPushButton("退出")
        btn_quit.clicked.connect(QApplication.quit)
        layout.addWidget(btn_quit)
        
        self.setLayout(layout)
    
    def toggle_breath(self, v):
        self.controller.enable_breath = v
        if self.controller.model:
            self.controller.model.SetAutoBreath(v)
    
    def toggle_blink(self, v):
        self.controller.enable_blink = v
        if self.controller.model:
            self.controller.model.SetAutoBlink(v)


def main():
    print("\n" + "=" * 50)
    print("Low Level Model 测试")
    print("=" * 50)
    print("\n核心思路: 使用底层 Model 类，手动控制每个 Update 步骤")
    print("这样可以禁用 idle Motion，消除自发转头\n")
    
    live2d.init()
    
    app = QApplication(sys.argv)
    
    model_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "live2d_local",
        "models",
        "sakiko.model3.json"
    )
    
    print(f"加载模型: {model_path}")
    
    controller = LowLevelModelController(model_path)
    controller.show()
    controller.move(100, 100)
    
    panel = ControlPanel(controller)
    panel.show()
    panel.move(650, 100)
    
    print("\n使用说明:")
    print("1. 默认 Motion 是关闭的，观察是否还有自发转头")
    print("2. 勾选 'Perlin Noise' 开启自定义头部动画")
    print("3. 用滑块调整幅度和速度")
    print("4. 尝试开/关各个 Update 组件观察效果")
    print("\n" + "=" * 50 + "\n")
    
    app.exec()
    live2d.dispose()


if __name__ == "__main__":
    main()
