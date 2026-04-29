# 云游 Voya — 部署说明

> 本文件分两部分：
> - **第一部分**：老师 / 评审在本机运行项目
> - **第二部分**：把网站发布到公网，让所有人可以访问

---

## 第一部分：本地运行（老师验证用）

### 环境要求

| 项目 | 最低版本 | 说明 |
|------|---------|------|
| Python | **3.12+** | `python --version` 查看 |
| pip | 任意 | 随 Python 附带 |
| 网络 | 可访问大模型 API | 需要调用外部 API |

> macOS 推荐用 [Homebrew](https://brew.sh) 安装 Python：`brew install python@3.12`

---

### 第一步：获取项目代码

**方式 A — 直接收到压缩包**（最常见）
```bash
unzip voya.zip          # 解压到当前目录
cd voya                 # 进入项目目录
```

**方式 B — 从 Git 仓库克隆**
```bash
git clone https://github.com/你的用户名/voya.git
cd voya
```

---

### 第二步：安装依赖

```bash
# 推荐使用清华镜像，国内速度快
pip install -r requirements_local.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

安装时间约 2–5 分钟，正常输出最后一行为 `Successfully installed ...`。

---

### 第三步：配置 API Key

```bash
# 复制配置模板
cp .env.example .env
```

用任意文本编辑器打开 `.env`，填写以下两项（至少填第一项）：

```env
# ① 大模型 API（必填，三选一）
# 豆包（推荐，新用户有免费额度）
OPENAI_API_KEY=你的豆包API密钥
OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3

# 通义千问
# OPENAI_API_KEY=你的通义API密钥
# OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# DeepSeek
# OPENAI_API_KEY=你的DeepSeek密钥
# OPENAI_BASE_URL=https://api.deepseek.com/v1

# ② 联网搜索（可选，不填则 AI 模式不搜索实时信息）
TAVILY_API_KEY=你的Tavily密钥
```

**如何获取 API Key**

| 服务 | 获取地址 | 费用 |
|------|---------|------|
| 豆包（推荐） | https://console.volcengine.com/ark | 新用户免费额度 |
| 通义千问 | https://bailian.console.aliyun.com | 新用户免费额度 |
| DeepSeek | https://platform.deepseek.com | 价格极低 |
| Tavily | https://tavily.com | 每月 1000 次免费 |

---

### 第四步：启动服务

```bash
python scripts/start_and_preview.py
```

启动成功后会自动打开浏览器，也可手动访问：

| 地址 | 说明 |
|------|------|
| http://localhost:8000/preview | **主界面**（推荐从这里开始） |
| http://localhost:8000/docs | API 接口文档（Swagger UI） |
| http://localhost:8000/redoc | API 接口文档（ReDoc） |

---

### 常见问题

**Q: 启动报错 `ModuleNotFoundError`**
```bash
pip install -r requirements_local.txt
```

**Q: 报错 `OPENAI_API_KEY not set` 或 AI 模式无响应**
- 检查 `.env` 文件是否存在（注意：`.env` 不是 `.env.example`）
- 确认 API Key 已正确填写，无多余空格

**Q: AI 模式显示"加载失败"**
- 确认 `OPENAI_BASE_URL` 与 Key 对应的服务商一致
- 用规则系统或监督系统先验证基本功能

**Q: 端口 8000 被占用**
```bash
lsof -ti:8000 | xargs kill -9   # macOS / Linux
# Windows: netstat -ano | findstr 8000，再 taskkill /PID xxx /F
```

**Q: 停止服务**
- 终端按 `Ctrl + C`，或：
```bash
pkill -f "uvicorn web.api_server"
```

---

## 第二部分：发布到公网

> 本节介绍三种方案，从易到难排序。  
> 推荐先试 **方案 A（Railway）**，5 分钟内可完成。

---

### 前提：把代码推到 GitHub

```bash
# 在项目目录执行
git add .
git commit -m "准备部署"
git push origin main
```

确认 `.gitignore` 中有 `.env`（已配置，API key 不会上传）。

---

### 方案 A — Railway（最简单，推荐）

**适合**：快速演示，不需要备案，国际访问友好

1. 访问 [railway.app](https://railway.app) → 用 GitHub 账号登录
2. 点击 **New Project → Deploy from GitHub repo** → 选择你的仓库
3. Railway 会自动检测 Python 项目，构建命令已通过项目根目录的 `Procfile` 配置好
4. 进入 **Variables** 标签，添加以下环境变量：

   ```
   OPENAI_API_KEY      = 你的密钥
   OPENAI_BASE_URL     = https://ark.cn-beijing.volces.com/api/v3
   TAVILY_API_KEY      = 你的密钥（可选）
   ```

5. 点击 **Deploy** → 等待约 3 分钟 → 获得公网地址（如 `https://voya-xxxx.up.railway.app`）

**费用**：每月 $5 免费额度，足够演示使用。

---

### 方案 B — Render（免费，有冷启动）

**适合**：完全免费，接受 15 分钟无访问后"睡眠"的限制

1. 访问 [render.com](https://render.com) → 用 GitHub 登录
2. **New → Web Service** → 选择仓库
3. 填写配置：
   - **Build Command**：`pip install -r requirements_local.txt`
   - **Start Command**：`uvicorn web.api_server:app --host 0.0.0.0 --port $PORT`
   - **Python Version**：`3.12`
4. 在 **Environment** 中添加环境变量（同上）
5. 点击 **Create Web Service** → 等待部署完成

**注意**：免费版 15 分钟无请求后自动睡眠，第一次访问需等待约 30 秒唤醒。

---

### 方案 C — 阿里云 ECS（稳定，适合国内用户）

**适合**：长期运行、国内访问速度快、需要备案

#### 购买服务器
- 访问 [aliyun.com](https://aliyun.com) → 云服务器 ECS
- 配置推荐：2核 2GB，Ubuntu 22.04，按量付费（约 ¥0.3/小时）

#### 服务器配置
```bash
# SSH 连接到服务器后执行

# 安装 Python 3.12
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip git

# 克隆项目
git clone https://github.com/你的用户名/voya.git
cd voya

# 安装依赖
pip3 install -r requirements_local.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 配置环境变量
cp .env.example .env
nano .env     # 填写 API keys

# 后台运行服务
nohup uvicorn web.api_server:app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &

echo "服务已启动，访问 http://服务器IP:8000/preview"
```

#### 开放端口
在阿里云控制台 → 安全组 → 入方向 → 添加规则：
- 端口范围：`8000/8000`
- 授权对象：`0.0.0.0/0`

---

### 三种方案对比

| | Railway | Render | 阿里云 ECS |
|--|---------|--------|----------|
| 难度 | ⭐ 最简单 | ⭐⭐ | ⭐⭐⭐ |
| 费用 | $5/月免费额度 | 完全免费 | ~¥0.3/小时 |
| 速度 | 快 | 有冷启动延迟 | 取决于配置 |
| 国内访问 | 一般 | 一般 | 快 |
| 适合 | 演示/答辩 | 长期免费展示 | 正式上线 |

---

## 项目文件结构速览

```
voya/
├── web/
│   ├── api_server.py          # FastAPI 后端主文件
│   └── assets/
│       ├── app.js             # 前端逻辑
│       ├── style.css          # 样式
│       └── index.html         # 主页面
├── systems/
│   ├── rule_based/            # 规则引擎
│   ├── supervised/            # 机器学习模型
│   └── goal_based/            # LLM Agent
├── assets/
│   └── knowledge_db/          # ChromaDB 向量知识库（22城市）
├── scripts/
│   └── start_and_preview.py   # 一键启动脚本
├── requirements_local.txt     # Python 依赖
├── .env.example               # 环境变量模板
├── Procfile                   # Railway/Heroku 部署配置
└── render.yaml                # Render 部署配置
```

---

*云游 Voya · AI Travel Planning · emlyon business school · Spring 2026*
