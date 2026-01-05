# -*- coding: utf-8 -*-
"""分析知识库内容，找出记忆系统的不足"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

import json
from knowledge import get_knowledge_base

def analyze_knowledge():
    kb = get_knowledge_base()
    all_data = kb._table.to_pandas()
    
    print(f'=== 知识库共 {len(all_data)} 条记忆 ===\n')
    
    # 按类型分组统计
    categories = {}
    sources = {}
    importance_dist = {
        '低 (1.0-2.0)': 0,
        '中 (2.1-4.0)': 0,
        '高 (4.1-6.0)': 0,
        '极高 (6.1+)': 0
    }
    
    all_records = []
    
    for i, (_, row) in enumerate(all_data.iterrows()):
        doc_id = row['id']
        text = row.get('text', '')
        meta = row.get('metadata', '{}')
        try:
            meta = json.loads(meta) if isinstance(meta, str) else meta
        except:
            meta = {}
        
        cat = meta.get('category', 'unknown')
        src = meta.get('source', 'unknown')
        imp = meta.get('importance', 1.0)
        
        categories[cat] = categories.get(cat, 0) + 1
        sources[src] = sources.get(src, 0) + 1
        
        if imp <= 2.0:
            importance_dist['低 (1.0-2.0)'] += 1
        elif imp <= 4.0:
            importance_dist['中 (2.1-4.0)'] += 1
        elif imp <= 6.0:
            importance_dist['高 (4.1-6.0)'] += 1
        else:
            importance_dist['极高 (6.1+)'] += 1
        
        all_records.append({
            'id': doc_id,
            'text': text,
            'category': cat,
            'source': src,
            'importance': imp,
            'context': meta.get('context', ''),
            'timestamp': meta.get('timestamp', '')
        })
    
    print('=== 按类型统计 ===')
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f'  {cat}: {count}')
    
    print('\n=== 按来源统计 ===')
    for src, count in sorted(sources.items(), key=lambda x: -x[1]):
        print(f'  {src}: {count}')
    
    print('\n=== 按重要性分布 ===')
    for level, count in importance_dist.items():
        print(f'  {level}: {count}')
    
    print('\n=== 高重要性记忆样本 (importance > 4.0) ===')
    high_imp = [r for r in all_records if r['importance'] > 4.0]
    for r in high_imp[:10]:
        print(f"[{r['category']}] imp={r['importance']:.1f} src={r['source']}")
        print(f"  内容: {r['text'][:150]}")
        if r['context']:
            print(f"  上下文: {r['context'][:100]}")
        print()
    
    print('\n=== 最近10条记忆 ===')
    for r in all_records[-10:]:
        print(f"[{r['category']}] imp={r['importance']:.1f} src={r['source']}")
        print(f"  内容: {r['text'][:150]}")
        print()
    
    # 找出潜在问题
    print('\n=== 潜在问题分析 ===')
    
    # 1. 检查重复或相似内容
    texts = [r['text'] for r in all_records]
    duplicates = []
    for i, t1 in enumerate(texts):
        for j, t2 in enumerate(texts[i+1:], i+1):
            if t1 and t2 and (t1 in t2 or t2 in t1):
                duplicates.append((i, j, t1[:50], t2[:50]))
    
    if duplicates:
        print(f'\n1. 发现 {len(duplicates)} 对可能重复的记忆:')
        for i, j, t1, t2 in duplicates[:5]:
            print(f"   记忆{i} vs 记忆{j}")
            print(f"     A: {t1}...")
            print(f"     B: {t2}...")
    else:
        print('\n1. 未发现明显重复记忆')
    
    # 2. 检查空内容或极短内容
    short_records = [r for r in all_records if len(r['text'].strip()) < 10]
    if short_records:
        print(f'\n2. 发现 {len(short_records)} 条极短记忆 (<10字符):')
        for r in short_records[:5]:
            print(f"   [{r['category']}] {repr(r['text'])}")
    else:
        print('\n2. 未发现极短记忆')
    
    # 3. 检查缺失元数据
    missing_meta = [r for r in all_records if r['category'] == 'unknown' or r['source'] == 'unknown']
    if missing_meta:
        print(f'\n3. 发现 {len(missing_meta)} 条缺失分类或来源的记忆')
    else:
        print('\n3. 所有记忆都有完整的分类和来源')
    
    # 4. 分析对话记忆 vs 事实记忆比例
    episodic = categories.get('episode', 0) + categories.get('conversation', 0)
    factual = categories.get('fact', 0) + categories.get('preference', 0) + categories.get('personal_info', 0)
    print(f'\n4. 对话记忆 vs 事实记忆比例: {episodic} : {factual}')
    
    return all_records

if __name__ == '__main__':
    analyze_knowledge()
