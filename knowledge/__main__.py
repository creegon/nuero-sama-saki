# -*- coding: utf-8 -*-
"""
知识库模块入口 - 运行测试

注意：必须在导入任何其他库之前设置 TensorFlow 禁用环境变量
"""

# ========== 关键：必须在所有 import 之前禁用 TensorFlow ==========
import os
os.environ["TRANSFORMERS_NO_TF"] = "1"  # 禁用 TensorFlow 后端
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"  # 抑制 TensorFlow 日志
os.environ["USE_TF"] = "0"  # 额外保险
os.environ["USE_TORCH"] = "1"  # 明确使用 PyTorch
# ================================================================

if __name__ == "__main__":
    import sys
    import tempfile
    import shutil
    
    # 确保可以导入
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from knowledge import KnowledgeBase
    
    print("=" * 50)
    print("知识库语义搜索测试 (LanceDB)")
    print("=" * 50)
    
    # 使用临时目录测试
    test_dir = tempfile.mkdtemp(prefix="lancedb_test_")
    print(f"\n测试目录: {test_dir}")
    
    kb = KnowledgeBase(persist_directory=test_dir, collection_name="test_kb_extended")
    
    # 添加更多样化的测试数据
    print("\n[1] 添加丰富知识库数据...")
    knowledge_data = [
        # 基础信息
        {"text": "祥子是月之森女子学园的高中生，目前就读于音乐科。", "metadata": {"category": "profile"}},
        {"text": "丰川祥子曾经是CRYCHIC乐队的键盘手，现在组建了Ave Mujica。", "metadata": {"category": "career"}},
        
        # 喜好与习惯 - 变式表达
        {"text": "对于甜点，祥子尤其钟爱草莓蛋糕，觉得那是治愈心灵的美味。", "metadata": {"category": "preference"}},
        {"text": "闲暇时光，祥子喜欢品尝红茶，对茶叶的品质很有研究。", "metadata": {"category": "preference"}},
        {"text": "她讨厌被叫错名字，对礼仪非常看重。", "metadata": {"category": "personality"}},

        # 人际关系
        {"text": "若叶睦是祥子的青梅竹马，两人从小就认识。", "metadata": {"category": "relationship"}},
        {"text": "祥子对高松灯有着复杂的情感，曾经邀请她加入乐队。", "metadata": {"category": "relationship"}},
        {"text": "实际上，祥子非常疼爱自己的妹妹，也就是丰川睦。", "metadata": {"category": "family"}}, # 故意制造命名混淆测试语义
        
        # 性格特征 - 抽象描述
        {"text": "她表面上看起来高傲冷淡，实际上背负着沉重的家庭压力。", "metadata": {"category": "personality"}},
        {"text": "祥子是一个完美主义者，对自己和队友的要求都极高，容不得半点失误。", "metadata": {"category": "personality"}},
        {"text": "在落魄的时候，祥子也展现出了惊人的行动力和领导才能。", "metadata": {"category": "personality"}},
    ]
    
    kb.add_batch(knowledge_data)
    
    print(f"   当前知识库条目数: {kb.count()}")
    
    # 搜索测试 - 测试语义理解能力
    print("\n[2] 语义搜索测试 (验证非关键词匹配能力)...")
    
    test_cases = [
        {
            "query": "她平时喝什么饮料？", 
            "intent": "匹配红茶相关",
            "expect_keyword": "红茶"
        },
        {
            "query": "祥子会在乐队里负责什么位置？",
            "intent": "匹配乐器/职位",
            "expect_keyword": "键盘手"
        },
        {
            "query": "她和睦的关系怎么样？",
            "intent": "匹配青梅竹马/妹妹",
            "expect_keyword": "青梅竹马"
        },
        {
            "query": "祥子的性格特点是什么？",
            "intent": "匹配性格描述",
            "expect_keyword": "高傲"
        },
        {
            "query": "她最喜欢的甜食是啥？",
            "intent": "同义词测试(甜食->甜点)",
            "expect_keyword": "草莓蛋糕"
        }
    ]
    
    for case in test_cases:
        query = case["query"]
        print(f"\n   Q: {query} ({case['intent']})")
        results = kb.search(query, n_results=2)
        
        for i, r in enumerate(results):
            # 检查是否包含预期关键词
            hit = "✅" if case["expect_keyword"] in r["text"] else "  "
            print(f"      {hit} [{r['distance']:.4f}] {r['text']}")
            
    # LLM 上下文生成测试
    print("\n[3] 模拟 LLM 上下文注入...")
    complex_query = "祥子为什么看起来那么严肃？她有什么经历吗？"
    print(f"   用户问题: {complex_query}")
    context = kb.get_context_for_llm(complex_query, n_results=3)
    print("   --- 生成的上下文 ---")
    print(context)
    print("   --------------------")
    
    # 清理
    shutil.rmtree(test_dir, ignore_errors=True)
    
    print("\n" + "=" * 50)
    print("深度测试完成!")
