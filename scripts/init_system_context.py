# -*- coding: utf-8 -*-
"""
初始化系统上下文到知识库

这些是 AI 需要知道的背景信息，但不需要放在 System Prompt 中
可以随时修改，不需要改代码
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge import get_knowledge_base

# 系统上下文条目
SYSTEM_CONTEXT_ENTRIES = [
    {
        "text": "主人的麦克风质量不太好，语音识别可能会有同音错字",
        "metadata": {"category": "system", "topic": "mic"}
    },
    {
        "text": "语音识别输出没有标点符号，长句子可能比较难读",
        "metadata": {"category": "system", "topic": "stt"}
    },
]


def init_system_context(force: bool = False):
    """
    初始化系统上下文
    
    Args:
        force: 是否强制重新添加（会先删除已有的 system 条目）
    """
    print("正在初始化系统上下文...")
    kb = get_knowledge_base()
    
    if force:
        # 删除已有的 system 条目
        print("清理已有的 system 条目...")
        try:
            all_rows = kb._table.to_pandas()
            import json
            for _, row in all_rows.iterrows():
                try:
                    metadata = json.loads(row.get("metadata", "{}"))
                    if metadata.get("category") == "system":
                        kb.delete(row.get("id"))
                        print(f"  删除: {row.get('id')}")
                except:
                    pass
        except Exception as e:
            print(f"清理失败: {e}")
    
    # 添加新条目
    print("添加系统上下文条目...")
    for entry in SYSTEM_CONTEXT_ENTRIES:
        doc_id = kb.add(entry["text"], entry["metadata"])
        print(f"  添加: [{doc_id}] {entry['text'][:30]}...")
    
    print(f"\n完成! 知识库现有 {kb.count()} 条记录")
    
    # 验证
    print("\n验证系统上下文:")
    context = kb.get_system_context()
    print(context if context else "(空)")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="强制重新初始化")
    args = parser.parse_args()
    
    init_system_context(force=args.force)
