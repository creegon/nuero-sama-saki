# -*- coding: utf-8 -*-
"""
测试情绪标签解析和移除
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.emotion_parser import EmotionParser
from tools.executor import get_tool_executor

def test_emotion_parsing():
    """测试不同情绪标签组合的解析"""
    
    # 关键：传入 tool_executor 以确保工具调用被移除！
    tool_executor = get_tool_executor()
    parser = EmotionParser(tool_executor=tool_executor)
    
    test_cases = [
        # (输入文本, 预期分段数, 描述)
        (
            "[pout] 哈？你居然在背地里吐槽本神明的语音？[angry] 那种事是程序的问题吧，跟我有什么关系嘛！",
            2,
            "两个连续情绪标签"
        ),
        (
            "[happy] 今天天气不错！",
            1,
            "单个情绪标签"
        ),
        (
            "[thinking] 嗯... [surprised] 诶？居然是这样！",
            2,
            "包含省略号的情绪切换"
        ),
        (
            "[neutral] 正常说话 [CALL:screenshot] 然后调用工具",
            1,
            "包含工具调用（工具调用应该被移除）"
        ),
        (
            "[sad] 好吧。[embarrassed] 其实...有点不好意思。",
            2,
            "多标点符号"
        ),
    ]
    
    print("="*60)
    print("情绪标签解析测试")
    print("="*60)
    
    for i, (text, expected_segments, desc) in enumerate(test_cases, 1):
        print(f"\n测试 {i}: {desc}")
        print(f"输入: {text}")
        print("-" * 60)
        
        segments = parser.split_by_emotion(text)
        
        print(f"分段数: {len(segments)} (预期: {expected_segments})")
        
        for j, (emotion, segment_text) in enumerate(segments, 1):
            print(f"  段 {j}:")
            print(f"    情绪: {emotion}")
            print(f"    文本: '{segment_text}'")
            
            # 检查是否还有情绪标签残留
            if any(tag in segment_text for tag in ["happy", "sad", "angry", "pout", "thinking", "surprised", "neutral", "embarrassed"]):
                print(f"    [WARNING] 文本中仍包含情绪标签！")
            
            # 检查是否有工具调用残留
            if "CALL:" in segment_text:
                print(f"    [ERROR] 文本中仍包含工具调用！<-- BUG")
            
            # 检查空白处理
            if "  " in segment_text:  # 检查连续空格
                print(f"    [WARNING] 文本中有连续空格！")
        
        print()
    
    print("="*60)
    print("测试完成")
    print("="*60)

if __name__ == "__main__":
    test_emotion_parsing()
