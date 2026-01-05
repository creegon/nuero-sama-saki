# Tools 模块 (工具系统)

小祥可调用的工具集合，支持截屏、搜索、记忆管理等功能。

---

## 文件结构

```
tools/
├── __init__.py
├── base.py               # 工具基类
├── registry.py           # 工具注册表
├── executor.py           # 工具执行器
├── screenshot_tool.py    # 截屏工具
├── memory_tools.py       # 记忆/知识库工具
├── live2d_control_tool.py # Live2D 控制工具
├── web_search_tool.py    # 网络搜索工具
├── window_tool.py        # 窗口信息工具 (已禁用)
└── time_aware_tool.py    # 时间感知工具 (已移除)
```

---

## 工具调用格式

LLM 输出中使用以下格式调用工具：

```
[CALL:工具名]           # 无参数
[CALL:工具名:参数]      # 带参数
```

**示例**：

```
[happy] 让我看看你在干嘛。[CALL:screenshot]
[thinking] 让我搜搜看。[CALL:web_search:勾股定理]
[curious] 我记得你喜欢什么来着？[CALL:knowledge:喜好]
```

---

## 可用工具

### 1. screenshot - 截屏

截取当前屏幕并发送给 LLM 分析。

| 属性     | 值                              |
| -------- | ------------------------------- |
| 调用格式 | `[CALL:screenshot]`             |
| 需要参数 | 否                              |
| 返回格式 | `IMAGE_RESULT:jpeg:base64_data` |

**实现文件**：`screenshot_tool.py`

---

### 2. knowledge - 搜索记忆

从知识库中搜索与关键词相关的记忆。

| 属性     | 值                            |
| -------- | ----------------------------- |
| 调用格式 | `[CALL:knowledge:搜索关键词]` |
| 需要参数 | 是（搜索关键词）              |
| 返回格式 | 文本（相关记忆列表）          |

**示例输出**：

```
[相关知识]
- 主人喜欢拉面
- 主人是程序员
```

---

### 3. add_knowledge - 添加记忆

将新信息存入知识库。

| 属性     | 值                                  |
| -------- | ----------------------------------- |
| 调用格式 | `[CALL:add_knowledge:要记住的内容]` |
| 需要参数 | 是（要记住的内容）                  |
| 返回格式 | 确认消息                            |

**示例**：

```
[happy] 好的，本神明记住了！[CALL:add_knowledge:主人最喜欢吃寿司]
```

---

### 4. move_self - 移动位置

移动 Live2D 角色到指定位置或调整大小。

| 属性     | 值                                                                               |
| -------- | -------------------------------------------------------------------------------- |
| 调用格式 | `[CALL:move_self:位置]`                                                          |
| 可用参数 | `left`, `right`, `top_left`, `bottom_right`, `hide`, `show`, `larger`, `smaller` |

**实现文件**：`live2d_control_tool.py`

---

### 5. web_search - 网络搜索

使用 DuckDuckGo 搜索网络信息。

| 属性     | 值                           |
| -------- | ---------------------------- |
| 调用格式 | `[CALL:web_search:搜索内容]` |
| 需要参数 | 是（搜索关键词）             |
| 返回格式 | 文本（搜索结果摘要）         |

**实现文件**：`web_search_tool.py`

---

## 工具注册表 (`registry.py`)

管理所有可用工具，生成 LLM 可读的工具描述。

**关键方法**：

| 方法                   | 功能                    |
| ---------------------- | ----------------------- |
| `register(tool)`       | 注册一个工具            |
| `get_tool(name)`       | 获取工具实例            |
| `list_tools()`         | 列出所有工具名          |
| `get_prompt_section()` | 生成工具描述供 LLM 使用 |

**Prompt 输出示例**：

```
**你的能力：**

1. **搜索记忆/知识库** [CALL:knowledge]
回忆关于主人或某事的信息，需要提供搜索关键词。
示例：
User: 你还记得我最喜欢吃什么吗
Assistant: [curious] 让我去知识库里查查。[CALL:knowledge:主人喜欢的食物]

2. **记住信息** [CALL:add_knowledge]
当主人告诉你重要信息时，你可以主动记住它。
...
```

---

## 工具执行器 (`executor.py`)

解析 LLM 输出中的工具调用并执行。

**关键方法**：

| 方法                       | 功能                              |
| -------------------------- | --------------------------------- |
| `parse_tool_calls(text)`   | 从文本中解析所有工具调用          |
| `has_tool_call(text)`      | 检查是否包含工具调用              |
| `split_at_tool_call(text)` | 在工具调用处分割文本              |
| `execute_tool(name, args)` | 执行指定工具                      |
| `handle_tool_execution()`  | 完整的工具执行流程（含 TTS 并行） |

**并行执行设计**：

```
LLM 输出: "[curious] 让我看看...[CALL:screenshot]"
    ↓
分割: before="[curious] 让我看看..." | tool="screenshot" | after=""
    ↓
并行执行:
├── TTS 播放 "让我看看..."
└── 执行 screenshot 工具
    ↓
工具结果返回给 LLM 继续生成
```

---

## 添加新工具

1. **继承 BaseTool**：

```python
# tools/my_tool.py
from .base import BaseTool, ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "工具描述"
    usage_hint = "使用提示"
    example_user = "用户示例输入"
    example_assistant = "[emotion] 回复 [CALL:my_tool:参数]"

    async def execute(self, context: str = "", args: str = "", **kwargs) -> ToolResult:
        # 实现逻辑
        return ToolResult(success=True, data="结果")
```

2. **注册工具**：

```python
# tools/registry.py
def _register_default_tools(registry: ToolRegistry) -> None:
    from .my_tool import MyTool
    registry.register(MyTool())
```

---

## 已禁用/移除的工具

| 工具           | 状态 | 原因                             |
| -------------- | ---- | -------------------------------- |
| `window_title` | 禁用 | 自动附加到每次对话，无需手动调用 |
| `time_aware`   | 移除 | 时间信息直接注入 prompt          |

---

## 工具结果整理

工具调用结果会被收集，由后台小祥整理后注入到下轮对话的 `[你检索得知的信息]` 区块。

详见 `knowledge/README.md` 中的 "工具结果上下文整理" 章节。
