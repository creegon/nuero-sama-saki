# Neuro-like AI Desktop Pet - Configuration

import os

# ====================
# 内存优化配置
# ====================
# 优化 CUDA 内存分配，减少碎片化
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:128"

# ====================
# Paths
# ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")

# ====================
# Antigravity LLM API
# ====================
LLM_API_BASE = "http://localhost:8045/v1"
LLM_API_KEY = "sk-text"  # Default key from antigravity2api
LLM_MODEL = "gemini-3-flash"  # High reasoning model

# ====================
# Vision Settings
# ====================
VISION_ENABLED = True
VISION_MODEL = "gemini-3-flash"  # 同 LLM_MODEL
SCREENSHOT_MAX_SIZE = 1024       # 最大边长 (像素)
SCREENSHOT_QUALITY = 85          # JPEG 质量

# ====================
# Knowledge Base
# ====================
ENABLE_KNOWLEDGE = True  # 启用知识库 (独立进程模式)
KNOWLEDGE_SERVER_HOST = "127.0.0.1"
KNOWLEDGE_SERVER_PORT = 19876
KNOWLEDGE_SOCKET_TIMEOUT = 10.0
KNOWLEDGE_LANCEDB_PATH = os.path.join(BASE_DIR, "data", "knowledge_lance")
KNOWLEDGE_COLLECTION_NAME = "sakiko_knowledge_v2"

# ====================
# Proactive Chat Settings (LLM 主导模式)
# ====================
PROACTIVE_CHAT_ENABLED = True

# 检查间隔（秒）- 每隔这个时间范围随机检查一次是否要主动说话
PROACTIVE_CHECK_INTERVAL_MIN = 10    # 最短检查间隔（秒）
PROACTIVE_CHECK_INTERVAL_MAX = 30    # 最长检查间隔（秒）

# 触发条件
PROACTIVE_MIN_IDLE_TIME = 10         # 用户至少空闲多久才会触发（秒）

# 追问设置
FOLLOW_UP_DELAY_MIN = 2              # 追问延迟最小值（秒）
FOLLOW_UP_DELAY_MAX = 4              # 追问延迟最大值（秒）

# 🔥 注意：已移除 PROACTIVE_CHAT_CHANCE 和 FOLLOW_UP_CHANCE
# 现在完全由后台小祥（LLM）决定是否说话，不再有机械概率审核

# ====================
# 记忆系统配置
# ====================
MEMORY_INJECTION_COUNT = 5           # 每轮注入的记忆数量
MEMORY_DECAY_DAYS = 7                # 超过多少天未访问开始衰减
MEMORY_DECAY_FACTOR = 0.9            # 衰减系数 (0.9 = 每次降低 10%)
MEMORY_SIMILARITY_THRESHOLD = 0.85   # 相似度阈值（超过则合并记忆而非新增）
MEMORY_MIN_IMPORTANCE = 0.3          # 低于此重要性的记忆会被遗忘
MEMORY_REFRESH_INTERVAL = 5          # 每 N 轮对话刷新一次相关记忆
MEMORY_IMPORTANT_THRESHOLD = 2.5     # 核心层记忆的重要性阈值

# ====================
# VoxCPM TTS 配置
# ====================
# 注意: 优先使用 merged 模型 (checkpoints/sakiko_merged/tts_model_merged.pt)
#       若 merged 不存在，则回退到 LoRA 模式
VOXCPM_LORA_PATH = os.path.join(BASE_DIR, "checkpoints", "sakiko_lora", "step_0002000")  # LoRA 回退路径
VOXCPM_CFG_VALUE = 2.2  # 降低到2.2以平衡稳定性以增加稳定性，降低音调失控概率)
VOXCPM_INFERENCE_STEPS = 10  # 推理步数 (保持原值以维持RTF性能)
VOXCPM_USE_PROMPT = False  # 是否使用参考音频 (LoRA 效果好时通常不需要)
VOXCPM_USE_EMOTION_REF = False  # 是否使用情感参考音频 (⚠️ 开启会增加 ~4s 延迟！)
# ⚠️ FP16 在 VoxCPM 库中存在 audio_vae dtype 不匹配问题，暂时禁用
VOXCPM_USE_FP16 = False  # 使用 FP16 精度 (当前因 audio_vae 兼容性问题已禁用)
VOXCPM_PROMPT_WAV = None # 默认提示音频路径 (None = 不使用)
VOXCPM_PROMPT_TEXT = None # 默认提示音频文本

# TTS 输出目录
TTS_OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "tts")

# Debug: 保存生成的音频到 debug_audio/ 目录 (用于后期分析)
DEBUG_SAVE_AUDIO = True  # 设为 True 启用音频保存

# ====================
# Module Paths
# ====================
MODULES_DIR = os.path.join(BASE_DIR, "modules")
ANTIGRAVITY_DIR = os.path.join(MODULES_DIR, "antigravity2api-nodejs")
LIVE2D_DIR = os.path.join(MODULES_DIR, "live2d-py")

# ====================
# Live2D Settings
# ====================
LIVE2D_MODEL_PATH = os.path.join(BASE_DIR, "live2d_local", "models", "sakiko.model3.json")
LIVE2D_FPS = 60  # 帧率
LIVE2D_LIPSYNC_ENABLED = True       # 口型同步
LIVE2D_LIPSYNC_SMOOTHING = 0.25     # 口型平滑系数 (0-1, 越大越平滑)

# ====================
# Live2D Idle 动画参数
# ====================
# 2026-01-02 测试得出的最佳值
# 注意: 这个模型的 ParamBreath 控制尾巴，不是身体呼吸！

# 身体呼吸模拟 (用 ParamBodyAngleY 实现)
LIVE2D_IDLE_BODY_BREATH_ENABLED = True   # 启用身体呼吸
LIVE2D_IDLE_BODY_BREATH_SPEED = 0.5      # 呼吸速度 (越小越慢)
LIVE2D_IDLE_BODY_BREATH_AMPLITUDE = 1.4  # 呼吸幅度 (ParamBodyAngleY 范围 -10~10)

# 尾巴摆动 (用 ParamBreath 实现)
LIVE2D_IDLE_TAIL_ENABLED = True          # 启用尾巴摆动
LIVE2D_IDLE_TAIL_SPEED = 0.8             # 尾巴摆动速度
LIVE2D_IDLE_TAIL_AMPLITUDE = 1.0         # 尾巴摆动幅度 (0-1)

# 眨眼 (手动实现，官方 UpdateBlink 不工作)
LIVE2D_IDLE_BLINK_ENABLED = True         # 启用眨眼
LIVE2D_IDLE_BLINK_INTERVAL_MIN = 2.0     # 眨眼最短间隔 (秒)
LIVE2D_IDLE_BLINK_INTERVAL_MAX = 5.0     # 眨眼最长间隔 (秒)

# 头发物理
LIVE2D_IDLE_PHYSICS_ENABLED = True       # 启用头发物理 (UpdatePhysics)

# 表情过渡
LIVE2D_EXPRESSION_LERP_SPEED = 0.08      # 表情过渡速度 (0.05=慢~1s, 0.1=中~0.3s, 0.2=快~0.15s)

# ====================
# Service Ports
# ====================
ANTIGRAVITY_PORT = 8045

# ====================
# Audio Capture
# ====================
AUDIO_SAMPLE_RATE = 16000  # 16kHz for Whisper
AUDIO_CHANNELS = 1
AUDIO_CHUNK_MS = 32  # 32ms = 512 samples (exact requirement for Silero VAD at 16kHz)
AUDIO_OUTPUT_DEVICE = None  # None = 默认设备, 或指定设备索引/名称

# ====================
# Silero VAD
# ====================
VAD_THRESHOLD = 0.4        # Speech probability threshold (降低以更快检测语音开始)
VAD_MIN_SPEECH_MS = 150    # Minimum speech duration (减少以更快确认语音)
VAD_MIN_SILENCE_MS = 500   # Silence duration to end speech
VAD_SPEECH_PAD_MS = 400    # Padding around speech (增加以保留更多开头音频)

# ====================
# 语音识别 (STT) 配置
# ====================
# Voice-to-LLM: 直接将语音发送给 Gemini，跳过 STT
# 优点：省显存（~2GB）、端到端理解、自动多语言
# 缺点：需要网络、隐私考虑
VOICE_TO_LLM_ENABLED = True  # 启用后跳过 STT，语音直接发给 LLM

# 传统 STT 引擎 (当 VOICE_TO_LLM_ENABLED=False 时使用)
# 可选引擎: "paraformer" (快速, ~0.2s) 或 "fireredasr" (准确, ~0.5s)
STT_ENGINE = "fireredasr"

# FunASR Paraformer 配置
STT_MODEL = "paraformer-large-zh"  # Paraformer-Large 中文模型（准确率95%+）
STT_DEVICE = "cuda"
STT_LANGUAGE = "zh"  # 主要语言

# FireRedASR 配置 (可选，准确率更高但速度较慢)
FIREREDASR_MODEL_DIR = os.path.join(MODULES_DIR, "FireRedASR", "pretrained_models", "FireRedASR-AED-L")

# STT 后处理配置
STT_POST_PROCESS = True  # 启用后处理 (语气词移除、同音字纠错等)
STT_CUSTOM_CORRECTIONS = {
    # 自定义纠错规则: {"错误词": "正确词"}
    # 例如角色名容易被识别错：
    "小象": "小祥",
    "晓祥": "小祥",

}


# ====================
# Character Settings
# ====================
CHARACTER_NAME = "小祥"

# 可用的情绪标签 (用于 Live2D 表情驱动)
def get_system_prompt() -> str:
    """
    获取完整的 system prompt
    """
    from llm.character_prompt import get_system_prompt
    return get_system_prompt()


# 保留 SYSTEM_PROMPT 作为兼容（但推荐使用 get_system_prompt()）
SYSTEM_PROMPT = get_system_prompt()

# ====================
# State Machine
# ====================
STATE_IDLE = "IDLE"
STATE_LISTENING = "LISTENING"
STATE_PROCESSING = "PROCESSING"
STATE_SPEAKING = "SPEAKING"

# ====================
# TTS Queue Settings
# ====================
TTS_MAX_WORKERS = 3  # Parallel TTS generation threads

# Ensure output directories exist
os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)
