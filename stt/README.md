# STT 模块 (语音识别)

语音转文字模块，支持多引擎和 Voice-to-LLM 模式。

---

## 文件结构

```
stt/
├── __init__.py
├── factory.py          # 引擎工厂
├── audio_capture.py    # 音频采集
├── vad.py              # 语音活动检测 (Silero VAD)
├── post_processor.py   # 后处理（语气词移除、纠错）
├── hotwords.py         # 热词增强
├── stt_client.py       # STT 客户端接口
└── engines/
    ├── paraformer.py   # FunASR Paraformer 引擎
    └── fireredasr.py   # FireRedASR 引擎
```

---

## 工作流程

```
麦克风输入
    ↓
AudioCapture (采集音频块)
    ↓
SileroVAD (检测语音活动)
    ↓
┌──────────────────────────────────────────────┐
│  Voice-to-LLM 模式 (推荐)                     │
│  config.VOICE_TO_LLM_ENABLED = True          │
│                                               │
│  音频直接发送给 LLM，跳过 STT                  │
│  优点：省显存(~2GB)、端到端理解               │
└──────────────────────────────────────────────┘
        或
┌──────────────────────────────────────────────┐
│  传统 STT 模式                                │
│  config.VOICE_TO_LLM_ENABLED = False         │
│                                               │
│  音频 → STT 引擎 → 文本                       │
│  ├── Paraformer：速度快 (~0.2s)              │
│  └── FireRedASR：准确率高 (~0.5s)            │
└──────────────────────────────────────────────┘
    ↓
PostProcessor (后处理)
    ↓
文本输出
```

---

## 核心组件

### 1. 音频采集 (`audio_capture.py`)

使用 `sounddevice` 采集麦克风输入。

**配置**：

```python
AUDIO_SAMPLE_RATE = 16000  # 16kHz
AUDIO_CHANNELS = 1         # 单声道
AUDIO_CHUNK_MS = 32        # 32ms 块大小
```

---

### 2. 语音活动检测 (`vad.py`)

使用 Silero VAD 检测语音开始和结束。

**配置**：

```python
VAD_THRESHOLD = 0.4        # 语音概率阈值
VAD_MIN_SPEECH_MS = 150    # 最小语音时长
VAD_MIN_SILENCE_MS = 500   # 结束静音时长
VAD_SPEECH_PAD_MS = 400    # 语音前后填充
```

**关键方法**：

| 方法              | 功能                     |
| ----------------- | ------------------------ |
| `process_chunk()` | 处理音频块，返回语音状态 |
| `get_speech()`    | 获取完整的语音段         |
| `reset()`         | 重置状态                 |

---

### 3. STT 引擎 (`engines/`)

**Paraformer** (`paraformer.py`)：

- 基于 FunASR
- 速度快 (~0.2s)
- 适合实时场景

**FireRedASR** (`fireredasr.py`)：

- 基于 FireRedASR-AED-L
- 准确率高
- 速度稍慢 (~0.5s)

**选择引擎**：

```python
# config.py
STT_ENGINE = "fireredasr"  # 或 "paraformer"
```

---

### 4. 后处理 (`post_processor.py`)

对 STT 输出进行纠错和清理。

**功能**：

| 功能       | 说明                       |
| ---------- | -------------------------- |
| 语气词移除 | 删除 "嗯"、"啊"、"那个" 等 |
| 同音字纠错 | 配合热词，修复常见错误     |
| 自定义纠错 | 用户可配置的替换规则       |

**自定义纠错**（`config.py`）：

```python
STT_CUSTOM_CORRECTIONS = {
    "小象": "小祥",
    "晓祥": "小祥",
}
```

---

### 5. 热词增强 (`hotwords.py`)

增强特定词汇的识别准确率。

```python
HOTWORDS = [
    "小祥", "丰川祥子", "Ave Mujica",
    "本神明", "傲娇"
]
```

---

## Voice-to-LLM 模式

**推荐使用**。直接将音频发送给 LLM，跳过 STT。

**优点**：

- 节省 ~2GB GPU 显存
- 端到端理解，无 STT 错误传播
- 自动多语言支持

**启用**：

```python
# config.py
VOICE_TO_LLM_ENABLED = True
```

**工作原理**：

```
音频 → base64 编码 → LLMClient.chat_with_audio_stream()
                            ↓
                     Gemini 直接理解语音
                            ↓
                        文本响应
```

---

## 使用示例

```python
from stt import get_transcriber
from stt.vad import SileroVAD
from stt.audio_capture import AudioCapture

# VAD
vad = SileroVAD()

# 音频采集
capture = AudioCapture()

# STT（仅当 Voice-to-LLM 禁用时需要）
if not config.VOICE_TO_LLM_ENABLED:
    transcriber = get_transcriber()
    transcriber.load_model()
```

---

## 配置汇总

| 配置项                 | 默认值         | 说明                   |
| ---------------------- | -------------- | ---------------------- |
| `VOICE_TO_LLM_ENABLED` | `True`         | 启用 Voice-to-LLM 模式 |
| `STT_ENGINE`           | `"fireredasr"` | STT 引擎选择           |
| `AUDIO_SAMPLE_RATE`    | `16000`        | 采样率 (Hz)            |
| `VAD_THRESHOLD`        | `0.4`          | VAD 语音概率阈值       |
| `STT_POST_PROCESS`     | `True`         | 启用后处理             |
