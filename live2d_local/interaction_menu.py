# -*- coding: utf-8 -*-
"""
Live2D 交互菜单 UI

美观的弹出菜单，包含：
- 文字输入框
- 退出按钮
- 毛玻璃效果
"""

from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QPoint
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QPushButton, QLabel, QGraphicsOpacityEffect
)
from PyQt5.QtGui import QFont, QPainter, QColor, QBrush, QPen, QPainterPath


class InteractionMenu(QWidget):
    """交互菜单 - 右键点击弹出"""
    
    # Signals
    text_submitted = pyqtSignal(str)  # 文字输入信号
    exit_requested = pyqtSignal()      # 退出请求信号
    menu_closed = pyqtSignal()         # 菜单关闭信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._setup_window()
        self._setup_ui()
        self._setup_animations()
        
    def _setup_window(self):
        """设置窗口属性"""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.Popup  # 点击外部自动关闭
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(280, 160)
        
    def _setup_ui(self):
        """设置 UI 组件"""
        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # 标题
        title = QLabel("💬 和小祥互动")
        title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 输入区域
        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)
        
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("输入想说的话...")
        self.text_input.setFont(QFont("Microsoft YaHei", 10))
        self.text_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.15);
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 8px;
                padding: 8px 12px;
                color: #ffffff;
            }
            QLineEdit:focus {
                border: 1px solid rgba(255, 255, 255, 0.6);
                background-color: rgba(255, 255, 255, 0.2);
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.5);
            }
        """)
        self.text_input.returnPressed.connect(self._on_submit)
        input_layout.addWidget(self.text_input)
        
        send_btn = QPushButton("发送")
        send_btn.setFont(QFont("Microsoft YaHei", 9))
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(100, 180, 255, 0.8);
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(120, 200, 255, 0.9);
            }
            QPushButton:pressed {
                background-color: rgba(80, 160, 235, 0.9);
            }
        """)
        send_btn.clicked.connect(self._on_submit)
        input_layout.addWidget(send_btn)
        
        layout.addLayout(input_layout)
        
        # 退出按钮
        exit_btn = QPushButton("🚪 退出程序")
        exit_btn.setFont(QFont("Microsoft YaHei", 10))
        exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        exit_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 100, 100, 0.7);
                border: none;
                border-radius: 8px;
                padding: 10px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: rgba(255, 120, 120, 0.85);
            }
            QPushButton:pressed {
                background-color: rgba(235, 80, 80, 0.9);
            }
        """)
        exit_btn.clicked.connect(self._on_exit)
        layout.addWidget(exit_btn)
        
        # 透明度效果（用于动画）
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0)
        self.setGraphicsEffect(self.opacity_effect)
        
    def _setup_animations(self):
        """设置动画"""
        # 透明度动画
        self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_anim.setDuration(150)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
    def paintEvent(self, event):
        """绘制毛玻璃背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 毛玻璃效果背景
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 16, 16)
        
        # 半透明深色背景
        painter.fillPath(path, QBrush(QColor(30, 30, 40, 220)))
        
        # 边框
        painter.setPen(QPen(QColor(255, 255, 255, 50), 1))
        painter.drawPath(path)
        
    def show_at(self, pos: QPoint):
        """在指定位置显示菜单"""
        # 调整位置，确保菜单不超出屏幕
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            screen_rect = screen.availableGeometry()
            x = pos.x()
            y = pos.y()
            
            # 右边界检查
            if x + self.width() > screen_rect.right():
                x = pos.x() - self.width() - 20
            
            # 下边界检查
            if y + self.height() > screen_rect.bottom():
                y = screen_rect.bottom() - self.height() - 20
            
            self.move(x, y)
        else:
            self.move(pos)
        
        # 显示并播放动画
        self.show()
        self.fade_anim.setStartValue(0)
        self.fade_anim.setEndValue(1)
        self.fade_anim.start()
        
        # 聚焦输入框
        self.text_input.setFocus()
        
    def hide_menu(self):
        """隐藏菜单（带动画）"""
        self.fade_anim.setStartValue(1)
        self.fade_anim.setEndValue(0)
        self.fade_anim.finished.connect(self._on_fade_out_finished)
        self.fade_anim.start()
        
    def _on_fade_out_finished(self):
        """淡出动画完成"""
        self.fade_anim.finished.disconnect(self._on_fade_out_finished)
        self.hide()
        self.menu_closed.emit()
        
    def _on_submit(self):
        """提交文字"""
        text = self.text_input.text().strip()
        if text:
            self.text_submitted.emit(text)
            self.text_input.clear()
            self.hide_menu()
            
    def _on_exit(self):
        """退出程序"""
        self.exit_requested.emit()
        self.hide_menu()
        
    def hideEvent(self, event):
        """窗口隐藏事件"""
        self.text_input.clear()
        super().hideEvent(event)


# 测试代码
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    menu = InteractionMenu()
    menu.text_submitted.connect(lambda t: print(f"提交: {t}"))
    menu.exit_requested.connect(lambda: print("退出请求"))
    
    # 显示在屏幕中央
    screen = app.primaryScreen().geometry()
    menu.show_at(QPoint(screen.width() // 2, screen.height() // 2))
    
    sys.exit(app.exec())
