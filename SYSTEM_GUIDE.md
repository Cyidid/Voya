# Voya · AI Travel Planner — 完整技术文档

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [目录结构](#3-目录结构)
4. [快速启动](#4-快速启动)
5. [三种 AI 范式详解](#5-三种-ai-范式详解)
6. [票务预订系统](#6-票务预订系统)
7. [前端界面](#7-前端界面)
8. [API 完整参考](#8-api-完整参考)
9. [Responsible AI 设计](#9-responsible-ai-设计)

---

## 1. 项目概述

**Voya** — AI Travel Planner，通过"旅行行程规划"这一具体领域，实现并对比三种主流 AI 设计范式。

| 范式 | 前端名称 | 核心机制 | 响应时间 | 可解释性 | 城市覆盖 |
|------|----------|----------|----------|----------|----------|
| 规则系统 | 经典规划 | 人工编写专家规则库，确定性匹配 | < 0.1ms | 完全透明，每条可追溯 | 25 个固定城市 |
| 监督学习 | 偏好匹配 | 集成分类器学习偏好模式，预测最适旅行类型 | < 1ms（单例） | 特征权重可见（Top-3） | 全局（训练分布内） |
| 目标导向智能体 | 实时规划 | LLM 自主决策 + 工具调用 + 实时联网 | 30–60s（缓存即时） | 决策步骤可追踪 | 全球无限制 |

**用户输入**：城市、天数、预算、兴趣偏好、出行类型、人数、出行方式、出发地、出发日期、特殊需求  
**系统输出**：Markdown 格式每日行程 + 预算估算 + 餐厅/交通/住宿建议

---

## 2. 系统架构

```
用户浏览器（web/index.html + assets/app.js）
        │  HTTP POST /api/generate          ← 同步返回（三种系统均支持）
        │  HTTP POST /api/generate/stream   ← SSE 流式（goal_based 逐字；supervised 分块；rule_based 即时 done）
        │  HTTP POST /api/chat              ← 自然语言对话接口
        │  HTTP POST /api/booking/*         ← 票务预订
        ▼
  FastAPI 后端（web/api_server.py）
        │
        ├─── agent_type = "rule_based"
        │         └── systems/rule_based/engine.py
        │                   └── parse_natural_language() → 规则匹配 → 行程组装
        │
        ├─── agent_type = "supervised"
        │         └── systems/supervised/inference.py
        │                   └── model.pkl（VotingClassifier，单例加载）
        │                         └── 特征提取 → 分类预测 → 行程生成
        │
        ├─── agent_type = "goal_based"
        │         └── agent_agentic.py（知识库预查询 + LLM + SSE 流式）
        │
        └─── /api/booking/*
                  └── booking_engine.py（确定性定价 + Tavily 联网兜底）
```

---

## 3. 目录结构

```
projects/
├── web/
│   ├── api_server.py        — FastAPI 后端
│   ├── assets/
│   │   ├── app.js           — 前端逻辑（渲染/流式/i18n/票务）
│   │   └── style.css        — 暖铜色调设计系统
│   └── index.html           — 主页面（中英双语）
├── systems/
│   ├── config.py            — 全局配置（模型参数、LLM配置）
│   ├── rule_based/
│   │   └── engine.py        — 规则引擎（25城市，含双语贴士 RULES_EN）
│   ├── supervised/
│   │   ├── inference.py     — VotingClassifier 训练/推理/行程生成
│   │   ├── model.pkl        — 已训练模型（首次运行自动生成）
│   │   └── training_dataset.json
│   ├── goal_based/
│   │   ├── agent_agentic.py         — 主智能体（知识库预查询 + SSE 流式）
│   │   ├── local_knowledge_client.py — ChromaDB 本地知识库客户端
│   │   └── tavily_client.py         — Tavily 联网搜索客户端
│   └── booking/
│       └── booking_engine.py        — 机票/火车票搜索 + 订单管理
├── assets/
│   ├── knowledge_paris.md   ─┐
│   ├── knowledge_tokyo.md    │ ChromaDB 知识库源文件（25城市）
│   └── ...                  ─┘
├── scripts/
│   ├── import_local_knowledge.py    — 导入知识库到 ChromaDB
│   ├── start_and_preview.py         — 一键启动
│   └── evaluate_systems.py          — 三系统对比评估
├── logs/api.log
├── requirements_local.txt
└── .env.example
```

---

## 4. 快速启动

### 安装与配置

```bash
pip install -r requirements_local.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY 和 OPENAI_BASE_URL
```

### 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `OPENAI_API_KEY` | 必填 | 大模型 API Key（通义千问 / DeepSeek 等） |
| `OPENAI_BASE_URL` | 必填 | LLM 接口地址 |
| `MODEL_NAME` | 可选 | 默认 `qwen3.6-plus` |
| `TAVILY_API_KEY` | 可选 | 联网搜索；不填时实时规划仅用 LLM 参数知识 |

### 启动服务

```bash
python scripts/start_and_preview.py        # 一键启动（推荐）
uvicorn web.api_server:app --port 8000 --reload  # 热重载开发模式
```

访问：`http://localhost:8000/preview`

### 单独测试各系统

```bash
python systems/rule_based/engine.py
python systems/supervised/inference.py      # 首次运行约 1 分钟（训练模型）
python systems/goal_based/agent_agentic.py  # 需要 .env 配置
```

---

## 5. 三种 AI 范式详解

### 5.1 规则系统（Rule-Based Expert System）— 经典规划

**文件**：`systems/rule_based/engine.py`

#### 功能定位

人工编写的确定性推荐引擎。每条行程推荐均可追溯至规则库中的具体条目，逻辑 100% 透明，无需联网，毫秒响应。适合对输出可预期性要求高的场景。

#### 工作机制

```
用户输入（自然语言 / 结构化参数）
    ↓
parse_natural_language()  — NLP 预处理层
    ↓ 提取：城市、天数、预算、兴趣、出行类型、人数、出行方式、特殊需求
规则匹配
    ↓ RULES[城市][兴趣类别] → 景点列表
    ↓ 轮换逻辑：step = (day-1)*2 + (上午0/下午1)，确保跨天不重复
行程组装 → Markdown 输出
```

**支持城市（25个）**：
> 国内：广州  
> 近邻亚洲：东京、大阪、京都、首尔、新加坡、曼谷、普吉岛、巴厘岛、马尔代夫  
> 中东：迪拜、伊斯坦布尔、开罗  
> 大洋洲：悉尼  
> 欧洲：巴黎、伦敦、罗马、巴塞罗那、阿姆斯特丹、维也纳、布拉格、哥本哈根、苏黎世、里斯本  
> 美洲：纽约

**NLP 预处理层（parse_natural_language）**：

| 提取字段 | 方法 |
|----------|------|
| `city` | CITY_NORMALIZE 别名字典（英文/别称 → 中文标准名） |
| `days` | 正则 `\d+天`，范围 1–14 |
| `budget` | 关键词（高/充裕/奢华 → 高；省钱/穷游 → 低） |
| `interests` | 7类兴趣关键词扫描 |
| `group` | 情侣/夫妻/朋友/家庭/单人 关键词 |
| `origin` | 正则 `从...出发` / `X飞Y` 双格式 |
| `special` | 儿童/老人/轮椅 关键词 |

**气候感知**：`CITY_CLIMATE` 按季节存储气候描述，结合 `start_date` 生成 `weather_note` 和极端天气备选建议。

**双语贴士**：`RULES_EN` 与 `RULES` 并行，API 同时返回 `transport_tip_en` / `city_tips_en`，前端按语言选择。

**城市外处理**：回退至巴黎 + `coverage_gap=True` 警告，不静默失败。

**性能**：响应时间 < 0.1ms；完全确定性（相同输入永远相同输出）。

---

### 5.2 监督学习系统（Supervised ML）— 偏好匹配

**文件**：`systems/supervised/inference.py`  
**模型文件**：`systems/supervised/model.pkl`（首次运行自动训练并保存）

#### 功能定位

集成学习分类器，从用户输入的 20 维特征中预测最适合的旅行类型（8选1），再根据类型生成匹配的行程内容。核心价值是**从偏好模式中学习**，而非写死规则。

#### 推荐算法机制

```
用户输入（城市/天数/预算/兴趣/出行类型等）
    ↓
_extract_features()  — 特征向量化（20维）
    ↓
VotingClassifier 软投票（3个基学习器并行预测）
    ├── GradientBoostingClassifier（n=120, depth=3, lr=0.08）
    ├── RandomForestClassifier（n=120, depth=6, min_leaf=5）
    └── ExtraTreesClassifier（n=100, depth=6, min_leaf=5）
    ↓ 软投票：取各类别概率均值，选概率最大的类别
预测结果：推荐类型（0–7）+ 置信度（max概率）
    ↓
_build_itinerary()  — 按推荐类型生成行程
    ├── CITY_TYPE_ACTIVITIES 有数据 → 使用真实景点（5城市）
    └── 无数据 → 通用活动模板（按类型8套）
    ↓
返回：Markdown 行程 + 推荐类型 + 置信度 + Top-3 特征重要性
```

**输入特征（20维）**：

| 维度 | 特征 |
|------|------|
| 行程参数（6维） | days, budget_level, num_people, group_type, has_special, travel_mode |
| 兴趣偏好（7维） | culture, nature, food, shopping, history, nightlife, outdoor |
| 城市编码（7维） | city_paris, city_tokyo, city_newyork, city_london, city_rome, city_seoul, city_dubai |

**8 种推荐类型**：

| ID | 中文名 | 主要触发条件（专家规则） |
|----|--------|------------------------|
| 0 | 经济观光 | 低预算，无其他强烈偏好 |
| 1 | 文化深度游 | 文化/历史兴趣为主，购物/美食兴趣为零 |
| 2 | 奢华体验 | 高预算（非情侣） |
| 3 | 亲子家庭游 | 家庭出行（group_type=3），兜底规则 |
| 4 | 美食购物游 | 美食/购物兴趣为主，文化/历史兴趣为零 |
| 5 | 户外探险游 | 户外/自然兴趣 + 天数 ≥ 3 |
| 6 | 情侣浪漫游 | 情侣出行 + 高预算 |
| 7 | 团队社交游 | 夜生活兴趣 + 人数 ≥ 4 |

**训练数据**：
- 10,000 条程序生成样本（`_expert_label()` 专家规则函数自动标注）
- **15% 均匀随机标签噪声**（训练集和测试集均施加，模拟真实标注不确定性）
- 80/20 训练/测试分割（random_state=42）
- 测试集准确率：**86.8%**（噪声数据下的真实场景估计，非规则完美复现）

**标签噪声的作用**：若不加噪声，模型直接学习 `_expert_label()` 确定性规则，训练集准确率可达 99.2% 但无现实意义（循环验证）。加入 15% 噪声后，模型需要应对标注歧义，准确率更接近真实用户偏好预测能力。

**城市-类型活动映射（CITY_TYPE_ACTIVITIES）**：

5个城市有真实景点数据，其余城市回退至通用模板：

| 城市 | 已覆盖推荐类型 |
|------|--------------|
| 东京 | 文化深度游(1)、亲子家庭游(3)、户外探险游(5) |
| 巴黎 | 文化深度游(1)、亲子家庭游(3)、户外探险游(5) |
| 首尔 | 文化深度游(1)、亲子家庭游(3)、美食购物游(4) |
| 新加坡 | 文化深度游(1)、亲子家庭游(3)、美食购物游(4) |
| 迪拜 | 奢华体验(2)、亲子家庭游(3)、美食购物游(4) |

**单例模式**：模块级 `_engine` 变量，首次请求加载 model.pkl，后续复用内存中模型，推理延迟 < 1ms。

**流式输出**：每 3 行合并为一个 chunk，延迟 10ms，产生打字机效果。

---

### 5.3 目标导向智能体（Goal-Based Agentic AI）— 实时规划

**主文件**：`systems/goal_based/agent_agentic.py`

#### 功能定位

给定高层目标，AI 自主决策调用哪些工具、调用多少次，最终生成基于实时信息的个性化行程。支持全球任意目的地，每份行程均融合了最新联网数据与本地知识库。

> 符合课程定义：*"The AI is given a high-level goal and freedom to determine its own process and solution."*

#### 工作机制

```
用户输入（自然语言描述）
    ↓
两阶段工具策略（stream_itinerary）
    │
    ├─ 阶段1：预查询（LLM 生成前执行）
    │    ├── query_knowledge_base(city, query)
    │    │       → ChromaDB 本地知识库（25城市，294条文档）
    │    │       → 注入本地 POI/价格/贴士（最多 1800 字符）
    │    └── search_web(query, topic)
    │            → Tavily API 实时搜索（中文关键词）
    │            → 注入最新攻略参考（最多 1500 字符）
    │
    └─ 阶段2：LLM 流式生成
         └── 结合两阶段注入的上下文，stream=True 逐 chunk yield
                 → SSE 推流到前端（data: {"chunk": "..."}）
                 → 完成后发送 done 事件（含 agent_steps）
```

**工具定义**：

```python
search_web(query, topic)           # Tavily API 实时搜索（query 必须为中文关键词）
query_knowledge_base(city, query)  # ChromaDB 本地知识库查询
```

**LLM 配置**（`systems/config.py`）：
- 模型：通义千问 Qwen（默认 qwen3.6-plus，支持任意 OpenAI 兼容接口）
- temperature：0.75（输出丰富多样）
- max_tokens：8192（支持完整多天详细行程）

**缓存机制**：类级别 `_class_cache` dict，最大 30 条，key 为城市+天数+偏好的 MD5 哈希，LRU 淘汰，缓存命中时秒级响应。

**SSE 流式输出**：
- chunk 事件：`data: {"chunk": "..."}`
- 完成事件：`data: {"done": true, "processing_time": X, "tool_rounds": N, "agent_steps": [...]}`
- `agent_steps` 每条记录：`tool`、`args.query`（中文查询词）、`result_preview`、`time_s`

**响应时间**：实时生成 30–60 秒；缓存命中即时响应。

---

## 6. 票务预订系统

**文件**：`systems/booking/booking_engine.py`

### API 路由

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/booking/search` | 搜索机票或火车票 |
| `POST` | `/api/booking/create` | 创建预订订单 |
| `GET` | `/api/booking/orders` | 获取订单列表（按创建时间倒序） |
| `GET` | `/api/booking/orders/{id}` | 获取单个订单详情 |
| `DELETE` | `/api/booking/orders/{id}` | 取消订单 |

**国内城市（21个）**：上海、北京、广州、深圳、成都、杭州、武汉、重庆、西安、南京、天津、青岛、厦门、昆明、三亚、长沙、郑州、沈阳、哈尔滨、乌鲁木齐、拉萨

**国际目的地（20个）**：巴黎(CDG)、东京(NRT)、纽约(JFK)、伦敦(LHR)、罗马(FCO)、悉尼(SYD)、巴塞罗那(BCN)、曼谷(BKK)、新加坡(SIN)、首尔(ICN)、迪拜(DXB)、阿姆斯特丹(AMS)、维也纳(VIE)、布拉格(PRG)、伊斯坦布尔(IST)、里斯本(LIS)、普吉岛(HKT)、马尔代夫(MLE)、冰岛(KEF)、开罗(CAI)

**确定性定价**：`_price()` 函数使用路线+日期的 MD5 哈希作为随机种子，相同查询永远返回相同结果。

**Tavily 联网兜底**：未覆盖路线自动启用 Tavily 搜索，返回 `type="web_info"` 参考信息卡，前端明确标注"网络参考信息"，不可直接预订。

**订单存储**：持久化至 `assets/orders/orders.json`，证件号仅存储后 4 位，前缀全部 `*` 脱敏。

---

## 7. 前端界面

**技术**：纯原生 HTML/CSS/JS，无框架；marked.js 渲染 Markdown；SSE 流式逐字渲染。

### 设计系统

暖铜色调，全部使用 CSS 变量：

| 变量 | 值 | 用途 |
|------|-----|------|
| `--accent` | `#C4854A` | 主品牌色（铜色） |
| `--bg` | `#F5F3EF` | 页面背景（暖米白） |
| `--card` | `#FFFFFF` | 卡片背景 |
| `--green` | `#22C55E` | 成功/公平 |

### 主要功能模块

| 模块 | 说明 |
|------|------|
| 系统选择 Tab | 顶部导航 + 搜索卡 Tab 双联动（nav-pill + sc-tab） |
| 搜索表单 | 目的地/出发地/天数/出行类型/预算/人数/出行方式/出发日期/特殊需求 |
| 目的地快选网格 | 城市图片卡，点击自动填入参数并检测国内/国际切换交通方式 |
| 结果视图 | 主区域 Markdown 行程（SSE 流式渲染）+ 右侧分析侧边栏 |
| 侧边栏（偏好匹配） | 行程摘要 + 模型决策（推荐类型/置信度/特征权重/准确率/模型类型） |
| 侧边栏（实时规划） | 行程摘要 + 规划过程时间线（工具调用步骤可视化） |
| 侧边栏（经典规划） | 行程摘要 + 规则引擎信息 + 交通贴士 + 城市小贴士 |
| 票务面板 | 机票/火车票搜索 + 订单管理，支持 web_info 兜底展示 |
| 对话栏 | 自然语言输入 → 自动解析填表（/api/chat） |
| 实用工具面板 | 悬浮侧边 Tab：汇率换算 / 紧急联系 / 常用短语 |
| 智能填写 | 历史记录一键回填表单，并 scrollIntoView 引导用户确认 |
| i18n | 中文/English 双语，localStorage 持久化，全组件同步切换 |

### 流式渲染

- `result-grid { align-items: start }` — 防止侧边栏撑高行程区产生空白
- 每帧调用 `text.trimEnd()` 再 `marked.parse()`，避免尾部 `\n\n` 生成空 `<p>`
- rAF 节流：每帧仅渲染一次，避免每个 token 操作 DOM

### 国际目的地自动切换交通

`_autoSwitchTransport(city)` 在 5 个入口自动调用。判断逻辑：命中国内城市列表或包含"省/市/区/县/山/岛"→ 国内不切换；其余 → 国际，若当前为"自驾"自动改为"飞机"并提示。

---

## 8. API 完整参考

### POST `/api/generate`

**请求体**：
```json
{
  "city": "东京",
  "days": 5,
  "budget": "中",
  "interests": ["文化", "美食"],
  "group": "家庭",
  "num_people": 4,
  "travel_mode": "飞机",
  "special": "有儿童",
  "origin": "上海",
  "start_date": "2026-05-01",
  "agent_type": "supervised"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `city` | string | 必填 | 目的地（中文或英文别名） |
| `days` | int(1–14) | 必填 | 旅行天数 |
| `budget` | string | 必填 | `低` / `中` / `高` |
| `interests` | string[] | 必填 | 文化/自然/美食/购物/历史/夜生活/户外运动 |
| `group` | string | 必填 | `单人` / `情侣` / `夫妻` / `朋友` / `家庭` |
| `num_people` | int | 可选 | 人数（情侣/夫妻自动归一为 2） |
| `travel_mode` | string | 可选 | `飞机` / `高铁` / `自驾` / `邮轮` |
| `origin` | string | 可选 | 出发城市 |
| `start_date` | string | 可选 | `YYYY-MM-DD`，用于气候判断和返程日期计算 |
| `special` | string | 可选 | `无` / `有儿童` / `有老人` / `轮椅友好` |
| `agent_type` | string | 可选 | `rule_based` / `supervised` / `goal_based`（默认 goal_based） |

**响应体**（监督学习示例）：
```json
{
  "itinerary": "# 东京 5日亲子家庭游\n...",
  "agent_type": "supervised",
  "processing_time": 0.0008,
  "metadata": { "city": "东京", "days": 5, "budget": "中" },
  "recommendation_type_zh": "亲子家庭游",
  "model_confidence": 0.82,
  "top_features": [["出行类型", 0.2341], ["旅行天数", 0.1823], ["特殊需求", 0.1205]]
}
```

监督学习额外字段：`recommendation_type_zh`、`model_confidence`、`top_features`  
规则系统额外字段：`transport_tip`、`city_tips`  
目标导向额外字段：`agent_steps`、`tool_rounds`

### POST `/api/generate/stream`

SSE 流式接口，请求体与 `/api/generate` 相同。

| 系统 | 流式行为 |
|------|---------|
| goal_based | 逐 chunk 推流（LLM 原生流式） |
| supervised | 每 3 行一个 chunk，延迟 10ms |
| rule_based | 单次 done 事件（毫秒响应） |

**SSE 事件格式**：

| 事件 | 结构 |
|------|------|
| 文本 chunk | `{"chunk": "..."}` |
| 完成（goal_based） | `{"done": true, "processing_time": X, "tool_rounds": N, "agent_steps": [...]}` |
| 完成（supervised/rule_based） | `{"done": true, "result_meta": {...}}` |
| 错误 | `{"error": "..."}` |

### POST `/api/chat`

```json
{ "role": "user", "content": "我想去巴黎玩5天，喜欢文化，预算充裕", "agent_type": "goal_based" }
```

自动解析城市/天数/预算/兴趣/出行类型等参数。`parse_warning` 字段：未能识别目的地时提示（不静默回退）。

### POST `/api/booking/search`

```json
{ "origin": "上海", "destination": "巴黎", "date": "2026-05-01", "type": "flight" }
```

覆盖路线返回 `flight`/`train` 类型；未覆盖路线触发 Tavily 联网，返回 `web_info` 类型。

---

## 9. Responsible AI 设计

> 本节从学术视角分析系统的负责任 AI 设计，包含五大支柱落地和公平性量化分析。  
> **重要说明**：公平性指标（AOD）为模型训练时的评估结果，属于算法审计范畴，不在用户界面中展示——向终端用户展示固定的训练集统计数字并无实际意义，详见 §9.2。

---

### 9.1 三范式的设计取舍对比

三种范式在"功能实现"之外，各有不同的 Responsible AI 特性：

| 维度 | 规则系统（经典规划） | 监督学习（偏好匹配） | 目标导向（实时规划） |
|------|--------------------|--------------------|-------------------|
| **可解释性** | 完全透明：每条推荐可追溯至规则库具体条目 | 部分可解释：特征重要性（Top-3）可见，内部黑箱 | 过程可追踪：agent_steps 记录每轮工具调用 |
| **确定性** | 完全确定：相同输入永远相同输出 | 确定（推理阶段）：模型权重固定，预测可复现 | 非确定：temperature=0.75，每次生成略有差异 |
| **数据依赖** | 无数据依赖：规则人工编写，无训练集 | 合成数据：10000条程序生成样本+15%标签噪声 | 实时数据：Tavily 联网 + ChromaDB 知识库 |
| **幻觉风险** | 无（规则库确定性） | 低（分类+模板，不自由生成文字） | 存在（LLM 自由生成，可能产生不准确信息） |
| **城市覆盖** | 固定25城，超出回退 | 25城预算数据，模型泛化能力有限 | 全球无限制 |
| **响应速度** | < 0.1ms | < 1ms（单例） | 30–60s（缓存命中即时） |

---

### 9.2 推荐算法机制（监督学习）与公平性审计的关系

#### 推荐算法做什么

偏好匹配系统的**推荐算法**只做一件事：根据用户输入的偏好特征，从 8 种旅行类型中预测最适合的一种，再据此生成行程内容。它不关心公平性——它只关心预测是否准确。

**预测路径**：
```
用户偏好特征（20维） → VotingClassifier → 推荐类型（0–7） → 行程生成
```

**有利标签定义**：label ≠ 0，即被预测为"非经济观光"类，代表获得品质更丰富的推荐。

#### 公平性审计做什么（独立于推荐算法）

公平性审计是对推荐算法的**事后检验**，回答的问题是：

> "这个模型在训练数据上，是否对不同用户群体提供了平等的优质推荐机会？"

它使用 **Average Odds Difference (AOD)**，由 Hardt et al.（2016）提出，IBM AIF360 采纳：

```
AOD = ½ × [(FPR_弱势群体 − FPR_优势群体) + (TPR_弱势群体 − TPR_优势群体)]

其中：
TPR（真正率）= 应该获得优质推荐的用户中，实际被预测为优质推荐的比例
FPR（假正率）= 不应获得优质推荐的用户中，被错误预测为优质推荐的比例
```

**判断标准**：
- `|AOD| < 0.05`：公平（两群体机会差异可忽略）
- `0.05 ≤ |AOD| < 0.10`：边界（存在轻微差异，建议关注）
- `|AOD| ≥ 0.10`：偏差（模型对该群体存在系统性差异对待）

#### 受保护属性的选择

选择受保护属性的原则：**用户通常无法主动改变或规避的特征**。

| 属性 | 是否选为受保护属性 | 理由 |
|------|------------------|------|
| `has_special`（携带儿童/老人/轮椅） | ✅ 是 | 用户无法轻易改变家庭成员构成 |
| `group_type`（家庭 vs 非家庭） | ✅ 是 | 家庭结构是客观状态，不是主观选择 |
| `budget_level`（预算等级） | ❌ 否 | 预算是用户主动申报的偏好约束；模型给高预算推荐奢华体验是**预期行为**，不是歧视 |

> 若将预算纳入保护属性，"高预算 → 奢华推荐"的设计逻辑本身就会被标记为偏差，这并不合理。

#### 实测公平性结果

基于 10,000 条合成数据（20% 测试集，含 15% 随机标签噪声）：

| 受保护属性 | 弱势群体 | 优势群体 | AOD 值 | 等级 | 分析 |
|-----------|---------|---------|--------|------|------|
| `has_special` | 有特殊需求（儿童/老人/轮椅）= 1 | 无特殊需求 = 0 | +0.025 | ✅ 公平 | 两组获得优质推荐的机会差异在可接受范围内 |
| `group_type` | 家庭出行（3） | 非家庭（单人/情侣/朋友） | +0.163 | ⚠ 偏差 | 家庭出行获得非经济类推荐的概率系统性偏低 |

**group_type 偏差的成因分析**：

原始规则中，家庭+特殊需求用户容易被锁定为 label=3（亲子家庭游），但亲子家庭游属于"有利标签"范围内（label≠0）。偏差来源于：其他出行类型（情侣/朋友）在某些特征组合下更容易被预测为 label≠0 的更高质量类型（如奢华体验/文化深度游）。

**已实施的缓解措施**：
1. 训练集各出行群体等权重采样（各 25%），避免家庭群体欠代表
2. `_expert_label()` 引入软规则：家庭+特殊需求用户根据兴趣分配多种类型，而非强制锁定为 label=3
3. 加入家庭无特殊需求兜底规则：`if group_type == 3: return 3`，统一家庭组处理逻辑
4. 15% 标签噪声防止模型过度拟合特定群体的规则模式

#### 为什么公平性指标不在前端展示

AOD 是训练集上的统计数字，描述的是模型在 2000 个测试样本上的**平均表现**，与特定用户的这一次请求没有直接关联。向用户展示同一个固定数字（无论用户是谁、输入什么），既无法解释这次推荐，也可能造成误导（让用户误以为这是对他本次请求的公平性评估）。

公平性指标的正确归宿是**算法审计报告**（本文档），而非用户界面。

---

### 9.3 五大支柱落地

#### ① 透明度与可解释性（Transparency & Explainability）

| 系统 | 实现方式 |
|------|---------|
| 规则系统 | 每条推荐可追溯规则库条目；`coverage_gap` 字段标注城市是否在覆盖范围内 |
| 监督学习 | 返回 Top-3 特征重要性（名称+权重）、模型置信度；前端侧边栏"模型决策"卡可视化 |
| 目标导向 | `agent_steps` 记录每轮工具调用（工具名/中文查询词/结果预览/耗时）；前端时间线可视化 |

#### ② 公平性与偏见（Fairness & Bias）

见 §9.2 完整分析。核心结论：`has_special` 公平（AOD=+0.025），`group_type` 存在偏差（AOD=+0.163），已通过等权采样和软规则进行缓解。

#### ③ 稳健性与可靠性（Robustness & Reliability）

- **规则系统**：城市缺失时触发 `coverage_gap=True` 警告并回退，不静默失败
- **监督学习**：VotingClassifier 三模型软投票，降低单模型过拟合；15% 标签噪声提升对脏数据鲁棒性
- **目标导向**：Tavily 不可用时降级为 LLM 参数知识；缓存避免重复 token 消耗
- **票务系统**：未覆盖路线触发联网兜底，前端明确标注"参考信息"而非可预订票务

#### ④ 问责制（Accountability）

- 所有请求记录元数据（城市/天数/Agent类型）至 `logs/api.log`
- 监督学习：`model_accuracy` 字段携带 `⚠` 提示，注明"基于合成数据，不代表真实用户行为预测能力"
- 目标导向：`agent_steps` 完整记录决策轨迹，输出可溯源
- 规则系统：`deterministic=True`，输出可复现、可审计

#### ⑤ 用户意图对齐（Alignment with User Intent）

- 7 维兴趣偏好特征精确捕捉用户偏好，8 种旅行类型覆盖主流场景
- 出行类型 + 人数 + 特殊需求（儿童/老人/轮椅）全面考虑差异化需求
- 监督学习置信度低时（< 60%），前端提示结果可靠性
- 目标导向 `agent_steps` 让用户了解"AI 做了什么"
- 自然语言聊天接口（/api/chat）降低填表门槛，识别失败时明确告知（不静默回退）

---

### 9.4 数据隐私

本系统不持久化用户输入数据。日志文件仅记录请求元数据（城市、天数、Agent 类型），不记录行程内容。订单存储仅保留乘客姓名和证件后 4 位脱敏数据。

---

*Voya · AI Travel Planner · v3.5 · 2026-04*
