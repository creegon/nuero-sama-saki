# -*- coding: utf-8 -*-
"""
测试工具调用移除逻辑
"""
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.executor import ToolExecutor

def test_tool_call_removal():
    """测试ToolExecutor.remove_tool_calls()"""
    
    executor = ToolExecutor()
    
    test_cases = [
        ("[CALL:screenshot]", ""),
        ("正常说话 [CALL:screenshot] 然后调用工具", "正常说话  然后调用工具"),
        ("[CALL:web_search:勾股定理]", ""),
        ("前面的话 [CALL:add_knowledge:记忆内容] 后面的话", "前面的话  后面的话"),
        ("没有工具调用", "没有工具调用"),
        ("[pout] 哈？[CALL:screenshot] 看看", "[pout] 哈？ 看看"),
    ]
    
    print("="*60)
    print("工具调用移除测试")
    print("="*60)
    
    all_passed = True
    
    for i, (input_text, expected) in enumerate(test_cases, 1):
        result = executor.remove_tool_calls(input_text)
        
        # 清理多余空格便于比较
        result_clean = re.sub(r'\s+', ' ', result).strip()
        expected_clean = re.sub(r'\s+', ' ', expected).strip()
        
        passed = result_clean == expected_clean
        all_passed = all_passed and passed
        
        status = "PASS" if passed else "FAIL"
        print(f"\n测试 {i}: [{status}]")
        print(f"  输入:   '{input_text}'")
        print(f"  预期:   '{expected_clean}'")
        print(f"  实际:   '{result_clean}'")
        
        if not passed:
            print(f"  [ERROR] 不匹配！")
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ 所有测试通过！")
    else:
        print("❌ 有测试失败！")
    print("="*60)
    
    return all_passed

if __name__ == "__main__":
    test_tool_call_removal()
