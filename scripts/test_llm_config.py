#!/usr/bin/env python3
"""
测试通义千问 API 配置
用于验证 qwen3.6-plus API Key 是否配置正确
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()


def test_qwen():
    """测试通义千问 API"""
    print("=" * 60)
    print("测试通义千问 API")
    print("=" * 60)

    try:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")

        if not api_key:
            print("❌ OPENAI_API_KEY 未配置")
            return False

        client = OpenAI(api_key=api_key, base_url=base_url)

        print(f"✅ API Key 已配置")
        print(f"   Base URL: {base_url}")
        print(f"   模型: qwen3.6-plus")

        # 测试调用
        print("\n正在测试调用...")
        response = client.chat.completions.create(
            model="qwen3.6-plus",
            messages=[{"role": "user", "content": "你好，请用一句话介绍你自己。"}],
            max_tokens=100,
            timeout=30
        )

        result = response.choices[0].message.content
        print(f"\n✅ 调用成功！")
        print(f"   响应: {result[:50]}...")

        return True

    except Exception as e:
        print(f"❌ 调用失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("大模型 API 配置测试")
    print("=" * 60)

    # 打印配置信息
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model_name = os.getenv("MODEL_NAME")

    if api_key:
        masked_key = api_key[:8] + "..." + api_key[-4:]
        print(f"✅ OPENAI_API_KEY: {masked_key}")
    else:
        print("❌ OPENAI_API_KEY: 未配置")

    print(f"   OPENAI_BASE_URL: {base_url}")
    print(f"   MODEL_NAME: {model_name or 'qwen3.6-plus (默认)'}")

    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        masked_tavily = tavily_key[:8] + "..." + tavily_key[-4:]
        print(f"✅ TAVILY_API_KEY: {masked_tavily}")
    else:
        print("⚠️  TAVILY_API_KEY: 未配置（可选）")

    # 测试调用
    success = test_qwen()

    print("\n" + "=" * 60)
    if success:
        print("✅ 配置正确！API 调用成功")
        print("\n下一步：")
        print("1. 导入知识库: python scripts/import_local_knowledge.py")
        print("2. 启动服务: python scripts/start_and_preview.py")
    else:
        print("❌ 配置有误，请检查 .env 文件和网络连接")
    print("=" * 60)


if __name__ == "__main__":
    main()
