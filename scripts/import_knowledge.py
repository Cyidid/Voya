#!/usr/bin/env python3
"""
导入旅行知识库到 Coze Knowledge
"""

import sys
import os
sys.path.insert(0, os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects"))

from coze_coding_dev_sdk import KnowledgeClient, Config, KnowledgeDocument, DataSourceType, ChunkConfig
from coze_coding_utils.runtime_ctx.context import new_context

def import_knowledge():
    """导入知识库"""

    print("=" * 80)
    print("📚 导入旅行知识库到 Coze Knowledge")
    print("=" * 80)
    print()

    # 初始化客户端
    ctx = new_context(method="import_travel_knowledge")
    config = Config()
    client = KnowledgeClient(config=config, ctx=ctx)

    # 读取知识库文件
    knowledge_files = [
        ("assets/knowledge_paris.md", "巴黎"),
        ("assets/knowledge_tokyo.md", "东京"),
        ("assets/knowledge_newyork.md", "纽约"),
    ]

    documents = []

    for file_path, city_name in knowledge_files:
        full_path = os.path.join("/workspace/projects", file_path)

        if os.path.exists(full_path):
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()

            print(f"📖 读取 {city_name} 知识库...")
            print(f"   文件: {file_path}")
            print(f"   字符数: {len(content)}")
            print(f"   行数: {len(content.splitlines())}")

            documents.append(
                KnowledgeDocument(
                    source=DataSourceType.TEXT,
                    raw_data=content
                )
            )
            print(f"   ✅ 已准备导入")
            print()
        else:
            print(f"⚠️  文件不存在: {file_path}")
            print()

    if not documents:
        print("❌ 没有找到知识库文件")
        return

    # 配置分块策略
    chunk_config = ChunkConfig(
        separator="\n\n",
        max_tokens=1000,  # 每个块最多1000 token
        remove_extra_spaces=True
    )

    print(f"📦 准备导入 {len(documents)} 个文档...")
    print(f"📋 数据集名称: travel_knowledge")
    print(f"🔧 分块策略: max_tokens=1000, separator=\\n\\n")
    print()

    # 导入知识库
    try:
        response = client.add_documents(
            documents=documents,
            table_name="travel_knowledge",
            chunk_config=chunk_config
        )

        if response.code == 0:
            print("=" * 80)
            print("✅ 知识库导入成功！")
            print("=" * 80)
            print(f"📊 导入结果:")
            print(f"   文档数量: {len(response.doc_ids)}")
            print(f"   文档IDs: {response.doc_ids}")
            print()
            print("🎉 知识库已就绪，可以开始使用！")
            return True
        else:
            print("=" * 80)
            print("❌ 知识库导入失败")
            print("=" * 80)
            print(f"错误代码: {response.code}")
            print(f"错误信息: {response.msg}")
            return False

    except Exception as e:
        print(f"❌ 导入过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_knowledge_search():
    """测试知识库搜索"""

    print("\n")
    print("=" * 80)
    print("🔍 测试知识库搜索")
    print("=" * 80)
    print()

    # 初始化客户端
    ctx = new_context(method="test_knowledge_search")
    config = Config()
    client = KnowledgeClient(config=config, ctx=ctx)

    # 测试查询
    test_queries = [
        "巴黎埃菲尔铁塔开放时间和门票价格",
        "东京筑地市场有什么好吃的",
        "巴黎米其林餐厅推荐",
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n📝 查询 {i}: {query}")
        print("-" * 40)

        try:
            response = client.search(
                query=query,
                top_k=3,
                min_score=0.3  # 相似度阈值
            )

            if response.code == 0:
                if response.chunks:
                    print(f"✅ 找到 {len(response.chunks)} 个相关结果")
                    for j, chunk in enumerate(response.chunks, 1):
                        print(f"\n结果 {j} (相似度: {chunk.score:.4f}):")
                        print(f"   {chunk.content[:200]}...")
                else:
                    print("⚠️  未找到相关结果")
            else:
                print(f"❌ 搜索失败: {response.msg}")

        except Exception as e:
            print(f"❌ 搜索出错: {e}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    # 导入知识库
    success = import_knowledge()

    if success:
        # 测试搜索
        test_knowledge_search()
    else:
        print("\n⚠️  导入失败，跳过搜索测试")
