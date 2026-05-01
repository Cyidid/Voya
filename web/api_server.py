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

# 日志
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

# 导入三大系统
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

# 导入票务引擎
from systems.booking.booking_engine import (
    search_tickets, create_order, get_orders, get_order, cancel_order,
    DOMESTIC_CITIES, INTL_HUB,
)

#  Tavily 联网搜索（票务兜底）──────────────────────────────────────
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

# 统计
_stats = {
    "total": 0, "success": 0, "failed": 0,
    "rule_based": 0, "supervised": 0, "goal_based": 0,
    "bookings_created": 0, "start_time": time.time(),
}


# 结构化错误响应助手
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

#  静态文件（CSS/JS）─────────────────────────────────────
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


# 格式化输出
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
_LUNCH_HINTS_EN = [
    "Find a local spot away from tourist areas — usually better value and more authentic.",
    "Street food stalls are the best way to experience the local food culture.",
    "Head to a nearby market or food hall for freshly made dishes and great variety.",
    "A quality café in this area makes for a relaxing lunch with local atmosphere.",
    "Lunch sets are often 30% cheaper than evening menus — a smart traveller's choice.",
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
_CATEGORY_LABELS_EN: dict[str, tuple[str, str]] = {
    "culture":   ("Cultural Experience", "Dive into local arts and heritage"),
    "history":   ("Historical Exploration", "Travel through time and rich history"),
    "nature":    ("Nature & Outdoors", "Breathe fresh air and embrace natural beauty"),
    "food":      ("Food Discovery", "Savour authentic local flavours"),
    "shopping":  ("Shopping & Leisure", "Explore boutiques and local markets"),
    "nightlife": ("Nightlife", "Experience the city's vibrant after-dark scene"),
    "morning":   ("Morning Activity", "Start the day with energy"),
    "afternoon": ("Afternoon Activity", "Continue exploring at your own pace"),
    "evening":   ("Evening Activity", "A perfect ending to a great day"),
}

_BUDGET_LABEL  = {"低": "经济实惠", "中": "舒适中档", "高": "高端奢华"}
_BUDGET_DAILY  = {"低": "¥200–400 / 人·天", "中": "¥600–1,000 / 人·天", "高": "¥2,000+ / 人·天"}
_BUDGET_HOTEL  = {"低": "青旅 / 经济连锁酒店", "中": "三星 / 舒适型酒店", "高": "五星级 / 精品度假酒店"}
_BUDGET_FOOD   = {"低": "街头小吃 / 平价餐馆", "中": "特色餐厅 / 本地料理", "高": "米其林 / 高级景观餐厅"}
_BUDGET_TICKET = {"低": "优先免费景点", "中": "主要景点标准票", "高": "私人导览 / 深度体验"}

_BUDGET_LABEL_EN  = {"低": "Budget-Friendly", "中": "Comfortable Mid-Range", "高": "Luxury"}
_BUDGET_DAILY_EN  = {"低": "¥200–400 / person·day", "中": "¥600–1,000 / person·day", "高": "¥2,000+ / person·day"}
_BUDGET_HOTEL_EN  = {"低": "Hostel / Budget Chain Hotel", "中": "3-star / Comfort Hotel", "高": "5-star / Boutique Resort"}
_BUDGET_FOOD_EN   = {"低": "Street Food / Local Diners", "中": "Local Restaurants / Specialty Cuisine", "高": "Michelin / Fine Dining"}
_BUDGET_TICKET_EN = {"低": "Free Attractions Priority", "中": "Standard Admission Tickets", "高": "Private Tours / VIP Experiences"}

_GROUP_TRIP = {
    "情侣": "情侣浪漫游", "夫妻": "情侣浪漫游",
    "家庭": "亲子家庭游", "朋友": "好友结伴游",
    "同事": "团队社交游", "独自": "独旅探索游",
}
_GROUP_TRIP_EN = {
    "情侣": "Romantic Couple's Trip", "夫妻": "Romantic Couple's Trip",
    "家庭": "Family Adventure", "朋友": "Friends Getaway",
    "同事": "Team Outing", "独自": "Solo Exploration",
    "单人": "Solo Exploration",
}
_INTEREST_TRIP = {
    "文化": "文化深度游", "美食": "美食探索游", "历史": "历史文化游",
    "自然": "自然探索游", "购物": "购物休闲游", "夜生活": "夜游体验",
}
_INTEREST_TRIP_EN = {
    "文化": "Cultural Immersion", "美食": "Food Explorer's Journey", "历史": "Historical Tour",
    "自然": "Nature Discovery", "购物": "Shopping & Leisure", "夜生活": "Nightlife Experience",
}


def _format_output(result: dict, agent_type: str, lang: str = "zh") -> str:
    en = (lang == "en")

    if agent_type == "goal_based":
        return (result.get("output") or result.get("itinerary")
                or ("Unable to generate itinerary. Please try again." if en
                    else "无法生成行程，请稍后重试。"))

    itinerary = result.get("itinerary", {})
    if not itinerary:
        return ("Unable to generate itinerary. Please check your inputs." if en
                else "无法生成行程，请检查输入信息。")
    if isinstance(itinerary, str):
        return itinerary   # rule_based: already fully rendered Markdown (bilingual via engine)

    meta     = result.get("metadata", {})
    city     = meta.get("city", "Destination" if en else "目的地")
    days     = meta.get("days", len(itinerary))
    budget   = meta.get("budget", "中")
    group    = meta.get("group", "")
    num_p    = meta.get("num_people", 2)
    mode     = meta.get("travel_mode", "飞机")
    special  = meta.get("special", "无")
    interests = meta.get("interests", [])
    origin   = meta.get("origin", "")

    # 出行类型标签
    if en:
        rec_label = result.get("recommendation_type_zh", "")  # still used as key
        rec_display = (_GROUP_TRIP_EN.get(group, "")
                       or _INTEREST_TRIP_EN.get(interests[0] if interests else "", "Sightseeing Tour"))
    else:
        rec_zh = result.get("recommendation_type_zh", "")
        if not rec_zh:
            rec_zh = _GROUP_TRIP.get(group, "") or _INTEREST_TRIP.get(interests[0] if interests else "", "精彩观光游")
        rec_display = rec_zh

    # transport / tips — prefer EN variants when available
    if en:
        transport_tip = result.get("transport_tip_en") or result.get("transport_tip", "")
        city_tips     = result.get("city_tips_en")     or result.get("city_tips", [])
    else:
        transport_tip = result.get("transport_tip", "")
        city_tips     = result.get("city_tips", [])

    total_budget  = result.get("total_budget_estimate", 0)
    daily_avg     = total_budget // days if days else total_budget

    # label lookups
    cat_map   = _CATEGORY_LABELS_EN if en else _CATEGORY_LABELS
    bud_label = _BUDGET_LABEL_EN    if en else _BUDGET_LABEL
    bud_hotel = _BUDGET_HOTEL_EN    if en else _BUDGET_HOTEL
    bud_food  = _BUDGET_FOOD_EN     if en else _BUDGET_FOOD
    bud_tick  = _BUDGET_TICKET_EN   if en else _BUDGET_TICKET
    bud_daily = _BUDGET_DAILY_EN    if en else _BUDGET_DAILY
    lunch_pool = _LUNCH_HINTS_EN    if en else _LUNCH_HINTS

    lines: list[str] = []

    # 标题
    if en:
        lines.append(f"# {city} · {days}-Day {rec_display}\n")
    else:
        lines.append(f"# {city} · {days} 日{rec_display}\n")

    # 概览
    if en:
        lines.append("## Trip Overview\n")
        origin_str  = f"Departing from **{origin}** · " if origin else ""
        special_str = f" · Special needs: {special}" if special and special not in ("无", "None", "") else ""
        lines.append(f"{origin_str}**{num_p} people** · Transport: {mode} · Budget: {bud_label.get(budget, budget)}{special_str}\n")
    else:
        lines.append("## 行程概览\n")
        origin_str  = f"从 **{origin}** 出发 · " if origin else ""
        special_str = f" · 特别需求：{special}" if special and special != "无" else ""
        lines.append(f"{origin_str}**{num_p} 人** · 出行方式：{mode} · 预算：{bud_label.get(budget, budget)}{special_str}\n")

    if agent_type == "supervised":
        confidence = result.get("model_confidence", 0)
        model_type = result.get("model_type", "VotingClassifier")
        if en:
            lines.append(f"> Model recommendation: **{rec_display}** (confidence {confidence:.0%})  ·  Model: {model_type}\n")
        else:
            lines.append(f"> 模型推荐类型：**{rec_display}**（置信度 {confidence:.0%}）  ·  模型：{model_type}\n")

    lines.append("---\n")

    # 每日行程
    for day_key in sorted(itinerary.keys()):
        day_data = itinerary[day_key]
        day_num  = day_key.replace("day_", "")
        default_theme = (f"{city} Exploration Day {day_num}" if en else f"{city}探索 Day {day_num}")
        theme    = day_data.get("theme", default_theme)

        if en:
            lines.append(f"## Day {day_num}: {theme}\n")
        else:
            lines.append(f"## 第 {day_num} 天：{theme}\n")

        try:
            day_num_int = int(day_num)
        except ValueError:
            day_num_int = 1

        # 上午 / Morning
        morning = day_data.get("morning")
        if morning:
            act      = morning.get("activity", "")
            cost     = morning.get("cost_estimate", 0)
            duration = morning.get("duration", 3)
            cat      = morning.get("category", "culture")
            cat_label, cat_desc = cat_map.get(cat, (("Morning Activity", "Explore local highlights") if en else ("上午活动", "探索当地精华")))
            if en:
                cost_str = f", est. ¥{cost}" if cost else ", free admission"
                lines.append(f"**Morning · {cat_label}**")
                lines.append(f"**{act}** — {cat_desc}. Recommended {duration} hrs{cost_str}.\n")
            else:
                cost_str = f"，参考费用约 ¥{cost}" if cost else "，免费开放"
                lines.append(f"**上午 · {cat_label}**")
                lines.append(f"**{act}** — {cat_desc}。建议游览约 {duration} 小时{cost_str}。\n")

        # 午餐 / Lunch
        lunch_hint = lunch_pool[(day_num_int - 1) % len(lunch_pool)]
        if en:
            food_type = bud_food.get(budget, "Local Specialty Restaurant")
            lines.append("**Lunch Suggestion**")
            lines.append(f"Recommended: **{food_type}** nearby. {lunch_hint}\n")
        else:
            food_type = bud_food.get(budget, "当地特色餐厅")
            lines.append("**午餐推荐**")
            lines.append(f"推荐就近选择 **{food_type}**。{lunch_hint}\n")

        # 下午 / Afternoon
        afternoon = day_data.get("afternoon")
        if afternoon:
            act      = afternoon.get("activity", "")
            cost     = afternoon.get("cost_estimate", 0)
            duration = afternoon.get("duration", 3)
            cat      = afternoon.get("category", "culture")
            cat_label, cat_desc = cat_map.get(cat, (("Afternoon Activity", "Continue the journey") if en else ("下午活动", "续写旅途故事")))
            if en:
                cost_str = f", est. ¥{cost}" if cost else ", free admission"
                lines.append(f"**Afternoon · {cat_label}**")
                lines.append(f"**{act}** — {cat_desc}. Recommended {duration} hrs{cost_str}.\n")
            else:
                cost_str = f"，参考费用约 ¥{cost}" if cost else "，免费开放"
                lines.append(f"**下午 · {cat_label}**")
                lines.append(f"**{act}** — {cat_desc}。建议游览约 {duration} 小时{cost_str}。\n")

        # 晚餐 / Dinner
        evening = day_data.get("evening")
        if evening:
            act  = evening.get("activity", "")
            cost = evening.get("cost_estimate", 0)
            if en:
                food_desc = {"低": "great value, local vibe", "中": "distinctive flavours, good quality", "高": "refined dining, worth every penny"}.get(budget, "")
                cost_str  = f", est. ¥{cost} per person" if cost else ""
                lines.append("**Dinner**")
                lines.append(f"**{act}** — {food_desc}{cost_str}. Perfect end to a great day.\n")
            else:
                food_desc = {"低": "经济实惠、接地气", "中": "特色鲜明、性价比高", "高": "精致讲究、值得一试"}.get(budget, "")
                cost_str  = f"，人均约 ¥{cost}" if cost else ""
                lines.append("**晚餐**")
                lines.append(f"**{act}** — {food_desc}{cost_str}。结束愉快的一天。\n")

        # 第一天附上交通提示
        if transport_tip and day_key == "day_1":
            label = "🚇 Getting Around" if en else "🚇 交通贴士"
            lines.append(f"> {label}: {transport_tip}\n")

        lines.append("---\n")

    # 住宿
    if en:
        lines.append("## Accommodation\n")
        lines.append(f"Recommended: **{bud_hotel.get(budget, 'Comfortable Hotel')}**. Prioritise locations near major attractions or city centre to save travel time.\n")
    else:
        lines.append("## 住宿建议\n")
        lines.append(f"推荐选择 **{bud_hotel.get(budget, '舒适型酒店')}**，优先考虑靠近主要景点或市中心的位置，节省通勤时间，行程更从容。\n")

    # 交通
    if transport_tip:
        lines.append("## Getting Around\n" if en else "## 交通建议\n")
        lines.append(f"{transport_tip}\n")

    # 当地贴士
    if city_tips:
        lines.append("## Local Tips\n" if en else "## 当地贴士\n")
        for tip in city_tips:
            lines.append(f"- {tip}")
        lines.append("")

    # 预算
    if en:
        lines.append("## Budget Reference\n")
        lines.append("| Item | Estimate (CNY) |")
        lines.append("|------|---------------|")
        lines.append(f"| Daily activities & admission | ~¥{daily_avg} / day |")
        lines.append(f"| Accommodation ({days} nights) | {bud_hotel.get(budget, 'See above')} |")
        lines.append(f"| Dining standard | {bud_food.get(budget, 'See above')} |")
        lines.append(f"| Attraction tickets | {bud_tick.get(budget, 'See above')} |")
        lines.append(f"| **Total ({days} days)** | **~¥{total_budget}** (excl. international transport) |")
        lines.append("")
        lines.append(f"> Reference spend: {bud_daily.get(budget, '')}. Actual costs vary by personal choices and local prices.\n")
    else:
        lines.append("## 预算参考\n")
        lines.append("| 费用项目 | 预估（人民币）|")
        lines.append("|---------|------------|")
        lines.append(f"| 每日活动 & 门票 | 约 ¥{daily_avg} / 天 |")
        lines.append(f"| 住宿（{days} 晚）| {bud_hotel.get(budget, '按实际')} |")
        lines.append(f"| 餐饮标准 | {bud_food.get(budget, '按实际')} |")
        lines.append(f"| 景点门票 | {bud_tick.get(budget, '按实际')} |")
        lines.append(f"| **行程合计（{days} 天）** | **约 ¥{total_budget}**（不含国际交通）|")
        lines.append("")
        lines.append(f"> 参考消费水平：{bud_daily.get(budget, '')}，实际费用因个人选择与当地物价而异。\n")

    # 货币换算
    cur = _CITY_CURRENCY.get(city)
    if cur:
        code, name, rate = cur
        if code != "CNY":
            daily_local = round(daily_avg / rate)
            if en:
                lines.append("## Currency\n")
                lines.append(f"Local currency: **{name} ({code})**")
                lines.append(f"Reference rate: **1 {code} ≈ ¥{rate:.3g} CNY**")
                lines.append(f"(Daily activity reference: ~{daily_local:,} {code} / person·day)\n")
                lines.append("> Rates fluctuate — check with your bank before departure and consider a no-fee travel card.\n")
            else:
                lines.append("## 货币参考\n")
                lines.append(f"当地通用货币：**{name}（{code}）**")
                lines.append(f"当前参考汇率：**1 {code} ≈ ¥{rate:.3g} 人民币**")
                lines.append(f"（每日活动参考：约 {daily_local:,} {code} / 人·天）\n")
                lines.append("> 汇率随市场波动，实际以出行时银行/兑换网点为准，建议提前适量兑换或使用境外免手续费银行卡。\n")

    # 系统说明
    if agent_type == "supervised":
        top = result.get("top_features", [])
        if top:
            sep = ", "
            top_str = sep.join(f[0] if isinstance(f, (list, tuple)) else str(f) for f in top[:3])
            if en:
                lines.append(f"> *Itinerary generated by supervised ML model ({result.get('model_type', 'VotingClassifier')}). Key decision features: {top_str}.*\n")
            else:
                lines.append(f"> *本行程由监督学习模型（{result.get('model_type', 'VotingClassifier')}）生成，关键决策特征：{top_str}。*\n")
    elif agent_type == "rule_based":
        if en:
            lines.append("> *Itinerary generated by the expert rule engine. Every recommendation traces back to a specific rule — fully transparent and deterministic.*\n")
        else:
            lines.append("> *本行程由专家规则库生成，每条推荐均可追溯至规则库具体条目，决策完全透明可解释。*\n")

    return "\n".join(lines)


# 数据模型
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
    language: Optional[str] = "zh"   # "zh" | "en"


class ChatMessage(BaseModel):
    role: str
    content: str
    agent_type: Optional[str] = "goal_based"
    language: Optional[str] = "zh"


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


# 行程生成路由
@app.post("/api/generate")
async def generate_itinerary(req: TravelRequest):
    """生成旅行行程（三种 AI 系统可选）"""
    # 公平性：情侣/夫妻人数归一为 2；其余保持用户输入
    num_people = 2 if req.group in ("情侣", "夫妻") else (req.num_people or 2)
    _lang = req.language or "zh"

    origin_prefix = f"从{req.origin}出发，" if req.origin else ""
    if _lang == "en":
        _origin_en = f"Departing from {req.origin} by {req.travel_mode or 'plane'}, " if req.origin else ""
        _special_en = f", special requirement: {req.special}" if req.special and req.special not in ("无", "None", "") else ""
        _input_str = (
            f"{_origin_en}{num_people} people, planning a {req.days}-day trip to {req.city}, "
            f"traveling as {req.group}, "
            f"interests: {', '.join(req.interests) or 'sightseeing'}, budget: {req.budget}"
            f"{_special_en}. Please write the entire itinerary in English."
        )
    else:
        _input_str = (
            f"{origin_prefix}乘{req.travel_mode or '飞机'}，共{num_people}人，"
            f"我想去{req.city}玩{req.days}天，和{req.group}一起，"
            f"喜欢{'、'.join(req.interests) or '观光'}，预算{req.budget}"
            f"{'，' + req.special if req.special and req.special != '无' else ''}。"
        )
    test_case = {
        "id": f"WEB_{req.city}",
        "input": _input_str,
        "metadata": {
            "city": req.city, "days": req.days, "budget": req.budget,
            "interests": req.interests, "group": req.group,
            "special": req.special, "origin": req.origin or "",
            "num_people": num_people, "travel_mode": req.travel_mode or "飞机",
            "start_date": req.start_date or "", "language": _lang,
        },
    }

    try:
        if req.agent_type == "rule_based":
            result = rule_based_generate(test_case)
            _stats["rule_based"] += 1
            if result.get("coverage_gap"):
                raise _api_error(
                    400, "CITY_NOT_SUPPORTED",
                    f"「{req.city}」不在经典规划支持的 25 个城市内，请切换到「实时规划」以生成任意城市行程。",
                )
        elif req.agent_type == "supervised":
            result = supervised_generate(test_case)
            _stats["supervised"] += 1
        else:
            result = goal_based_generate(test_case, enable_knowledge=True, enable_web_search=True)
            _stats["goal_based"] += 1

        formatted = _format_output(result, req.agent_type, _lang)
        meta = result.get("metadata", test_case["metadata"])

        #  公共字段（所有 agent 均返回）───────────────────────────
        resp: dict = {
            "itinerary": formatted,
            "agent_type": req.agent_type,
            "processing_time": result.get("processing_time", 0),
            "token_estimate": result.get("token_estimate", len(formatted) // 2),
            "metadata": meta,
        }

        #  Agent 专属字段（按类型精简，减少无关字段传输）──────────
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
    SSE 流式接口（三种系统均支持）。
    每行格式：data: <JSON>\\n\\n
      - 文本块：      {"chunk": "..."}
      - 工具日志字符：{"tool_char": "..."}
      - 完成(goal):  {"done": true, "processing_time": X, "tool_rounds": N, "cache_hit": false, "agent_steps": [...]}
      - 完成(rule):  {"done": true, "itinerary": "...", "processing_time": X, "tool_rounds": 0, "cache_hit": false, "result_meta": {...}}
      - 完成(sup):   {"done": true, "processing_time": X, "tool_rounds": 0, "cache_hit": false, "result_meta": {...}}
      - 错误：        {"error": "..."}
    rule_based 毫秒响应，直接一次性返回 done（含 itinerary）；
    supervised 逐行流式（每3行一chunk，10ms延迟）；
    goal_based 真正流式，同时后台并行执行工具调用。
    """
    num_people = 2 if req.group in ("情侣", "夫妻") else (req.num_people or 2)
    _lang = req.language or "zh"
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

    if _lang == "en":
        _origin_en = f"Departing from {req.origin} by {req.travel_mode or 'plane'}, " if req.origin else ""
        _date_en = ""
        if _dep_date:
            _date_en = f", departure date {_dep_date}"
            if _ret_date:
                _date_en += f", return date {_ret_date}"
        _special_en = f", special requirement: {req.special}" if req.special and req.special not in ("无", "None", "") else ""
        user_input = (
            f"{_origin_en}{num_people} people, planning a {req.days}-day trip to {req.city}, "
            f"traveling as {req.group}, "
            f"interests: {', '.join(req.interests) or 'sightseeing'}, budget: {req.budget}"
            f"{_special_en}{_date_en}."
            f" Please write the entire itinerary in English."
        )
    else:
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
        "start_date": req.start_date or "", "language": _lang,
    }
    test_case = {"id": f"WEB_{req.city}", "input": user_input, "metadata": meta}

    # 非流式系统
    if req.agent_type != "goal_based":
        try:
            if req.agent_type == "rule_based":
                result = rule_based_generate(test_case)
                if result.get("coverage_gap"):
                    async def _city_err():
                        yield f"data: {json.dumps({'error': f'「{req.city}」不在经典规划支持的 25 个城市内，请切换到「实时规划」以生成任意城市行程。'}, ensure_ascii=False)}\n\n"
                    return StreamingResponse(_city_err(), media_type="text/event-stream",
                                             headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})
            else:
                result = supervised_generate(test_case)
            formatted = _format_output(result, req.agent_type, _lang)
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

    # goal_based：并行执行 — 立即流式输出 + 后台调用工具
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

            # 主线程：立即开始流式输出
            _sys_prompt = AGENT_SYSTEM_PROMPT
            if _lang == "en":
                _sys_prompt += (
                    "\n\nCRITICAL LANGUAGE REQUIREMENT: The user interface is in English. "
                    "You MUST write the ENTIRE itinerary — every day, every activity, every tip, "
                    "every section heading — in English only. Do NOT use any Chinese characters."
                )
            messages = [
                {"role": "system", "content": _sys_prompt},
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
                    if _lang == "en":
                        tool_label = 'Knowledge Base' if step['tool'] == 'query_knowledge_base' else 'Web Search'
                    else:
                        tool_label = '知识库查询' if step['tool'] == 'query_knowledge_base' else '联网搜索'
                    readable = f"{tool_label}: {step['args'].get('city', '') or step['args'].get('query', '')}\n"
                    for ch in readable:
                        yield f"data: {json.dumps({'tool_char': ch}, ensure_ascii=False)}\n\n"

            # 等待剩余工具完成（最多 10 秒）
            kb_thread.join(timeout=10)
            web_thread.join(timeout=10)
            while not tool_queue.empty():
                step = tool_queue.get_nowait()
                tool_steps.append(step)
                if _lang == "en":
                    tool_label = 'Knowledge Base' if step['tool'] == 'query_knowledge_base' else 'Web Search'
                else:
                    tool_label = '知识库查询' if step['tool'] == 'query_knowledge_base' else '联网搜索'
                readable = f"{tool_label}: {step['args'].get('city', '') or step['args'].get('query', '')}\n"
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

    # 解析关键参数，同时记录置信度
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
            "language": message.language or "zh",
        },
    }

    agent_type = message.agent_type or "goal_based"
    try:
        if agent_type == "rule_based":
            result = rule_based_generate(test_case)
            _stats["rule_based"] += 1
            if result.get("coverage_gap"):
                raise _api_error(
                    400, "CITY_NOT_SUPPORTED",
                    f"「{city}」不在经典规划支持的 25 个城市内，请切换到「实时规划」以生成任意城市行程。",
                )
        elif agent_type == "supervised":
            result = supervised_generate(test_case); _stats["supervised"] += 1
        else:
            result = goal_based_generate(test_case, enable_knowledge=True, enable_web_search=True)
            _stats["goal_based"] += 1

        return {
            "role": "assistant",
            "content": _format_output(result, agent_type, message.language or "zh"),
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


# 票务路由
@app.post("/api/booking/search")
async def booking_search(req: BookingSearchRequest):
    """搜索机票或火车票（所有用户相同权限，无区别对待）"""

    # 城市名校验：防止无效输入静默返回空列表
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


# 通用路由
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
            {"id": "supervised", "name": "智能推荐", "desc": "集成分类器，84.5% 准确率，<1ms 响应", "time": "<1ms"},
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
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/preview")


if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
