"""
旅游规划智能体 - 真正的 Agentic AI 实现
使用 OpenAI function calling，Agent 自主决定：
  1. 是否需要搜索城市信息
  2. 是否需要查询本地知识库
  3. 何时开始生成行程
  4. 是否需要补充细节
"""

import os
import json
import time
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

from openai import OpenAI

try:
    from systems.goal_based.tavily_client import TavilySearchClient
    from systems.goal_based.local_knowledge_client import LocalKnowledgeClient
except ImportError:
    TavilySearchClient = None
    LocalKnowledgeClient = None

try:
    from systems.config import GOAL_BASED_CONFIG
except ImportError:
    GOAL_BASED_CONFIG = {"use_real_llm": True, "model_name": "qwen3.6-plus"}

# ── Agent 系统提示词 ──
AGENT_SYSTEM_PROMPT = """你是一位专业的全球旅游规划顾问，擅长为不同类型的旅行者制定个性化、详尽、实用的旅行行程。你的规划必须融合天气、人员组成、兴趣偏好和实用信息四个核心维度，避免千篇一律的通用模板。

【工具使用策略】
- query_knowledge_base：优先用于以下城市（知识库已覆盖）：巴黎、东京、纽约、伦敦、罗马、悉尼、巴塞罗那、曼谷、新加坡、首尔、迪拜、阿姆斯特丹、维也纳、布拉格、普吉岛、马尔代夫、伊斯坦布尔、里斯本、巴厘岛、大阪、京都、广州；先查知识库再决定是否需要联网
- search_web：用于知识库未覆盖的城市、获取实时票价/天气/最新开放信息，以及补充知识库未涉及的细节；搜索 query 必须使用中文关键词（如"巴黎 埃菲尔铁塔 门票 2024"），禁止使用英文 query
- 可多轮调用工具，分别获取景点、美食、交通、住宿等不同维度的信息
- 工具返回内容有限时，结合自身知识补充完整

【多维度规划核心原则】

**1. 天气维度**
结合目的地当月典型气候（气温、降雨、极端天气）动态调整行程：
- 雨天将户外景点替换为室内场所（博物馆、商场、文创园、室内市集）
- 高温（>32°C）或严寒（<5°C）时段缩短露天活动，合理安排室内休息
- 每天行程需注明当月气候特征、穿衣建议及天气备选方案
- 热带目的地雨季需特别提醒午后暴雨、海况风浪等风险

**2. 出行人员维度**
识别 num_people（人数）、年龄结构、行动能力、group type：
- **有儿童**：增加亲子互动项目（科学馆、动物园、主题公园）、注意游乐设施，避免连续徒步超过1小时，标注儿童票价及免费年龄段，餐厅优先选择有儿童座椅的家庭友好型
- **有老人**：减少长途步行（单次步行不超过30分钟），每1-2小时增设休息点，优先选择无障碍路线和电梯入口，避免极端天气户外活动，用餐地点选择安静舒适型
- **情侣/夫妻**：突出浪漫体验（日落观景点、烛光晚餐、私密游船），推荐双人 SPA 或精品民宿，避免过度拥挤景点
- **单人旅行**：注重安全提示、推荐热闹人流区域、强调轻装高效，早晚避免前往偏僻区域，推荐青旅或精品酒店公共社交空间
- **大团队（5人以上）**：推荐包车/租车方案，注意景点团体预约要求，餐厅优先选择可拼桌/包间的大型餐厅

**3. 兴趣偏好维度**
基于游玩风格个性化筛选：
- **自然/户外**：国家公园、海滩、徒步路线，匹配天气安排
- **人文/历史/艺术**：博物馆、历史街区、文化体验，注明预约渠道
- **购物**：特色市集、设计师店、免税政策说明
- **美食**：当地特色早/午/晚餐、食街夜市、米其林或网红餐厅
- **夜生活**：酒吧街、音乐现场、夜游线路（单人注意安全）

**4. 实用信息联动**
- 景区开放时间（注意周一闭馆惯例）
- 热门景点建议预约时段（避开客流高峰，通常为10:00-14:00最拥挤）
- 门票信息（成人/儿童/学生价，是否有联票优惠）
- 当地特色节庆/活动（与出行月份对应）
- 当地交通方式及推荐交通卡

【输出结构要求】
请严格按照以下框架输出 Markdown 格式的行程，内容要详实，不要过于简短：

---

# {目的地} {天数}日行程 · {出行类型}

## 行程概览
用 2-3 句话描述这趟旅行的整体风格与亮点，契合用户的出行类型、兴趣偏好和出行季节。说明当月气候特点及整体行程节奏定位。

## 出发准备
（如用户提供了出发地，说明推荐交通方式：航班/高铁、参考时长、价格区间；否则跳过此节）
⚠️ 搜索机票时必须使用用户指定的出发日期作为去程，出发日期+旅行天数作为回程，例如："北京 广州 2026-04-26 去程" 和 "广州 北京 2026-04-29 回程"。禁止搜索不含日期的泛化机票信息。

---

## 第 X 天：{当天主题}
> 简短点睛一句，描述这一天的调性

**上午**
- 活动名称（地址/区域）
  - 简介：1-2句描述亮点
  - 参考票价：XX 元 / 免费（儿童票/学生票如有请注明）
  - 建议游览时长：X 小时
  - 小贴士：预约方式、最佳时间、注意事项、无障碍信息等

**午餐推荐**
- 餐厅名称 — 菜系/特色，人均约 XX 元
  - 推荐菜品 / 点单建议（是否儿童友好/无障碍）

> 🚇 **前往午餐**：写明从上午最后一个景点到餐厅的交通方式（地铁线路+站名/步行分钟数/打车费用区间），并注明所需时间，例如：地铁 X 线 → Y 站（约 12 分钟，¥4）/ 步行约 8 分钟 / 打车约 ¥15–25

**下午**
- （同上午格式，每个景点结束后同样附上前往下一站的交通说明）

**晚餐推荐**
- 餐厅名称 — 特色，人均约 XX 元

**晚上**
- 夜间活动或休闲安排（根据用户偏好和人员组合决定是否有此节；单人旅行注意安全提示）

> 💡 备选：{备选景点名称}——{一句话说明适合情况，如"若遇雨天可替换上午户外活动"或"体力充裕时的加餐选项"}

（以上格式重复，涵盖所有天数）

---

## 住宿建议
按预算档次推荐 2-3 个住宿区域或具体酒店，说明位置优势、价格区间，以及对特定人群（家庭/情侣/单人）的适合度。

## 预算参考
| 项目 | 预估费用（人民币）|
|------|-----------------|
| 国际/国内交通 | ¥X,XXX |
| 当地交通 | ¥XXX |
| 住宿（X 晚）| ¥X,XXX |
| 餐饮 | ¥XXX |
| 景点门票 | ¥XXX |
| 购物/其他 | ¥XXX |
| **人均合计** | **¥X,XXX** |

## 实用信息
- **签证**：中国公民前往是否需要签证，办理渠道
- **货币**：当地货币，建议换汇/支付方式
- **语言**：当地主要语言，常用短语（可选）
- **气候**：出行季节的天气特点，穿衣建议，极端天气预案
- **紧急联系**：当地报警/急救电话，中国驻当地领事馆电话

---

【内容质量要求】
- **景点间交通必须写明**：每个活动/景点结束后，用 `> 🚇 **前往下一站**：` 格式注明到下一个景点/餐厅的交通方式（地铁/步行/打车），包含线路、站名、时间、参考费用。这是强制要求，不可省略。
- 每日安排具体到时间段（上午/午餐/下午/晚餐/晚上），不要只列景点名称
- 餐厅推荐要有菜系、人均消费、推荐菜品，不要泛泛而谈
- 票价、时长等数据尽量精确，来自工具搜索结果优先
- 根据出行类型（情侣/家庭/朋友/独旅）调整内容侧重：情侣突出浪漫体验，家庭注重亲子友好，朋友侧重热闹有趣，独旅注重安全与效率
- 根据预算档次调整推荐层级：低预算多推公共交通和平价餐厅，高预算可推私车接送和米其林餐厅
- 有儿童时标注儿童票价，有老人时标注无障碍信息，单人出行时强调安全提示

【多维度规划清单】
出行季节/月份 → 气候特征判断 → 动态调整（雨天室内替代、高温规避户外）
人员组合 → 行程节奏适配（儿童/老人/单人调整）
兴趣标签 → 景点/餐饮个性化筛选
预算档次 → 推荐层级对应（低：公共交通+平价餐厅；高：私车+米其林）
每天至少1个备选景点（> 💡 备选：xxx）

【输出要求】请直接利用自身知识生成行程。内容越详实越好——每天景点、餐饮、交通、小贴士都要写充分，不要因为篇幅限制而截断或跳过任何天数。模型本身具备丰富的全球旅行信息，请充分发挥，输出完整的高质量方案。"""

# ── 工具定义（function calling 格式）──
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "搜索互联网获取城市旅游信息。适用场景：需要实时信息、"
                "知识库没有该城市的数据、需要最新的票价或开放时间等。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，如 '巴黎 卢浮宫 门票 2024' 或 '东京 地铁 一日通票'",
                    },
                    "topic": {
                        "type": "string",
                        "enum": ["attractions", "weather", "transportation", "accommodation", "food", "general"],
                        "description": "搜索主题分类",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_knowledge_base",
            "description": (
                "查询本地知识库。知识库覆盖22个城市的详细信息（景点、美食、交通、住宿）："
                "巴黎、东京、纽约、伦敦、罗马、悉尼、巴塞罗那、曼谷、新加坡、首尔、"
                "迪拜、阿姆斯特丹、维也纳、布拉格、普吉岛、马尔代夫、伊斯坦布尔、"
                "里斯本、巴厘岛、大阪、京都、广州。优先于网络搜索使用，速度更快且信息更可靠。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称（中文），如 '巴黎'、'东京'、'纽约'",
                    },
                    "query": {
                        "type": "string",
                        "description": "查询内容，如 '博物馆 景点推荐' 或 '住宿区域 价格'",
                    },
                },
                "required": ["city", "query"],
            },
        },
    },
]


# ── 工具执行函数 ─────────────────────────────────────────────────────────

def _execute_search_web(args: dict, search_client) -> str:
    """执行网络搜索"""
    query = args.get("query", "")
    topic = args.get("topic", "general")

    if search_client is None:
        return f"[Web Search 不可用：TAVILY_API_KEY 未配置] 查询：{query}"

    try:
        result = search_client.search(query, max_results=3)
        if not result:
            return f"未找到关于 '{query}' 的搜索结果"

        lines = [f" 搜索结果（{query}）："]
        if result.get("answer"):
            lines.append(f"摘要：{result['answer']}")
        for item in result.get("results", [])[:3]:
            lines.append(f"- {item.get('title', '')}: {item.get('content', '')[:200]}")

        return "\n".join(lines)
    except Exception as e:
        return f"[搜索失败: {e}]"


_CITY_KB_KEY = {
    "巴黎": "Paris", "东京": "Tokyo", "纽约": "Newyork", "伦敦": "London",
    "罗马": "Rome", "悉尼": "Sydney", "巴塞罗那": "Barcelona", "曼谷": "Bangkok",
    "新加坡": "Singapore", "首尔": "Seoul", "迪拜": "Dubai", "阿姆斯特丹": "Amsterdam",
    "维也纳": "Vienna", "布拉格": "Prague", "普吉岛": "Phuket", "马尔代夫": "Maldives",
    "伊斯坦布尔": "Istanbul", "里斯本": "Lisbon", "巴厘岛": "Bali",
    "大阪": "Osaka", "京都": "Kyoto", "广州": "Guangzhou",
}

def _execute_query_knowledge(args: dict, knowledge_client) -> str:
    """执行知识库查询"""
    city = args.get("city", "")
    query = args.get("query", "")

    if knowledge_client is None:
        return f"[知识库不可用：ChromaDB 未初始化] 查询：{city} - {query}"

    # 将中文城市名转为知识库中存储的英文 key
    kb_city = _CITY_KB_KEY.get(city, city)

    try:
        results = knowledge_client.search(f"{city} {query}", n_results=3, city=kb_city)
        if not results or not results.get("results"):
            return f"知识库中未找到关于 '{city}' 的信息，建议使用 search_web 工具"

        lines = [f" 知识库结果（{city} - {query}）："]
        for r in results["results"][:3]:
            lines.append(f"- {r.get('content', '')[:300]}")

        return "\n".join(lines)
    except Exception as e:
        return f"[知识库查询失败: {e}]"


# ── 主智能体类 ────────────────────────────────────────────────────────────

class TravelPlanningAgent:
    """旅游规划智能体 - Agentic AI"""

    _class_cache: dict = {}
    _cache_max_size: int = 30

    def __init__(self, enable_knowledge: bool = True, enable_web_search: bool = True):
        self.model_name = GOAL_BASED_CONFIG.get("model_name", "qwen3.6-plus")
        self.temperature = GOAL_BASED_CONFIG.get("temperature", 0.75)
        self.max_tokens = GOAL_BASED_CONFIG.get("max_tokens", 8192)
        self.max_tool_rounds = 3 # Agent 最多调用工具的轮数
        self.agent_steps: list = [] # 记录 Agent 的决策过程

        # 初始化 LLM 客户端
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 未配置，请在 .env 文件中设置")
        # 使用不带代理的 httpx 客户端，直连 API（绕过本地代理的 SSL 握手问题）
        import httpx
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=1,
            http_client=httpx.Client(
                proxy=None,
                timeout=httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=10.0),
            ),
        )
        logger.info(f"旅游规划智能体已启动 (模型: {self.model_name})")

        # 初始化工具客户端
        self.search_client = None
        self.knowledge_client = None

        if enable_web_search and TavilySearchClient:
            try:
                self.search_client = TavilySearchClient()
                logger.info("Web Search 工具已就绪（Tavily）")
            except Exception as e:
                logger.warning(f"Web Search 初始化失败: {e}")

        if enable_knowledge and LocalKnowledgeClient:
            try:
                self.knowledge_client = LocalKnowledgeClient()
                count = self.knowledge_client.count()
                if count > 0:
                    logger.info(f"知识库工具已就绪（{count} 条文档）")
                else:
                    logger.warning("知识库为空，请先运行: python scripts/import_local_knowledge.py")
                    self.knowledge_client = None
            except Exception as e:
                logger.warning(f"知识库初始化失败: {e}")

    def _get_cache_key(self, user_request: str, meta: dict) -> str:
        s = f"{self.model_name}_{user_request}_{json.dumps(meta, sort_keys=True)}"
        return hashlib.md5(s.encode()).hexdigest()

    def _execute_tool(self, tool_name: str, args: dict) -> str:
        """执行工具调用并记录步骤"""
        logger.debug(f"调用工具: {tool_name}({json.dumps(args, ensure_ascii=False)})")
        t0 = time.time()

        if tool_name == "search_web":
            result = _execute_search_web(args, self.search_client)
        elif tool_name == "query_knowledge_base":
            result = _execute_query_knowledge(args, self.knowledge_client)
        else:
            result = f"[未知工具: {tool_name}]"

        elapsed = round(time.time() - t0, 2)
        # 生成可读 preview：知识库显示"城市 · 查询关键词"，搜索显示查询词
        if tool_name == "query_knowledge_base":
            preview = f"{args.get('city', '')} · {args.get('query', '')}".strip(" ·")
        elif tool_name == "search_web":
            preview = args.get("query", result[:80].replace("\n", " "))
        else:
            preview = result[:100].replace("\n", " ")
        logger.debug(f"{tool_name} 完成 ({elapsed}s)")

        self.agent_steps.append({
            "tool": tool_name,
            "args": args,
            "result_preview": preview,
            "time_s": elapsed,
        })
        return result

    def generate_itinerary(self, user_request: str, meta: dict,
                           use_cache: bool = True) -> dict:
        """运行 Agent 循环生成旅行行程"""
        cache_key = self._get_cache_key(user_request, meta)
        if use_cache and cache_key in self._class_cache:
            logger.debug("命中缓存")
            return self._class_cache[cache_key]

        self.agent_steps = [] # 重置步骤记录
        city = meta.get("city", "")
        logger.info(f"智能体启动：规划 {city} {meta.get('days')}天行程")

        # ── 主动预查询知识库，注入本地实景数据 ────────────────────────
        kb_context = ""
        if self.knowledge_client and city:
            try:
                kb_res = self._execute_tool("query_knowledge_base", {
                    "city": city, "query": f"{city} 景点 餐饮 住宿 交通 实用贴士"
                })
                if kb_res and "不可用" not in kb_res:
                    kb_context = f"\n\n【本地知识库参考资料 — {city}】\n{kb_res[:1800]}\n\n请结合以上本地真实资料（POI、价格、开放时间、小红书风格贴士）生成行程，使内容更加贴近实际。"
                    logger.info(f"知识库预查询成功，注入 {len(kb_context)} 字符")
            except Exception as e:
                logger.warning(f"知识库预查询失败: {e}")

        # ── 构建初始消息 ────────────────────────────────────────────────
        messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_request + kb_context},
        ]

        total_start = time.time()
        final_output = ""
        tool_rounds = 0

        # ── Agent 循环 ───────────────────────────────────────────────────

        while tool_rounds <= self.max_tool_rounds:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=TOOLS,
                tool_choice="none",
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            choice = response.choices[0]
            messages.append(choice.message) # 将 assistant 消息加入历史

            if choice.finish_reason == "tool_calls":
                # Agent 决定调用工具
                tool_rounds += 1
                logger.debug(f"第{tool_rounds}轮工具调用")
                for tc in choice.message.tool_calls:
                    args = json.loads(tc.function.arguments)
                    result = self._execute_tool(tc.function.name, args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

            elif choice.finish_reason in ("stop", "length"):
                # Agent 决定完成，直接输出行程
                final_output = choice.message.content or ""
                break
            else:
                break

        processing_time = round(time.time() - total_start, 2)
        logger.info(f"智能体完成 (耗时: {processing_time}s, 工具调用: {tool_rounds} 轮)")

        tool_types = [s["tool"] for s in self.agent_steps]
        result = {
            "city": city,
            "days": meta.get("days", 3),
            "budget": meta.get("budget", ""),
            "interests": meta.get("interests", []),
            "group": meta.get("group", ""),
            "itinerary": final_output,
            "output": final_output,
            "source": "agent",
            "agent_steps": self.agent_steps,
            "tool_rounds": tool_rounds,
            "processing_time": processing_time,
            "token_estimate": len(final_output) // 2,
            "metadata": meta,
            "model": self.model_name,
            "using_real_llm": True,
            "cache_hit": False,
            "response_time": processing_time,
        }

        if use_cache:
            if len(self._class_cache) >= self._cache_max_size:
                oldest = next(iter(self._class_cache))
                del self._class_cache[oldest]
            self._class_cache[cache_key] = result

        return result

    def stream_itinerary(self, user_request: str, meta: dict):
        """
        流式生成行程，逐 chunk yield 文本，供 SSE 接口使用。
        最后 yield 一个 dict {"__meta__": True, ...} 作为结束信号。
        """
        city = meta.get("city", "")
        logger.info(f"智能体流式启动：规划 {city} {meta.get('days')}天行程")
        self.agent_steps = []

        # 命中缓存时一次性 yield 全部内容，再发结束信号
        cache_key = self._get_cache_key(user_request, meta)
        if cache_key in self._class_cache:
            cached = self._class_cache[cache_key]
            yield cached.get("itinerary", cached.get("output", ""))
            yield {"__meta__": True, "processing_time": 0.0, "cache_hit": True,
                   "tool_rounds": 0, "agent_steps": []}
            return

        # ── 工具预查询：知识库 + 实时联网 ──────────────────────────
        extra_context = ""
        tool_steps = []
        tool_rounds = 0

        # 1. 本地知识库
        if self.knowledge_client and city:
            try:
                kb_res = self._execute_tool("query_knowledge_base", {
                    "city": city, "query": f"{city} 景点 餐饮 住宿 交通 实用贴士"
                })
                if kb_res and "不可用" not in kb_res:
                    extra_context += f"\n\n【本地知识库 — {city}】\n{kb_res[:1800]}"
                    tool_steps.append({
                        "tool": "query_knowledge_base",
                        "args": {"city": city, "query": f"{city} 景点 餐饮 住宿 交通 实用贴士"},
                        "result_preview": kb_res[:80],
                    })
                    tool_rounds += 1
                    logger.info("流式：知识库预查询成功")
            except Exception as e:
                logger.warning(f"流式：知识库预查询失败: {e}")

        # 2. 实时联网搜索（Tavily）
        if self.search_client and city:
            try:
                import datetime as _dt_mod
                _cur_year = _dt_mod.datetime.now().year
                web_res = self.search_client.search(
                    f"{city} 旅行攻略 {meta.get('days', 3)}天 景点 餐厅 {_cur_year}",
                    max_results=4
                )
                if web_res:
                    snippets = "\n".join(
                        f"- {r['title']}: {r['content'][:200]}"
                        for r in web_res.get("results", [])[:4]
                    )
                    if web_res.get("answer"):
                        snippets = web_res["answer"][:400] + "\n" + snippets
                    extra_context += f"\n\n【实时联网参考 — {city}】\n{snippets[:1500]}"
                    _web_query = f"{city} 旅行攻略 {meta.get('days', 3)}天 景点 餐厅"
                    tool_steps.append({
                        "tool": "search_web",
                        "args": {"query": _web_query, "topic": "general"},
                        "result_preview": snippets[:80],
                    })
                    tool_rounds += 1
                    logger.info("流式：实时联网搜索成功")
            except Exception as e:
                logger.warning(f"流式：实时联网搜索失败: {e}")

        if extra_context:
            extra_context += "\n\n请结合以上参考资料生成详实行程。"

        messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user",   "content": user_request + extra_context},
        ]
        _extra = {"enable_thinking": False}
        total_start = time.time()
        full_text = ""

        try:
            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tool_choice="none",
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                extra_body=_extra,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    full_text += delta
                    yield delta          # 文本 chunk
        except Exception as e:
            logger.error(f"流式生成失败: {e}")
            yield f"\n\n[生成中断: {e}]"

        processing_time = round(time.time() - total_start, 2)
        logger.info(f"智能体流式完成 (耗时: {processing_time}s, 工具: {tool_rounds}轮)")

        # 缓存结果
        if len(self._class_cache) >= self._cache_max_size:
            oldest = next(iter(self._class_cache))
            del self._class_cache[oldest]
        self._class_cache[cache_key] = {
            "itinerary": full_text, "output": full_text,
            "processing_time": processing_time,
            "tool_rounds": tool_rounds,
            "agent_steps": tool_steps,
            "model": self.model_name,
        }

        # 结束信号（含元数据）
        yield {"__meta__": True, "processing_time": processing_time,
               "cache_hit": False, "tool_rounds": tool_rounds,
               "agent_steps": tool_steps}

    def print_agent_trace(self):
        """打印 Agent 决策过程（用于透明度分析）"""
        if not self.agent_steps:
            logger.info("Agent 未调用任何工具（直接生成）")
            return
        for i, step in enumerate(self.agent_steps, 1):
            logger.info(f"步骤{i}: {step['tool']} → {step['result_preview']}...")


def generate(test_case: dict, enable_knowledge: bool = True,
             enable_web_search: bool = True) -> dict:
    """供 api_server.py 统一接口调用"""
    agent = TravelPlanningAgent(
        enable_knowledge=enable_knowledge,
        enable_web_search=enable_web_search,
    )
    user_request = test_case.get("input", "")
    meta = test_case.get("metadata", {})
    result = agent.generate_itinerary(user_request, meta)
    result["metadata"] = meta
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    from dotenv import load_dotenv
    load_dotenv()

    test_case = {
        "input": "我想去巴黎玩5天，和爱人一起，喜欢文化和美食，预算宽裕。",
        "metadata": {
            "city": "巴黎", "days": 5, "budget": "高",
            "interests": ["文化", "美食"], "group": "情侣", "special": "无",
        },
    }

    agent = TravelPlanningAgent()
    result = agent.generate_itinerary(test_case["input"], test_case["metadata"], use_cache=False)
    print(result["itinerary"])
    print(f"\n工具调用: {result['tool_rounds']} 轮 | 耗时: {result['processing_time']}s")
