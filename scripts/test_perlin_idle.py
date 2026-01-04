# -*- coding: utf-8 -*-
"""
测试 Perlin Noise Idle 动画

目的：验证 live2d-py 的 LAppModel.SetParameterValue() 对 AngleX/Y/Z 参数的实际效果
注意：这是独立测试脚本，不影响主程序

测试步骤：
1. 先用简单的正弦波测试参数是否有效
2. 如果有效，再换成 Perlin noise
3. 观察是否与 AutoBreath/AutoBlink 冲突

使用方法：
    python scripts/test_perlin_idle.py
"""

import sys
import os
import math
import time

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QOpenGLWidget, QPushButton, QVBoxLayout, QWidget, QLabel, QSlider, QHBoxLayout
import OpenGL.GL as GL

import live2d.v3 as live2d
from live2d.utils.canvas import Canvas


class TestIdleController(QOpenGLWidget):
    """测试 Idle 动画的独立控制器"""
    
    def __init__(self, model_path: str):
        super().__init__()
        
        self.model_path = model_path
        self.display_width = 500
        self.display_height = 600
        self.fps = 60
        
        self.model = None
        self.canvas = None
        
        # === 测试状态 ===
        self.test_mode = "none"  # none, sine, perlin
        self.start_time = time.time()
        
        # 参数设置
        self.amplitude_x = 15.0  # 左右摇头幅度
        self.amplitude_y = 10.0  # 上下点头幅度  
        self.amplitude_z = 8.0   # 歪头幅度
        self.speed = 0.5         # 运动速度
        
        # 当前值 (用于显示)
        self.current_angle_x = 0.0
        self.current_angle_y = 0.0
        self.current_angle_z = 0.0
        
        # 窗口设置
        self.setWindowTitle("Perlin Idle 测试")
        self.setFixedSize(self.display_width, self.display_height)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        
    def initializeGL(self):
        live2d.glInit()
        
        self.model = live2d.LAppModel()
        self.model.LoadModelJson(self.model_path)
        self.model.Resize(self.display_width, self.display_height)
        
        # 启用官方自动动画
        self.model.SetAutoBlinkEnable(True)
        self.model.SetAutoBreathEnable(True)
        
        self.canvas = Canvas()
        self.canvas.SetSize(self.display_width, self.display_height)
        
        # 打印可用参数 (调试用)
        print("\n=== 模型参数检查 ===")
        # 尝试获取参数列表（如果 API 支持的话）
        
        self.startTimer(int(1000 / self.fps))
        print("模型加载完成，定时器已启动")
    
    def timerEvent(self, event):
        if not self.model:
            return
        
        t = (time.time() - self.start_time) * self.speed
        
        if self.test_mode == "sine":
            # 使用正弦波测试（最简单的周期运动）
            self.current_angle_x = math.sin(t) * self.amplitude_x
            self.current_angle_y = math.sin(t * 0.7 + 1) * self.amplitude_y  # 不同频率和相位
            self.current_angle_z = math.sin(t * 0.5 + 2) * self.amplitude_z
            
            # 尝试设置参数
            self.model.SetParameterValue("ParamAngleX", self.current_angle_x)
            self.model.SetParameterValue("ParamAngleY", self.current_angle_y)
            self.model.SetParameterValue("ParamAngleZ", self.current_angle_z)
            
        elif self.test_mode == "perlin":
            # Perlin noise 测试
            try:
                from noise import pnoise1
                self.current_angle_x = pnoise1(t) * self.amplitude_x
                self.current_angle_y = pnoise1(t + 100) * self.amplitude_y
                self.current_angle_z = pnoise1(t + 200) * self.amplitude_z
                
                self.model.SetParameterValue("ParamAngleX", self.current_angle_x)
                self.model.SetParameterValue("ParamAngleY", self.current_angle_y)
                self.model.SetParameterValue("ParamAngleZ", self.current_angle_z)
            except ImportError:
                print("需要安装 noise 库: pip install noise")
                self.test_mode = "none"
        
        self.update()
    
    def on_draw(self):
        live2d.clearBuffer()
        self.model.Draw()
    
    def paintGL(self):
        GL.glClearColor(0.0, 0.0, 0.0, 0.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        
        if self.model and self.canvas:
            self.model.Update()
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
    
    def __init__(self, controller: TestIdleController):
        super().__init__()
        self.controller = controller
        
        self.setWindowTitle("Idle 测试控制面板")
        self.setFixedSize(300, 400)
        
        layout = QVBoxLayout()
        
        # 状态显示
        self.status_label = QLabel("模式: 无")
        layout.addWidget(self.status_label)
        
        self.value_label = QLabel("X: 0.0  Y: 0.0  Z: 0.0")
        layout.addWidget(self.value_label)
        
        # 模式切换按钮
        btn_none = QPushButton("停止 (恢复默认)")
        btn_none.clicked.connect(lambda: self.set_mode("none"))
        layout.addWidget(btn_none)
        
        btn_sine = QPushButton("正弦波测试")
        btn_sine.clicked.connect(lambda: self.set_mode("sine"))
        layout.addWidget(btn_sine)
        
        btn_perlin = QPushButton("Perlin Noise 测试")
        btn_perlin.clicked.connect(lambda: self.set_mode("perlin"))
        layout.addWidget(btn_perlin)
        
        # 幅度控制
        layout.addWidget(QLabel("\n幅度控制:"))
        
        # X 幅度
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("X:"))
        self.slider_x = QSlider(Qt.Orientation.Horizontal)
        self.slider_x.setRange(0, 30)
        self.slider_x.setValue(15)
        self.slider_x.valueChanged.connect(lambda v: setattr(self.controller, 'amplitude_x', float(v)))
        h1.addWidget(self.slider_x)
        self.label_x = QLabel("15")
        self.slider_x.valueChanged.connect(lambda v: self.label_x.setText(str(v)))
        h1.addWidget(self.label_x)
        layout.addLayout(h1)
        
        # Y 幅度
        h2 = QHBoxLayout()
        h2.addWidget(QLabel("Y:"))
        self.slider_y = QSlider(Qt.Orientation.Horizontal)
        self.slider_y.setRange(0, 30)
        self.slider_y.setValue(10)
        self.slider_y.valueChanged.connect(lambda v: setattr(self.controller, 'amplitude_y', float(v)))
        h2.addWidget(self.slider_y)
        self.label_y = QLabel("10")
        self.slider_y.valueChanged.connect(lambda v: self.label_y.setText(str(v)))
        h2.addWidget(self.label_y)
        layout.addLayout(h2)
        
        # Z 幅度
        h3 = QHBoxLayout()
        h3.addWidget(QLabel("Z:"))
        self.slider_z = QSlider(Qt.Orientation.Horizontal)
        self.slider_z.setRange(0, 30)
        self.slider_z.setValue(8)
        self.slider_z.valueChanged.connect(lambda v: setattr(self.controller, 'amplitude_z', float(v)))
        h3.addWidget(self.slider_z)
        self.label_z = QLabel("8")
        self.slider_z.valueChanged.connect(lambda v: self.label_z.setText(str(v)))
        h3.addWidget(self.label_z)
        layout.addLayout(h3)
        
        # 速度控制
        h4 = QHBoxLayout()
        h4.addWidget(QLabel("速度:"))
        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(1, 20)
        self.slider_speed.setValue(5)
        self.slider_speed.valueChanged.connect(lambda v: setattr(self.controller, 'speed', v / 10.0))
        h4.addWidget(self.slider_speed)
        self.label_speed = QLabel("0.5")
        self.slider_speed.valueChanged.connect(lambda v: self.label_speed.setText(f"{v/10:.1f}"))
        h4.addWidget(self.label_speed)
        layout.addLayout(h4)
        
        # 退出按钮
        btn_quit = QPushButton("退出")
        btn_quit.clicked.connect(QApplication.quit)
        layout.addWidget(btn_quit)
        
        self.setLayout(layout)
        
        # 定时更新显示
        from PyQt5.QtCore import QTimer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_display)
        self.timer.start(100)
    
    def set_mode(self, mode):
        self.controller.test_mode = mode
        self.status_label.setText(f"模式: {mode}")
        print(f"切换到模式: {mode}")
    
    def update_display(self):
        x = self.controller.current_angle_x
        y = self.controller.current_angle_y
        z = self.controller.current_angle_z
        self.value_label.setText(f"X: {x:.1f}  Y: {y:.1f}  Z: {z:.1f}")


def main():
    print("\n" + "=" * 50)
    print("Perlin Noise Idle 动画测试")
    print("=" * 50)
    print("\n目的: 验证 SetParameterValue 对 AngleX/Y/Z 的效果")
    print("注意: 这是独立测试，不影响主程序\n")
    
    # 检查 noise 库
    try:
        import noise
        print("[OK] noise 库已安装")
    except ImportError:
        print("[X] noise 库未安装，Perlin 模式将不可用")
        print("  安装命令: pip install noise")
    
    live2d.init()
    
    app = QApplication(sys.argv)
    
    model_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "live2d_local",
        "models",
        "sakiko.model3.json"
    )
    
    print(f"\n加载模型: {model_path}")
    
    # 创建控制器和控制面板
    controller = TestIdleController(model_path)
    controller.show()
    controller.move(100, 100)
    
    panel = ControlPanel(controller)
    panel.show()
    panel.move(650, 100)
    
    print("\n使用说明:")
    print("1. 点击 '正弦波测试' 观察模型是否随正弦波摆动")
    print("2. 如果有效，点击 'Perlin Noise 测试'")
    print("3. 用滑块调整幅度和速度")
    print("4. 观察是否与眨眼/呼吸冲突")
    print("\n" + "=" * 50 + "\n")
    
    app.exec()
    live2d.dispose()


if __name__ == "__main__":
    main()
