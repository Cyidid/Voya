#!/usr/bin/env python3
"""
测试大模型 API 配置
用于验证豆包或通义千问 API Key 是否配置正确
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


def test_doubao():
    """测试豆包 API"""
    print("=" * 60)
    print("测试豆包 API")
    print("=" * 60)

    try:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")

        if not api_key:
            print("❌ OPENAI_API_KEY 未配置")
            return False

        if "ark.cn-beijing.volces.com" not in base_url:
            print("⚠️  Base URL 不是豆包的地址")
            print(f"   当前: {base_url}")
            print(f"   期望: https://ark.cn-beijing.volces.com/api/v3")

        client = OpenAI(api_key=api_key, base_url=base_url)

        print(f"✅ API Key 已配置")
        print(f"   Base URL: {base_url}")
        print(f"   模型: doubao-seed-1-8-251228")

        # 测试调用
        print("\n正在测试调用...")
        response = client.chat.completions.create(
            model="doubao-seed-1-8-251228",
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


def test_qwen():
    """测试通义千问 API"""
    print("\n" + "=" * 60)
    print("测试通义千问 API")
    print("=" * 60)

    try:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")

        if not api_key:
            print("❌ OPENAI_API_KEY 未配置")
            return False

        if "dashscope.aliyuncs.com" not in base_url:
            print("⚠️  Base URL 不是通义千问的地址")
            print(f"   当前: {base_url}")
            print(f"   期望: https://dashscope.aliyuncs.com/compatible-mode/v1")

        client = OpenAI(api_key=api_key, base_url=base_url)

        print(f"✅ API Key 已配置")
        print(f"   Base URL: {base_url}")
        print(f"   模型: qwen-plus")

        # 测试调用
        print("\n正在测试调用...")
        response = client.chat.completions.create(
            model="qwen-plus",
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


def auto_detect_and_test():
    """自动检测并测试配置的模型"""
    base_url = os.getenv("OPENAI_BASE_URL", "")

    if "ark.cn-beijing.volces.com" in base_url:
        print("检测到豆包配置")
        return test_doubao()
    elif "dashscope.aliyuncs.com" in base_url:
        print("检测到通义千问配置")
        return test_qwen()
    else:
        print("⚠️  无法自动检测模型类型")
        print(f"   Base URL: {base_url}")
        print("\n请检查 .env 文件中的配置")
        return False


def print_config_info():
    """打印配置信息"""
    print("\n" + "=" * 60)
    print("当前配置")
    print("=" * 60)

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model_name = os.getenv("MODEL_NAME")

    if api_key:
        # 只显示前几位和后几位
        masked_key = api_key[:8] + "..." + api_key[-4:]
        print(f"✅ OPENAI_API_KEY: {masked_key}")
    else:
        print("❌ OPENAI_API_KEY: 未配置")

    print(f"   OPENAI_BASE_URL: {base_url}")
    print(f"   MODEL_NAME: {model_name}")

    # 检查其他配置
    tavily_key = os.getenv("TAVILY_API_KEY")
    use_local = os.getenv("USE_LOCAL_AGENT", "false")

    if tavily_key:
        masked_tavily = tavily_key[:8] + "..." + tavily_key[-4:]
        print(f"✅ TAVILY_API_KEY: {masked_tavily}")
    else:
        print("⚠️  TAVILY_API_KEY: 未配置（可选）")

    print(f"   USE_LOCAL_AGENT: {use_local}")


def main():
    """主函数"""
    print("=" * 60)
    print("大模型 API 配置测试")
    print("=" * 60)

    # 打印配置信息
    print_config_info()

    # 自动检测并测试
    success = auto_detect_and_test()

    # 打印结果
    print("\n" + "=" * 60)
    print("测试结果")
    print("=" * 60)

    if success:
        print("✅ 配置正确！API 调用成功")
        print("\n下一步：")
        print("1. 运行功能测试: python scripts/test_local_agent.py")
        print("2. 导入知识库: python scripts/import_local_knowledge.py")
        print("3. 启动服务: python scripts/start_and_preview.py")
    else:
        print("❌ 配置有误，请检查：")
        print("1. .env 文件是否存在")
        print("2. OPENAI_API_KEY 是否正确填写")
        print("3. OPENAI_BASE_URL 是否正确")
        print("4. 网络连接是否正常")
        print("\n配置指南: docs/LLM_CONFIG_GUIDE.md")

    print("=" * 60)


if __name__ == "__main__":
    main()
