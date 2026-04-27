#!/usr/bin/env python3
"""
Web 服务启动脚本
"""

import subprocess
import time
import sys
import os
from pathlib import Path


def check_service_running(url):
    try:
        import requests
        return requests.get(url, timeout=5).status_code == 200
    except:
        return False


def main():
    # 切换到项目根目录
    project_dir = Path(__file__).parent.parent
    os.chdir(project_dir)

    # 加载 .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    # 检查 .env
    if not Path(".env").exists():
        print("未找到 .env 文件，请先执行: cp .env.example .env 并填写 API keys")
        print()

    # 检查依赖
    try:
        import fastapi, uvicorn
    except ImportError:
        print(" 安装依赖...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements_local.txt"], check=True)

    # 启动服务
    subprocess.Popen([
        sys.executable, "-m", "uvicorn",
        "web.api_server:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ])

    # 等待服务就绪
    for _ in range(15):
        if check_service_running("http://localhost:8000/"):
            break
        time.sleep(1)
    else:
        print(" 服务启动失败，请检查日志")
        return

    print(" 服务启动成功！")
    print()
    print(" http://localhost:8000/preview")
    print(" http://localhost:8000/docs")
    print()
    print("停止服务: lsof -ti:8000 | xargs kill -9")
    print()

    # 自动打开浏览器
    import webbrowser
    webbrowser.open("http://localhost:8000/preview")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        subprocess.run(["pkill", "-f", "uvicorn web.api_server"])
        print("服务已停止")


if __name__ == "__main__":
    main()
