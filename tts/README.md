# VoxCPM TTS 优化指南

> 📅 最后更新: 2026-01-04
>
> 本文档记录了 VoxCPM 1.5 在本项目中的优化探索，包括**有效方案**和**已排除方案**。

---

## 📊 当前环境

| 项目     | 版本                 |
| -------- | -------------------- |
| VoxCPM   | 1.5.0                |
| PyTorch  | 2.6.0+cu124          |
| CUDA     | 12.4                 |
| 模型精度 | **bfloat16**（默认） |

---

## ✅ 有效方案

### 1. 调整 `inference_timesteps`（最有效）

这是**唯一直接有效**的 RTF 优化手段。

| Steps  | RTF   | 音质         | 适用场景     |
| ------ | ----- | ------------ | ------------ |
| 15     | ~0.79 | 能听但不精致 | 极端实时     |
| **20** | ~0.85 | **推荐折中** | **日常使用** |
| 35     | ~1.79 | 较好         | 离线生成     |

> ⚠️ **结论**：实时场景用 15~20，质量优先用 30+

### 2. 动态 CFG（推荐）

根据文本长度动态调整 CFG，已在 `config.py` 实现：

```python
VOXCPM_CFG_SHORT = 4.0   # 短句 (<20字): 清晰度优先
VOXCPM_CFG_MEDIUM = 3.0  # 中句 (20-60字): 平衡
VOXCPM_CFG_LONG = 2.5    # 长句 (>60字): 稳定性优先
```

社区共识：**CFG 2.0~5.0 是稳定区间**，超过可能导致不自然。

### 3. 关闭 Denoiser（已做）

```python
load_denoiser=False  # 节省时间，prompt 已经干净
```

---

## ❌ 已排除方案（不要再试）

### 1. torch.compile + triton

**测试日期**：2026-01-04  
**结果**：**无效，甚至略慢 (-3%)**

```
✅ none (原版): RTF=0.81
❌ inductor:    RTF=0.83 (-3%)
```

**原因**：

- VoxCPM streaming 模式频繁图断开
- bf16 已经是优化精度，编译收益有限
- triton-windows 在 Windows 上可能没完全优化

> ⚠️ **不要启用 torch.compile**

---

### 2. CUDA Graph

**排除原因**：完全不适合 VoxCPM streaming

| CUDA Graph 要求 | VoxCPM streaming 情况  |
| --------------- | ---------------------- |
| 静态 shape      | ❌ 输出长度每次不同    |
| 固定内存地址    | ❌ 每个 chunk 地址变化 |
| 无条件分支      | ❌ 有动态控制流        |

> ⚠️ **不要尝试 CUDA Graph**

---

### 3. ONNX Runtime (VoxCPM-ONNX)

**项目**：[bluryar/VoxCPM-ONNX](https://github.com/bluryar/VoxCPM-ONNX)

**排除原因**：

- ❌ **只支持 VoxCPM 0.5B**，不支持 1.5
- ❌ Timesteps 固定在导出时，无法动态调整
- ❌ 需要作为 API 服务运行，不是直接替换

> ⚠️ **除非官方支持 1.5，否则不可用**

---

### 4. NanoVLLM (nanovllm-voxcpm)

**项目**：[a710128/nanovllm-voxcpm](https://github.com/a710128/nanovllm-voxcpm)

**排除原因**：

- ❌ **只支持 VoxCPM 0.5B**（从 Known Issue 权重结构判断）
- ❌ 存在 `Missing parameters` 已知 bug
- ❌ 不在 PyPI，需源码安装
- ❌ 项目不成熟

> ⚠️ **除非官方为 1.5 开发新版本，否则不可用**

---

### 5. Micro-batching

**排除原因**：

- ❌ VoxCPM streaming 模式强制 `batch_size=1`
- ❌ 单用户逐句生成场景无法拼批
- ❌ 即使能拼，延迟反而增加

> ⚠️ **对桌宠场景无意义**

---

### 6. FP16 手动转换

**排除原因**：

- VoxCPM 1.5 默认已是 **bfloat16**
- 手动转 FP16 可能导致 audio_vae dtype 不匹配

> ⚠️ **保持 `VOXCPM_USE_FP16 = False`**

---

## 📌 最终推荐配置

```python
# config.py

# 动态 CFG
VOXCPM_USE_DYNAMIC_CFG = True
VOXCPM_CFG_SHORT = 4.0
VOXCPM_CFG_MEDIUM = 3.0
VOXCPM_CFG_LONG = 2.5
VOXCPM_CFG_VALUE = 3.0

# 推理步数（关键参数）
VOXCPM_INFERENCE_STEPS = 20  # 实时折中

# 其他
VOXCPM_USE_FP16 = False      # 不启用，模型默认 bf16
VOXCPM_USE_PROMPT = False    # LoRA 效果好时不需要
VOXCPM_USE_EMOTION_REF = False  # 会增加 4s 延迟
```

---

## 🔧 测试脚本

测试脚本位于 `scripts/` 目录：

| 脚本                    | 用途                                  |
| ----------------------- | ------------------------------------- |
| `test_voxcpm_rtf.py`    | 测试不同 steps/CFG 组合的 RTF         |
| `test_torch_compile.py` | 测试 torch.compile 效果（已证明无效） |

---

## 📚 参考资源

- [VoxCPM 官方仓库](https://github.com/OpenBMB/VoxCPM)
- [VoxCPM HuggingFace](https://huggingface.co/openbmb/VoxCPM1.5)
- 社区经验：CFG 2.0~5.0 稳定，Steps 30~50 性价比最高
