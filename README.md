# 云游 Voya · AI 旅行规划系统

> 以"旅行行程规划"为具体场景，实现并横向对比**三种主流 AI 设计范式**，同时开展负责任 AI 公平性分析。

---

## 三种 AI 范式对比

| 前端名称 | 范式 | 核心机制 | 响应时间 | 城市覆盖 | 可解释性 |
|---------|------|---------|---------|---------|---------|
| 经典规划 | 规则系统 | 人工编写专家规则库，确定性匹配 | < 0.1ms | 25 个固定城市 | 完全透明 |
| 偏好匹配 | 监督学习 | VotingClassifier 集成分类，84.5% 准确率 | < 1ms | 全局（训练分布内）| 特征权重可见 |
| 实时规划 | 目标导向智能体 | LLM 自主决策 + 工具调用 + 实时联网 | 30–60s | 全球无限制 | 决策步骤可追踪 |

**输入**：城市、天数、预算、兴趣偏好、出行类型、人数、出发地、出发日期、特殊需求  
**输出**：逐日详细行程（Markdown）+ 预算参考 + 餐厅 / 交通 / 住宿建议 + 模拟票务预订

---

## 快速启动

```bash
git clone https://github.com/Cyidid/Voya.git && cd Voya
pip install -r requirements_local.txt
cp .env.example .env        # 填写 API Key
python scripts/start_and_preview.py
```

服务启动后自动打开浏览器，或手动访问 **http://localhost:8000/preview**

详细部署步骤（含公网发布）见 [DEPLOY.md](DEPLOY.md)

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI · Python 3.12 · SSE 流式输出 |
| 前端 | 原生 HTML / CSS / JS · marked.js · 中英双语 |
| AI 接口 | OpenAI 兼容 API（通义千问 / DeepSeek） |
| 知识库 | ChromaDB 本地向量数据库（25 城市） |
| 联网搜索 | Tavily API |

---

## 公平性分析

监督学习系统基于 **Average Odds Difference（AOD）** 进行算法公平性审计：

| 受保护属性 | AOD 值 | 结论 |
|-----------|--------|------|
| 特殊需求（has_special） | +0.025 | 公平 |
| 出行群体（家庭 vs 非家庭） | +0.163 | 存在偏差，已缓解 |

缓解措施：等权重采样 + 软规则标注。完整分析见 [SYSTEM_GUIDE.md § 9](SYSTEM_GUIDE.md#9-responsible-ai-设计)

---

## Phase 2 实现材料

三套系统均已完成批量测试，结果保存在 `results/` 目录。

### Phase 2A · 规则系统（Rule-Based）

- **测试规模**：1,000 条用例全量测试
- **平均响应时间**：< 0.1ms
- **规则库导出**：908 条规则（25 城市 × 景点 / 餐厅 / 交通 / 预算），见 [`results/rule_based_city_rules.csv`](results/rule_based_city_rules.csv)
- **输出文件**：[`results/phase2a_outputs.csv`](results/phase2a_outputs.csv) · [`results/phase2a_outputs.json`](results/phase2a_outputs.json)

运行方式：

```bash
python scripts/run_phase2a.py
```

### Phase 2B · 监督学习系统（Supervised）

- **测试规模**：1,000 条用例全量测试
- **模型准确率**：84.45%（VotingClassifier：GBT + RF + ExtraTrees）
- **Top 特征**：出行类型（0.2189）· 自然兴趣（0.1376）· 旅行天数（0.1339）
- **训练数据集**：10,000 条合成样本，见 `systems/supervised/training_dataset.json`
- **输出文件**：[`results/phase2b_outputs.csv`](results/phase2b_outputs.csv) · [`results/phase2b_outputs.json`](results/phase2b_outputs.json)

运行方式：

```bash
python scripts/run_phase2b.py
```

### Phase 2C · 目标导向智能体（Goal-Based）

- **测试规模**：20 条代表性用例 × 3 次独立运行（共 60 次 LLM 调用）
- **平均响应时间**：426s（含 Qwen3.6-plus 推理 + Tavily 联网搜索）
- **非确定性验证**：跨运行平均输出长度差异 1,368 字符，印证了 LLM 的非确定性特征
- **重试机制**：网络断开自动重试 3 次（15 / 30 / 45s 退避）
- **输出文件**：[`results/phase2c_outputs.csv`](results/phase2c_outputs.csv) · [`results/phase2c_outputs.json`](results/phase2c_outputs.json)

运行方式：

```bash
python scripts/run_phase2c.py           # 默认 20 条
python scripts/run_phase2c.py --count 5 # 快速验证
```

---

## 文档导航

| 文件 | 内容 |
|------|------|
| [DEPLOY.md](DEPLOY.md) | 本地运行 · 公网部署（Railway / Render / 阿里云 ECS） |
| [SYSTEM_GUIDE.md](SYSTEM_GUIDE.md) | 系统架构 · 算法原理 · API 参考 · 负责任 AI 分析 |

---

*云游 Voya · 2026*
