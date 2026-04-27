# Voya · AI Travel Planner — 完整技术文档

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [目录结构](#3-目录结构)
4. [快速启动](#4-快速启动)
5. [三种 AI 系统详解](#5-三种-ai-系统详解)
6. [票务预订系统](#6-票务预订系统)
7. [前端界面](#7-前端界面)
8. [API 完整参考](#8-api-完整参考)
9. [Responsible AI 设计](#9-responsible-ai-设计)

---

## 1. 项目概述

**Voya** — AI Travel Planner，通过"旅行行程规划"这一具体领域，实现并对比三种主流 AI 设计范式。

| 范式 | 前端名称 | 实现方式 | 响应时间 | 可解释性 | 城市覆盖 |
|------|----------|----------|----------|----------|----------|
| 规则系统 | 经典规划 | 专家规则库（25城市） | < 0.1ms | 完全透明，每条可追溯 | 25 个固定城市 |
| 监督学习 | 偏好匹配 | VotingClassifier 集成 | < 1ms（单例） | 特征重要性（Top-3） | 全局（训练分布内） |
| 目标导向智能体 | 实时规划 | LLM + 工具调用 + SSE 流式 | 30–60s（缓存命中即时） | 决策步骤可追踪 | 全球无限制 |

**用户输入**：城市、天数、预算、兴趣偏好、出行类型、人数、出行方式、出发地、出发日期、特殊需求  
**系统输出**：Markdown 格式每日行程 + 预算估算 + 餐厅/交通/住宿建议 + `responsible_ai` 字段

---

## 2. 系统架构

```
用户浏览器（web/index.html）
        │  HTTP POST /api/generate          ← 同步返回（三种系统）
        │  HTTP POST /api/generate/stream   ← SSE 流式（goal_based 逐字推流；supervised 分块流式；rule_based 即时 done）
        │  HTTP POST /api/chat
        │  HTTP POST /api/booking/*
        ▼
  FastAPI 后端（web/api_server.py）
        │
        ├─── agent_type = "rule_based"
        │         └── systems/rule_based/engine.py
        │                   └── parse_natural_language()  ← NLP预处理层
        │
        ├─── agent_type = "supervised"
        │         └── systems/supervised/inference.py
        │                   └── model.pkl（VotingClassifier，单例加载）
        │
        ├─── agent_type = "goal_based"
        │         └── agent_agentic.py（Function Calling + stream_itinerary）
        │                 │  失败时
        │                 └── RuntimeError（抛出错误，无静默兜底）
        │
        └─── /api/booking/*
                  └── systems/booking/booking_engine.py
                            └── Tavily 联网兜底（未覆盖路线 → web_info 类型）

所有路由的格式化输出均经过 _format_output() 统一处理后返回前端。
```

### 请求流程（/api/generate/stream — goal_based）

```
1. 前端收集表单 → 构造 JSON → POST /api/generate/stream
2. 后端创建 TravelPlanningAgent（enable_knowledge=True, enable_web_search=True）
3. agent.stream_itinerary() 同步生成器 → iterate_in_threadpool → SSE 推流
   每行：data: {"chunk": "..."}
   完成：data: {"done": true, "processing_time": X, "tool_rounds": N,
                "cache_hit": false, "agent_steps": [...]}
4. 前端 ReadableStream 接收 chunk，逐字追加到 marked.js 渲染区（trimEnd 避免尾部空白段落）
5. done 事件触发 → 渲染 agent_steps 到右侧分析面板
```

---

## 3. 目录结构

```
projects/
├── web/
│   ├── api_server.py        — FastAPI后端（/api/generate · /api/generate/stream · /api/chat · /api/booking/*）
│   └── index.html           — 前端（中英双语，暖铜色调设计系统）
├── systems/
│   ├── config.py            — 全局配置（模型参数、LLM配置）
│   ├── rule_based/
│   │   └── engine.py        — 规则引擎+NLP预处理（25城市，含双语贴士 RULES_EN）
│   ├── supervised/
│   │   ├── inference.py     — VotingClassifier训练/推理
│   │   └── training_dataset.json
│   ├── goal_based/
│   │   ├── agent_agentic.py         — 主智能体（知识库预查询 + SSE流式输出）
│   │   ├── local_knowledge_client.py — ChromaDB 知识库客户端（25城市，294条文档）
│   │   └── tavily_client.py         — Tavily 联网搜索客户端（直连，绕过系统代理）
│   └── booking/
│       └── booking_engine.py        — 机票/火车票搜索+订单管理
├── assets/
│   ├── knowledge_paris.md   ─┐
│   ├── knowledge_tokyo.md    │
│   ├── ...（共25个城市）      │ ChromaDB 知识库源文件
│   └── knowledge_kyoto.md   ─┘
├── scripts/
│   ├── import_local_knowledge.py    — 导入知识库到ChromaDB
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
# 1. 安装依赖
pip install -r requirements_local.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 配置 API Keys
cp .env.example .env
# 编辑 .env，至少填入 OPENAI_API_KEY 和 OPENAI_BASE_URL
```

### 环境变量说明（基于 .env.example）

| 变量 | 默认值 | 必填 | 说明 |
|------|--------|------|------|
| `OPENAI_API_KEY` | — | 必填 | 大模型 API Key（通义千问 / DeepSeek 等） |
| `OPENAI_BASE_URL` | — | 必填 | LLM 接口地址，如 `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `MODEL_NAME` | `qwen-plus` | 可选 | 模型名称（推荐 qwen-plus，旗舰用 qwen-max） |
| `TAVILY_API_KEY` | — | 可选 | 联网搜索；不填时目标导向系统仅用 LLM 参数知识 |
| `ENABLE_KNOWLEDGE` | `true` | — | 是否启用 ChromaDB 本地知识库 |
| `ENABLE_WEB_SEARCH` | `true` | — | 是否启用 Tavily 联网搜索 |
| `LOG_LEVEL` | `INFO` | — | 日志级别 |
| `API_PORT` | `8000` | — | API 服务端口 |

### 启动服务

```bash
# 方式一：一键启动（推荐）
python scripts/start_and_preview.py

# 方式二：uvicorn 热重载
uvicorn web.api_server:app --host 0.0.0.0 --port 8000 --reload
```

访问：`http://localhost:8000/preview`

### 可选：导入/更新知识库

```bash
# 导入全部25个城市知识库到 ChromaDB（不清空时追加）
echo "n" | python scripts/import_local_knowledge.py
# 导入完成后显示：总文档数 294，支持城市 22 个
```

### 单独测试各系统

```bash
python systems/rule_based/engine.py
python systems/supervised/inference.py          # 首次运行约1分钟（训练模型）
python systems/goal_based/agent_agentic.py      # 需要 .env 配置
```

---

## 5. 三种 AI 系统详解

### 5.1 规则系统（Rule-Based Expert System）— 经典规划

**文件**：`systems/rule_based/engine.py`

**核心思路**：人工编写 25 个城市的景点、餐厅、预算、交通规则，根据用户输入的兴趣标签匹配内容，按天组装行程。每条推荐精准溯源至规则库具体条目，无需联网，毫秒响应。

**支持城市（25个）**：
> **国内**：广州  
> **近邻亚洲**：东京、大阪、京都、首尔、新加坡、曼谷、普吉岛、巴厘岛、马尔代夫  
> **中东**：迪拜、伊斯坦布尔、开罗  
> **大洋洲**：悉尼  
> **欧洲**：巴黎、伦敦、罗马、巴塞罗那、阿姆斯特丹、维也纳、布拉格、哥本哈根、苏黎世、里斯本  
> **美洲**：纽约

**城市规范化**：`CITY_NORMALIZE` 字典将英文/别名映射为中文标准名，例如：
```
"paris" / "Paris"     → "巴黎"
"osaka" / "Osaka"     → "大阪"
"kyoto" / "Kyoto"     → "京都"
"bali"  / "Bali"      → "巴厘岛"
"guangzhou"           → "广州"
```

**NLP 预处理层**：`parse_natural_language(text)` 函数从自由文本中提取结构化参数：

| 提取字段 | 方法 | 说明 |
|----------|------|------|
| `city` | CITY_NORMALIZE 别名匹配 + 正则 `去...玩` | 默认巴黎 |
| `days` | 正则 `\d+天` | 1–14，默认 3 |
| `budget` | 关键词列表（高/充裕/奢华 → 高；省钱/穷游 → 低） | 默认中 |
| `interests` | 7类兴趣关键词扫描 | 默认 [文化, 美食] |
| `group` | 情侣/夫妻/朋友/家庭/单人 关键词 | 默认朋友 |
| `num_people` | 正则 `\d+人` | 情侣/夫妻固定为2 |
| `origin` | 正则 `从...出发` / `X飞Y` 双格式 | 默认空 |
| `travel_mode` | 高铁/自驾/邮轮 关键词 | 默认飞机 |
| `special` | 儿童/老人/轮椅 关键词 | 默认无 |

**行程轮换逻辑**：`step = (day-1)*2 + (1 if afternoon else 0)`，确保同天上午/下午及跨天不重复景点。

**双语贴士**：`RULES_EN` 字典与 `RULES` 并行，为每个城市提供英文 `transport` 和 `tips`。API 同时返回 `transport_tip_en` / `city_tips_en`，前端按语言选择显示。

**气候感知**：`CITY_CLIMATE` 字典按季节（spring/summer/autumn/winter）存储气候描述，结合 `start_date` 参数生成 `weather_note`，并触发雨天/高温/严寒备选方案建议。

**性能与 Responsible AI**：

| 属性 | 值 |
|------|----|
| 响应时间 | < 0.1ms |
| 确定性 | 完全确定，相同输入永远相同输出 |
| 城市外处理 | 回退至巴黎 + `coverage_gap=True` 警告 |

**responsible_ai 字段**：`transparency`（每条推荐可追溯）、`coverage_gap`（城市是否在规则库内）、`fairness_warning`、`deterministic`

---

### 5.2 监督学习系统（Supervised ML）— 偏好匹配

**文件**：`systems/supervised/inference.py`  
**模型文件**：`systems/supervised/model.pkl`（≈23MB，首次运行自动训练并保存）

**核心思路**：集成学习模型综合分析出行偏好、预算与人群特征，从 8 种旅行模式中智能匹配最适方案，推荐依据特征权重完全透明可查。

**模型架构**：VotingClassifier 软投票集成

```
输入特征（13维偏好维度 + 城市编码）
  ├── 行程参数: days, budget_level, num_people, group_type,
  │             has_special, travel_mode
  ├── 兴趣偏好: interest_culture, interest_nature, interest_food,
  │             interest_shopping, interest_history,
  │             interest_nightlife, interest_outdoor
  └── 城市编码: city_paris, city_tokyo, city_newyork,
                city_london, city_rome, city_seoul, city_dubai

    ┌──────────────────────────────────────────────┐
    │  GradientBoostingClassifier                  │
    │  (n_estimators=200, lr=0.08, depth=4)        │
    ├──────────────────────────────────────────────┤  软投票
    │  RandomForestClassifier                      │ ────────► 预测类别（0–7）
    │  (n_estimators=200, depth=8)                 │           + 置信度
    ├──────────────────────────────────────────────┤
    │  ExtraTreesClassifier                        │
    │  (n_estimators=150, depth=8)                 │
    └──────────────────────────────────────────────┘
```

**8 种推荐类型**：

| ID | 英文标识 | 中文名 | 主要触发条件 |
|----|----------|--------|------------|
| 0 | budget_sightseeing | 经济观光 | 低预算 |
| 1 | cultural_deep_dive | 文化深度游 | 文化/历史兴趣为主 |
| 2 | luxury_experience | 奢华体验 | 高预算（非情侣） |
| 3 | family_friendly | 亲子家庭游 | 家庭出行 + 特殊需求 |
| 4 | foodie_adventure | 美食购物游 | 美食/购物兴趣为主 |
| 5 | adventure_outdoor | 户外探险游 | 户外/自然 + 天数≥3 |
| 6 | romantic_couple | 情侣浪漫游 | 情侣 + 高预算 |
| 7 | group_social | 团队社交游 | 夜生活 + 人数≥4 |

**训练数据**：
- 10,000 条程序生成的专家标注样本（`_expert_label()` 规则函数自动生成标签）
- 15% 随机标签噪声（模拟真实标注误差，增强鲁棒性）
- 80/20 训练/测试分割（随机种子 42）
- 测试集准确率：**86.8%**（数据集含 15% 随机标签噪声，模拟真实用户偏好不确定性，准确率更接近真实场景性能）

**公平性（AOD 量化）**：依照 IBM AIF360 方法论，训练后自动计算 Average Odds Difference：

| 受保护属性 | 弱势群体 | 优势群体 | AOD 值 | 等级 |
|-----------|---------|---------|--------|------|
| 特殊需求 (has_special) | 有需求：携带儿童/老人/轮椅(1) | 无特殊需求(0) | +0.025 | ✅ 公平（|AOD|<0.05） |
| 出行类型 (group_type) | 家庭(3) | 非家庭（单人/情侣/朋友） | +0.163 | ⚠ 偏差（家庭获非经济推荐概率偏低） |

> **为什么不用  作保护属性？**  
> 预算是用户主动申报的约束条件，模型给不同预算提供不同层级推荐属于**预期行为**，  
> 不是人口学歧视。保护属性应选择用户通常无法主动规避的特征（如是否携带残障人士/幼儿）。

> AOD = ½×[(FPR_弱势−FPR_优势)+(TPR_弱势−TPR_优势)]，有利标签 = 预测非"经济观光"(label≠0)  
> |AOD|<0.05 公平；0.05~0.10 边界；≥0.10 需关注偏差缓解（参考 Hardt et al. 2016）

各出行群体（单人/情侣/朋友/家庭）训练集均等采样 `[0.25, 0.25, 0.25, 0.25]`。

**单例模式**：模型使用模块级 `_engine` 变量，仅在首次请求时加载 model.pkl，后续所有请求复用内存中的模型，推理延迟从 ~2s 降至 **<1ms**。

**流式输出**：监督学习系统通过 `/api/generate/stream` 路由以分块流式方式输出，每 3 行合并为一个 chunk，延迟 10ms，产生打字机效果（约4x快于逐行输出）。

**responsible_ai 字段**（v3.4 新增）：

| 字段 | 含义 |
|------|------|
| `transparency` | 置信度 + 决策路径说明 |
| `accuracy_note` | 诚实说明准确率的合成数据局限性 |
| `fairness_aod_budget` | AOD（预算等级受保护属性） |
| `fairness_aod_group` | AOD（出行类型受保护属性） |
| `fairness_spd_budget` | Statistical Parity Difference |
| `fairness_level_budget/group` | 公平等级文字标注 |
| `fairness_method` | "Average Odds Difference (IBM AIF360 / Hardt et al. 2016)" |
| `fairness_note` | AOD 公式解释（中文） |
| `data_bias` | 鲁棒性/数据偏差说明 |
| `group_fairness` | 均等采样 + AOD 量化声明 |
| `city_coverage_note` | 城市是否在训练分布内 |

---

### 5.3 目标导向智能体（Goal-Based Agentic AI）— 实时规划

**主文件**：`systems/goal_based/agent_agentic.py`

**核心理念**：给定高层目标，AI 自主决定调用哪些工具、调用多少次，最终生成高质量个性化行程。符合课程定义：*"The AI is given a high-level goal and freedom to determine its own process and solution."*

**LLM**：通义千问 Qwen（通过 `.env` 配置，默认 `qwen-plus`，支持任意 OpenAI 兼容接口）

**模型参数**（`systems/config.py`）：
- `temperature`：0.75（输出更丰富多样）
- `max_tokens`：6000（支持完整 7 天详细行程输出）

**结构化输出框架**：`AGENT_SYSTEM_PROMPT` 包含详细的行程格式模板，要求模型按以下结构输出：

```
# {目的地} {天数}日行程 · {出行类型}
## 行程概览
## 出发准备（含机票日期：去程=出发日期，返程=出发日期+天数）
## 第 X 天：{当天主题}
  **上午** — 活动名称、简介、票价、时长、贴士
  **午餐推荐** — 餐厅、菜系、人均、推荐菜
  **下午** ...
  **晚餐推荐** ...
  **晚上** ...
  > 💡 备选：{备选景点}
## 住宿建议
## 预算参考（Markdown 表格，人均合计）
## 实用信息 — 签证、货币、气候、紧急联系
```

**工具定义**：

```python
search_web(query, topic)           # Tavily API 实时搜索（query 必须为中文关键词）
query_knowledge_base(city, query)  # ChromaDB 本地知识库（25城市，294条文档）
```

**两阶段工具策略（stream_itinerary）**：

```
阶段1：预查询（生成前执行）
  ├── query_knowledge_base → 注入本地 POI/价格/贴士（最多1800字符）
  └── search_web → 注入实时攻略参考（最多1500字符，当年年份动态生成）

阶段2：LLM 流式生成（结合两阶段注入的上下文）
  └── stream=True → chunk by chunk yield → SSE 推流
```

**城市 → 知识库 key 映射**（`_CITY_KB_KEY`）：

ChromaDB 以英文文件名存储（如 `Guangzhou`），agent 接收中文城市名（如 `广州`），通过映射字典透明转换：

```python
_CITY_KB_KEY = {
    "巴黎": "Paris", "东京": "Tokyo", "广州": "Guangzhou",
    "大阪": "Osaka", "京都": "Kyoto", "巴厘岛": "Bali", ...
}
```

**SSE 流式输出**（`stream_itinerary`）：
- 生成器逐 chunk yield LLM 输出文本，最后 yield 一个 `{"__meta__": True, ...}` 结束信号
- `/api/generate/stream` 路由通过 `iterate_in_threadpool` 将同步生成器转为异步 SSE 流
- SSE 格式：`data: {"chunk": "..."}` 持续推流，`data: {"done": true, "agent_steps": [...]}` 收尾
- `agent_steps` 每条记录包含 `tool`、`args`（含 `query`）、`result_preview`、`time_s`

**agent_steps 结构**：
```json
[
  {
    "tool": "query_knowledge_base",
    "args": {"city": "大阪", "query": "大阪 景点 餐饮 住宿 交通 实用贴士"},
    "result_preview": "知识库结果（大阪 - ...）",
    "time_s": 0.12
  },
  {
    "tool": "search_web",
    "args": {"query": "大阪 旅行攻略 4天 景点 餐厅 2026", "topic": "general"},
    "result_preview": "大阪道顿堀美食攻略...",
    "time_s": 1.43
  }
]
```

**缓存机制**：
- 类级别 `_class_cache` dict，最大 30 条，key 为城市+天数+偏好的 MD5 哈希
- LRU 淘汰：达到上限时删除最早插入的条目（`next(iter(dict))`）
- `generate_itinerary` 和 `stream_itinerary` 共享同一缓存池

**响应时间**：实时生成 30–60 秒；缓存命中即时响应。

**responsible_ai 字段**：`transparency`（agent_steps 记录）、`hallucination_risk`、`data_sources`（工具来源列表）、`accountability`、`deterministic`（false）

---

## 6. 票务预订系统（Booking Engine）

**文件**：`systems/booking/booking_engine.py`

### API 路由

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/booking/search` | 搜索机票或火车票 |
| `POST` | `/api/booking/create` | 创建预订订单 |
| `GET` | `/api/booking/orders` | 获取订单列表（按创建时间倒序，支持分页） |
| `GET` | `/api/booking/orders/{id}` | 获取单个订单详情 |
| `DELETE` | `/api/booking/orders/{id}` | 取消/删除订单 |

### 城市覆盖

**国内城市（21个）**：上海、北京、广州、深圳、成都、杭州、武汉、重庆、西安、南京、天津、青岛、厦门、昆明、三亚、长沙、郑州、沈阳、哈尔滨、乌鲁木齐、拉萨

**国际目的地（20个，INTL_HUB）**：巴黎(CDG)、东京(NRT)、纽约(JFK)、伦敦(LHR)、罗马(FCO)、悉尼(SYD)、巴塞罗那(BCN)、曼谷(BKK)、新加坡(SIN)、首尔(ICN)、迪拜(DXB)、阿姆斯特丹(AMS)、维也纳(VIE)、布拉格(PRG)、伊斯坦布尔(IST)、里斯本(LIS)、普吉岛(HKT)、马尔代夫(MLE)、冰岛(KEF)、开罗(CAI)

### 搜索结果

**机票**：每次搜索返回 3–6 个选项，包含经济舱/商务舱/头等舱；国内航空公司 6 家，国际 6 家。  
**火车票**：3–5 个选项，类型包含高铁(G)、动车(D)、城际(C)；仅支持国内城市间。

**确定性定价**：`_price()` 函数使用路线+日期的 MD5 哈希作为随机种子，相同查询永远返回相同结果。

### Tavily 联网兜底（web_info 类型）

当搜索路线不在数据库覆盖范围时，系统自动启用 Tavily 联网搜索作为兜底：

```python
{
    "type": "web_info",        # 区别于 "flight" / "train"
    "title": "...",
    "snippet": "...",
    "url": "..."
}
```

前端对 `type === "web_info"` 的结果以参考信息卡形式展示，明确标注"网络参考信息"而非可预订票务。

**订单存储**：持久化至 `assets/orders/orders.json`，订单 ID 格式 `YY{YYYYMMDDHHMMSS}{seq}`。  
**证件脱敏**：乘客证件号仅存储后 4 位，前缀用 `*` 补全（长度 ≤ 4 位时全部脱敏）。

**公平性原则**：所有用户（无论出行群体）享有完全相同的搜索结果、价格算法和服务权限。

---

## 7. 前端界面（web/index.html）

**技术**：纯原生 HTML/CSS/JS，无框架；marked.js（CDN）渲染 Markdown 行程结果。

### 设计系统

**色彩**：暖铜色调统一调色板，全部使用 CSS 变量，无硬编码深色值

| 变量 | 值 | 用途 |
|------|-----|------|
| `--accent` | `#C4854A` | 主品牌色（铜色） |
| `--bg` | `#F5F3EF` | 页面背景（暖米白） |
| `--card` | `#FFFFFF` | 卡片背景 |
| `--text` | `#0E0C0A` | 主文字 |
| `--text2` | `#3A3632` | 次要文字 |
| `--text3` | `#78706A` | 辅助文字 |
| `--border` | `rgba(14,12,10,.10)` | 边框 |

**系统 Tab 字体**：三个导航 Tab（经典规划/偏好匹配/实时规划）统一为 `font-size: 15px`，无差异化处理，激活态 `font-weight: 600`。

### 主要功能区块

| 区块 | 说明 |
|------|------|
| 系统选择 Tab | 三个导航 Tab（经典规划/偏好匹配/实时规划），含顶部和底部两套同步联动（`nav-pill` + `sc-tab`） |
| 搜索表单 | 行程参数（目的地/出发地/天数/出行类型/预算/人数/出行方式/出发日期/特殊需求） |
| 目的地快选网格 | 21 张城市图片卡，点击后自动填入参数并检测是否需要切换交通方式（国内/国际） |
| 热门目的地快捷按钮 | 顶部 8 个快捷城市按钮 |
| 实用工具面板 | 右侧悬浮 Tab（汇率换算 / 紧急联系 / 常用短语） |
| 票务面板 | 机票/火车票搜索 + 订单管理（支持 web_info 兜底展示） |
| 底部对话栏 | 自然语言聊天接口（/api/chat），解析后自动填表 |
| 结果视图 | 主区域 Markdown 行程（SSE 流式逐字渲染）+ 右侧分析面板（responsible_ai 字段） |
| 我的旅行 | 本地保存行程记录，支持星级评分和出行备注 |

### 流式渲染防空白处理

**根本原因**：CSS Grid 默认 `align-items: stretch`，右侧侧边栏比左侧行程内容高时，`itin-card` 被撑高产生空白区域。

**修复**：`.result-grid { align-items: start; }` — 两列各自按内容高度排列。

**Markdown 尾部空白**：流式渲染每帧调用 `text.trimEnd()` 后再传入 `marked.parse()`，避免尾部 `\n\n` 生成空 `<p>` 元素。

### 规划过程步骤面板（agent_steps）

右侧"规划过程"卡显示 Agent 决策轨迹：
- `query_knowledge_base` 步骤：显示 `args.query`（中文查询词）
- `search_web` 步骤：显示 `args.query`（中文搜索关键词，不显示英文原始结果片段）

### i18n 国际化系统

- **语言**：中文 / English 双语，导航栏一键切换，`localStorage` 持久化
- **history strip**：语言切换时同步触发 `_histRender()`，"最近：" / "✦ 智能填写" 随语言更新
- **规则系统侧边栏**：交通贴士和城市小贴士根据 `_lang` 选择 `transport_tip` 或 `transport_tip_en`

**特殊 i18n 属性**：

| 属性 | 处理方式 |
|------|---------|
| `data-i18n` | textContent 替换 |
| `data-i18n-html` | innerHTML 替换（含 HTML） |
| `data-i18n-placeholder` | input placeholder 替换 |
| `data-i18n-select` | 重建 option 文本（保持 value 不变） |
| `data-i18n-sctab` | 保留 SVG 图标 + 角标，仅替换文字 |

### 国际目的地自动切换交通方式

`_autoSwitchTransport(city)` 在 5 个入口自动调用（`pickDestCity` / `quickPlan` / `swapCities` / `_histApply` / `parseAndFill`）。

**判断逻辑**（`_isInternational(city)`）：
1. 命中 `_DOMESTIC_DESTS`（~80个国内城市/景区）→ 国内，不切换
2. 包含 `省/市/区/县/山/岛/湖/江/河/古镇` → 国内，不切换
3. 其余 → 国际，若当前交通为"自驾"则自动切换为"飞机"并提示

### _format_output() 格式化函数

`web/api_server.py` 中的 `_format_output(result, agent_type)` 将各系统返回的 dict 统一转换为 Markdown：

- **goal_based**：直接返回 LLM 输出（已按结构化 prompt 格式化）
- **rule_based / supervised**：富文本格式化，包含：
  - 标题（城市 · 天数 · 出行类型）
  - 行程概览（人数/方式/预算/特需/模型置信度）
  - 每日行程（上午 · 午餐 · 下午 · 晚餐，午餐文案按天轮换）
  - 住宿建议、交通建议、当地贴士
  - 预算参考表格 + 货币换算节（按目的地货币自动生成）
  - 系统透明度说明脚注

---

## 8. API 完整参考

### POST `/api/generate`

生成完整旅行行程（三种 AI 系统可选，同步返回）。

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
  "agent_type": "rule_based"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `city` | string | 必填 | 目的地城市（中文或英文别名） |
| `days` | int(1–14) | 必填 | 旅行天数 |
| `budget` | string | 必填 | `低` / `中` / `高` |
| `interests` | string[] | 必填 | 可选：文化/自然/美食/购物/历史/夜生活/户外运动 |
| `group` | string | 必填 | `单人` / `情侣` / `夫妻` / `朋友` / `家庭` |
| `num_people` | int(1–20) | 可选 | 出行人数（情侣/夫妻自动归一为 2） |
| `travel_mode` | string | 可选 | `飞机` / `高铁` / `自驾` / `邮轮` |
| `origin` | string | 可选 | 出发城市 |
| `start_date` | string | 可选 | 出发日期，格式 `YYYY-MM-DD`；用于气候判断和返程日期计算 |
| `special` | string | 可选 | `无` / `有儿童` / `有老人` / `轮椅友好` |
| `agent_type` | string | 可选 | `rule_based` / `supervised` / `goal_based`（默认 goal_based） |

**响应体**（规则系统示例）：
```json
{
  "itinerary": "# 东京 5日亲子家庭游\n## 行程概览\n...",
  "agent_type": "rule_based",
  "processing_time": 0.0001,
  "token_estimate": 400,
  "metadata": { "city": "东京", "days": 5, "budget": "中" },
  "responsible_ai": {
    "transparency": "完全可解释：每条推荐均可追溯至规则库中的具体条目",
    "coverage_gap": false,
    "deterministic": true
  },
  "transport_tip": "地铁+JR线全面覆盖，推荐 Suica 卡",
  "city_tips": ["购买 24/48/72h 地铁通票划算", "便利店是日本饮食体验的一部分"]
}
```

监督学习系统额外返回：`recommendation_type_zh`、`model_confidence`、`top_features`  
目标导向系统额外返回：`agent_steps`（含 `tool`/`args`/`result_preview`/`time_s`）、`tool_rounds`

---

### POST `/api/generate/stream`

SSE 流式接口（三种系统均支持，行为差异见下表）。

**请求体**：与 `/api/generate` 相同。

| 系统 | 流式行为 | done 事件额外字段 |
|------|---------|-----------------|
| goal_based | 逐 chunk 推流（LLM 原生流式） | `agent_steps`（含 args） |
| supervised | 每 3 行一个 chunk，延迟 10ms | `result_meta`（置信度/特征） |
| rule_based | 单次 done 事件（毫秒响应） | `itinerary`（完整行程文本）、`result_meta` |

**SSE 事件格式**：

| 事件类型 | 数据结构 |
|---------|---------|
| 文本 chunk | `{"chunk": "..."}` |
| 完成（goal_based） | `{"done": true, "processing_time": X, "tool_rounds": N, "cache_hit": false, "agent_steps": [...]}` |
| 完成（supervised） | `{"done": true, "processing_time": X, "result_meta": {...}}` |
| 完成（rule_based） | `{"done": true, "itinerary": "...", "result_meta": {...}}` |
| 错误 | `{"error": "..."}` |

**返程日期自动计算**：`_ret_date = start_date + timedelta(days=days)`，自动追加到 user_input，Agent 机票搜索时使用正确的去程/返程日期。

---

### POST `/api/chat`

自然语言对话接口，自动从文本中解析城市/天数/预算/兴趣/出行类型等参数。

```json
{
  "role": "user",
  "content": "我想去巴黎玩5天，和爱人一起，喜欢文化，预算充裕",
  "agent_type": "goal_based"
}
```

> `parse_warning`：若未能从输入识别目的地，此字段包含提示信息（不静默回退）。

---

### POST `/api/booking/search`

```json
{ "origin": "上海", "destination": "巴黎", "date": "2026-05-01", "type": "flight" }
```

返回：覆盖路线返回 `flight`/`train` 类型；未覆盖路线触发 Tavily 联网，返回 `web_info` 类型。

---

### POST `/api/booking/create`

```json
{ "ticket_id": "MU1234-20260501", "ticket_data": {}, "passenger_name": "张三", "id_number": "310..." }
```

证件号仅存储脱敏后版本（后4位明文，前缀全部 `*` 替换）。

---

### GET `/api/booking/orders`

获取订单列表（按创建时间倒序）。支持分页：`?limit=20&offset=0`

---

### GET `/api/health`

服务健康检查，返回状态、版本、运行时长、各系统请求计数。

### GET `/preview`

返回前端 `index.html` 页面。

---

## 9. Responsible AI 设计

> 参照课程 Project Description（Spring 2026）五大支柱：透明度与可解释性、公平性与偏见、稳健性与可靠性、问责制、用户意图对齐。

### 9.1 标准化 `responsible_ai` 字段

每次响应均包含 `responsible_ai` 对象，三系统均实现以下字段（具体字段见各系统说明）：

| 字段 | 含义 | 出现的系统 |
|------|------|-----------|
| `transparency` | 本次输出的可解释性说明 | 全部 |
| `fairness_warning` / `fairness_aod_*` | 公平性预警 / AOD 量化指标 | 全部 |
| `coverage_gap` | 是否触发城市回退 | 规则系统 |
| `deterministic` | 是否确定性输出 | 全部 |
| `hallucination_risk` | 幻觉风险提示 | 目标导向 |
| `data_sources` | 实际使用的数据来源列表 | 目标导向 |
| `accountability` | 责任归属声明 | 目标导向 |
| `model_confidence` | 模型预测置信度 | 监督学习 |
| `accuracy_note` | 准确率局限性诚实说明 | 监督学习 |
| `fairness_aod_budget` / `fairness_aod_group` | AOD 公平性指标 | 监督学习 |
| `city_in_training_distribution` | 城市是否在训练分布内 | 监督学习 |

### 9.2 五大支柱落地

#### ① 透明度与可解释性（Transparency & Explainability）

| 系统 | 实现 |
|------|------|
| 规则系统 | 每条推荐均可追溯规则库具体条目，100% 确定性；前端显示交通贴士原文 |
| 监督学习 | 返回 Top-3 特征重要性（名称+权重）及模型置信度；决策路径文字化说明 |
| 目标导向 | `agent_steps` 记录每轮工具调用（工具名/查询词/结果预览/耗时）；前端时间线可视化 |

#### ② 公平性与偏见（Fairness & Bias）— 监督学习 AOD 量化

**方法**：参照 IBM AIF360 / Hardt et al.（2016）Average Odds Difference：

```
AOD = ½ × [(FPR_弱势群体 − FPR_优势群体) + (TPR_弱势群体 − TPR_优势群体)]
```

- **有利标签**：预测非"经济观光"类（label ≠ 0），即获得品质更优的旅行推荐
- **受保护属性①**：`budget_level`（低预算=0=弱势，高预算=2=优势）
- **受保护属性②**：`group_type`（家庭=3=弱势，非家庭=优势）

**实测结果**（10,000条合成数据，20%测试集）：

| 受保护属性 | AOD | 等级 | 分析 |
|-----------|-----|------|------|
| 预算等级 | −0.46 | ⚠ 偏差 | FPR_高预算=1.0：高预算用户始终被预测为非经济类，属于设计意图（高预算 → 奢华体验），但揭示了模型对预算的强依赖 |
| 出行类型 | +0.10 | 🟡 边界 | 家庭出行用户在相同条件下获得"非经济"推荐的机会略低，值得持续监控 |

> 注：`budget_level` 的高 AOD 是规则体系本身决定的（`_expert_label()` 中"高预算→奢华"优先级高），反映系统设计决策而非无意识歧视，但客观上对不同社会经济群体产生差异化对待，应在报告中如实披露。

**缓解措施（已实施）**：
- 训练数据各出行群体等权重采样（各25%），避免群体欠代表
- 15% 随机标签噪声，防止模型过度拟合特定群体的规则模式
- `fairness_aod_budget`/`fairness_aod_group` 字段随模型一同持久化在 model.pkl，每次重训自动刷新

#### ③ 稳健性与可靠性（Robustness & Reliability）

- **规则系统**：输入边界明确，行为 100% 确定；城市缺失时触发 `coverage_gap` 警告并回退至巴黎，不静默失败
- **监督学习**：集成学习（VotingClassifier = GBT+RF+ET），软投票降低单模型过拟合；15% 标签噪声提升对脏数据鲁棒性；训练集外城市预测时 `city_in_training_distribution=False` 明示
- **目标导向**：Tavily 不可用时降级为 LLM 参数知识；缓存命中（city+days+budget 三元组）时不消耗 token；非确定性输出（temperature=0.75）
- **票务系统**：未覆盖路线触发联网兜底，前端明确标注为参考信息

#### ④ 问责制（Accountability）

- 所有请求记录请求元数据（城市/天数/Agent类型）至 `logs/api.log`
- `responsible_ai.accountability` 字段（目标导向）明示"AI 辅助生成，用户应交叉核实"
- `accuracy_note` 字段（监督学习）诚实说明：**95.5% 准确率基于合成数据，不代表真实用户行为预测能力**
- 规则系统：`deterministic=True`，输出可复现，可审计

#### ⑤ 用户意图对齐（Alignment with User Intent）

- 7 维兴趣偏好特征（文化/自然/美食/购物/历史/夜生活/户外）精确捕捉用户偏好
- 出行类型（单人/情侣/朋友/家庭）+ 人数 + 特殊需求（儿童/老人/轮椅友好）全面考虑
- 规则系统：实地 NLP 解析用户自然语言 → 结构化特征 → 规则匹配，链路清晰
- 监督学习：置信度低时（<60%）前端通过 `⚠` 提示用户结果可靠性
- 目标导向：agent_steps 可视化让用户了解"AI 做了什么"

### 9.3 三系统可解释性对比

| 系统 | 可解释性级别 | 说明 |
|------|------------|------|
| 规则系统（经典规划） | 完全透明 | 每条推荐均可追溯到规则库的具体条目，完全确定性 |
| 监督学习（偏好匹配） | 部分可解释 | 返回 Top-3 特征重要性；模型内部为黑箱；AOD 量化公平性 |
| 目标导向（实时规划） | 过程可追踪 | `agent_steps` 记录每轮工具调用（工具名/查询词/结果/耗时） |

### 9.4 数据隐私

本系统不持久化用户输入数据；日志文件（`logs/api.log`）仅记录请求元数据（城市、天数、Agent 类型），不记录完整行程内容。订单数据仅存储乘客姓名和证件后 4 位脱敏数据，不做其他用途。

---

*Voya · AI Travel Planner · v3.4 · 2026-04*
