#!/usr/bin/env python3
"""
启动Web服务 - Python版本
"""

import sys
import os
import subprocess

def start_server():
    """启动Web服务器"""

    print("=" * 80)
    print("🚀 旅行规划系统 Web 服务")
    print("=" * 80)
    print()

    # 切换到项目目录
    os.chdir("/workspace/projects")

    # 检查依赖
    print("📦 检查依赖...")
    try:
        import fastapi
        import uvicorn
        print("✅ 依赖已安装")
    except ImportError:
        print("⚠️  缺少依赖，正在安装...")
        subprocess.run(["uv", "add", "fastapi", "uvicorn"], check=True)
        print("✅ 依赖安装完成")

    print()
    print("📡 启动API服务器...")
    print()
    print("📝 访问地址:")
    print("  • API文档: http://localhost:8000/docs")
    print("  • 前端页面: file:///workspace/projects/web/index.html")
    print()
    print("💡 使用说明:")
    print("  1. 打开浏览器访问前端页面（上面提供的文件路径）")
    print("  2. 或者使用本地服务器:")
    print("     python -m http.server 8080 --directory web")
    print("     然后访问: http://localhost:8080")
    print()
    print("==========================================")
    print()

    # 启动服务器
    import uvicorn
    from web.api_server import app

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    start_server()
