"""
本地知识库客户端 — 基于 ChromaDB 的向量检索
"""

import os
import logging
import chromadb
from chromadb.config import Settings
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class LocalKnowledgeClient:
    """本地知识库客户端（基于 ChromaDB）"""

    def __init__(self, collection_name: str = "travel_knowledge", persist_directory: str = None):
        """
        初始化本地知识库客户端

        Args:
            collection_name: 集合名称
            persist_directory: 数据存储目录
        """
        if persist_directory is None:
            persist_directory = os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "assets",
                "knowledge_db"
            )

        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # 初始化 ChromaDB 客户端
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # 获取或创建集合
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

        logger.info(f"本地知识库已初始化: {self.persist_directory}")
        logger.debug(f"集合名称: {collection_name}")
        logger.debug(f"文档数量: {self.collection.count()}")

    def add_documents(self, documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        """
        添加文档到知识库

        Args:
            documents: 文档内容列表
            metadatas: 元数据列表
            ids: 文档 ID 列表
        """
        try:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"已添加 {len(documents)} 个文档到知识库")
        except Exception as e:
            logger.error(f"添加文档失败: {e}")

    def search(self, query: str, n_results: int = 3, city: str = None) -> Optional[Dict[str, Any]]:
        """
        搜索知识库

        Args:
            query: 搜索查询
            n_results: 返回结果数
            city: 城市名称（用于过滤）

        Returns:
            搜索结果
        """
        try:
            # 构建查询条件
            where_filter = None
            if city:
                where_filter = {"city": city}

            # 执行搜索
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter
            )

            if not results or not results["documents"] or not results["documents"][0]:
                return None

            # 格式化结果
            formatted_results = []
            for i, doc in enumerate(results["documents"][0]):
                formatted_results.append({
                    "content": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if "distances" in results else 0
                })

            return {
                "query": query,
                "results": formatted_results
            }

        except Exception as e:
            logger.warning(f"知识库搜索失败: {e}")
            return None

    def search_city_info(self, city: str) -> Optional[Dict[str, Any]]:
        """
        搜索城市信息

        Args:
            city: 城市名称

        Returns:
            城市信息
        """
        query = f"{city} 旅游 景点 美食 住宿"
        return self.search(query, n_results=5, city=city)

    def search_attractions(self, city: str) -> Optional[Dict[str, Any]]:
        """
        搜索城市景点

        Args:
            city: 城市名称

        Returns:
            景点信息
        """
        query = f"{city} 景点 必去景点"
        return self.search(query, n_results=5, city=city)

    def search_food(self, city: str) -> Optional[Dict[str, Any]]:
        """
        搜索城市美食

        Args:
            city: 城市名称

        Returns:
            美食信息
        """
        query = f"{city} 美食 特色美食"
        return self.search(query, n_results=5, city=city)

    def get_all_cities(self) -> List[str]:
        """
        获取所有城市

        Returns:
            城市列表
        """
        try:
            # 获取所有文档的元数据
            results = self.collection.get()
            cities = set()
            for metadata in results.get("metadatas", []):
                if "city" in metadata:
                    cities.add(metadata["city"])
            return list(cities)
        except Exception as e:
            logger.warning(f"获取城市列表失败: {e}")
            return []

    def clear_collection(self):
        """清空知识库"""
        try:
            # 删除并重新创建集合
            self.client.delete_collection(self.collection.name)
            self.collection = self.client.create_collection(
                name=self.collection.name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("知识库已清空")
        except Exception as e:
            logger.error(f"清空知识库失败: {e}")

    def count(self) -> int:
        """获取文档数量"""
        try:
            return self.collection.count()
        except Exception as e:
            logger.warning(f"获取文档数量失败: {e}")
            return 0
