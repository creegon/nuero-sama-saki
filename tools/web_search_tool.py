# -*- coding: utf-8 -*-
"""
网络搜索工具 - 使用 DuckDuckGo

允许 AI 搜索网络获取信息。
调用格式: [CALL:web_search:搜索关键词]
"""

import asyncio
from typing import Optional
from loguru import logger

from .base import BaseTool, ToolResult


import time

class WebSearchTool(BaseTool):
    """网络搜索工具"""
    
    name = "web_search"
    description = "搜索网络获取信息"
    usage_hint = "格式：[CALL:web_search:搜索关键词]，把要搜的内容写在冒号后面"
    usage_example = ("帮我查一下勾股定理", "[thinking] 让我搜搜看。[CALL:web_search:勾股定理]")
    parallel_hint = "等我搜一下..."
    
    def __init__(self):
        self._ddgs = None
    
    def _get_ddgs(self):
        """懒加载 DuckDuckGo 搜索客户端"""
        if self._ddgs is None:
            try:
                from ddgs import DDGS
                self._ddgs = DDGS()
            except ImportError:
                logger.error("ddgs 未安装，请运行: pip install ddgs")
                return None
        return self._ddgs
    
    def _search_with_retry(self, ddgs, query: str, max_results: int, max_retries: int = 3) -> list:
        """带重试机制的搜索执行函数"""
        for attempt in range(max_retries):
            try:
                # ddgs.text 返回的是 generator，需要转 list
                return list(ddgs.text(query, max_results=max_results))
            except Exception as e:
                # 检查是否是 RateLimit 相关错误
                error_str = str(e).lower()
                is_ratelimit = "ratelimit" in error_str or "429" in error_str
                
                if is_ratelimit and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3  # 3s, 6s, 9s
                    logger.warning(f"搜索触发 RateLimit，等待 {wait_time} 秒后重试 (尝试 {attempt+1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    # 如果不是 RateLimit 或者重试次数用尽，抛出异常
                    if attempt == max_retries - 1:
                         raise e
                    # 非 RateLimit 异常可能不需要重试，这里选择保守策略：也重试一下还是直接抛出？
                    # 通常连接错误也可以重试，但这里主要针对 Ratelimit。
                    # 如果是其他严重错误，可能直接抛出更好。但为了稳健，暂只对 Ratelimit 重试。
                    if not is_ratelimit:
                        raise e
    
    async def execute(
        self,
        context: str = "",
        args: str = "",
        **kwargs
    ) -> ToolResult:
        """
        执行网络搜索
        
        Args:
            context: 对话上下文
            args: 搜索关键词（从 [CALL:web_search:xxx] 的 xxx 部分提取）
        """
        # 获取搜索关键词
        query = args.strip() if args else context.strip()
        
        if not query:
            return ToolResult(
                success=False,
                error="没有提供搜索关键词"
            )
        
        logger.info(f"🔍 网络搜索: {query}")
        
        ddgs = self._get_ddgs()
        if not ddgs:
            return ToolResult(
                success=False,
                error="搜索服务不可用 (ddgs 未安装)"
            )
        
        try:
            # 在线程池中执行搜索（避免阻塞事件循环）
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self._search_with_retry(ddgs, query, max_results=5)
            )
            
            if not results:
                return ToolResult(
                    success=True,
                    data=f"没有找到关于「{query}」的搜索结果。"
                )
            
            # 格式化结果
            formatted = self._format_results(query, results)
            logger.info(f"🔍 搜索完成，找到 {len(results)} 条结果")
            
            return ToolResult(
                success=True,
                data=formatted
            )
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return ToolResult(
                success=False,
                error=f"搜索失败: {str(e)}"
            )
    
    def _format_results(self, query: str, results: list) -> str:
        """格式化搜索结果"""
        lines = [f"搜索「{query}」的结果：\n"]
        
        for i, r in enumerate(results, 1):
            title = r.get("title", "无标题")
            body = r.get("body", "无摘要")
            # 截断过长的摘要
            if len(body) > 200:
                body = body[:200] + "..."
            
            lines.append(f"{i}. {title}")
            lines.append(f"   {body}\n")
        
        return "\n".join(lines)


# 工具实例
web_search_tool = WebSearchTool()
