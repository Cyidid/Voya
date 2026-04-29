#!/usr/bin/env python3
"""
云游 AI 旅行规划 — FastAPI 后端
路由：/api/generate · /api/chat · /api/booking/* · /preview
"""

import os, sys, re, time, logging, json, asyncio
from contextlib import asynccontextmanager
from typing import Optional, List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 加载 .env 环境变量（本地运行必须）
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    load_dotenv(_env_path)
except ImportError:
    pass

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import iterate_in_threadpool
from pydantic import BaseModel, Field
import uvicorn

# ── 日志 ────────────────────────────────────────────────────────
_log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(_log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(_log_dir, "api.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ── 导入三大系统 ─────────────────────────────────────────────────
from systems.rule_based.engine import generate as rule_based_generate
from systems.supervised.inference import generate as supervised_generate

# Goal-Based Agent：优先使用 tool-calling 版本
try:
    from systems.goal_based.agent_agentic import TravelPlanningAgent

    def goal_based_generate(test_case: dict, **kw) -> dict:
        agent = TravelPlanningAgent(
            enable_knowledge=kw.get("enable_knowledge", True),
            enable_web_search=kw.get("enable_web_search", True),
        )
        result = agent.generate_itinerary(test_case.get("input", ""), test_case.get("metadata", {}))
        return result

    logger.info("Goal-Based: Tool Calling Agent 已加载")
except Exception as e:
    logger.error(f"Goal-Based Agent 加载失败: {e}")
    def goal_based_generate(test_case: dict, **kw) -> dict:
        raise RuntimeError("Goal-Based Agent 不可用，请检查 OPENAI_API_KEY 配置")

# ── 导入票务引擎 ─────────────────────────────────────────────────
from systems.booking.booking_engine import (
    search_tickets, create_order, get_orders, get_order, cancel_order,
    DOMESTIC_CITIES, INTL_HUB,
)

# ── Tavily 联网搜索（票务兜底）──────────────────────────────────────
try:
    from systems.goal_based.tavily_client import TavilySearchClient as _TavilyClient
    _tavily = _TavilyClient()
except Exception:
    _tavily = None

async def _search_flights_online(origin: str, dest: str, date: str) -> list[dict]:
    """路线不在数据库时，用 Tavily 联网搜索，返回 web_info 类型结果"""
    if not _tavily:
        return []
    try:
        from starlette.concurrency import run_in_threadpool
        query = f"{origin} {dest} 机票 航班 {date[:7]}"
        raw = await run_in_threadpool(_tavily.search, query, 5)
        if not raw:
            return []
        items = []
        # 把 Tavily answer 作为第一条摘要卡
        if raw.get("answer"):
            items.append({
                "type": "web_info",
                "title": f"{origin} → {dest} 航班摘要",
                "snippet": raw["answer"][:400],
                "url": "",
                "from": origin, "to": dest,
            })
        for r in raw.get("results", [])[:4]:
            items.append({
                "type": "web_info",
                "title": r.get("title", ""),
                "snippet": r.get("content", "")[:300],
                "url": r.get("url", ""),
                "from": origin, "to": dest,
            })
        return items
    except Exception as e:
        import logging; logging.getLogger(__name__).warning(f"票务联网搜索失败: {e}")
        return []

# 票务支持的城市集合（国内 + 国际）
KNOWN_CITIES: frozenset = frozenset(DOMESTIC_CITIES) | frozenset(INTL_HUB.keys())

# ── 统计 ─────────────────────────────────────────────────────────
_stats = {
    "total": 0, "success": 0, "failed": 0,
    "rule_based": 0, "supervised": 0, "goal_based": 0,
    "bookings_created": 0, "start_time": time.time(),
}


# ── 结构化错误响应助手 ────────────────────────────────────────────

def _api_error(status: int, code: str, user_msg: str, detail: str = "") -> HTTPException:
    """返回统一格式的结构化错误，避免裸 Python 异常泄露给前端。"""
    return HTTPException(
        status_code=status,
        detail={
            "error_code": code,
            "user_message": user_msg,
            "detail": detail[:300] if detail else "",
        },
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(" 云游 AI 旅行规划系统启动")
    yield
    logger.info(" 系统关闭")


app = FastAPI(
    title="云游 API",
    description="三种 AI 范式的旅行行程规划 + 机票/火车票预订",
    version="3.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 静态文件（CSS/JS）─────────────────────────────────────
_web_dir = os.path.dirname(os.path.abspath(__file__))
_assets_dir = os.path.join(_web_dir, "assets")
app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")


@app.middleware("http")
async def track_requests(request: Request, call_next):
    _stats["total"] += 1
    t0 = time.time()
    try:
        resp = await call_next(request)
        _stats["success"] += 1
        resp.headers["X-Process-Time"] = f"{(time.time()-t0)*1000:.1f}ms"
        return resp
    except Exception as e:
        _stats["failed"] += 1
        logger.error(f" {request.method} {request.url.path} — {e}")
        raise


# ── 格式化输出 ───────────────────────────────────────────────────

# 城市货币信息：(货币代码, 货币名称, 1货币=?人民币)
_CITY_CURRENCY: dict[str, tuple[str, str, float]] = {
    "巴黎":     ("EUR", "欧元",        7.80),
    "伦敦":     ("GBP", "英镑",        9.10),
    "罗马":     ("EUR", "欧元",        7.80),
    "巴塞罗那": ("EUR", "欧元",        7.80),
    "阿姆斯特丹":("EUR", "欧元",       7.80),
    "维也纳":   ("EUR", "欧元",        7.80),
    "布拉格":   ("CZK", "捷克克朗",    0.31),
    "里斯本":   ("EUR", "欧元",        7.80),
    "东京":     ("JPY", "日元",        0.048),
    "大阪":     ("JPY", "日元",        0.048),
    "京都":     ("JPY", "日元",        0.048),
    "首尔":     ("KRW", "韩元",        0.0053),
    "新加坡":   ("SGD", "新加坡元",    5.30),
    "曼谷":     ("THB", "泰铢",        1.98),
    "普吉岛":   ("THB", "泰铢",        1.98),
    "马尔代夫": ("MVR", "马尔代夫卢非亚", 4.40),
    "迪拜":     ("AED", "阿联酋迪拉姆", 1.96),
    "伊斯坦布尔":("TRY", "土耳其里拉", 0.22),
    "悉尼":     ("AUD", "澳大利亚元",  4.70),
    "纽约":     ("USD", "美元",        7.20),
    "广州":     ("CNY", "人民币",      1.00),
    "开罗":     ("EGP", "埃及镑",      0.14),
    "哥本哈根": ("DKK", "丹麦克朗",   1.04),
    "苏黎世":   ("CHF", "瑞士法郎",   8.20),
    "巴厘岛":   ("IDR", "印尼盾",     0.00044),
}

# 午餐建议文案（按天轮换，增加真实感）
_LUNCH_HINTS = [
    "在附近找一家当地人常去的小馆落座，避开游客集中区往往物美价廉。",
    "路边的街头小吃是感受当地市井文化的最好方式，别错过小摊上的限定风味。",
    "可以去附近的市集或室内美食广场，现点现做、选择多样，轻松补充能量。",
    "这一带不乏品质咖啡馆，点一份简餐顺便感受本地的下午茶氛围。",
    "午市套餐（Lunch Set）往往比晚市同款便宜三成，旅途中的省心之选。",
]

_CATEGORY_LABELS: dict[str, tuple[str, str]] = {
    "culture":   ("文化体验", "深入了解当地艺术与人文精髓"),
    "history":   ("历史探访", "穿越时光，感受厚重历史底蕴"),
    "nature":    ("自然游览", "亲近自然，呼吸新鲜空气"),
    "food":      ("美食探索", "品尝地道风味，犒劳味蕾"),
    "shopping":  ("购物休闲", "逛遍特色街区，带走心仪纪念品"),
    "nightlife": ("夜间活动", "感受城市夜晚的活力与魅力"),
    "morning":   ("上午活动", "元气满满地开启美好一天"),
    "afternoon": ("下午活动", "午后悠然，继续探索"),
    "evening":   ("晚间活动", "为精彩一天画上完美句号"),
}

_BUDGET_LABEL  = {"低": "经济实惠", "中": "舒适中档", "高": "高端奢华"}
_BUDGET_DAILY  = {"低": "¥200–400 / 人·天", "中": "¥600–1,000 / 人·天", "高": "¥2,000+ / 人·天"}
_BUDGET_HOTEL  = {"低": "青旅 / 经济连锁酒店", "中": "三星 / 舒适型酒店", "高": "五星级 / 精品度假酒店"}
_BUDGET_FOOD   = {"低": "街头小吃 / 平价餐馆", "中": "特色餐厅 / 本地料理", "高": "米其林 / 高级景观餐厅"}
_BUDGET_TICKET = {"低": "优先免费景点", "中": "主要景点标准票", "高": "私人导览 / 深度体验"}

_GROUP_TRIP = {
    "情侣": "情侣浪漫游", "夫妻": "情侣浪漫游",
    "家庭": "亲子家庭游", "朋友": "好友结伴游",
    "同事": "团队社交游", "独自": "独旅探索游",
}
_INTEREST_TRIP = {
    "文化": "文化深度游", "美食": "美食探索游", "历史": "历史文化游",
    "自然": "自然探索游", "购物": "购物休闲游", "夜生活": "夜游体验",
}


def _format_output(result: dict, agent_type: str) -> str:
    if agent_type == "goal_based":
        return result.get("output") or result.get("itinerary") or "无法生成行程，请稍后重试。"

    itinerary = result.get("itinerary", {})
    if not itinerary:
        return "无法生成行程，请检查输入信息。"
    if isinstance(itinerary, str):
        return itinerary

    meta     = result.get("metadata", {})
    city     = meta.get("city", "目的地")
    days     = meta.get("days", len(itinerary))
    budget   = meta.get("budget", "中")
    group    = meta.get("group", "")
    num_p    = meta.get("num_people", 2)
    mode     = meta.get("travel_mode", "飞机")
    special  = meta.get("special", "无")
    interests = meta.get("interests", [])
    origin   = meta.get("origin", "")

    # 出行类型标签
    rec_zh = result.get("recommendation_type_zh", "")
    if not rec_zh:
        rec_zh = _GROUP_TRIP.get(group, "") or _INTEREST_TRIP.get(interests[0] if interests else "", "精彩观光游")

    transport_tip = result.get("transport_tip", "")
    city_tips     = result.get("city_tips", [])
    total_budget  = result.get("total_budget_estimate", 0)
    daily_avg     = total_budget // days if days else total_budget

    lines: list[str] = []

    # ── 标题 ──────────────────────────────────────────────────────
    lines.append(f"# {city} · {days} 日{rec_zh}\n")

    # ── 行程概览 ──────────────────────────────────────────────────
    lines.append("## 行程概览\n")
    origin_str = f"从 **{origin}** 出发 · " if origin else ""
    special_str = f" · 特别需求：{special}" if special and special != "无" else ""
    lines.append(
        f"{origin_str}**{num_p} 人** · 出行方式：{mode} "
        f"· 预算：{_BUDGET_LABEL.get(budget, budget)}{special_str}\n"
    )

    if agent_type == "supervised":
        confidence = result.get("model_confidence", 0)
        model_type = result.get("model_type", "VotingClassifier")
        lines.append(
            f"> 模型推荐类型：**{rec_zh}**（置信度 {confidence:.0%}）"
            f"  ·  模型：{model_type}\n"
        )

    lines.append("---\n")

    # ── 每日行程 ──────────────────────────────────────────────────
    for day_key in sorted(itinerary.keys()):
        day    = itinerary[day_key]
        day_num = day_key.replace("day_", "")
        theme  = day.get("theme", f"{city}探索 Day {day_num}")

        lines.append(f"## 第 {day_num} 天：{theme}\n")

        # 解析天号（用于午餐轮换）
        try:
            day_num_int = int(day_num)
        except ValueError:
            day_num_int = 1

        # 上午
        morning = day.get("morning")
        if morning:
            act      = morning.get("activity", "")
            cost     = morning.get("cost_estimate", 0)
            duration = morning.get("duration", 3)
            cat      = morning.get("category", "culture")
            cat_label, cat_desc = _CATEGORY_LABELS.get(cat, ("上午活动", "探索当地精华"))
            cost_str = f"，参考费用约 ¥{cost}" if cost else "，免费开放"
            lines.append(f"**上午 · {cat_label}**")
            lines.append(f"**{act}** — {cat_desc}。建议游览约 {duration} 小时{cost_str}。\n")

        # 午餐（按天轮换，不再每天相同）
        lunch_hint = _LUNCH_HINTS[(day_num_int - 1) % len(_LUNCH_HINTS)]
        food_type  = _BUDGET_FOOD.get(budget, "当地特色餐厅")
        lines.append("**午餐推荐**")
        lines.append(f"推荐就近选择 **{food_type}**。{lunch_hint}\n")

        # 下午
        afternoon = day.get("afternoon")
        if afternoon:
            act      = afternoon.get("activity", "")
            cost     = afternoon.get("cost_estimate", 0)
            duration = afternoon.get("duration", 3)
            cat      = afternoon.get("category", "culture")
            cat_label, cat_desc = _CATEGORY_LABELS.get(cat, ("下午活动", "续写旅途故事"))
            cost_str = f"，参考费用约 ¥{cost}" if cost else "，免费开放"
            lines.append(f"**下午 · {cat_label}**")
            lines.append(f"**{act}** — {cat_desc}。建议游览约 {duration} 小时{cost_str}。\n")

        # 晚餐（显示餐厅名，加预算定性描述）
        evening = day.get("evening")
        if evening:
            act  = evening.get("activity", "")
            cost = evening.get("cost_estimate", 0)
            food_desc = {"低": "经济实惠、接地气", "中": "特色鲜明、性价比高", "高": "精致讲究、值得一试"}.get(budget, "")
            cost_str = f"，人均约 ¥{cost}" if cost else ""
            lines.append("**晚餐**")
            lines.append(f"**{act}** — {food_desc}{cost_str}。结束愉快的一天。\n")

        # 第一天附上交通提示
        if transport_tip and day_key == "day_1":
            lines.append(f"> 🚇 交通贴士：{transport_tip}\n")

        lines.append("---\n")

    # ── 住宿建议 ──────────────────────────────────────────────────
    lines.append("## 住宿建议\n")
    lines.append(
        f"推荐选择 **{_BUDGET_HOTEL.get(budget, '舒适型酒店')}**，"
        f"优先考虑靠近主要景点或市中心的位置，节省通勤时间，行程更从容。\n"
    )

    # ── 交通建议 ──────────────────────────────────────────────────
    if transport_tip:
        lines.append("## 交通建议\n")
        lines.append(f"{transport_tip}\n")

    # ── 当地贴士 ──────────────────────────────────────────────────
    if city_tips:
        lines.append("## 当地贴士\n")
        for tip in city_tips:
            lines.append(f"- {tip}")
        lines.append("")

    # ── 预算参考 ──────────────────────────────────────────────────
    lines.append("## 预算参考\n")
    lines.append("| 费用项目 | 预估（人民币）|")
    lines.append("|---------|------------|")
    lines.append(f"| 每日活动 & 门票 | 约 ¥{daily_avg} / 天 |")
    lines.append(f"| 住宿（{days} 晚）| {_BUDGET_HOTEL.get(budget, '按实际')} |")
    lines.append(f"| 餐饮标准 | {_BUDGET_FOOD.get(budget, '按实际')} |")
    lines.append(f"| 景点门票 | {_BUDGET_TICKET.get(budget, '按实际')} |")
    lines.append(f"| **行程合计（{days} 天）** | **约 ¥{total_budget}**（不含国际交通）|")
    lines.append("")
    lines.append(f"> 参考消费水平：{_BUDGET_DAILY.get(budget, '')}，实际费用因个人选择与当地物价而异。\n")

    # ── 货币换算提示 ──────────────────────────────────────────────
    cur = _CITY_CURRENCY.get(city)
    if cur:
        code, name, rate = cur
        if code != "CNY":
            # 用当地货币显示对应参考价
            daily_local = round(daily_avg / rate)
            lines.append(f"## 货币参考\n")
            lines.append(f"当地通用货币：**{name}（{code}）**")
            lines.append(f"当前参考汇率：**1 {code} ≈ ¥{rate:.3g} 人民币**")
            lines.append(f"（每日活动参考：约 {daily_local:,} {code} / 人·天）\n")
            lines.append(f"> 汇率随市场波动，实际以出行时银行/兑换网点为准，建议提前适量兑换或使用境外免手续费银行卡。\n")

    # ── 系统说明 ──────────────────────────────────────────────────
    if agent_type == "supervised":
        top = result.get("top_features", [])
        if top:
            top_str = "、".join(
                f[0] if isinstance(f, (list, tuple)) else str(f) for f in top[:3]
            )
            lines.append(
                f"> *本行程由监督学习模型（{result.get('model_type', 'VotingClassifier')}）生成，"
                f"关键决策特征：{top_str}。*\n"
            )
    elif agent_type == "rule_based":
        lines.append(
            "> *本行程由专家规则库生成，每条推荐均可追溯至规则库具体条目，决策完全透明可解释。*\n"
        )

    return "\n".join(lines)


# ── 数据模型 ─────────────────────────────────────────────────────

class TravelRequest(BaseModel):
    city: str
    days: int = Field(..., ge=1, le=14)
    budget: str
    interests: List[str] = []
    group: str
    num_people: Optional[int] = Field(default=2, ge=1, le=20)
    travel_mode: Optional[str] = "飞机"
    special: Optional[str] = "无"
    origin: Optional[str] = ""
    agent_type: str = "goal_based"
    start_date: Optional[str] = ""   # YYYY-MM-DD，可选出发日期


class ChatMessage(BaseModel):
    role: str
    content: str
    agent_type: Optional[str] = "goal_based"


class BookingSearchRequest(BaseModel):
    origin: str = Field(..., description="出发地城市")
    destination: str = Field(..., description="目的地城市")
    date: str = Field(..., description="出发日期 YYYY-MM-DD")
    type: str = Field(default="flight", description="flight 或 train")
    budget_hint: Optional[str] = None


class BookingCreateRequest(BaseModel):
    ticket_id: str
    ticket_data: dict
    passenger_name: str = Field(..., min_length=2)
    id_number: Optional[str] = ""


# ── 行程生成路由 ─────────────────────────────────────────────────

@app.post("/api/generate")
async def generate_itinerary(req: TravelRequest):
    """生成旅行行程（三种 AI 系统可选）"""
    # 公平性：情侣/夫妻人数归一为 2；其余保持用户输入
    num_people = 2 if req.group in ("情侣", "夫妻") else (req.num_people or 2)

    origin_prefix = f"从{req.origin}出发，" if req.origin else ""
    test_case = {
        "id": f"WEB_{req.city}",
        "input": (
            f"{origin_prefix}乘{req.travel_mode or '飞机'}，共{num_people}人，"
            f"我想去{req.city}玩{req.days}天，和{req.group}一起，"
            f"喜欢{'、'.join(req.interests) or '观光'}，预算{req.budget}"
            f"{'，' + req.special if req.special and req.special != '无' else ''}。"
        ),
        "metadata": {
            "city": req.city, "days": req.days, "budget": req.budget,
            "interests": req.interests, "group": req.group,
            "special": req.special, "origin": req.origin or "",
            "num_people": num_people, "travel_mode": req.travel_mode or "飞机",
            "start_date": req.start_date or "",
        },
    }

    try:
        if req.agent_type == "rule_based":
            result = rule_based_generate(test_case)
            _stats["rule_based"] += 1
        elif req.agent_type == "supervised":
            result = supervised_generate(test_case)
            _stats["supervised"] += 1
        else:
            result = goal_based_generate(test_case, enable_knowledge=True, enable_web_search=True)
            _stats["goal_based"] += 1

        formatted = _format_output(result, req.agent_type)
        meta = result.get("metadata", test_case["metadata"])

        # ── 公共字段（所有 agent 均返回）───────────────────────────
        resp: dict = {
            "itinerary": formatted,
            "agent_type": req.agent_type,
            "processing_time": result.get("processing_time", 0),
            "token_estimate": result.get("token_estimate", len(formatted) // 2),
            "metadata": meta,
        }

        # ── Agent 专属字段（按类型精简，减少无关字段传输）──────────
        if req.agent_type == "rule_based":
            resp["transport_tip"] = result.get("transport_tip", "")
            resp["city_tips"] = result.get("city_tips", [])

        elif req.agent_type == "supervised":
            resp["recommendation_type_zh"] = result.get("recommendation_type_zh", "")
            resp["model_confidence"] = result.get("model_confidence", 0)
            resp["top_features"] = result.get("top_features", [])

        else: # goal_based
            resp["agent_steps"] = result.get("agent_steps", [])
            resp["tool_rounds"] = result.get("tool_rounds", 0)

        return resp

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"generate_itinerary error: {e}", exc_info=True)
        raise _api_error(
            500, "ITINERARY_GENERATION_FAILED",
            "行程生成失败，请稍后重试",
            str(e),
        )


@app.post("/api/generate/stream")
async def generate_stream(req: TravelRequest):
    """
    SSE 流式接口（goal_based 专用）。
    每行格式：data: <JSON>\\n\\n
      - 文本块：{"chunk": "..."}
      - 完成：  {"done": true, "processing_time": X, "tool_rounds": 0, "cache_hit": false}
      - 错误：  {"error": "..."}
    非 goal_based 系统直接返回一个 done 事件（秒返）。
    """
    num_people = 2 if req.group in ("情侣", "夫妻") else (req.num_people or 2)
    origin_prefix = f"从{req.origin}出发，" if req.origin else ""
    # 计算出发日期与返程日期
    _dep_date = req.start_date or ""
    _ret_date = ""
    if _dep_date and req.days:
        try:
            from datetime import datetime as _dt, timedelta as _td
            _d = _dt.strptime(_dep_date, "%Y-%m-%d")
            _ret_date = (_d + _td(days=req.days)).strftime("%Y-%m-%d")
        except Exception:
            pass
    date_suffix = ""
    if _dep_date:
        date_suffix = f"，出发日期{_dep_date}"
        if _ret_date:
            date_suffix += f"，返程日期{_ret_date}"
    user_input = (
        f"{origin_prefix}乘{req.travel_mode or '飞机'}，共{num_people}人，"
        f"我想去{req.city}玩{req.days}天，和{req.group}一起，"
        f"喜欢{'、'.join(req.interests) or '观光'}，预算{req.budget}"
        f"{'，' + req.special if req.special and req.special != '无' else ''}"
        f"{date_suffix}。"
    )
    meta = {
        "city": req.city, "days": req.days, "budget": req.budget,
        "interests": req.interests, "group": req.group,
        "special": req.special, "origin": req.origin or "",
        "num_people": num_people, "travel_mode": req.travel_mode or "飞机",
        "start_date": req.start_date or "",
    }
    test_case = {"id": f"WEB_{req.city}", "input": user_input, "metadata": meta}

    # ── 非流式系统 ────────────────────────────────────────────────
    if req.agent_type != "goal_based":
        try:
            if req.agent_type == "rule_based":
                result = rule_based_generate(test_case)
            else:
                result = supervised_generate(test_case)
            formatted = _format_output(result, req.agent_type)
            result_meta = {
                "recommendation_type_zh": result.get("recommendation_type_zh", ""),
                "model_confidence": result.get("model_confidence", 0),
                "top_features": result.get("top_features", []),
                "transport_tip": result.get("transport_tip", ""),
                "city_tips": result.get("city_tips", []),
                "transport_tip_en": result.get("transport_tip_en", result.get("transport_tip", "")),
                "city_tips_en": result.get("city_tips_en", result.get("city_tips", [])),
                "total_budget_estimate": result.get("total_budget_estimate"),
                "weather_note": result.get("weather_note", ""),
                "proba_distribution": result.get("proba_distribution", []),
                "is_uncertain": result.get("is_uncertain", False),
                "model_accuracy": result.get("model_accuracy", 0),
                "dataset_size": result.get("dataset_size", 0),
            }
        except Exception as e:
            async def err_shot():
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
            return StreamingResponse(err_shot(), media_type="text/event-stream",
                                     headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})

        # rule_based: 毫秒响应，直接一次返回 done 事件
        if req.agent_type == "rule_based":
            payload = json.dumps({
                "done": True, "itinerary": formatted,
                "processing_time": result.get("processing_time", 0),
                "tool_rounds": 0, "cache_hit": False,
                "result_meta": result_meta,
            }, ensure_ascii=False)

            async def one_shot():
                yield f"data: {payload}\n\n"
            return StreamingResponse(one_shot(), media_type="text/event-stream",
                                     headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})

        # supervised: 逐行流式输出，模拟打字机效果
        import time as _time

        def _supervised_stream():
            import time as _t
            # 每 3 行合并成一个 chunk，延迟 10ms → 视觉上流畅，速度快约 4x
            lines = formatted.split("\n")
            buf = []
            for line in lines:
                buf.append(line)
                if len(buf) >= 3:
                    chunk = "\n".join(buf) + "\n"
                    yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
                    buf = []
                    _t.sleep(0.01)
            if buf:  # 剩余行
                chunk = "\n".join(buf) + "\n"
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
            done_payload = json.dumps({
                "done": True,
                "processing_time": result.get("processing_time", 0),
                "tool_rounds": 0, "cache_hit": False,
                "result_meta": result_meta,
            }, ensure_ascii=False)
            yield f"data: {done_payload}\n\n"

        return StreamingResponse(
            iterate_in_threadpool(_supervised_stream()),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
        )

    # ── goal_based：并行执行 — 立即流式输出 + 后台调用工具 ──
    try:
        from systems.goal_based.agent_agentic import TravelPlanningAgent
        from systems.goal_based.agent_agentic import AGENT_SYSTEM_PROMPT
        from systems.goal_based.agent_agentic import _execute_search_web, _execute_query_knowledge
        import datetime as _dt_mod
        import threading, queue
        agent = TravelPlanningAgent(enable_knowledge=True, enable_web_search=True)
    except Exception as e:
        _err_msg = str(e)
        async def err_stream():
            yield f"data: {json.dumps({'error': _err_msg})}\n\n"
        return StreamingResponse(err_stream(), media_type="text/event-stream")

    def sync_event_gen():
        """同步生成器：立即开始流式输出，工具在后台并行执行"""
        try:
            tool_steps = []
            full_text = ""
            total_start = time.time()
            _city = meta.get("city", "")

            # 线程安全队列：后台工具结果推送进来
            tool_queue = queue.Queue()

            def _query_kb():
                if not agent.knowledge_client or not _city:
                    return
                try:
                    t0 = time.time()
                    res = _execute_query_knowledge(
                        {"city": _city, "query": f"{_city} 景点 餐饮 住宿 交通 实用贴士"},
                        agent.knowledge_client,
                    )
                    elapsed = round(time.time() - t0, 2)
                    if res and "不可用" not in res:
                        tool_queue.put({
                            "tool": "query_knowledge_base",
                            "args": {"city": _city, "query": "景点 餐饮 住宿 交通 实用贴士"},
                            "result_preview": res[:100],
                            "time_s": elapsed,
                        })
                except Exception as e:
                    logger.warning(f"后台知识库查询失败: {e}")

            def _search_web():
                if not agent.search_client or not _city:
                    return
                try:
                    t0 = time.time()
                    _cur_year = _dt_mod.datetime.now().year
                    res = agent.search_client.search(
                        f"{_city} 旅行攻略 {meta.get('days', 3)}天 景点 餐厅 {_cur_year}",
                        max_results=4
                    )
                    elapsed = round(time.time() - t0, 2)
                    if res:
                        _web_query = f"{_city} 旅行攻略 {meta.get('days', 3)}天 景点 餐厅"
                        tool_queue.put({
                            "tool": "search_web",
                            "args": {"query": _web_query, "topic": "general"},
                            "result_preview": (res.get("answer", "") or "")[:100],
                            "time_s": elapsed,
                        })
                except Exception as e:
                    logger.warning(f"后台网络搜索失败: {e}")

            # 启动后台线程
            kb_thread = threading.Thread(target=_query_kb, daemon=True)
            web_thread = threading.Thread(target=_search_web, daemon=True)
            kb_thread.start()
            web_thread.start()

            # ── 主线程：立即开始流式输出 ──
            messages = [
                {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ]

            # 先发送工具调用开始提示
            yield f"data: {json.dumps({'tool_start': True, 'city': _city}, ensure_ascii=False)}\n\n"

            stream = agent.client.chat.completions.create(
                model=agent.model_name,
                messages=messages,
                temperature=agent.temperature,
                max_tokens=agent.max_tokens,
                extra_body={"enable_thinking": False},
                stream=True,
            )

            # 流式输出 + 同时检查工具队列
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    full_text += delta
                    yield f"data: {json.dumps({'chunk': delta}, ensure_ascii=False)}\n\n"

                # 检查后台工具结果，逐字符注入到侧边栏
                while not tool_queue.empty():
                    step = tool_queue.get_nowait()
                    tool_steps.append(step)
                    # 逐字符展示工具结果（中文名称，无图标）
                    cn_name = '知识库查询' if step['tool'] == 'query_knowledge_base' else '联网搜索'
                    readable = f"{cn_name}: {step['args'].get('city', '') or step['args'].get('query', '')}\n"
                    for ch in readable:
                        yield f"data: {json.dumps({'tool_char': ch}, ensure_ascii=False)}\n\n"

            # 等待剩余工具完成（最多 10 秒）
            kb_thread.join(timeout=10)
            web_thread.join(timeout=10)
            while not tool_queue.empty():
                step = tool_queue.get_nowait()
                tool_steps.append(step)
                readable = f"{'📚' if step['tool'] == 'query_knowledge_base' else '🔍'} {step['tool']}: {step['args'].get('city', '') or step['args'].get('query', '')}\n"
                for ch in readable:
                    yield f"data: {json.dumps({'tool_char': ch}, ensure_ascii=False)}\n\n"

            processing_time = round(time.time() - total_start, 2)
            logger.info(f"智能体完成 (耗时: {processing_time}s, 后台工具: {len(tool_steps)}项)")

            yield f"data: {json.dumps({
                'done': True,
                'processing_time': processing_time,
                'tool_rounds': len(tool_steps),
                'cache_hit': False,
                'agent_steps': tool_steps,
            }, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"stream error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        iterate_in_threadpool(sync_event_gen()),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@app.post("/api/chat")
async def chat(message: ChatMessage):
    """自然语言对话接口"""
    if message.role != "user":
        return {"error": "仅支持 user 角色"}

    content = message.content

    # ── 解析关键参数，同时记录置信度 ────────────────────────────
    city_m = re.search(r"去(.{2,6}?)(?:玩|旅游|游玩|度假)", content)
    city_recognized = city_m is not None
    city = city_m.group(1).replace("一下", "").replace("一趟", "").strip() if city_m else "巴黎"

    # 未能识别目的地时给出明确提示，而非静默 fallback
    parse_warning: Optional[str] = None
    if not city_recognized:
        parse_warning = f"未能从输入中识别目的地，已默认使用「{city}」，如需更改请重新描述。"

    days_m = re.search(r"(\d+)\s*天", content)
    days = min(14, max(1, int(days_m.group(1)))) if days_m else 3

    budget_map = {"高|贵|奢|充裕|宽裕": "高", "低|省|便宜|节省": "低"}
    budget = next((v for pat, v in budget_map.items() if re.search(pat, content)), "中")

    interests = [k for k in ["文化", "美食", "购物", "历史", "自然", "夜生活", "户外运动"] if k in content]
    if not interests:
        interests = ["文化", "美食"]

    group_map = {"夫妻": "夫妻", "情侣": "情侣", "朋友": "朋友",
                 "家庭|家人|小孩|儿童": "家庭", "独自|单人|一个人": "单人"}
    group = next((v for pat, v in group_map.items() if re.search(pat, content)), "朋友")

    _CN_NUMS = {'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
    np_m = re.search(r"(\d+)\s*(?:人|位)", content)
    if np_m:
        num_people = int(np_m.group(1))
    else:
        cn_m = re.search(r"([一二两三四五六七八九十]+)\s*[个]?\s*人", content)
        num_people = _CN_NUMS.get(cn_m.group(1), 2) if cn_m else 2
    if group in ("情侣", "夫妻"):
        num_people = 2

    test_case = {
        "id": f"CHAT_{city}",
        "input": content,
        "metadata": {
            "city": city, "days": days, "budget": budget,
            "interests": interests, "group": group,
            "num_people": num_people, "special": "无",
            "travel_mode": "飞机", "origin": "",
        },
    }

    agent_type = message.agent_type or "goal_based"
    try:
        if agent_type == "rule_based":
            result = rule_based_generate(test_case); _stats["rule_based"] += 1
        elif agent_type == "supervised":
            result = supervised_generate(test_case); _stats["supervised"] += 1
        else:
            result = goal_based_generate(test_case, enable_knowledge=True, enable_web_search=True)
            _stats["goal_based"] += 1

        return {
            "role": "assistant",
            "content": _format_output(result, agent_type),
            "agent_type": agent_type,
            "processing_time": result.get("processing_time", 0),
            "city": city,
            "days": days,
            "budget": budget,
            "interests": interests,
            "group": group,
            # 解析置信度字段
            "city_recognized": city_recognized,
            "parse_warning": parse_warning,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"chat error: {e}", exc_info=True)
        raise _api_error(
            500, "CHAT_GENERATION_FAILED",
            "对话生成失败，请稍后重试",
            str(e),
        )


# ── 票务路由 ─────────────────────────────────────────────────────

@app.post("/api/booking/search")
async def booking_search(req: BookingSearchRequest):
    """搜索机票或火车票（所有用户相同权限，无区别对待）"""

    # ── 城市名校验：防止无效输入静默返回空列表 ───────────────────
    if req.origin not in KNOWN_CITIES:
        raise _api_error(
            400, "INVALID_CITY",
            f"出发城市「{req.origin}」暂不支持，请输入国内主要城市或常见国际目的地",
            f"origin={req.origin!r} not in KNOWN_CITIES",
        )
    if req.destination not in KNOWN_CITIES:
        raise _api_error(
            400, "INVALID_CITY",
            f"目的地「{req.destination}」暂不支持，请输入国内主要城市或常见国际目的地",
            f"destination={req.destination!r} not in KNOWN_CITIES",
        )
    if req.type not in ("flight", "train"):
        raise _api_error(
            400, "INVALID_TICKET_TYPE",
            "票务类型无效，请选择「flight」（机票）或「train」（火车票）",
            f"type={req.type!r}",
        )

    try:
        tickets = search_tickets(
            origin=req.origin,
            destination=req.destination,
            date=req.date,
            ticket_type=req.type,
            budget_hint=req.budget_hint,
        )
        web_sourced = False
        # 数据库无结果且为机票 → 联网搜索兜底
        if not tickets and req.type == "flight":
            tickets = await _search_flights_online(req.origin, req.destination, req.date)
            web_sourced = bool(tickets)
        return {"tickets": tickets, "count": len(tickets), "web_sourced": web_sourced}
    except HTTPException:
        raise
    except Exception as e:
        raise _api_error(
            500, "TICKET_SEARCH_FAILED",
            "票务搜索失败，请稍后重试",
            str(e),
        )


@app.post("/api/booking/create")
async def booking_create(req: BookingCreateRequest):
    """创建预订订单"""
    try:
        order = create_order(
            ticket_data=req.ticket_data,
            passenger_name=req.passenger_name,
            id_number=req.id_number or "",
        )
        _stats["bookings_created"] += 1
        return order
    except HTTPException:
        raise
    except Exception as e:
        raise _api_error(
            500, "ORDER_CREATION_FAILED",
            "预订失败，请检查信息后重试",
            str(e),
        )


@app.get("/api/booking/orders")
async def booking_orders(limit: int = 20, offset: int = 0):
    """获取订单列表（支持分页）"""
    all_orders = get_orders()
    total = len(all_orders)
    # 按创建时间倒序排列（最新订单在前）
    sorted_orders = sorted(all_orders, key=lambda o: o.get("created_at", ""), reverse=True)
    page_orders = sorted_orders[offset: offset + limit]
    return {
        "orders": page_orders,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total,
    }


@app.get("/api/booking/orders/{order_id}")
async def booking_order_detail(order_id: str):
    order = get_order(order_id)
    if not order:
        raise _api_error(404, "ORDER_NOT_FOUND", f"订单「{order_id}」不存在")
    return order


@app.delete("/api/booking/orders/{order_id}")
async def booking_cancel(order_id: str):
    order = cancel_order(order_id)
    if not order:
        raise _api_error(404, "ORDER_NOT_FOUND", f"订单「{order_id}」不存在")
    return order


# ── 通用路由 ─────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "version": "3.1.0",
        "uptime": round(time.time() - _stats["start_time"], 1),
        "stats": _stats,
    }

# 轻量心跳，供前端 30s 轮询（无 stats 开销）
@app.get("/api/health/ping")
async def health_ping():
    return {"status": "ok"}


@app.get("/api/agents")
async def agents():
    return {
        "agents": [
            {"id": "goal_based", "name": "联网规划", "desc": "LLM + 实时搜索，全球目的地，个性化程度最高", "time": "30–60s"},
            {"id": "supervised", "name": "智能推荐", "desc": "集成分类器，86.8% 准确率，<1ms 响应", "time": "<1ms"},
            {"id": "rule_based", "name": "经典规划", "desc": "专家规则库，25城市，完全确定性，完全可解释", "time": "<0.1ms"},
        ],
        "default": "goal_based",
    }


@app.get("/stats")
async def stats():
    return {**_stats, "uptime": round(time.time() - _stats["start_time"], 1)}


@app.get("/preview", response_class=HTMLResponse)
async def preview():
    f = os.path.join(os.path.dirname(__file__), "index.html")
    if not os.path.exists(f):
        raise _api_error(404, "FRONTEND_NOT_FOUND", "前端页面未找到")
    with open(f, encoding="utf-8") as fh:
        return fh.read()


@app.get("/ppt", response_class=HTMLResponse)
async def ppt_bg():
    f = os.path.join(os.path.dirname(__file__), "ppt_bg.html")
    if not os.path.exists(f):
        raise _api_error(404, "PPT_NOT_FOUND", "PPT背景页未找到")
    with open(f, encoding="utf-8") as fh:
        return fh.read()


@app.get("/")
async def root():
    return {"name": "云游 API", "version": "3.1.0", "ui": "/preview", "docs": "/docs"}


if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
