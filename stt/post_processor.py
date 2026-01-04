# -*- coding: utf-8 -*-
"""
STT 后处理模块

基于规则的语音识别结果后处理，提高准确率。
不依赖大模型，纯机械规则处理。
"""

import re
from typing import List, Tuple, Optional
from loguru import logger


# ====================
# 同音字/常见错误纠正规则
# ====================
# 格式: {"错误词": "正确词"}
CORRECTION_RULES = {
    # ========== 角色相关（根据你的角色调整）==========
    # 如果角色叫"小祥"，常见错误可能是：
    # "小象": "小祥",
    # "小翔": "小祥",
    # "晓祥": "小祥",
    
    # ========== 常见同音错误 ==========
    "在吗": "在嘛",
    "那这": "那这",
    "那这样": "那这样",
    
    # ========== 口语习惯纠正 ==========
    "木有": "没有",
    "酱紫": "这样子",
    "表": "不要",
    
    # ========== 技术词汇（如果你的项目涉及）==========
    # "派森": "Python",
    # "机ava": "Java",
}


# ====================
# 语气词/填充词
# ====================
# 开头需要移除的语气词
REMOVE_PREFIXES = [
    "嗯", "啊", "呃", "额", "哦", "噢",
    "那个", "就是说", "就是", "然后", "所以说", "所以",
    "我说", "你看", "你说",
]

# 结尾需要移除的语气词
REMOVE_SUFFIXES = [
    "啊", "呀", "呢", "吧", "嘛", "哦", "哈", "嗯",
    "的话", "这样", "这样子",
]


# ====================
# 敏感词/过滤词（可选）
# ====================
FILTER_WORDS = [
    # 如果 ASR 经常把某些噪音识别成特定词，可以在这里过滤
    # "咳咳",
    # "嗯嗯嗯",
]


class STTPostProcessor:
    """STT 后处理器"""
    
    def __init__(
        self,
        enable_correction: bool = True,
        enable_remove_filler: bool = True,
        enable_remove_stutter: bool = True,
        enable_normalize: bool = True,
        custom_corrections: Optional[dict] = None,
    ):
        """
        初始化后处理器
        
        Args:
            enable_correction: 启用同音字纠错
            enable_remove_filler: 启用语气词移除
            enable_remove_stutter: 启用去重（口吃）
            enable_normalize: 启用文本规范化
            custom_corrections: 自定义纠错规则
        """
        self.enable_correction = enable_correction
        self.enable_remove_filler = enable_remove_filler
        self.enable_remove_stutter = enable_remove_stutter
        self.enable_normalize = enable_normalize
        
        # 合并自定义规则
        self.corrections = CORRECTION_RULES.copy()
        if custom_corrections:
            self.corrections.update(custom_corrections)
    
    def process(self, text: str) -> str:
        """
        处理识别结果
        
        Args:
            text: 原始识别文本
            
        Returns:
            处理后的文本
        """
        if not text or not text.strip():
            return ""
        
        original = text
        
        # 1. 基础清理
        text = self._basic_clean(text)
        
        # 2. 去除口吃/重复
        if self.enable_remove_stutter:
            text = self._remove_stutter(text)
        
        # 3. 移除开头/结尾语气词
        if self.enable_remove_filler:
            text = self._remove_filler_words(text)
        
        # 4. 同音字纠错
        if self.enable_correction:
            text = self._apply_corrections(text)
        
        # 5. 文本规范化
        if self.enable_normalize:
            text = self._normalize(text)
        
        # 6. 过滤词
        text = self._filter_words(text)
        
        # 记录处理结果
        if text != original:
            logger.debug(f"后处理: '{original}' -> '{text}'")
        
        return text.strip()
    
    def _basic_clean(self, text: str) -> str:
        """基础清理"""
        # 去除多余空格
        text = re.sub(r'\s+', ' ', text)
        # 去除首尾空格
        text = text.strip()
        return text
    
    def _remove_stutter(self, text: str) -> str:
        """去除口吃/重复"""
        # 连续相同字符（3个以上）-> 保留1个
        # 例如: "我我我想" -> "我想"
        text = re.sub(r'(.)\1{2,}', r'\1', text)
        
        # 连续相同词语（2个以上）-> 保留1个
        # 例如: "那个那个那个" -> "那个"
        # 这个规则比较复杂，先用简单版本
        for word in ["那个", "就是", "然后", "所以"]:
            pattern = f"({re.escape(word)}){{2,}}"
            text = re.sub(pattern, word, text)
        
        return text
    
    def _remove_filler_words(self, text: str) -> str:
        """移除语气词/填充词"""
        # 移除开头语气词
        for prefix in REMOVE_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix):].lstrip()
                # 可能有多个，继续检查
                break
        
        # 再检查一次（处理连续的情况）
        for prefix in REMOVE_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix):].lstrip()
                break
        
        # 移除结尾语气词
        for suffix in REMOVE_SUFFIXES:
            if text.endswith(suffix) and len(text) > len(suffix):
                text = text[:-len(suffix)].rstrip()
                break
        
        return text
    
    def _apply_corrections(self, text: str) -> str:
        """应用同音字纠错"""
        for wrong, correct in self.corrections.items():
            text = text.replace(wrong, correct)
        return text
    
    def _normalize(self, text: str) -> str:
        """文本规范化"""
        # 全角转半角（标点符号）
        text = self._fullwidth_to_halfwidth_punctuation(text)
        
        # 英文字母统一小写（可选，根据需求）
        # text = self._normalize_english(text)
        
        return text
    
    def _fullwidth_to_halfwidth_punctuation(self, text: str) -> str:
        """全角标点转半角"""
        mapping = {
            '，': ',',
            '。': '.',
            '！': '!',
            '？': '?',
            '：': ':',
            '；': ';',
            '"': '"',
            '"': '"',
            ''': "'",
            ''': "'",
        }
        for full, half in mapping.items():
            text = text.replace(full, half)
        return text
    
    def _filter_words(self, text: str) -> str:
        """过滤特定词语"""
        for word in FILTER_WORDS:
            text = text.replace(word, "")
        return text
    
    def add_correction(self, wrong: str, correct: str):
        """添加纠错规则"""
        self.corrections[wrong] = correct
    
    def add_corrections(self, rules: dict):
        """批量添加纠错规则"""
        self.corrections.update(rules)


# 全局单例
_processor = None


def get_post_processor() -> STTPostProcessor:
    """获取全局后处理器实例"""
    global _processor
    if _processor is None:
        # 从 config 读取配置
        try:
            import config
            enabled = getattr(config, 'STT_POST_PROCESS', True)
            custom_corrections = getattr(config, 'STT_CUSTOM_CORRECTIONS', {})
        except ImportError:
            enabled = True
            custom_corrections = {}
        
        if not enabled:
            # 禁用后处理时，创建一个空处理器
            _processor = STTPostProcessor(
                enable_correction=False,
                enable_remove_filler=False,
                enable_remove_stutter=False,
                enable_normalize=False,
            )
        else:
            _processor = STTPostProcessor(
                custom_corrections=custom_corrections
            )
    return _processor


def post_process(text: str) -> str:
    """快捷后处理函数"""
    return get_post_processor().process(text)


# ====================
# 测试
# ====================
if __name__ == "__main__":
    processor = STTPostProcessor()
    
    test_cases = [
        "嗯那个我想问一下",
        "我我我想要这个",
        "那个那个那个你好",
        "今天天气怎么样啊",
        "小象你好",  # 如果添加了角色名纠错
        "   多余空格   会被清理   ",
        "木有问题酱紫可以表着急",
    ]
    
    print("=" * 50)
    print("STT 后处理测试")
    print("=" * 50)
    
    for text in test_cases:
        result = processor.process(text)
        print(f"输入: '{text}'")
        print(f"输出: '{result}'")
        print("-" * 30)
