# -*- coding: utf-8 -*-
"""
知识库管理工具 - 交互式界面

提供以下功能：
1. 查看所有记忆
2. 搜索记忆
3. 添加记忆
4. 更新记忆
5. 删除记忆
6. 导出记忆

使用方法：
    python scripts/manage_knowledge.py
"""

import sys
import os
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge import get_knowledge_base, create_memory_manager


def show_menu():
    """显示主菜单"""
    print("\n" + "=" * 50)
    print("🧠 小祥知识库管理工具")
    print("=" * 50)
    print("1. 📋 查看所有记忆")
    print("2. 🔍 搜索记忆")
    print("3. ➕ 添加记忆")
    print("4. ✏️  更新记忆")
    print("5. 🗑️  删除记忆")
    print("6. 📊 统计信息")
    print("7. 💾 导出记忆 (JSON)")
    print("0. 退出")
    print("-" * 50)
    return input("请选择操作 [0-7]: ").strip()


def list_all_memories(kb):
    """列出所有记忆"""
    try:
        all_data = kb._table.to_pandas()
        count = len(all_data)
        
        if count == 0:
            print("\n📭 知识库为空")
            return
        
        print(f"\n📋 共 {count} 条记忆:\n")
        
        for _, row in all_data.iterrows():
            doc_id = row['id']
            text = row.get('text', '')
            metadata = row.get('metadata', '{}')
            importance = row.get('importance', 1.0)
            
            # 解析 metadata
            try:
                meta = json.loads(metadata) if isinstance(metadata, str) else metadata
                category = meta.get('category', 'unknown')
            except:
                category = 'unknown'
            
            # 显示记忆
            category_emoji = {
                'core': '⭐',
                'fact': '📝',
                'preference': '❤️',
                'unknown': '❓'
            }.get(category, '📝')
            
            print(f"{category_emoji} [{doc_id}] (重要性: {importance:.1f})")
            print(f"   {text}")
            print()
            
    except Exception as e:
        print(f"❌ 读取失败: {e}")


def search_memories(kb):
    """搜索记忆"""
    query = input("\n🔍 输入搜索关键词: ").strip()
    if not query:
        print("❌ 搜索词不能为空")
        return
    
    try:
        n = input("返回结果数量 (默认 5): ").strip()
        n_results = int(n) if n else 5
    except:
        n_results = 5
    
    try:
        results = kb.search(query, n_results=n_results)
        
        if not results:
            print(f"\n📭 未找到与 '{query}' 相关的记忆")
            return
        
        print(f"\n🔍 搜索 '{query}' 的结果:\n")
        
        for r in results:
            doc_id = r['id']
            text = r['text']
            distance = r.get('distance', 0)
            
            # 距离越小，相似度越高
            similarity = max(0, 1 - distance / 2)  # 粗略估算
            
            print(f"📝 [{doc_id}] (相似度: {similarity:.1%})")
            print(f"   {text}")
            print()
            
    except Exception as e:
        print(f"❌ 搜索失败: {e}")


def add_memory(kb):
    """添加新记忆"""
    print("\n➕ 添加新记忆")
    print("-" * 30)
    
    text = input("记忆内容 (建议用第一人称 '我知道...'): ").strip()
    if not text:
        print("❌ 内容不能为空")
        return
    
    print("\n选择记忆类型:")
    print("  1. fact - 事实记忆 (默认)")
    print("  2. core - 核心记忆 (永不遗忘)")
    print("  3. preference - 偏好记忆")
    
    type_choice = input("类型 [1-3, 默认 1]: ").strip()
    category = {
        '1': 'fact',
        '2': 'core', 
        '3': 'preference'
    }.get(type_choice, 'fact')
    
    try:
        doc_id = kb.add(
            text=text,
            metadata={
                "category": category,
                "source": "manual",
                "verified": True
            }
        )
        print(f"\n✅ 记忆已添加: [{doc_id}]")
        print(f"   类型: {category}")
        print(f"   内容: {text}")
        
    except Exception as e:
        print(f"❌ 添加失败: {e}")


def update_memory(kb):
    """更新记忆"""
    print("\n✏️  更新记忆")
    print("-" * 30)
    
    doc_id = input("输入要更新的记忆 ID: ").strip()
    if not doc_id:
        print("❌ ID 不能为空")
        return
    
    # 先显示当前内容
    try:
        all_data = kb._table.to_pandas()
        found = False
        old_text = ""
        
        for _, row in all_data.iterrows():
            if row['id'] == doc_id:
                old_text = row.get('text', '')
                print(f"\n📝 当前内容: {old_text}")
                found = True
                break
        
        if not found:
            print(f"❌ 未找到 ID: {doc_id}")
            return
            
    except Exception as e:
        print(f"❌ 读取失败: {e}")
        return
    
    new_text = input("输入新内容: ").strip()
    if not new_text:
        print("❌ 新内容不能为空")
        return
    
    try:
        manager = create_memory_manager(kb)
        success = manager.update_text(doc_id, new_text)
        
        if success:
            print(f"\n✅ 记忆已更新: [{doc_id}]")
            print(f"   旧内容: {old_text}")
            print(f"   新内容: {new_text}")
        else:
            print(f"❌ 更新失败")
            
    except Exception as e:
        print(f"❌ 更新失败: {e}")


def delete_memory(kb):
    """删除记忆"""
    print("\n🗑️  删除记忆")
    print("-" * 30)
    
    doc_id = input("输入要删除的记忆 ID: ").strip()
    if not doc_id:
        print("❌ ID 不能为空")
        return
    
    # 先显示内容确认
    try:
        all_data = kb._table.to_pandas()
        found = False
        text = ""
        is_core = False
        
        for _, row in all_data.iterrows():
            if row['id'] == doc_id:
                text = row.get('text', '')
                metadata = row.get('metadata', '{}')
                try:
                    meta = json.loads(metadata) if isinstance(metadata, str) else metadata
                    is_core = meta.get('category') == 'core'
                except:
                    pass
                print(f"\n📝 将要删除: {text}")
                found = True
                break
        
        if not found:
            print(f"❌ 未找到 ID: {doc_id}")
            return
        
        if is_core:
            print("⚠️  警告: 这是核心记忆!")
            
    except Exception as e:
        print(f"❌ 读取失败: {e}")
        return
    
    confirm = input("确认删除? (y/N): ").strip().lower()
    if confirm != 'y':
        print("❌ 已取消")
        return
    
    try:
        kb.delete(doc_id)
        print(f"\n✅ 记忆已删除: [{doc_id}]")
        
    except Exception as e:
        print(f"❌ 删除失败: {e}")


def show_stats(kb):
    """显示统计信息"""
    try:
        all_data = kb._table.to_pandas()
        count = len(all_data)
        
        print(f"\n📊 知识库统计")
        print("-" * 30)
        print(f"总记忆数: {count}")
        
        if count == 0:
            return
        
        # 统计类型
        categories = {'core': 0, 'fact': 0, 'preference': 0, 'other': 0}
        
        for _, row in all_data.iterrows():
            metadata = row.get('metadata', '{}')
            try:
                meta = json.loads(metadata) if isinstance(metadata, str) else metadata
                cat = meta.get('category', 'other')
                if cat in categories:
                    categories[cat] += 1
                else:
                    categories['other'] += 1
            except:
                categories['other'] += 1
        
        print(f"\n按类型统计:")
        print(f"  ⭐ 核心记忆 (core): {categories['core']}")
        print(f"  📝 事实记忆 (fact): {categories['fact']}")
        print(f"  ❤️  偏好记忆 (preference): {categories['preference']}")
        print(f"  ❓ 其他: {categories['other']}")
        
    except Exception as e:
        print(f"❌ 统计失败: {e}")


def export_memories(kb):
    """导出记忆为 JSON"""
    try:
        all_data = kb._table.to_pandas()
        
        if len(all_data) == 0:
            print("\n📭 知识库为空，无法导出")
            return
        
        # 转换为可序列化格式
        memories = []
        for _, row in all_data.iterrows():
            metadata = row.get('metadata', '{}')
            try:
                meta = json.loads(metadata) if isinstance(metadata, str) else metadata
            except:
                meta = {}
            
            memories.append({
                "id": row['id'],
                "text": row.get('text', ''),
                "importance": float(row.get('importance', 1.0)),
                "metadata": meta
            })
        
        # 保存文件
        output_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "knowledge_export.json"
        )
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(memories, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 已导出 {len(memories)} 条记忆到:")
        print(f"   {output_path}")
        
    except Exception as e:
        print(f"❌ 导出失败: {e}")


def main():
    """主函数"""
    print("\n🚀 正在加载知识库...")
    
    try:
        kb = get_knowledge_base()
        print(f"✅ 知识库加载成功 (共 {kb.count()} 条记忆)")
    except Exception as e:
        print(f"❌ 知识库加载失败: {e}")
        return
    
    while True:
        choice = show_menu()
        
        if choice == '0':
            print("\n👋 再见!")
            break
        elif choice == '1':
            list_all_memories(kb)
        elif choice == '2':
            search_memories(kb)
        elif choice == '3':
            add_memory(kb)
        elif choice == '4':
            update_memory(kb)
        elif choice == '5':
            delete_memory(kb)
        elif choice == '6':
            show_stats(kb)
        elif choice == '7':
            export_memories(kb)
        else:
            print("❌ 无效选项，请重新选择")
        
        input("\n按回车键继续...")


if __name__ == "__main__":
    main()
