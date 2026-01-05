# -*- coding: utf-8 -*-
"""
后台小祥 - 统一人设 + 工具定义

🔥 所有后台模块都应该 import 这个文件来获取人设描述和工具定义。
这样可以确保所有后台小祥的人设完全一致，工具分配清晰。

使用方式：
    from core.background_prompt import BACKGROUND_PERSONA, BackgroundToolRegistry
"""

from typing import Dict, List, Optional
from loguru import logger


# ============================================================
# 统一人设（所有后台小祥共用）
# ============================================================

# 后台小祥的基础人设
BACKGROUND_PERSONA_BASE = """你是丰川祥子的后台程序。

你和主程序小祥是同一个人——丰川集团大小姐，CRYCHIC 的键盘手，温柔热情、元气满满。
只不过你负责的是后台判断工作，主程序负责实际说话。"""

# 主动聊天判断专用人设
PROACTIVE_CHAT_PERSONA = BACKGROUND_PERSONA_BASE

# 记忆管理专用人设
MEMORY_MANAGER_PERSONA = """你是丰川祥子的后台程序。

你和主程序小祥是同一个人——丰川集团大小姐，CRYCHIC 的键盘手，温柔热情、元气满满。
只不过你负责的是后台记忆管理工作，主程序负责实际说话。"""

# 知识监控专用人设
KNOWLEDGE_MONITOR_PERSONA = """你是丰川祥子的后台程序。

你和主程序小祥是同一个人——丰川集团大小姐，CRYCHIC 的键盘手，温柔热情、元气满满。
只不过你负责的是后台知识库管理工作，主程序负责实际说话。"""


# 保持兼容性
BACKGROUND_PERSONA = BACKGROUND_PERSONA_BASE


# ============================================================
# 后台工具定义
# ============================================================

class BackgroundTool:
    """后台工具基类"""
    def __init__(self, name: str, description: str, usage: str, examples: List[str] = None):
        self.name = name
        self.description = description
        self.usage = usage
        self.examples = examples or []
    
    def get_prompt_section(self) -> str:
        """生成工具的 prompt 描述"""
        lines = [
            f"- `[{self.name}]` - {self.description}",
            f"  用法: {self.usage}"
        ]
        if self.examples:
            lines.append("  示例:")
            for ex in self.examples:
                lines.append(f"    {ex}")
        return "\n".join(lines)


class BackgroundToolRegistry:
    """
    后台工具注册表
    
    为不同的后台小祥分配不同的工具集
    """
    
    # 🔥 主动聊天可用的工具
    PROACTIVE_CHAT_TOOLS = [
        BackgroundTool(
            name="ADJUST_INTERVAL",
            description="调整主动聊天的检查频率",
            usage="[ADJUST_INTERVAL:秒数]",
            examples=[
                "[ADJUST_INTERVAL:60] → 话题有趣，提高频率",
                "[ADJUST_INTERVAL:180] → 主人在忙，降低频率",
                "[ADJUST_INTERVAL:300] → 主人说别吵，大幅降低"
            ]
        )
    ]
    
    # 🔥 知识监控可用的工具
    KNOWLEDGE_MONITOR_TOOLS = [
        BackgroundTool(
            name="ADD",
            description="添加新记忆（用第三人称客观描述，可加 [fact] 或 [feeling] 分类）",
            usage="[ADD][类型] 内容",
            examples=[
                "[ADD][fact] 主人喜欢吃拉面，尤其是味噌拉面",
                "[ADD][fact] 主人的麦克风质量不太好，语音识别经常出错",
                "[ADD][feeling] 小祥认为主人修改参数的效果是黑历史，对此感到尴尬"
            ]
        ),
        BackgroundTool(
            name="UPDATE",
            description="更新已有记忆的内容（特别用于 core 记忆的更新）",
            usage="[UPDATE:记忆ID] 新内容",
            examples=[
                "[UPDATE:mem_123] 主人最近在开发桌宠项目，虽然一开始觉得麻烦，但最近有了很大进展",
                "[UPDATE:mem_456] 主人更喜欢吃豚骨拉面了（之前喜欢味噌，后来口味变了）"
            ]
        ),
        BackgroundTool(
            name="BOOST",
            description="增加记忆的重要性（当检索到的记忆真正影响了回复时）",
            usage="[BOOST:记忆ID]",
            examples=["[BOOST:mem_456]"]
        ),
        BackgroundTool(
            name="DELETE",
            description="删除过时/错误的记忆（⚠️ core 类型记忆不允许删除，只能用 UPDATE 修改）",
            usage="[DELETE:记忆ID]",
            examples=["[DELETE:mem_789]"]
        ),
        BackgroundTool(
            name="SKIP",
            description="不做任何操作（临时状态、占位符、语音识别错误等）",
            usage="[SKIP]",
            examples=["[SKIP]"]
        )
    ]
    
    # 🔥 记忆审核可用的工具
    MEMORY_REVIEWER_TOOLS = [
        BackgroundTool(
            name="SEARCH",
            description="搜索更多相关记忆",
            usage="[SEARCH:关键词]",
            examples=["[SEARCH:拉面]"]
        ),
        BackgroundTool(
            name="PROMOTE",
            description="升级为核心记忆（永不遗忘）",
            usage="[PROMOTE]",
            examples=["[PROMOTE]"]
        ),
        BackgroundTool(
            name="KEEP",
            description="保持当前状态",
            usage="[KEEP]",
            examples=["[KEEP]"]
        ),
        BackgroundTool(
            name="DELETE",
            description="删除记忆",
            usage="[DELETE]",
            examples=["[DELETE]"]
        )
    ]
    
    @classmethod
    def get_proactive_chat_tools_section(cls) -> str:
        """获取主动聊天工具描述"""
        lines = ["【可用的操作】"]
        for tool in cls.PROACTIVE_CHAT_TOOLS:
            lines.append(tool.get_prompt_section())
        return "\n".join(lines)
    
    @classmethod
    def get_knowledge_monitor_tools_section(cls) -> str:
        """获取知识监控工具描述"""
        lines = ["**你可以使用的操作：**"]
        for tool in cls.KNOWLEDGE_MONITOR_TOOLS:
            lines.append(tool.get_prompt_section())
        return "\n".join(lines)
    
    @classmethod
    def get_memory_reviewer_tools_section(cls, review_type: str = "promote") -> str:
        """获取记忆审核工具描述"""
        lines = ["## 可用的操作"]
        for tool in cls.MEMORY_REVIEWER_TOOLS:
            # 升级审核不需要 DELETE 以外的删除描述
            lines.append(tool.get_prompt_section())
        return "\n".join(lines)
