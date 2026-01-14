# ZcChat 与 Letta 调研分析

> 调研日期: 2026-01-14
> 目的: 评估现有方案，考虑是否简化/替换部分模块

---

## ZcChat 项目概述

**项目地址**: https://github.com/Zao-chen/ZcChat

**定位**: 模仿 Galgame 效果的 AI 桌宠

### 核心特色

| 特性 | 实现方式 |
|------|----------|
| **视觉呈现** | Galgame 立绘 PNG（非 Live2D）|
| **长期记忆** | 接入 Letta |
| **表情动作** | 按心情命名的立绘文件（`开心.png`、`难过.png`）|
| **语音合成** | vits-simple-api 或自定义 HTTP API |
| **语音输入** | whisper-asr-webservice 或百度语音 |

### 输出格式

```
{心情}|{中文}|{日语}
```

### 角色制作

1. 准备立绘 PNG 文件，按心情命名
2. 放入 `characters/{名称}/` 文件夹
3. 配置提示词

**优势**: 制作成本极低，不需要 Live2D 模型

---

## Letta (原 MemGPT) 原理

### 核心思想：操作系统式的记忆管理

把 LLM 当作有限 RAM 的"虚拟机"，借鉴操作系统的虚拟内存管理：

```
┌─────────────────────────────────────────────────────────────┐
│                    LLM Context Window                       │
│                    (类似 RAM - 有限)                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Core Memory (Memory Blocks)                        │   │
│  │  - persona: "我是丰川祥子..."                       │   │
│  │  - human: "主人喜欢拉面..."                         │   │
│  │  → 始终在 context 中，LLM 可以自己编辑              │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Messages (对话历史) → 会被自动压缩/摘要            │   │
│  └─────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │ 工具调用
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                External Memory (类似磁盘)                   │
│  - Archival Memory: 向量数据库存储的长期记忆               │
│  - Recall Memory: 可搜索的对话历史                         │
│  → 需要时通过工具调用检索                                   │
└─────────────────────────────────────────────────────────────┘
```

### 最核心的创新

**Agent 自己管理记忆，而不是外部代码！**

LLM 自己调用工具来更新记忆：

```python
# Letta agent 自主生成的工具调用
memory_replace(
    block_label="human",
    old_text="主人喜欢寿司",
    new_text="主人之前喜欢寿司，但现在更喜欢拉面"
)
```

### 记忆编辑工具

- `memory_replace` - 搜索并替换
- `memory_insert` - 插入新行
- `memory_rethink` - 重写整个 block

### 部署方式

```bash
# Docker 自托管
docker run -p 8283:8283 \
  -v ~/.letta/.persist/pgdata:/var/lib/postgresql/data \
  -e OPENAI_API_KEY="your-key" \
  letta/letta:latest

# 支持 OpenAI 兼容接口，可接入 gcli2api
-e OPENAI_API_BASE="http://host.docker.internal:7861/antigravity/v1"
```

---

## 与 nuero-sama-saki 项目对比

| 特性 | nuero-sama-saki | ZcChat | Letta |
|------|-----------------|--------|-------|
| **视觉** | Live2D（复杂） | Galgame 立绘（简单）| N/A |
| **记忆架构** | 三层（Working/Episodic/Semantic）| 无（依赖 Letta）| 两层（Core/External）|
| **记忆更新** | 后台小祥 LLM 判断 | 无 | Agent 自己调用工具 |
| **衰减机制** | ✅ 有 | ❌ 无 | ❌ 无 |
| **三元组存储** | ✅ 有 | ❌ 无 | ❌ 无 |
| **Hybrid 检索** | ✅ Vector + Graph | ❌ 无 | 仅 Vector |
| **升级/审核机制** | ✅ 有 | ❌ 无 | ❌ 无 |
| **TTS** | VoxCPM LoRA | vits-simple-api | N/A |
| **Tool 系统** | 完整（截屏/搜索/知识库）| 基础 | 完整 |

---

## 可以借鉴/替换的部分

### 1. ⭐ 视觉呈现：Live2D → Galgame 立绘

**现状问题**:
- Live2D 模型各种 bug（眨眼不工作、呼吸乱动）
- 手动实现所有动画参数
- 维护成本高，但视觉优势不明显

**ZcChat 方案**:
- 直接放 PNG 立绘，按情绪命名
- CSS 动画做简单的晃动/淡入淡出
- 制作成本极低

**建议**: 添加 Galgame 立绘模式与 Live2D 并存

### 2. 📝 记忆系统：保留优势，可选 Letta

**我们的优势**:
- 三层架构概念清晰
- 后台小祥的 LLM 驱动审核比机械规则更智能
- Hybrid 检索（Vector + Graph）更准确
- 有衰减/升级机制

**Letta 优势**:
- 开箱即用，减少维护负担
- Agent 自主管理记忆

**建议**: 不一定要换，但可以考虑渐进式接入测试

### 3. 🎙️ TTS

**现状**: VoxCPM LoRA 微调（效果好但占显存）

**建议**: 保留 VoxCPM 作为主力，加一个轻量备选（VITS 或云端）

---

## 结论

| 情况 | 建议 |
|------|------|
| **想快速有可用的长期记忆** | ✅ 试用 Letta |
| **想深度定制记忆逻辑** | ❌ 保留现有系统 |
| **想减少维护负担** | ✅ 用 Letta |
| **想保留三元组/Hybrid** | ❌ 保留现有系统 |
| **想降低视觉模块复杂度** | ✅ 添加 Galgame 立绘模式 |

**总结**: nuero-sama-saki 项目更"重"更完整，ZcChat 是轻量化方案。不是造轮子的问题，而是需求不同。可以考虑：
1. 添加 Galgame 立绘作为可选模式
2. 评估 Letta 是否满足记忆需求后再决定是否迁移

---

## 相关链接

- [ZcChat GitHub](https://github.com/Zao-chen/ZcChat)
- [Letta GitHub](https://github.com/letta-ai/letta)
- [Letta 文档](https://docs.letta.com)
- [MemGPT 论文](https://arxiv.org/abs/2310.08560)
