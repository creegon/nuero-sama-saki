# -*- coding: utf-8 -*-
"""
Vision Manager
整合屏幕截取 (ScreenCapture) 和视觉分析 (VisionAnalyzer) 功能
合并自原 vision/screenshot.py 和 vision/analyzer.py
"""

import base64
import io
import sys
import os
import time
import httpx
from typing import Optional, Tuple
from dataclasses import dataclass
from PIL import Image
import mss
import mss.tools
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


# ==========================================
# Screen Capture Logic
# ==========================================

@dataclass
class ScreenshotResult:
    """截屏结果"""
    base64_data: str       # base64 编码的图片数据
    width: int             # 图片宽度
    height: int            # 图片高度
    format: str = "jpeg"   # 图片格式


class ScreenCapture:
    """屏幕截取工具"""
    
    def __init__(
        self,
        max_size: int = 1024,      # 最大边长
        quality: int = 85,          # JPEG 质量
        format: str = "jpeg"        # 输出格式
    ):
        self.max_size = max_size
        self.quality = quality
        self.format = format
        self.sct = mss.mss()
    
    def _resize_image(self, img: Image.Image) -> Image.Image:
        """等比缩放图片到最大边长"""
        width, height = img.size
        
        if max(width, height) <= self.max_size:
            return img
        
        if width > height:
            new_width = self.max_size
            new_height = int(height * (self.max_size / width))
        else:
            new_height = self.max_size
            new_width = int(width * (self.max_size / height))
        
        return img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    def _image_to_base64(self, img: Image.Image) -> str:
        """将 PIL Image 转换为 base64 字符串"""
        buffer = io.BytesIO()
        
        # JPEG 不支持透明通道，需要转换
        if self.format.lower() == "jpeg" and img.mode in ("RGBA", "LA"):
            # 创建白色背景
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "RGBA":
                background.paste(img, mask=img.split()[3])
            else:
                background.paste(img)
            img = background
        elif self.format.lower() == "jpeg" and img.mode != "RGB":
            img = img.convert("RGB")
        
        img.save(buffer, format=self.format.upper(), quality=self.quality)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    
    def capture_full(self, monitor_index: int = 1) -> ScreenshotResult:
        """捕获整个屏幕"""
        monitor = self.sct.monitors[monitor_index]
        screenshot = self.sct.grab(monitor)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        img = self._resize_image(img)
        base64_data = self._image_to_base64(img)
        
        logger.debug(f"截屏完成: {img.size[0]}x{img.size[1]}, {len(base64_data)} bytes")
        
        return ScreenshotResult(
            base64_data=base64_data,
            width=img.size[0],
            height=img.size[1],
            format=self.format
        )
    
    def capture_region(self, left: int, top: int, width: int, height: int) -> ScreenshotResult:
        """捕获指定区域"""
        region = {"left": left, "top": top, "width": width, "height": height}
        screenshot = self.sct.grab(region)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        img = self._resize_image(img)
        base64_data = self._image_to_base64(img)
        
        return ScreenshotResult(
            base64_data=base64_data,
            width=img.size[0],
            height=img.size[1],
            format=self.format
        )
    
    def capture_active_window(self) -> Optional[ScreenshotResult]:
        """捕获当前活动窗口"""
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return self.capture_full()
            
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            left, top = rect.left, rect.top
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            
            if width <= 0 or height <= 0:
                return self.capture_full()
            
            return self.capture_region(left, top, width, height)
        except Exception as e:
            logger.warning(f"获取活动窗口失败: {e}，回退到全屏")
            return self.capture_full()
    
    def capture(self, mode: str = "full") -> ScreenshotResult:
        """统一截屏接口: mode="full"|"active"|"region" """
        if mode == "active":
            result = self.capture_active_window()
            return result if result else self.capture_full()
        return self.capture_full()


# 全局单例
_screen_capture: Optional[ScreenCapture] = None

def get_screen_capture() -> ScreenCapture:
    global _screen_capture
    if _screen_capture is None:
        _screen_capture = ScreenCapture(
            max_size=getattr(config, 'SCREENSHOT_MAX_SIZE', 1024),
            quality=getattr(config, 'SCREENSHOT_QUALITY', 85)
        )
    return _screen_capture


# ==========================================
# Vision Analyzer Logic
# ==========================================

class VisionAnalyzer:
    """视觉分析器 - 调用 LLM Vision API"""
    
    def __init__(
        self,
        api_base: str = None,
        api_key: str = None,
        model: str = None,
        timeout: float = 30.0
    ):
        self.api_base = (api_base or config.LLM_API_BASE).rstrip('/')
        self.api_key = api_key or config.LLM_API_KEY
        self.model = model or config.LLM_MODEL
        self.timeout = timeout
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        self.screen_capture = get_screen_capture()
    
    async def analyze_image(
        self,
        image_base64: str,
        prompt: str = "描述这张图片的内容，用简短的一两句话。",
        image_format: str = "jpeg"
    ) -> str:
        """分析图片内容"""
        url = f"{self.api_base}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{image_format};base64,{image_base64}"
                        }
                    }
                ]
            }],
            "max_tokens": 200,
            "temperature": 0.7
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=self.headers)
                if response.status_code != 200:
                    logger.error(f"Vision API 错误: {response.status_code} - {response.text[:200]}")
                    return f"[分析失败: {response.status_code}]"
                
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                return content.strip()
        except Exception as e:
            logger.error(f"Vision API 错误: {e}")
            return f"[分析错误: {e}]"
    
    async def analyze_screen(self, mode: str = "full", prompt: str = None) -> str:
        """截屏并分析"""
        if prompt is None:
            prompt = (
                "你在看一个人的电脑屏幕。"
                "用一句话简单描述你看到了什么（比如在玩什么游戏、在看什么网页、在做什么）。"
                "不要太详细，就像朋友随口说的那样。"
            )
        
        try:
            screenshot = self.screen_capture.capture(mode)
        except Exception as e:
            logger.error(f"截屏失败: {e}")
            return "[截屏失败]"
        
        logger.debug(f"分析屏幕: {screenshot.width}x{screenshot.height}")
        return await self.analyze_image(screenshot.base64_data, prompt, screenshot.format)

    async def describe_for_chat(self, context: str = "") -> str:
        """为聊天场景分析屏幕"""
        prompt = f"""你在看主人的电脑屏幕。
{f'主人刚才说: {context}' if context else ''}

请**详细**描述你看到的内容，包括:
- 正在使用的应用/网页名称
- 屏幕上显示的主要内容（如代码、视频、游戏场景）
- 任何有趣或值得注意的细节

要求:
1. 限制在 100 字以内
2. 用客观描述，不要角色扮演
3. 只输出描述内容，不要加标签
"""
        return await self.analyze_screen(mode="full", prompt=prompt)


# 全局单例
_vision_analyzer: Optional[VisionAnalyzer] = None

def get_vision_analyzer() -> VisionAnalyzer:
    global _vision_analyzer
    if _vision_analyzer is None:
        _vision_analyzer = VisionAnalyzer()
    return _vision_analyzer


if __name__ == "__main__":
    import asyncio
    async def test():
        print("Vision Manager Test")
        analyzer = get_vision_analyzer()
        print("[1] Analyzing Screen...")
        start = time.time()
        res = await analyzer.analyze_screen()
        print(f"Result: {res} ({time.time()-start:.2f}s)")
    asyncio.run(test())
