# -*- coding: utf-8 -*-
"""
情绪 Idle 调制器

定义不同情绪对 Idle 动画参数的影响:
- 呼吸速度/幅度
- 尾巴速度/幅度
- 眨眼频率
- 头部轻微摆动
- 表情参数偏移（笑眼、眉毛、脸红等）
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class EmotionModifier:
    """情绪调制参数"""
    # Idle 动画倍率
    breath_speed_mult: float = 1.0
    breath_amp_mult: float = 1.0
    tail_speed_mult: float = 1.0
    tail_amp_mult: float = 1.0
    blink_interval_mult: float = 1.0  # >1 = 眨眼更慢, <1 = 更快
    
    # 头部摆动
    head_sway_amp: float = 0.0  # 幅度 (0 = 不摆)
    head_sway_speed: float = 0.3
    
    # 表情参数偏移（叠加到基础表情上）
    eye_open_offset: float = 0.0     # 眼睛大小偏移
    eye_smile_offset: float = 0.0    # 笑眼程度
    brow_y_offset: float = 0.0       # 眉毛高度
    cheek_offset: float = 0.0        # 脸红
    mouth_form_offset: float = 0.0   # 嘴巴形状


# 情绪调制器定义
EMOTION_MODIFIERS: Dict[str, EmotionModifier] = {
    "neutral": EmotionModifier(),
    
    "happy": EmotionModifier(
        breath_speed_mult=1.2,
        breath_amp_mult=1.1,
        tail_speed_mult=1.5,
        tail_amp_mult=1.3,
        blink_interval_mult=0.8,
        head_sway_amp=3.0,
        head_sway_speed=0.5,
        eye_smile_offset=0.15,
        brow_y_offset=0.1,
        cheek_offset=0.1,
        mouth_form_offset=0.2,
    ),
    
    "excited": EmotionModifier(
        breath_speed_mult=1.5,
        breath_amp_mult=1.3,
        tail_speed_mult=2.0,
        tail_amp_mult=1.5,
        blink_interval_mult=0.6,
        head_sway_amp=5.0,
        head_sway_speed=0.8,
        eye_open_offset=0.2,
        eye_smile_offset=0.1,
        brow_y_offset=0.2,
        cheek_offset=0.15,
        mouth_form_offset=0.3,
    ),
    
    "angry": EmotionModifier(
        breath_speed_mult=1.4,
        breath_amp_mult=1.2,
        tail_speed_mult=1.3,
        tail_amp_mult=0.8,
        blink_interval_mult=1.5,
        head_sway_amp=1.0,
        head_sway_speed=0.2,
        eye_open_offset=0.2,
        eye_smile_offset=-0.1,
        brow_y_offset=-0.3,
        mouth_form_offset=-0.2,
    ),
    
    "sad": EmotionModifier(
        breath_speed_mult=0.7,
        breath_amp_mult=0.8,
        tail_speed_mult=0.5,
        tail_amp_mult=0.5,
        blink_interval_mult=1.3,
        head_sway_amp=0.5,
        head_sway_speed=0.15,
        eye_open_offset=-0.15,
        brow_y_offset=0.2,
        mouth_form_offset=-0.15,
    ),
    
    "thinking": EmotionModifier(
        breath_speed_mult=0.9,
        breath_amp_mult=0.9,
        tail_speed_mult=0.6,
        tail_amp_mult=0.7,
        blink_interval_mult=1.2,
        head_sway_amp=2.0,
        head_sway_speed=0.2,
        brow_y_offset=0.15,
    ),
    
    "shy": EmotionModifier(
        breath_speed_mult=1.1,
        breath_amp_mult=1.2,
        tail_speed_mult=0.8,
        tail_amp_mult=0.6,
        blink_interval_mult=0.7,
        head_sway_amp=2.0,
        head_sway_speed=0.4,
        eye_open_offset=-0.1,
        eye_smile_offset=0.2,
        cheek_offset=0.3,
        mouth_form_offset=0.1,
    ),
    
    "sleepy": EmotionModifier(
        breath_speed_mult=0.5,
        breath_amp_mult=1.4,
        tail_speed_mult=0.3,
        tail_amp_mult=0.3,
        blink_interval_mult=0.5,
        head_sway_amp=1.5,
        head_sway_speed=0.1,
        eye_open_offset=-0.5,
        brow_y_offset=-0.1,
    ),
    
    "surprised": EmotionModifier(
        breath_speed_mult=1.8,
        breath_amp_mult=0.7,
        tail_speed_mult=2.0,
        tail_amp_mult=1.8,
        blink_interval_mult=2.0,
        eye_open_offset=0.4,
        brow_y_offset=0.3,
    ),
    
    "curious": EmotionModifier(
        breath_speed_mult=1.1,
        tail_speed_mult=1.2,
        tail_amp_mult=1.2,
        blink_interval_mult=0.9,
        head_sway_amp=4.0,
        head_sway_speed=0.3,
        eye_open_offset=0.15,
        brow_y_offset=0.2,
    ),
    
    "pout": EmotionModifier(
        breath_speed_mult=0.9,
        breath_amp_mult=1.1,
        tail_speed_mult=0.4,
        tail_amp_mult=0.5,
        head_sway_amp=1.0,
        head_sway_speed=0.2,
        eye_open_offset=-0.1,
        brow_y_offset=-0.15,
        cheek_offset=0.2,
        mouth_form_offset=-0.3,
    ),
    
    "smug": EmotionModifier(
        breath_speed_mult=0.85,
        tail_speed_mult=0.9,
        blink_interval_mult=1.2,
        head_sway_amp=3.0,
        head_sway_speed=0.25,
        eye_smile_offset=0.25,
        brow_y_offset=0.1,
        cheek_offset=0.1,
        mouth_form_offset=0.25,
    ),
    
    "confused": EmotionModifier(
        breath_speed_mult=0.9,
        tail_speed_mult=0.7,
        tail_amp_mult=0.8,
        blink_interval_mult=1.1,
        head_sway_amp=2.5,
        head_sway_speed=0.25,
        brow_y_offset=0.1,
    ),
    
    "worried": EmotionModifier(
        breath_speed_mult=1.1,
        breath_amp_mult=1.1,
        tail_speed_mult=0.6,
        tail_amp_mult=0.6,
        blink_interval_mult=0.8,
        head_sway_amp=1.5,
        head_sway_speed=0.2,
        eye_open_offset=0.1,
        brow_y_offset=0.25,
    ),
    
    "embarrassed": EmotionModifier(
        breath_speed_mult=1.2,
        breath_amp_mult=1.2,
        tail_speed_mult=0.5,
        tail_amp_mult=0.5,
        blink_interval_mult=0.6,
        head_sway_amp=2.0,
        head_sway_speed=0.3,
        eye_open_offset=-0.2,
        cheek_offset=0.4,
    ),
    
    "mischievous": EmotionModifier(
        breath_speed_mult=1.1,
        tail_speed_mult=1.3,
        tail_amp_mult=1.2,
        blink_interval_mult=0.9,
        head_sway_amp=3.0,
        head_sway_speed=0.4,
        eye_smile_offset=0.2,
        brow_y_offset=0.1,
        mouth_form_offset=0.2,
    ),
}

# 默认调制器
DEFAULT_MODIFIER = EmotionModifier()


def get_emotion_modifier(emotion: str) -> EmotionModifier:
    """获取情绪调制器"""
    return EMOTION_MODIFIERS.get(emotion, DEFAULT_MODIFIER)
