# -*- coding: utf-8 -*-
"""
知识库管理工具 - Web 图形界面 (v4 - 卡片式布局)

使用方法：
    python scripts/manage_knowledge_gui.py
    然后在浏览器打开 http://127.0.0.1:7861
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gradio as gr

from knowledge import get_knowledge_client


# 全局状态
client = None
selected_ids = set()


def init_client():
    global client
    if client is None:
        client = get_knowledge_client()
    return client


def format_timestamp(ts):
    if not ts or ts == 0:
        return "未知"
    try:
        return datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
    except:
        return str(ts)


# 类型图标映射
CATEGORY_ICONS = {
    'core': '⭐',
    'fact': '📝',
    'preference': '❤️',
    'feeling': '💭',
    'episode': '📅',
    'observation': '👁️',
    'system': '⚙️',
    'unknown': '❓'
}

CATEGORY_COLORS = {
    'core': '#ffd700',
    'fact': '#87ceeb',
    'preference': '#ffb6c1',
    'feeling': '#dda0dd',
    'episode': '#98fb98',
    'system': '#d3d3d3',
    'unknown': '#f0f0f0'
}


def render_memory_cards(filter_text=""):
    """渲染记忆卡片 HTML"""
    c = init_client()
    
    try:
        records = c.get_all()
        
        if not records:
            return "<div style='text-align:center; padding: 40px; color: #888;'>知识库为空</div>", "0 条记忆"
        
        # 过滤
        if filter_text.strip():
            records = [r for r in records if filter_text.lower() in r.get('text', '').lower()]
        
        html = """
        <style>
        .memory-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 12px;
            padding: 10px;
        }
        .memory-card {
            background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            padding: 14px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            transition: all 0.2s ease;
            position: relative;
        }
        .memory-card:hover {
            box-shadow: 0 4px 16px rgba(0,0,0,0.12);
            transform: translateY(-2px);
        }
        .memory-card.selected {
            border-color: #007bff;
            background: linear-gradient(135deg, #e7f3ff 0%, #f0f7ff 100%);
        }
        .card-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }
        .card-checkbox {
            width: 18px;
            height: 18px;
            cursor: pointer;
        }
        .card-icon {
            font-size: 16px;
        }
        .card-type {
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 10px;
            font-weight: 500;
        }
        .card-id {
            font-size: 10px;
            color: #999;
            margin-left: auto;
            font-family: monospace;
        }
        .card-content {
            font-size: 13px;
            line-height: 1.5;
            color: #333;
            margin: 10px 0;
            word-break: break-word;
        }
        .card-footer {
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 11px;
            color: #888;
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid #eee;
        }
        .card-importance {
            display: flex;
            align-items: center;
            gap: 4px;
        }
        .importance-bar {
            width: 40px;
            height: 4px;
            background: #eee;
            border-radius: 2px;
            overflow: hidden;
        }
        .importance-fill {
            height: 100%;
            background: linear-gradient(90deg, #4CAF50, #8BC34A);
            border-radius: 2px;
        }
        </style>
        <div class="memory-grid">
        """
        
        for r in records:
            doc_id = r['id']
            text = r.get('text', '')
            meta = r.get('metadata', {})
            
            category = meta.get('category', 'unknown')
            importance = meta.get('importance', 1.0)
            timestamp = meta.get('timestamp', 0)
            
            icon = CATEGORY_ICONS.get(category, '❓')
            color = CATEGORY_COLORS.get(category, '#f0f0f0')
            importance_pct = min(100, max(0, importance * 33))  # 0-3 映射到 0-100%
            
            # 截断长文本
            display_text = text[:150] + ('...' if len(text) > 150 else '')
            
            html += f"""
            <div class="memory-card" data-id="{doc_id}">
                <div class="card-header">
                    <input type="checkbox" class="card-checkbox" value="{doc_id}" onclick="toggleSelect('{doc_id}')">
                    <span class="card-icon">{icon}</span>
                    <span class="card-type" style="background:{color};">{category}</span>
                    <span class="card-id">{doc_id[:8]}</span>
                </div>
                <div class="card-content">{display_text}</div>
                <div class="card-footer">
                    <div class="card-importance">
                        <span>重要性</span>
                        <div class="importance-bar">
                            <div class="importance-fill" style="width:{importance_pct}%"></div>
                        </div>
                        <span>{importance:.1f}</span>
                    </div>
                    <span>{format_timestamp(timestamp)}</span>
                </div>
            </div>
            """
        
        html += "</div>"
        
        return html, f"{len(records)} 条记忆"
        
    except Exception as e:
        return f"<div style='color:red;padding:20px;'>加载失败: {e}</div>", "错误"


def search_and_render(query):
    """搜索并渲染"""
    if not query.strip():
        return render_memory_cards()
    
    c = init_client()
    try:
        results = c.search(query, n_results=20)
        
        if not results:
            return "<div style='text-align:center;padding:40px;color:#888;'>未找到相关记忆</div>", "0 条"
        
        # 转换格式
        records = []
        for r in results:
            meta = r.get('metadata', {})
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except:
                    meta = {}
            records.append({
                'id': r['id'],
                'text': r['text'],
                'metadata': meta
            })
        
        # 手动渲染（复用逻辑）
        html = render_cards_html(records)
        return html, f"搜索到 {len(records)} 条"
        
    except Exception as e:
        return f"<div style='color:red;'>搜索失败: {e}</div>", "错误"


def render_cards_html(records):
    """渲染卡片 HTML（内部函数）"""
    html = """
    <style>
    .memory-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 12px;
        padding: 10px;
    }
    .memory-card {
        background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 14px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        transition: all 0.2s ease;
    }
    .memory-card:hover {
        box-shadow: 0 4px 16px rgba(0,0,0,0.12);
        transform: translateY(-2px);
    }
    .card-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
    }
    .card-checkbox { width: 18px; height: 18px; cursor: pointer; }
    .card-type {
        font-size: 11px;
        padding: 2px 8px;
        border-radius: 10px;
        font-weight: 500;
    }
    .card-id { font-size: 10px; color: #999; margin-left: auto; font-family: monospace; }
    .card-content { font-size: 13px; line-height: 1.5; color: #333; margin: 10px 0; word-break: break-word; }
    .card-footer {
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 11px;
        color: #888;
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px solid #eee;
    }
    </style>
    <div class="memory-grid">
    """
    
    for r in records:
        doc_id = r['id']
        text = r.get('text', '')
        meta = r.get('metadata', {})
        
        category = meta.get('category', 'unknown')
        importance = meta.get('importance', 1.0)
        
        icon = CATEGORY_ICONS.get(category, '❓')
        color = CATEGORY_COLORS.get(category, '#f0f0f0')
        display_text = text[:150] + ('...' if len(text) > 150 else '')
        
        html += f"""
        <div class="memory-card" data-id="{doc_id}">
            <div class="card-header">
                <input type="checkbox" class="card-checkbox" value="{doc_id}">
                <span>{icon}</span>
                <span class="card-type" style="background:{color};">{category}</span>
                <span class="card-id">{doc_id[:8]}</span>
            </div>
            <div class="card-content">{display_text}</div>
            <div class="card-footer">
                <span>重要性: {importance:.1f}</span>
            </div>
        </div>
        """
    
    html += "</div>"
    return html


def add_memory(text, category):
    """添加记忆"""
    if not text.strip():
        return "请输入内容", *render_memory_cards()
    
    c = init_client()
    category_map = {
        "📝 事实": "fact",
        "⭐ 核心": "core", 
        "❤️ 偏好": "preference",
        "💭 感受": "feeling"
    }
    
    try:
        doc_id = c.add(
            text=text.strip(),
            metadata={
                "category": category_map.get(category, "fact"),
                "source": "manual",
                "verified": True
            }
        )
        return f"✅ 已添加: {doc_id[:8]}", *render_memory_cards()
    except Exception as e:
        return f"❌ 失败: {e}", *render_memory_cards()


def delete_by_ids(ids_text):
    """批量删除"""
    if not ids_text.strip():
        return "请输入要删除的 ID", *render_memory_cards()
    
    c = init_client()
    import re
    ids = [id.strip() for id in re.split(r'[,\s\n]+', ids_text) if id.strip()]
    
    if not ids:
        return "未找到有效 ID", *render_memory_cards()
    
    deleted = 0
    skipped = 0
    
    try:
        records = c.get_all()
        core_ids = {r['id'] for r in records if r.get('metadata', {}).get('category') == 'core'}
        
        for doc_id in ids:
            if doc_id in core_ids:
                skipped += 1
                continue
            try:
                c.delete(doc_id)
                deleted += 1
            except:
                pass
        
        msg = f"✅ 删除 {deleted} 条"
        if skipped:
            msg += f"，跳过 {skipped} 条核心记忆"
        return msg, *render_memory_cards()
    except Exception as e:
        return f"❌ 失败: {e}", *render_memory_cards()


def get_stats():
    """统计"""
    c = init_client()
    try:
        records = c.get_all()
        if not records:
            return "知识库为空"
        
        cats = {}
        for r in records:
            cat = r.get('metadata', {}).get('category', 'unknown')
            cats[cat] = cats.get(cat, 0) + 1
        
        lines = [f"📊 总计: {len(records)} 条\n"]
        for cat, n in sorted(cats.items(), key=lambda x: -x[1]):
            icon = CATEGORY_ICONS.get(cat, '❓')
            lines.append(f"  {icon} {cat}: {n}")
        
        return "\n".join(lines)
    except Exception as e:
        return f"错误: {e}"


# ============================================================
# Gradio UI
# ============================================================

CUSTOM_CSS = """
#main-container { max-width: 1400px; margin: 0 auto; }
.status-bar { 
    display: flex; 
    align-items: center; 
    justify-content: space-between;
    padding: 8px 16px;
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-radius: 8px;
    margin-bottom: 12px;
}
"""

def create_ui():
    with gr.Blocks(title="🧠 知识库管理", theme=gr.themes.Soft()) as demo:
        
        gr.HTML("""
        <div style="text-align:center; padding: 20px 0 10px 0;">
            <h1 style="margin:0; font-size: 28px;">🧠 知识库管理</h1>
            <p style="color: #666; margin: 5px 0;">点击卡片勾选 → 批量操作</p>
        </div>
        """)
        
        # 工具栏
        with gr.Row():
            search_box = gr.Textbox(
                placeholder="🔍 搜索...", 
                show_label=False,
                scale=3
            )
            refresh_btn = gr.Button("🔄 刷新", scale=1)
            delete_btn = gr.Button("🗑️ 删除选中", variant="stop", scale=1)
        
        # 状态栏
        status_text = gr.Textbox(value="加载中...", show_label=False, interactive=False, max_lines=1)
        
        # 卡片区域
        cards_html = gr.HTML()
        
        # 选中的 ID（用于批量删除）
        selected_ids_box = gr.Textbox(
            label="📋 选中的 ID (复制到这里进行批量删除)",
            placeholder="粘贴或输入要删除的 ID，用逗号/空格/换行分隔",
            lines=2
        )
        
        with gr.Accordion("➕ 添加新记忆", open=False):
            with gr.Row():
                new_text = gr.Textbox(label="内容", placeholder="输入记忆内容...", scale=3)
                new_type = gr.Dropdown(
                    ["📝 事实", "⭐ 核心", "❤️ 偏好", "💭 感受"],
                    value="📝 事实",
                    label="类型",
                    scale=1
                )
            add_btn = gr.Button("➕ 添加", variant="primary")
            add_status = gr.Textbox(show_label=False, interactive=False, max_lines=1)
        
        with gr.Accordion("📊 统计", open=False):
            stats_box = gr.Textbox(lines=8, interactive=False, show_label=False)
            stats_btn = gr.Button("刷新统计")
        
        # 事件绑定
        demo.load(render_memory_cards, outputs=[cards_html, status_text])
        refresh_btn.click(render_memory_cards, outputs=[cards_html, status_text])
        search_box.submit(search_and_render, inputs=search_box, outputs=[cards_html, status_text])
        
        delete_btn.click(delete_by_ids, inputs=selected_ids_box, outputs=[add_status, cards_html, status_text])
        add_btn.click(add_memory, inputs=[new_text, new_type], outputs=[add_status, cards_html, status_text])
        
        stats_btn.click(get_stats, outputs=stats_box)
        
        gr.Markdown("""
        ---
        💡 **提示**: 勾选卡片上的复选框，然后复制 ID 到上方输入框，点击删除按钮批量删除。核心记忆 (⭐) 会被自动跳过。
        """)
    
    return demo


if __name__ == "__main__":
    print("[*] Starting Knowledge Management GUI (v4 - Card Layout)...")
    print("[*] Connecting to knowledge server...")
    print("[*] Open http://127.0.0.1:7861")
    
    demo = create_ui()
    demo.launch(
        server_name="127.0.0.1",
        server_port=7861,
        share=False,
        inbrowser=True
    )
