# Vision 模块 (视觉功能)

屏幕截图和视觉分析模块，支持截屏和 LLM 图像理解。

---

## 文件结构

```
vision/
├── __init__.py   # 公共接口
└── core.py       # 核心实现
```

---

## 核心组件

### 1. ScreenCapture (截屏)

截取当前屏幕，返回 base64 编码的图像数据。

**关键方法**：

| 方法            | 功能                            |
| --------------- | ------------------------------- |
| `capture(mode)` | 截屏，mode 可选 "full"/"region" |
| `to_base64()`   | 将截屏转为 base64 编码          |

**配置**（`config.py`）：

```python
VISION_ENABLED = True
SCREENSHOT_MAX_SIZE = 1024   # 最大边长 (像素)
SCREENSHOT_QUALITY = 85      # JPEG 质量
```

**返回格式**：

```python
class ScreenshotResult:
    width: int              # 图像宽度
    height: int             # 图像高度
    format: str             # "jpeg" 或 "png"
    base64_data: str        # base64 编码的图像数据
```

---

### 2. VisionAnalyzer (视觉分析)

将图像发送给 LLM Vision API 进行分析。

**关键方法**：

| 方法               | 功能                   |
| ------------------ | ---------------------- |
| `analyze_image()`  | 分析 base64 图像       |
| `analyze_screen()` | 截屏并分析（组合方法） |

**使用场景**：

1. **screenshot 工具**：用户要求小祥"看看屏幕"
2. **静默屏幕观察器**：后台定期观察用户活动

---

## 使用示例

```python
from vision import get_screen_capture, get_vision_analyzer

# 截屏
capture = get_screen_capture()
screenshot = capture.capture(mode="full")
print(f"截屏: {screenshot.width}x{screenshot.height}")

# 发送给 LLM 分析
analyzer = get_vision_analyzer(llm_client)
result = await analyzer.analyze_screen("描述这个屏幕上的内容")
print(result)
```

---

## 公共接口 (`__init__.py`)

```python
from vision import (
    get_screen_capture,    # 获取截屏器单例
    get_vision_analyzer,   # 获取视觉分析器单例
)
```

---

## 与其他模块的关系

```
vision/
 │
 ├──→ tools/screenshot_tool.py  截屏工具调用 get_screen_capture()
 │
 ├──→ core/screen_observer.py   静默观察器调用视觉分析
 │
 └──→ llm/client.py             发送图像给 LLM Vision API
```

---

## 静默屏幕观察器

`core/screen_observer.py` 使用本模块定期截屏，让后台小祥分析用户活动。

**工作流程**：

```
每 2 分钟触发
    ↓
get_screen_capture().capture()
    ↓
构建分析 prompt
    ↓
LLM Vision API 分析
    ↓
提取有用信息存入知识库
```

**配置**：

```python
SCREEN_OBSERVER_ENABLED = True    # 启用静默观察
SCREEN_OBSERVER_INTERVAL = 120    # 观察间隔 (秒)
```

---

## 图像压缩

为减少 API 传输量和成本，截图会进行压缩：

1. **尺寸限制**：最大边长 1024 像素
2. **JPEG 压缩**：质量 85%
3. **Base64 编码**：便于 HTTP 传输
