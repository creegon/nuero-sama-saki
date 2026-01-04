# -*- coding: utf-8 -*-
"""测试 _split_by_emotion 分段逻辑"""

import re
import sys
sys.path.insert(0, 'd:/neruo')

from llm.character_prompt import EMOTION_TAGS
from tools.executor import get_tool_executor

executor = get_tool_executor()

text = '[shy] 呜……那只是... [pout] [CALL:screenshot] 不许盯着我看'
print(f'原文: {text}')

# 移除工具调用
clean = executor.remove_tool_calls(text)
print(f'移除工具后: {clean}')

# 匹配情绪标签
emotion_pattern = r'\[(' + '|'.join(EMOTION_TAGS) + r')\]'
matches = list(re.finditer(emotion_pattern, clean, re.IGNORECASE))
print(f'找到 {len(matches)} 个标签: {[m.group(1) for m in matches]}')

# 分段
segments = []
for i, match in enumerate(matches):
    emotion = match.group(1).lower()
    start = match.end()
    if i + 1 < len(matches):
        end = matches[i + 1].start()
    else:
        end = len(clean)
    segment_text = clean[start:end].strip()
    print(f'  [{emotion}] pos {start}-{end}: "{segment_text}"')
    if segment_text:
        segments.append((emotion, segment_text))

print(f'\n最终分段: {segments}')
