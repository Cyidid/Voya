"""
知识库导入脚本
将 markdown 文件导入到本地知识库（ChromaDB）
"""

import os
import sys
from pathlib import Path
import re


# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def parse_markdown_file(file_path: Path) -> dict:
    """
    解析 markdown 文件

    Args:
        file_path: markdown 文件路径

    Returns:
        解析后的数据，包含 city, content, sections
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取城市名称（从文件名或内容）
    city = file_path.stem.replace('knowledge_', '').replace('_', ' ').title()

    # 分段（按 ## 标题分割）
    sections = re.split(r'\n##\s+', content)

    parsed_sections = []
    for i, section in enumerate(sections):
        if section.strip():
            # 第一段是标题
            if i == 0:
                title = section.strip()
                continue

            # 分离标题和内容
            lines = section.split('\n', 1)
            section_title = lines[0].strip()
            section_content = lines[1].strip() if len(lines) > 1 else ""

            parsed_sections.append({
                "title": section_title,
                "content": section_content
            })

    return {
        "city": city,
        "content": content,
        "sections": parsed_sections
    }


def import_knowledge_from_markdown(file_path: Path, client) -> int:
    """
    从 markdown 文件导入知识

    Args:
        file_path: markdown 文件路径
        client: 知识库客户端

    Returns:
        导入的文档数量
    """
    parsed = parse_markdown_file(file_path)
    city = parsed["city"]

    print(f"\n📖 正在导入 {city} 的知识...")

    documents = []
    metadatas = []
    ids = []

    # 为每个段落创建一个文档
    for i, section in enumerate(parsed["sections"]):
        doc_id = f"{city}_{i}"

        documents.append(section["content"])
        metadatas.append({
            "city": city,
            "section": section["title"],
            "source": str(file_path.name)
        })
        ids.append(doc_id)

        print(f"   - {section['title']}")

    # 批量添加
    if documents:
        client.add_documents(documents, metadatas, ids)
        return len(documents)

    return 0


def main():
    """主函数"""
    print("=" * 60)
    print("📚 知识库导入工具")
    print("=" * 60)

    # 导入客户端
    try:
        from systems.goal_based.local_knowledge_client import LocalKnowledgeClient

        # 初始化客户端
        client = LocalKnowledgeClient()

        # 清空现有知识库（可选）
        choice = input("\n是否清空现有知识库？(y/N): ").strip().lower()
        if choice == 'y':
            client.clear_collection()
            print("✅ 已清空现有知识库\n")

    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("请确保已安装依赖: pip install chromadb")
        return

    # 查找知识库文件
    assets_dir = Path("assets")
    knowledge_files = list(assets_dir.glob("knowledge_*.md"))

    if not knowledge_files:
        print(f"⚠️  未在 {assets_dir} 目录找到知识库文件")
        print("   查找模式: knowledge_*.md")
        return

    print(f"\n找到 {len(knowledge_files)} 个知识库文件:")
    for f in knowledge_files:
        print(f"   - {f.name}")

    # 导入所有文件
    total_imported = 0
    for file_path in knowledge_files:
        try:
            count = import_knowledge_from_markdown(file_path, client)
            total_imported += count
        except Exception as e:
            print(f"❌ 导入失败 ({file_path.name}): {e}")

    # 输出统计
    print("\n" + "=" * 60)
    print("✅ 导入完成")
    print("=" * 60)
    print(f"总文档数: {client.count()}")
    print(f"导入文档: {total_imported}")
    print(f"支持城市: {', '.join(client.get_all_cities())}")
    print(f"存储位置: {client.persist_directory}")
    print("=" * 60)


if __name__ == "__main__":
    main()
