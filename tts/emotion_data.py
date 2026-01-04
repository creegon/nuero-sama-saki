# -*- coding: utf-8 -*-
"""
TTS 情感数据映射与辅助函数
"""

import os
import random
import config
from loguru import logger

# ====================
# 情感音频映射 (基于 generate_dataset.py 的 EMOTION_DATA)
# ====================
# 每个情感类别对应的音频文件索引范围 [起始, 结束] (1-indexed)
EMOTION_AUDIO_RANGES = {
    "calm": (1, 8),          # 平静/日常
    "happy": (9, 14),        # 快乐
    "very_excited": (15, 19),# 非常兴奋
    "few_excited": (20, 23), # 轻微兴奋
    "gentle": (24, 29),      # 温柔
    "allured": (30, 34),     # 诱惑
    "confident": (35, 40),   # 自信/骄傲
    "angry": (41, 45),       # 生气
    "heartless": (46, 51),   # 冷酷
    "few_angry": (52, 55),   # 轻微生气
    "amazed": (56, 59),      # 惊讶
    "shocked": (60, 63),     # 震惊
    "few_shocked": (64, 66), # 轻微震惊
    "puzzled": (67, 70),     # 困惑
    "worried": (71, 74),     # 担心
    "sighing": (75, 78),     # 叹气
    "alarmed": (79, 82),     # 警惕
    "slack_off": (83, 87),   # 慵懒
}

# LLM 情感标签到数据集情感的映射
# config.EMOTION_TAGS: neutral, happy, sad, angry, thinking, surprised,
#                      shy, confused, smug, pout, worried, sleepy,
#                      excited, curious, embarrassed, mischievous
EMOTION_TAG_MAPPING = {
    "neutral": "calm",
    "happy": "happy",
    "sad": "sighing",
    "angry": "angry",
    "thinking": "puzzled",
    "surprised": "amazed",
    "shy": "gentle",
    "confused": "puzzled",
    "smug": "confident",
    "pout": "few_angry",
    "worried": "worried",
    "sleepy": "slack_off",
    "excited": "very_excited",
    "curious": "few_excited",
    "embarrassed": "gentle",
    "mischievous": "allured",
}

# 情感音频目录
EMOTION_AUDIO_DIR = os.path.join(config.BASE_DIR, "datasets", "sakiko_lora", "audio")

# 每个情感类别的代表性 prompt_text (来自 generate_dataset.py)
EMOTION_PROMPT_TEXTS = {
    "calm": "今天的天气真不错，微风拂过脸庞的感觉很舒服。",
    "happy": "太棒了！这次演出一定会非常成功的！",
    "very_excited": "我实在是太兴奋了！等不及要上台了！",
    "few_excited": "嗯，这个主意不错，我觉得可以试试看。",
    "gentle": "这样啊...那我就放心了，谢谢你告诉我。",
    "allured": "怎么了？是被我的魅力迷住了吗？",
    "confident": "交给本大小姐就好了，没有什么是我做不到的。",
    "angry": "什么！？这种事情怎么可以！太过分了！",
    "heartless": "这种程度的话，对我来说根本不算什么。",
    "few_angry": "哼，真是的，说了多少次了...下次可不会再帮你了。",
    "amazed": "诶！？真的吗！？这也太厉害了吧！",
    "shocked": "什...什么！？怎么会发生这种事！？",
    "few_shocked": "欸？这样吗...我还以为会不一样呢。",
    "puzzled": "唔...这个我还真没想过，让我想想看...",
    "worried": "这样真的没问题吗...我有点担心呢。",
    "sighing": "唉...为什么会变成这样呢...真是令人头疼。",
    "alarmed": "等、等一下！这是怎么回事！？",
    "slack_off": "唔...好困...再让我休息一会儿嘛...",
}

def get_emotion_audio(emotion_tag: str):
    """
    根据情感标签获取随机参考音频路径和对应的文本
    
    Args:
        emotion_tag: LLM 返回的情感标签 (如 "happy", "sad")
    
    Returns:
        (audio_path, prompt_text) 或 (None, None) 如果没有匹配的情感
    """
    # 映射到数据集情感
    dataset_emotion = EMOTION_TAG_MAPPING.get(emotion_tag.lower())
    if not dataset_emotion:
        logger.debug(f"情感标签 '{emotion_tag}' 未找到映射，跳过情感参考")
        return None, None
    
    # 获取音频范围
    audio_range = EMOTION_AUDIO_RANGES.get(dataset_emotion)
    if not audio_range:
        return None, None
    
    # 随机选择一个音频
    start_idx, end_idx = audio_range
    random_idx = random.randint(start_idx, end_idx)
    audio_filename = f"sakiko_emo_{random_idx:04d}.wav"
    audio_path = os.path.join(EMOTION_AUDIO_DIR, audio_filename)
    
    # 检查文件是否存在
    if not os.path.exists(audio_path):
        logger.warning(f"情感参考音频不存在: {audio_path}")
        return None, None
    
    # 获取对应的 prompt_text
    prompt_text = EMOTION_PROMPT_TEXTS.get(dataset_emotion)
    if not prompt_text:
        logger.warning(f"情感 '{dataset_emotion}' 没有对应的 prompt_text")
        return None, None
    
    logger.info(f"🎭 情感参考: {emotion_tag} → {dataset_emotion} → {audio_filename}")
    return audio_path, prompt_text
