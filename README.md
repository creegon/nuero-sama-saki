# NeuroPet - AI 桌宠

基于 Live2D + LLM 的智能桌面宠物，拥有完整的记忆系统和语音交互能力。

---

## 快速开始

```batch
# 安装依赖
setup.bat

# 启动（正常模式）
start.bat

# 启动（调试模式，详细日志）
start_debug.bat
```

---

## 项目架构

```
neruo/
├── main.py              # 程序入口
├── config.py            # 全局配置
│
├── core/                # 🧠 核心业务逻辑
│   ├── pet.py           # 主控制器
│   ├── response_handler.py  # 响应处理
│   ├── proactive_chat.py    # 主动聊天/追问
│   ├── knowledge_monitor.py # 后台知识管理
│   └── ...
│
├── llm/                 # 💬 LLM 交互
│   ├── client.py        # API 客户端
│   ├── character_prompt.py  # 角色设定
│   └── prompt_builder.py    # Prompt 构建
│
├── stt/                 # 🎤 语音识别
│   ├── vad.py           # 语音活动检测
│   ├── audio_capture.py # 音频采集
│   └── engines/         # STT 引擎
│
├── tts/                 # 🔊 语音合成
│   ├── voxcpm_engine.py # VoxCPM TTS
│   └── player.py        # 音频播放
│
├── tools/               # 🔧 工具系统
│   ├── registry.py      # 工具注册
│   ├── executor.py      # 工具执行
│   └── *_tool.py        # 各类工具
│
├── knowledge/           # 📚 记忆系统
│   ├── core.py          # 知识库核心
│   └── memory_manager.py # 记忆管理
│
├── vision/              # 👁️ 视觉功能
│   └── core.py          # 截屏/图像分析
│
└── live2d_local/        # 🎭 Live2D 渲染
    ├── controller.py    # 窗口控制
    └── models/          # Live2D 模型
```

---

## 模块导航

根据需要查找的内容，参考以下指南：

### 🎯 我想了解...

| 内容                      | 查看                                             |
| ------------------------- | ------------------------------------------------ |
| **完整架构和设计原则**    | [core/README.md](core/README.md)                 |
| **三层记忆体系**          | [knowledge/README.md](knowledge/README.md)       |
| **角色设定和 Prompt**     | [llm/README.md](llm/README.md)                   |
| **语音识别流程**          | [stt/README.md](stt/README.md)                   |
| **TTS 语音合成**          | [tts/README.md](tts/README.md)                   |
| **工具系统（截屏/搜索）** | [tools/README.md](tools/README.md)               |
| **视觉功能**              | [vision/README.md](vision/README.md)             |
| **Live2D 交互**           | [live2d_local/README.md](live2d_local/README.md) |

---

### 🔧 我想修改...

| 需求                 | 修改文件                       |
| -------------------- | ------------------------------ |
| **添加新工具**       | `tools/` + `tools/registry.py` |
| **修改角色人设**     | `llm/character_prompt.py`      |
| **调整记忆策略**     | `core/knowledge_monitor.py`    |
| **增加情绪标签**     | `llm/character_prompt.py`      |
| **修改 TTS 参数**    | `config.py` (VOXCPM\_\*)       |
| **修改 Live2D 表情** | `live2d_local/controller.py`   |

---

## 核心工作流程

```
用户语音/文字输入
    ↓
┌─────────────────────────────────────────────────┐
│  Voice-to-LLM 模式（推荐）                       │
│  音频直接发送给 LLM，跳过 STT                    │
└─────────────────────────┬───────────────────────┘
                          或
┌─────────────────────────────────────────────────┐
│  传统 STT 模式                                   │
│  音频 → VAD → STT → 文本                        │
└─────────────────────────┬───────────────────────┘
                          ↓
             PromptBuilder 构建消息
             (角色设定 + 记忆 + 对话历史)
                          ↓
             LLMClient.chat_stream()
                          ↓
             StreamParser 解析流式输出
             (情绪标签 + 工具调用)
                          ↓
         ┌────────────────┴────────────────┐
         ↓                                 ↓
   有工具调用                         无工具调用
   ToolExecutor 执行                  直接生成语音
   结果返回给 LLM                          ↓
         ↓                            TTS 合成
   继续生成回复                            ↓
         ↓                          AudioPlayer 播放
        ...                                ↓
                                    Live2D 表情驱动
```

---

## 后台系统

### 1. 后台小祥 (知识监控)

每轮对话后，后台小祥分析对话内容，管理记忆：

- `[ADD]` 添加新记忆
- `[UPDATE]` 更新旧记忆
- `[BOOST]` 增加重要性
- `[DELETE]` 删除错误记忆

详见 [knowledge/README.md](knowledge/README.md)

### 2. 主动聊天

小祥会在用户空闲时主动说话或追问。

详见 [core/README.md](core/README.md)

### 3. 静默屏幕观察

后台定期截屏，分析用户活动，存入知识库。

配置：`SCREEN_OBSERVER_ENABLED`、`SCREEN_OBSERVER_INTERVAL`

---

## 关键配置

编辑 `config.py` 修改以下配置：

### LLM

```python
LLM_API_BASE = "http://localhost:8045/v1"
LLM_MODEL = "gemini-3-flash"
```

### 语音

```python
VOICE_TO_LLM_ENABLED = True  # 推荐开启，省显存
STT_ENGINE = "fireredasr"     # 或 "paraformer"
```

### TTS

```python
VOXCPM_CFG_VALUE = 3.0        # CFG 值
VOXCPM_INFERENCE_STEPS = 12   # 推理步数
```

### 主动聊天

```python
PROACTIVE_CHAT_ENABLED = True
PROACTIVE_MIN_IDLE_TIME = 10  # 空闲多久后触发
```

### 记忆

```python
MEMORY_INJECTION_COUNT = 5    # 每轮注入的记忆数
MEMORY_DECAY_DAYS = 7         # 超过多少天开始衰减
```

---

## 知识库管理

### 图形界面（推荐）

```batch
.\venv\Scripts\python.exe scripts\manage_knowledge_gui.py
```

自动打开浏览器访问 `http://127.0.0.1:7861`，支持：

- 📋 表格浏览 (显示类型、重要性、来源、创建时间、访问次数)
- 🔍 查看完整 metadata (输入 ID 查看所有属性)
- 🔍 语义搜索
- ✅ 批量勾选删除 / 按 ID 删除
- ➕ 添加新记忆 (支持上下文)
- ✏️ 更新记忆内容
- 💾 导出 JSON (完整属性)

### 命令行版本

```batch
.\venv\Scripts\python.exe scripts\manage_knowledge.py
```

---

## 常见问题排查

### 启动报错

1. **ModuleNotFoundError**：运行 `setup.bat` 安装依赖
2. **CUDA out of memory**：启用 `VOICE_TO_LLM_ENABLED = True` 省显存
3. **LLM 连接失败**：检查 `LLM_API_BASE` 配置

### 运行问题

1. **TTS 音质差**：调整 `VOXCPM_CFG_*` 和 `VOXCPM_INFERENCE_STEPS`
2. **记忆错误**：删除 `data/knowledge_lance/` 重建知识库
3. **表情不变化**：检查 LLM 输出是否包含情绪标签

---

## 技术栈

- **LLM**: Gemini / OpenAI 格式 API
- **TTS**: VoxCPM (LoRA 微调)
- **STT**: FireRedASR / FunASR Paraformer
- **VAD**: Silero VAD
- **Live2D**: live2d-py
- **向量数据库**: LanceDB + SentenceTransformer

---

## 目录说明

| 目录           | 用途                        |
| -------------- | --------------------------- |
| `checkpoints/` | TTS 模型权重                |
| `data/`        | 知识库数据 (LanceDB)        |
| `logs/`        | 运行日志                    |
| `debug_audio/` | 调试用音频保存              |
| `models/`      | VAD 等模型                  |
| `modules/`     | 第三方模块（FireRedASR 等） |
| `scripts/`     | 测试和工具脚本              |
