# Voya · AI Travel Planner

> 三种 AI 设计范式的旅行行程规划系统：规则系统 · 监督学习 · 目标导向智能体

---

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements_local.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 配置 API Keys
cp .env.example .env
# 编辑 .env，填入大模型 API Key（通义千问 / DeepSeek 等 OpenAI 兼容接口）

# 3. 启动服务
python scripts/start_and_preview.py

# 4. 打开浏览器
open http://localhost:8000/preview
```

停止服务：
```bash
lsof -ti:8000 | xargs kill -9
```

---

## 三种 AI 系统

| 系统 | 前端名称 | 文件 | 响应时间 | 城市覆盖 | 特点 |
|------|----------|------|----------|----------|------|
| 规则系统 | 经典规划 | `systems/rule_based/engine.py` | < 0.1ms | 18 个固定城市 | 完全确定，100% 可解释，无需联网 |
| 监督学习 | 偏好匹配 | `systems/supervised/inference.py` | < 1ms | 训练分布内 | VotingClassifier，95.4% 准确率，13 维偏好特征 |
| 目标导向智能体 | 实时规划 | `systems/goal_based/agent_agentic.py` | 30–60s | 全球无限制 | 通义千问 Qwen + Tavily 实时联网搜索 + SSE 流式输出 |

---

## 目录结构

```
projects/
├── web/
│   ├── index.html          # 前端界面（单文件 SPA，中英双语）
│   └── api_server.py       # FastAPI 后端（/api/generate · /api/generate/stream · /api/booking/*）
├── systems/
│   ├── rule_based/         # 规则系统（18城市专家规则库）
│   ├── supervised/         # 监督学习系统（VotingClassifier）
│   ├── goal_based/         # 目标导向智能体
│   │   ├── agent_agentic.py    # 主 Agent（Tool Calling，SSE 流式输出）
│   │   ├── tavily_client.py    # Tavily 实时联网搜索客户端
│   │   └── local_knowledge_client.py  # ChromaDB 本地知识库
│   ├── booking/
│   │   └── booking_engine.py   # 机票/火车票搜索 + 订单管理
│   └── config.py           # 系统配置（LLM 参数、temperature、max_tokens）
├── assets/
│   ├── knowledge_paris.md  # 巴黎知识库
│   ├── knowledge_tokyo.md  # 东京知识库
│   ├── knowledge_newyork.md # 纽约知识库
│   └── orders/orders.json  # 订单持久化
├── scripts/
│   ├── start_and_preview.py   # 一键启动脚本
│   └── import_local_knowledge.py  # 导入知识库到 ChromaDB
├── .env.example            # 环境变量模板
├── requirements_local.txt  # 本地依赖
└── SYSTEM_GUIDE.md         # 完整技术文档
```

---

## 大模型配置

在 `.env` 中配置，支持任意 OpenAI 兼容接口：

```env
# 通义千问（推荐）
OPENAI_API_KEY=你的API密钥
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_NAME=qwen-plus

# DeepSeek
# OPENAI_BASE_URL=https://api.deepseek.com/v1
# MODEL_NAME=deepseek-chat
```

模型参数（`systems/config.py`）：
- `model_name`：默认 `qwen-plus`（可选 `qwen-max` / `qwen-turbo`）
- `temperature`：0.75（适度随机，行程内容更丰富）
- `max_tokens`：6000（支持完整多日详细行程输出）

**注意**：系统自动绕过本地代理直连 API，无需额外配置。

---

## 主要功能

| 功能 | 说明 |
|------|------|
| **SSE 流式输出** | 实时规划行程逐字推流显示，`/api/generate/stream` |
| **自然语言输入** | 对话框解析自由文本，自动填写出行参数 |
| **实用工具面板** | 汇率换算（15种货币）· 紧急联系方式（19城市）· 常用短语 |
| **票务预订** | 机票/火车票搜索（真实数据）+ 未覆盖路线 Tavily 联网兜底 |
| **国际目的地检测** | 选择海外目的地时自动将"自驾"切换为"飞机" |
| **我的旅行** | 本地保存行程记录，支持星级评分和出行备注 |
| **中英双语** | 界面完整中英双语切换，持久化记忆语言选择 |

---

## 知识库（可选）

导入知识库可提升巴黎、东京、纽约的行程质量：

```bash
python scripts/import_local_knowledge.py
```

其他城市通过 Tavily 实时联网搜索补充信息。

---

详细技术文档见 [SYSTEM_GUIDE.md](SYSTEM_GUIDE.md)

*Voya · AI Travel Planner · v3.2 · 2026-04*
