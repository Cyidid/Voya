#!/usr/bin/env python3
"""
Web 服务完整测试脚本
"""

import requests
import json
import time

# API 基础 URL
API_BASE_URL = "http://localhost:8000"

def test_root():
    """测试根路径"""
    print("🧪 测试 1: 根路径访问")
    try:
        response = requests.get(f"{API_BASE_URL}/")
        print(f"✅ 状态码: {response.status_code}")
        print(f"📄 响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        print()
        return True
    except Exception as e:
        print(f"❌ 错误: {e}")
        print()
        return False

def test_get_agents():
    """测试获取 Agent 列表"""
    print("🧪 测试 2: 获取 Agent 列表")
    try:
        response = requests.get(f"{API_BASE_URL}/api/agents")
        print(f"✅ 状态码: {response.status_code}")
        print(f"📄 响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        print()
        return True
    except Exception as e:
        print(f"❌ 错误: {e}")
        print()
        return False

def test_generate_itinerary():
    """测试生成行程"""
    print("🧪 测试 3: 生成行程（基于规则）")
    try:
        payload = {
            "city": "东京",
            "days": 3,
            "budget": "中",
            "interests": ["文化", "美食"],
            "group": "朋友",
            "special": "无",
            "agent_type": "rule_based"
        }
        response = requests.post(f"{API_BASE_URL}/api/generate", json=payload)
        print(f"✅ 状态码: {response.status_code}")
        print(f"⏱️  处理时间: {response.json().get('processing_time', 0):.2f} 秒")
        print(f"📊 Token 估计: {response.json().get('token_estimate', 0)}")
        print(f"📄 行程预览 (前 200 字): {response.json().get('itinerary', '')[:200]}...")
        print()
        return True
    except Exception as e:
        print(f"❌ 错误: {e}")
        print()
        return False

def test_chat_goal_based():
    """测试聊天接口（基于目标 AI）"""
    print("🧪 测试 4: 聊天接口（基于目标 AI）")
    try:
        payload = {
            "role": "user",
            "content": "我想去伦敦玩4天，和家人一起，我们喜欢博物馆和历史，预算较高。",
            "agent_type": "goal_based"
        }
        print("⏳ 发送请求...")
        response = requests.post(f"{API_BASE_URL}/api/chat", json=payload)
        print(f"✅ 状态码: {response.status_code}")
        print(f"⏱️  处理时间: {response.json().get('processing_time', 0):.2f} 秒")
        print(f"🏙️  城市: {response.json().get('city')}")
        print(f"📅 天数: {response.json().get('days')}")
        print(f"💰 预算: {response.json().get('budget')}")
        print(f"👥 人群: {response.json().get('group')}")
        print(f"🎯 兴趣: {', '.join(response.json().get('interests', []))}")
        print(f"📄 响应预览 (前 300 字): {response.json().get('content', '')[:300]}...")
        print()
        return True
    except Exception as e:
        print(f"❌ 错误: {e}")
        print()
        return False

def test_chat_supervised():
    """测试聊天接口（监督学习）"""
    print("🧪 测试 5: 聊天接口（监督学习）")
    try:
        payload = {
            "role": "user",
            "content": "我想去纽约玩5天，和朋友一起，我们喜欢购物和美食，预算中等。",
            "agent_type": "supervised"
        }
        response = requests.post(f"{API_BASE_URL}/api/chat", json=payload)
        print(f"✅ 状态码: {response.status_code}")
        print(f"📄 响应预览 (前 200 字): {response.json().get('content', '')[:200]}...")
        print()
        return True
    except Exception as e:
        print(f"❌ 错误: {e}")
        print()
        return False

def test_preview():
    """测试预览端点"""
    print("🧪 测试 6: 预览端点（前端页面）")
    try:
        response = requests.get(f"{API_BASE_URL}/preview")
        print(f"✅ 状态码: {response.status_code}")
        print(f"📄 页面标题: {'旅行规划系统' if '旅行规划' in response.text else '未知'}")
        print(f"📄 页面大小: {len(response.text)} 字符")
        print(f"✅ 前端页面可访问: http://localhost:8000/preview")
        print()
        return True
    except Exception as e:
        print(f"❌ 错误: {e}")
        print()
        return False

def main():
    """主测试函数"""
    print("=" * 80)
    print("🚀 旅行规划系统 Web 服务完整测试")
    print("=" * 80)
    print()

    tests = [
        ("根路径访问", test_root),
        ("获取 Agent 列表", test_get_agents),
        ("生成行程（基于规则）", test_generate_itinerary),
        ("聊天接口（基于目标 AI）", test_chat_goal_based),
        ("聊天接口（监督学习）", test_chat_supervised),
        ("预览端点（前端页面）", test_preview),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
            time.sleep(1)  # 避免请求过快
        except Exception as e:
            print(f"❌ 测试 '{name}' 执行失败: {e}")
            results.append((name, False))
            print()

    # 汇总结果
    print("=" * 80)
    print("📊 测试结果汇总")
    print("=" * 80)
    print()

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")

    print()
    print(f"总计: {passed}/{total} 测试通过")
    print()

    if passed == total:
        print("🎉 所有测试通过！Web 服务运行正常！")
        print()
        print("📝 访问地址:")
        print(f"  • 前端页面: http://localhost:8000/preview")
        print(f"  • API 文档: http://localhost:8000/docs")
        print(f"  • 根路径: {API_BASE_URL}/")
    else:
        print("⚠️  部分测试失败，请检查服务状态")

    print()
    print("=" * 80)

if __name__ == "__main__":
    main()
