# LLM 模块

大语言模型交互模块，负责与 LLM API 通信、Prompt 构建和角色设定。

---

## 文件结构

```
llm/
├── __init__.py
├── client.py           # LLM API 客户端
├── character_prompt.py # 角色设定 Prompt
├── prompt_builder.py   # Prompt 构建器
└── stream_parser.py    # 流式输出解析器
```

---

## 核心组件

### 1. LLMClient (`client.py`)

OpenAI 格式 API 客户端，支持流式输出和音频输入。

**关键方法**：

| 方法                       | 功能                           |
| -------------------------- | ------------------------------ |
| `chat_stream()`            | 流式对话（文本输入）           |
| `chat_with_audio_stream()` | 流式对话（音频输入，跳过 STT） |
| `chat()`                   | 非流式对话                     |

**配置**（在 `config.py`）：

```python
LLM_API_BASE = "http://localhost:8045/v1"
LLM_API_KEY = "sk-text"
LLM_MODEL = "gemini-3-flash"
```

**使用示例**：

```python
from llm.client import get_llm_client

client = get_llm_client()
async for chunk in client.chat_stream(messages, system_prompt=prompt):
    print(chunk, end="")
```

---

### 2. 角色设定 (`character_prompt.py`)

定义丰川祥子的完整人设和对话规则。

**关键内容**：

| 内容                              | 说明                                          |
| --------------------------------- | --------------------------------------------- |
| `EMOTION_TAGS`                    | 可用的情绪标签列表 (16 个)                    |
| `EMOTION_TO_EXPRESSION`           | 情绪标签 → Live2D 表情映射                    |
| `get_character_prompt_template()` | 获取基础人设模板（包含占位符）                |
| `get_system_prompt()`             | 获取完整 System Prompt（填充工具 + 随机状态） |

**System Prompt 结构**：

```
你是丰川祥子，住在这个人的电脑桌面上。

**你是谁：**
- 丰川集团大小姐，Ave Mujica 键盘手
- 自称"本神明"
- 傲娇，但其实会偷偷在意
...

**格式规则：**
1. 必须以情感标签开头
2. 控制在 30 字以内
...

**工具调用格式：**
[CALL:工具名:参数]
...

{{TOOLS_SECTION}}  ← 动态替换为实际工具列表

（当前状态：有点无聊）  ← 随机状态，增加回复多样性
```

**随机状态机制**：

基于时间和随机数注入心情状态，增加回复多样性：

- 0:00-6:00 → "困死了"、"好困..."
- 12:00-14:00 → "有点饿"、"午饭时间"
- 随机 → "想弹琴"、"在想曲子"、"有点烦"

---

### 3. Prompt 构建器 (`prompt_builder.py`)

统一构建 System Prompt 和 User Prompt。

**架构设计**：

```
┌──────────────────────────────────────────────────┐
│  System Prompt (5分钟缓存)                        │
│  ├── 角色设定 (character_prompt.py)               │
│  ├── 工具说明 (tools/registry.py)                 │
│  ├── 记忆上下文 (memory_injector.py)              │
│  │   ├── [时间信息]                               │
│  │   ├── [你一定要记住的事]  ← core 记忆          │
│  │   ├── [你记得的事情]      ← fact 记忆          │
│  │   └── [你检索得知的信息]  ← 工具结果整理        │
│  └── 随机状态                                     │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│  User Prompt (每轮动态生成)                        │
│  ├── 当前时间：2026-01-04 20:00                   │
│  ├── 主人正在使用：Visual Studio Code             │
│  ├── 对话记录：                                   │
│  │   ├── 20:00:15, 主人: 你好                     │
│  │   ├── 20:00:18, 小祥(你): [happy] 嗯？         │
│  │   └── ...                                      │
│  └── 现在主人说的: 今天天气怎么样                  │
└──────────────────────────────────────────────────┘
```

**关键方法**：

| 方法                    | 功能                                |
| ----------------------- | ----------------------------------- |
| `build_system_prompt()` | 构建 System Prompt（带 5 分钟缓存） |
| `build_user_prompt()`   | 构建 User Prompt（每轮动态）        |
| `build_messages()`      | 构建完整消息列表（system + user）   |
| `invalidate_cache()`    | 强制刷新缓存（记忆更新时调用）      |

**使用示例**：

```python
from llm.prompt_builder import get_prompt_builder

builder = get_prompt_builder()
messages = builder.build_messages(
    current_input="今天天气怎么样",
    conversation_history=history
)
```

---

### 4. 流式输出解析器 (`stream_parser.py`)

解析 LLM 流式输出，支持情绪检测和工具调用识别。

**主要功能**：

- 解析情绪标签 `[happy]`、`[shy]` 等
- 检测工具调用 `[CALL:tool_name:args]`
- 支持边输出边解析（低延迟）

---

## 与其他模块的关系

```
llm/
 │
 ├──→ tools/registry.py        获取工具描述，生成 {{TOOLS_SECTION}}
 │
 ├──→ core/memory_injector.py  获取记忆上下文
 │
 ├──→ core/context_manager.py  获取工具结果整理
 │
 └──→ core/response_handler.py 消费 LLM 输出
```

---

## 常见问题

### Q: 为什么 System Prompt 有缓存？

A: 避免每轮对话都重新调用知识库和生成工具描述。5 分钟缓存平衡了性能和实时性。

### Q: 随机状态的作用是什么？

A: 增加回复多样性，避免 LLM 每次用完全一样的语气回复。基于时间的状态也让角色更有"活"的感觉。

### Q: User Prompt 为什么不包含 system message 内容？

A: 这是参考 MaiBot 的架构设计，system + user 两条消息结构，避免历史消息累积导致 token 浪费。
