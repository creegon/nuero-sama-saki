# -*- coding: utf-8 -*-
"""
Stream Parser Module - Optimized V2
流式输出解析，智能句子合并和情感标签提取

优化点：
1. 最小字数阈值，避免过短句子
2. 颜文字保护，颜文字附加到前一句
3. 智能合并短句
"""

import re
from typing import Optional, Tuple, Generator, List
from loguru import logger


class StreamParser:
    """流式文本解析器（优化版 V3 - 支持多情感标签）"""
    
    # 句子结束标志
    SENTENCE_ENDINGS = ['。', '！', '？', '!', '?', '…']
    
    # 情感标签正则 - 支持句首和句中
    EMOTION_PATTERN = re.compile(r'\[(\w+)\]\s*')
    
    # 颜文字正则（常见模式）
    KAOMOJI_PATTERNS = [
        r'[\(（\[【<＜][^\)）\]】>＞]*[\)）\]】>＞]',  # (xxx) 类型
        r'[\^＾][\._ 。·]*[\^＾]',  # ^.^ 类型
        r'[>＞][_＿<＜]',  # >_< 类型
        r'[TQД口][\._ 。·]*[TQД口]',  # T_T 类型
        r'[OwOUwU0w0QwQ]+',  # OwO 类型
        r'[♪♫♬♩☆★✿❀❤♥]+',  # 符号类型
    ]
    
    # 配置
    MIN_SENTENCE_LENGTH = 12  # 最小句子长度（字符数）
    
    def __init__(self):
        self.buffer = ""
        self.current_emotion: Optional[str] = None
        self._last_output: Optional[str] = None  # 上一个输出的句子
    
    def reset(self):
        """重置状态"""
        self.buffer = ""
        self.current_emotion = None
        self._last_output = None
    
    def _is_mostly_kaomoji(self, text: str) -> bool:
        """检查是否主要是颜文字"""
        cleaned = text
        for pattern in self.KAOMOJI_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned)
        # 去掉颜文字后，剩余有意义的字符很少
        remaining = re.sub(r'[\s\.,!?。！？、~～]+', '', cleaned)
        return len(remaining) <= 3
    
    def _should_merge_with_previous(self, sentence: str) -> bool:
        """判断是否应该与前一句合并"""
        # 纯颜文字或太短
        if self._is_mostly_kaomoji(sentence):
            return True
        if len(sentence) < self.MIN_SENTENCE_LENGTH:
            return True
        return False
    
    def feed(self, chunk: str) -> Generator[Tuple[str, Optional[str]], None, None]:
        """
        喂入文本块，产出完整句子
        
        支持多情感标签：
        - [happy] 嘿嘿~今天心情不错呢。[thinking] 不过...你在干嘛？
        - 会 yield: ("嘿嘿~今天心情不错呢。", "happy"), ("不过...你在干嘛？", "thinking")
        
        Args:
            chunk: 文本片段
            
        Yields:
            (sentence, emotion) - 句子和情感标签
        """
        self.buffer += chunk
        
        # 提取开头的情感标签（如果有）
        match = self.EMOTION_PATTERN.match(self.buffer)
        if match:
            self.current_emotion = match.group(1).lower()
            self.buffer = self.buffer[match.end():]
            logger.debug(f"提取到情感标签: [{self.current_emotion}]")
        
        # 收集所有句子
        sentences = []
        while True:
            sentence, remaining, new_emotion = self._extract_sentence_with_emotion(self.buffer)
            if sentence:
                self.buffer = remaining
                sentences.append((sentence, self.current_emotion))
                # 更新情绪用于下一句
                if new_emotion:
                    self.current_emotion = new_emotion
            else:
                break
        
        # 智能合并句子
        merged = self._merge_sentences_with_emotion(sentences)
        for s, e in merged:
            self._last_output = s
            yield (s, e)
    
    def _extract_sentence_with_emotion(self, text: str) -> Tuple[Optional[str], str, Optional[str]]:
        """
        提取第一个完整句子，同时检查是否有新的情感标签
        
        Returns:
            (sentence, remaining, new_emotion) - 句子、剩余文本、新情感标签
        """
        if not text:
            return None, "", None
        
        # 找到最近的句子结束符
        min_pos = -1
        for ending in self.SENTENCE_ENDINGS:
            pos = text.find(ending)
            if pos != -1:
                if min_pos == -1 or pos < min_pos:
                    min_pos = pos
        
        if min_pos != -1:
            # 包含结束符
            sentence = text[:min_pos + 1].strip()
            remaining = text[min_pos + 1:].strip()
            
            # 检查剩余文本开头是否有新的情感标签
            new_emotion = None
            if remaining:
                match = self.EMOTION_PATTERN.match(remaining)
                if match:
                    new_emotion = match.group(1).lower()
                    remaining = remaining[match.end():]
                    logger.debug(f"句中提取到新情感标签: [{new_emotion}]")
            
            return sentence, remaining, new_emotion
        
        return None, text, None
    
    def _merge_sentences(self, sentences: List[str]) -> List[str]:
        """智能合并句子"""
        if not sentences:
            return []
        
        result = []
        current = ""
        
        for s in sentences:
            if not current:
                current = s
            elif self._should_merge_with_previous(s):
                # 合并到当前句子
                current += s
            elif self._should_merge_with_previous(current):
                # 当前句子太短，和新句子合并
                current += s
            else:
                # 输出当前句子，开始新的
                result.append(current)
                current = s
        
        # 如果当前句子足够长或者是最后一个，加入结果
        if current:
            if len(current) >= self.MIN_SENTENCE_LENGTH or not self._is_mostly_kaomoji(current):
                result.append(current)
            elif result:
                # 太短就附加到上一个
                result[-1] += current
            else:
                # 没有其他句子，只能输出
                result.append(current)
        
        return result
    
    def _merge_sentences_with_emotion(self, sentences: List[Tuple[str, Optional[str]]]) -> List[Tuple[str, Optional[str]]]:
        """智能合并句子（带情感标签版本）"""
        if not sentences:
            return []
        
        result = []
        current_text = ""
        current_emotion = None
        
        for text, emotion in sentences:
            if not current_text:
                current_text = text
                current_emotion = emotion
            elif self._should_merge_with_previous(text):
                # 合并到当前句子（保持原情绪）
                current_text += text
            elif self._should_merge_with_previous(current_text):
                # 当前句子太短，和新句子合并（使用新情绪）
                current_text += text
                if emotion:
                    current_emotion = emotion
            else:
                # 输出当前句子，开始新的
                result.append((current_text, current_emotion))
                current_text = text
                current_emotion = emotion
        
        # 处理最后一个
        if current_text:
            if len(current_text) >= self.MIN_SENTENCE_LENGTH or not self._is_mostly_kaomoji(current_text):
                result.append((current_text, current_emotion))
            elif result:
                # 太短就附加到上一个
                last_text, last_emotion = result[-1]
                result[-1] = (last_text + current_text, last_emotion)
            else:
                # 没有其他句子，只能输出
                result.append((current_text, current_emotion))
        
        return result
    
    def _extract_sentence(self, text: str) -> Tuple[Optional[str], str]:
        """
        提取第一个完整句子
        
        Returns:
            (sentence, remaining) - 句子和剩余文本
        """
        if not text:
            return None, ""
        
        # 找到最近的句子结束符
        min_pos = -1
        for ending in self.SENTENCE_ENDINGS:
            pos = text.find(ending)
            if pos != -1:
                if min_pos == -1 or pos < min_pos:
                    min_pos = pos
        
        if min_pos != -1:
            # 包含结束符
            sentence = text[:min_pos + 1].strip()
            remaining = text[min_pos + 1:].strip()
            return sentence, remaining
        
        return None, text
    
    def flush(self) -> Optional[Tuple[str, Optional[str]]]:
        """
        刷新缓冲区，返回剩余内容
        
        Returns:
            (sentence, emotion) 或 None
        """
        remaining = self.buffer.strip()
        self.buffer = ""
        
        if not remaining:
            return None
        
        # 如果剩余内容主要是颜文字或太短，尝试不单独输出
        if self._is_mostly_kaomoji(remaining) and len(remaining) < 10:
            # 太短的颜文字就丢弃或附加到 last_output（但这里无法修改已输出的）
            # 实际上这种情况下应该在 feed 阶段处理好
            pass
        
        return (remaining, self.current_emotion)
    
    def get_emotion(self) -> Optional[str]:
        """获取当前情感标签"""
        return self.current_emotion


def split_text_to_sentences(text: str, min_length: int = 12) -> List[Tuple[str, Optional[str]]]:
    """
    将文本分割为句子列表（同步版本）
    
    Args:
        text: 完整文本
        min_length: 最小句子长度
        
    Returns:
        [(sentence, emotion), ...] 列表
    """
    parser = StreamParser()
    parser.MIN_SENTENCE_LENGTH = min_length
    
    sentences = list(parser.feed(text))
    final = parser.flush()
    if final and final[0].strip():
        # 检查是否应该合并到上一个
        if sentences and parser._is_mostly_kaomoji(final[0]):
            # 合并到最后一个句子
            last_text, last_emotion = sentences[-1]
            sentences[-1] = (last_text + final[0], last_emotion)
        else:
            sentences.append(final)
    return sentences


if __name__ == "__main__":
    # 测试
    test_cases = [
        "[pout] 哈？你叫我？本神明现在忙着呢...开玩笑的，怎么了。",
        "[thinking] 嗯...让我想想。这个问题有点复杂呢！",
        "[surprised] 哇！真的吗？太厉害了！(≧▽≦)",
        "[happy] 你好！我很开心！",
        "[neutral] 是的。好的。知道了。明白。",
        # 多标签测试
        "[happy] 嘿嘿~今天心情不错呢。[thinking] 不过...你在干嘛？",
        "[curious] 欸？[surprised] 诶诶诶！？这是什么！",
        "[neutral] 嗯...是这样吗。[happy] 唔，突然想笑了！[confused] 不对，好像哪里怪怪的。",
    ]
    
    print("=" * 60)
    print("优化版句子分割测试 V3 - 支持多情感标签")
    print("=" * 60)
    
    for text in test_cases:
        print(f"\n输入: {text}")
        print("-" * 40)
        sentences = split_text_to_sentences(text)
        for i, (s, e) in enumerate(sentences, 1):
            print(f"  句子 {i}: [{e}] {s} ({len(s)}字)")

