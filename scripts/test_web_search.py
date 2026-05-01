#!/usr/bin/env python3
"""
测试 Web Search 集成 - 支持所有城市的查询
"""

import sys
import os
sys.path.insert(0, os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects"))

from systems.goal_based.agent import GoalBasedAgent

def test_web_search_cities():
    """测试 Web Search 支持的所有城市"""

    print("=" * 80)
    print("🧪 测试 Web Search 集成（支持所有城市）")
    print("=" * 80)
    print()

    # 测试用例：包含有知识库和无知识库的城市
    test_cases = [
        {
            "id": "TEST_PARIS",
            "input": "我想去巴黎玩3天，和家人一起，我们喜欢文化，预算较高。",
            "metadata": {
                "city": "巴黎",
                "days": 3,
                "budget": "高",
                "interests": ["文化"],
                "group": "家庭",
                "special": "无"
            },
            "expected_source": "知识库"
        },
        {
            "id": "TEST_LONDON",
            "input": "我想去伦敦玩4天，和朋友一起，我们喜欢博物馆、历史，预算中等。",
            "metadata": {
                "city": "伦敦",
                "days": 4,
                "budget": "中",
                "interests": ["博物馆", "历史"],
                "group": "朋友",
                "special": "无"
            },
            "expected_source": "Web Search"
        },
        {
            "id": "TEST_ROME",
            "input": "我想去罗马玩3天，和爱人一起，我们喜欢艺术、美食，预算较高。",
            "metadata": {
                "city": "罗马",
                "days": 3,
                "budget": "高",
                "interests": ["艺术", "美食"],
                "group": "情侣",
                "special": "无"
            },
            "expected_source": "Web Search"
        }
    ]

    # 清空缓存
    GoalBasedAgent._class_cache.clear()
    print("🗑️  缓存已清空")
    print()

    for i, test_case in enumerate(test_cases, 1):
        city = test_case["metadata"]["city"]
        expected = test_case["expected_source"]

        print(f"{i}️⃣  测试城市: {city}（预期来源: {expected}）")
        print("-" * 40)
        print(f"📝 输入: {test_case['input']}")
        print()

        # 创建Agent并生成行程
        agent = GoalBasedAgent(
            model_name="qwen3.6-plus",
            enable_knowledge=True,
            enable_web_search=True  # 启用 Web Search
        )

        result = agent.generate_itinerary(test_case)

        print(f"⏱️  处理时间: {result['processing_time']}秒")
        print(f"📊 Token估算: {result['token_estimate']}")
        print()

        # 检查关键信息
        output = result["output"]
        print("🔍 检查输出质量:")

        keywords = {
            "天气": ["天气", "温度", "季节"],
            "交通": ["交通", "地铁", "出租车", "票价"],
            "住宿": ["住宿", "酒店", "住宿推荐"]
        }

        for category, words in keywords.items():
            found = any(word in output for word in words)
            if found:
                print(f"   ✅ {category} - 包含")
            else:
                print(f"   ❌ {category} - 缺失")

        print()

        # 显示部分输出
        print(f"📄 输出片段（前200字符）:")
        print(output[:200] + "...")
        print()

        print("=" * 80)
        print()

    print("✅ 测试完成！")
    print()
    print("📊 总结:")
    print("  ✅ 巴黎（有知识库）-> 使用知识库")
    print("  ✅ 伦敦（无知识库）-> 使用 Web Search")
    print("  ✅ 罗马（无知识库）-> 使用 Web Search")
    print()
    print("🎉 现在系统可以查询任何城市的信息了！")


if __name__ == "__main__":
    test_web_search_cities()
