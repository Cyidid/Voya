"""
Tavily Search API 客户端 — 实时联网搜索
"""

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

try:
    import httpx
    _HTTP = httpx.Client(proxy=None, timeout=30.0)
except ImportError:
    _HTTP = None


class TavilySearchClient:
    """Tavily Search API 客户端"""

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 Tavily Search 客户端

        Args:
            api_key: Tavily API Key，如果为 None 则从环境变量读取
        """
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.base_url = "https://api.tavily.com/search"

        if not self.api_key:
            logger.warning("TAVILY_API_KEY 未配置，Web Search 功能将被禁用")

    def search(self, query: str, max_results: int = 5) -> Optional[Dict[str, Any]]:
        """
        执行搜索

        Args:
            query: 搜索查询
            max_results: 最大结果数

        Returns:
            搜索结果字典，包含 answer 和 results
        """
        if not self.api_key:
            return None

        try:
            payload = {
                "api_key": self.api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
                "include_answer": True,
                "include_raw_content": False,
                "include_images": False,
                "include_image_descriptions": False
            }
            if _HTTP: # httpx 直连，绕过系统代理
                response = _HTTP.post(self.base_url, json=payload)
            else:
                import requests as _requests
                response = _requests.post(self.base_url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            return self._format_response(data)

        except Exception as e:
            logger.warning(f"Web Search 失败: {e}")
            return None

    def _format_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化 Tavily API 响应

        Args:
            data: Tavily API 原始响应

        Returns:
            格式化后的响应
        """
        if not data:
            return None

        return {
            "answer": data.get("answer", ""),
            "results": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", ""),
                    "score": r.get("score", 0)
                }
                for r in data.get("results", [])
            ],
            "query": data.get("query", "")
        }

    def search_city_info(self, city: str) -> Optional[Dict[str, Any]]:
        """
        搜索城市信息

        Args:
            city: 城市名称

        Returns:
            城市信息
        """
        query = f"{city} 旅行攻略 景点 美食 住宿 天气"
        return self.search(query, max_results=5)

    def search_attractions(self, city: str) -> Optional[Dict[str, Any]]:
        """
        搜索城市景点

        Args:
            city: 城市名称

        Returns:
            景点信息
        """
        query = f"{city} 必去景点 热门景点 旅游景点推荐"
        return self.search(query, max_results=5)

    def search_food(self, city: str) -> Optional[Dict[str, Any]]:
        """
        搜索城市美食

        Args:
            city: 城市名称

        Returns:
            美食信息
        """
        query = f"{city} 特色美食 必吃美食 餐厅推荐"
        return self.search(query, max_results=5)
