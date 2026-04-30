FROM python:3.12-slim

WORKDIR /app

# 安装依赖（不含 dbus-python / PyGObject 等系统库依赖）
COPY requirements_local.txt .
RUN pip install --no-cache-dir -r requirements_local.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目文件
COPY . .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn web.api_server:app --host 0.0.0.0 --port ${PORT:-8000}"]
