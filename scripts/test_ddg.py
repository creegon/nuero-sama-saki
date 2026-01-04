# -*- coding: utf-8 -*-
"""
测试 DuckDuckGo 搜索 API
"""

import asyncio
from ddgs import DDGS
import logging

import time

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def search_with_retry(ddgs, query, max_results, max_retries=3):
    """带重试机制的搜索函数"""
    for attempt in range(max_retries):
        try:
            return list(ddgs.text(query, max_results=max_results))
        except Exception as e:
            is_ratelimit = "ratelimit" in str(e).lower() or "429" in str(e)
            if is_ratelimit and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5  # 递增等待时间: 5s, 10s, 15s
                logger.warning(f"触发 RateLimit，等待 {wait_time} 秒后重试 (尝试 {attempt+1}/{max_retries})...")
                time.sleep(wait_time)
            else:
                if attempt == max_retries - 1:
                    logger.error(f"搜索最终失败: {e}")
                raise e

def test_ddg_sync():
    """同步测试"""
    logger.info("开始同步搜索测试...")
    try:
        ddgs = DDGS()
        keywords = "Python 教程"
        logger.info(f"搜索关键词: {keywords}")
        
        # 使用重试机制
        results = search_with_retry(ddgs, keywords, max_results=3)
        
        if not results:
            logger.warning("未找到结果")
            return
            
        logger.info(f"找到 {len(results)} 条结果:")
        for i, r in enumerate(results, 1):
            print(f"\n结果 {i}:")
            print(f"标题: {r.get('title')}")
            print(f"链接: {r.get('href')}")
            print(f"摘要: {r.get('body')}")
            
        logger.info("同步测试成功！")
        
    except Exception as e:
        logger.error(f"同步测试失败: {e}")

async def test_ddg_async():
    """虽然库主要是同步的，但我们在项目中是用 run_in_executor 调用的，这里模拟项目中的用法"""
    logger.info("\n开始模拟项目中的异步调用...")
    try:
        ddgs = DDGS()
        keywords = "Live2D SDK"
        
        loop = asyncio.get_event_loop()
        # 在 executor 中调用带重试的函数
        results = await loop.run_in_executor(
            None,
            lambda: search_with_retry(ddgs, keywords, max_results=2)
        )
        
        if not results:
            logger.warning("未找到结果")
            return

        logger.info(f"找到 {len(results)} 条结果:")
        for i, r in enumerate(results, 1):
            print(f"结果 {i}: {r.get('title')}")
            
        logger.info("模拟异步调用成功！")

    except Exception as e:
        logger.error(f"模拟异步调用失败: {e}")

if __name__ == "__main__":
    test_ddg_sync()
    asyncio.run(test_ddg_async())  
