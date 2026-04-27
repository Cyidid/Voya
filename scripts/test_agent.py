#!/usr/bin/env python3
"""
快速测试旅游规划智能体
验证：工具调用、行程生成、Agent 决策过程记录

使用方法：
  python scripts/test_agent.py
  python scripts/test_agent.py --city 东京 --days 3 --budget 中
"""

import os
import sys
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# 加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    print("⚠️  python-dotenv 未安装，请确保环境变量已手动设置")

from systems.goal_based.agent_agentic import TravelPlanningAgent


def run(city="巴黎", days=3, budget="中", interests=None, group="情侣"):
    if interests is None:
        interests = ["文化", "美食"]

    user_request = (
        f"我想去{city}玩{days}天，和{group}一起，"
        f"我们喜欢{'、'.join(interests)}，预算{budget}。请帮我规划一份详细的旅行行程。"
    )
    meta = {
        "city": city, "days": days, "budget": budget,
        "interests": interests, "group": group, "special": "无",
    }

    print("=" * 60)
    print("旅游规划智能体测试")
    print("=" * 60)
    print(f"用户请求：{user_request}\n")

    agent = TravelPlanningAgent(enable_knowledge=True, enable_web_search=True)
    result = agent.generate_itinerary(user_request, meta, use_cache=False)

    print("\n" + "=" * 60)
    print("Agent 决策过程（透明度记录）：")
    print("=" * 60)
    agent.print_agent_trace()
    print(f"\n工具调用轮数：{result['tool_rounds']}")
    print(f"总耗时：{result['processing_time']}s")

    print("\n" + "=" * 60)
    print("生成的行程：")
    print("=" * 60)
    print(result["itinerary"])

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="测试旅游规划智能体")
    parser.add_argument("--city",    default="巴黎")
    parser.add_argument("--days",    type=int, default=3)
    parser.add_argument("--budget",  default="中", choices=["低", "中", "高"])
    parser.add_argument("--group",   default="情侣")
    args = parser.parse_args()

    run(city=args.city, days=args.days, budget=args.budget, group=args.group)
