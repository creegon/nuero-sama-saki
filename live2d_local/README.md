# Live2D 模块

## 重要发现 (2026-01-02 测试)

### 模型特点 (sakiko)

这个模型的特殊配置：

1. **ParamBreath 控制尾巴，不是身体呼吸**

   - `ParamBreath` → `PhysicsSetting18 (尾巴)` → 尾巴摆动
   - 模型没有身体呼吸变形动画

2. **官方眨眼不工作**

   - `UpdateBlink()` 无效
   - `model3.json` 中 `EyeBlink.Ids` 为空数组
   - 需要手动控制 `ParamEyeLOpen` / `ParamEyeROpen`

3. **UpdateBreath() 会导致身体乱动！**
   - 会周期性修改 `ParamBodyAngleX` (5 秒 +10, 5 秒 -10)
   - 这是 live2d-py 的行为，不是模型问题
   - **解决方案**：不要调用 `UpdateBreath()`

### 正确的 Idle 实现

```python
# 使用底层 Model 类获得完全控制
model = live2d.Model()
model.LoadModelJson(path)
model.CreateRenderer()

# 每帧更新
def update(delta_time):
    # 只调用 Physics（头发、尾巴物理）
    model.UpdatePhysics(delta_time)

    # 手动尾巴摆动
    breath = (math.sin(time * speed) + 1) / 2
    model.SetParameterValueById("ParamBreath", breath, 1.0)

    # 手动眨眼
    model.SetParameterValueById("ParamEyeLOpen", blink_value, 1.0)
    model.SetParameterValueById("ParamEyeROpen", blink_value, 1.0)

# 不要调用的函数：
# - UpdateBreath() → 会导致身体乱动
# - UpdateBlink() → 不工作
# - UpdateMotion() → 没有 idle 动作
```

### Update 函数效果表

| 函数                 | 效果            | 是否使用 |
| -------------------- | --------------- | -------- |
| `UpdatePhysics()`    | 头发、衣服物理  | ✅ 使用  |
| `UpdateBreath()`     | Body 乱动 (bug) | ❌ 不用  |
| `UpdateBlink()`      | 无效            | ❌ 不用  |
| `UpdateMotion()`     | 无效            | ❌ 不用  |
| `UpdateDrag()`       | 视线追踪        | ⚠️ 按需  |
| `UpdateExpression()` | 表情            | ⚠️ 按需  |
| `UpdatePose()`       | 姿势            | ⚠️ 按需  |

### 参数对照表

| 参数                  | 控制部位 | 范围   |
| --------------------- | -------- | ------ |
| `ParamBreath`         | 尾巴     | 0~1    |
| `ParamEyeLOpen`       | 左眼     | 0~1    |
| `ParamEyeROpen`       | 右眼     | 0~1    |
| `ParamAngleX/Y/Z`     | 头部     | -30~30 |
| `ParamBodyAngleX/Y/Z` | 身体     | -10~10 |
| `ParamMouthOpenY`     | 嘴巴开合 | 0~1    |
| `ParamMouthForm`      | 嘴巴形状 | -1~1   |

### Idle 动画最佳配置 (2026-01-02 测试)

参数在 `config.py` 中配置：

| 配置项                              | 默认值 | 说明                    |
| ----------------------------------- | ------ | ----------------------- |
| `LIVE2D_IDLE_BODY_BREATH_SPEED`     | 0.5    | 身体呼吸速度 (越小越慢) |
| `LIVE2D_IDLE_BODY_BREATH_AMPLITUDE` | 1.4    | 身体呼吸幅度            |
| `LIVE2D_IDLE_TAIL_SPEED`            | 0.8    | 尾巴摆动速度            |
| `LIVE2D_IDLE_TAIL_AMPLITUDE`        | 1.0    | 尾巴摆动幅度            |
| `LIVE2D_IDLE_BLINK_INTERVAL_MIN`    | 2.0    | 眨眼最短间隔 (秒)       |
| `LIVE2D_IDLE_BLINK_INTERVAL_MAX`    | 5.0    | 眨眼最长间隔 (秒)       |
| `LIVE2D_IDLE_PHYSICS_ENABLED`       | True   | 头发物理开关            |

---

## 原有文档

### 1. 官方 API 优先

使用 [live2d-py](https://github.com/EasyLive2D/live2d-py) 库。

**参考官方示例**：

- `main_pyqt5_canvas_opacity.py` - PyQt5 透明窗口
- `main_pygame_fine_grained.py` - 精细控制更新流程
- `main_facial_bind.py` - 面部参数绑定

### 2. 这个模型没有表情文件

`sakiko.model3.json` 没有定义 `.exp3.json` 表情文件。
所有表情通过 `SetParameterValue()` 手动实现，见 `controller.py` 中的 `EXPRESSIONS` 字典。

### 3. 透明背景三要素

```python
# 1. Qt 窗口属性
self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

# 2. paintGL 清除
GL.glClearColor(0.0, 0.0, 0.0, 0.0)
GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)

# 3. on_draw 清除
live2d.clearBuffer()
```

### 4. PyQt5 vs Pygame

| 框架   | 初始化函数          |
| ------ | ------------------- |
| PyQt5  | `live2d.glInit()`   |
| Pygame | `live2d.glewInit()` |

### 5. LAppModel vs Model

| 类          | 特点                                                    |
| ----------- | ------------------------------------------------------- |
| `LAppModel` | 高层封装，`Update()` 自动处理眨眼/呼吸/物理             |
| `Model`     | 底层类，需手动调用 `UpdateBlink()`, `UpdateBreath()` 等 |

**推荐使用 Model（底层类），因为 LAppModel 的 Update() 会导致问题。**

## 文件结构

```
live2d_local/
├── __init__.py     # 模块导出
├── controller.py   # 主控制器 (PyQt5 + Model)
├── expressions.py  # 表情参数定义
├── lipsync.py      # 口型同步
├── models/         # Live2D 模型文件
│   ├── sakiko.model3.json
│   ├── sakiko.moc3
│   ├── sakiko.physics3.json  # 物理设置(尾巴用ParamBreath)
│   └── sakiko.vtube.json     # VTube Studio 配置
└── clips/          # 动画片段 (暂未使用)
```
