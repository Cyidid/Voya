# 云游 Voya · 部署指南

本文档分两部分：**本地运行**和**发布到公网**。

---

## 第一部分：本地运行

### 环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.12 或以上（`python --version` 查看） |
| pip | 随 Python 附带，无需单独安装 |
| 网络 | 可访问所选大模型的 API 地址 |

macOS 推荐通过 Homebrew 安装：`brew install python@3.12`

---

### 第一步：获取代码

```bash
git clone https://github.com/Cyidid/Voya.git
cd Voya
```

---

### 第二步：安装依赖

```bash
pip install -r requirements_local.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

安装时间约 2–5 分钟，最后一行出现 `Successfully installed ...` 即为成功。

---

### 第三步：配置 API Key

```bash
cp .env.example .env
```

用任意文本编辑器打开 `.env`，填写大模型 API Key。推荐使用通义千问（新用户有免费额度），详见 `.env.example` 中的说明和 API Key 获取链接。

---

### 第四步：启动服务

```bash
python scripts/start_and_preview.py
```

启动成功后自动打开浏览器。也可手动访问：

| 地址 | 说明 |
|------|------|
| http://localhost:8000/preview | 主界面 |
| http://localhost:8000/docs | API 文档（Swagger UI） |
| http://localhost:8000/redoc | API 文档（ReDoc） |

---

### 常见问题

**报错 `ModuleNotFoundError`**

```bash
pip install -r requirements_local.txt
```

**报错 `OPENAI_API_KEY not set` 或实时规划无响应**

- 确认 `.env` 文件存在（不是 `.env.example`）
- 确认 API Key 已填写且无多余空格

**实时规划显示"加载失败"**

- 确认 `OPENAI_BASE_URL` 与所选服务商一致
- 可先切换到"经典规划"或"偏好匹配"验证基本功能是否正常

**端口 8000 被占用**

```bash
# macOS / Linux
lsof -ti:8000 | xargs kill -9

# Windows
netstat -ano | findstr 8000
taskkill /PID <上面查到的PID> /F
```

**停止服务**

```bash
# Ctrl+C，或：
pkill -f "uvicorn web.api_server"
```

---

## 第二部分：发布到公网

三种方案对比：

| 方案 | 难度 | 费用 | 冷启动 | 国内访问速度 |
|------|------|------|--------|------------|
| Railway（推荐） | 低 | 每月 $5 免费额度 | 无 | 一般 |
| Render | 中 | 完全免费 | 有（约 30s） | 一般 |
| 阿里云 ECS | 高 | 约 ¥0.3 / 小时 | 无 | 快 |

---

### 方案 A — Railway（推荐）

适合快速上线，无需备案，国际访问友好。

1. 访问 [railway.app](https://railway.app)，使用 GitHub 账号登录
2. 点击 **New Project → Deploy from GitHub repo**，选择本仓库
3. Railway 自动检测 `Dockerfile` 并构建，无需额外配置
4. 进入 **Variables** 标签，添加以下环境变量：

   ```
   OPENAI_API_KEY  = 你的 API Key
   OPENAI_BASE_URL = https://dashscope.aliyuncs.com/compatible-mode/v1
   MODEL_NAME      = qwen3.6-plus
   TAVILY_API_KEY  = 你的 Tavily Key（可选）
   ```

5. 点击 **Deploy**，约 3 分钟后获得公网 HTTPS 地址

说明：Railway 通过 `$PORT` 环境变量注入端口，uvicorn 自动监听，无需手动配置。

---

### 方案 B — Render（完全免费）

适合零成本部署，可接受 15 分钟无流量后自动休眠的限制。

1. 访问 [render.com](https://render.com)，使用 GitHub 账号登录
2. 点击 **New → Web Service**，选择本仓库
3. 填写以下配置：
   - **Build Command**：`pip install -r requirements_local.txt`
   - **Start Command**：`uvicorn web.api_server:app --host 0.0.0.0 --port $PORT`
   - **Python Version**：`3.12`
4. 在 **Environment** 中添加环境变量（同方案 A）
5. 点击 **Create Web Service**，等待部署完成

注意：免费版在 15 分钟无请求后自动休眠，首次访问需等待约 30 秒唤醒。

---

### 方案 C — 阿里云 ECS

适合国内访问速度要求高、需要长期稳定运行的场景。

```bash
# SSH 登录服务器后执行

sudo apt update && sudo apt install -y python3.12 python3.12-venv python3-pip git

git clone https://github.com/Cyidid/Voya.git
cd Voya

pip3 install -r requirements_local.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

cp .env.example .env
nano .env   # 填写 API Key

nohup uvicorn web.api_server:app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
```

在阿里云控制台的安全组规则中，开放入方向 `8000` 端口。

---

> 系统架构和 API 完整参考见 [SYSTEM_GUIDE.md](SYSTEM_GUIDE.md)
