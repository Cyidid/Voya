"""
visualize_rule.py — 经典规划（RuleBasedEngine）可视化
生成 4 张图，直接来自 engine.py 的实际数据结构。
Run: python visualize_rule.py
Outputs: ./charts/ directory
"""
import os, sys, re
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.colors import LinearSegmentedColormap
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from systems.rule_based.engine import RULES, CITY_CLIMATE, INTEREST_PRIORITY, INTEREST_MAP

OUT = os.path.join(os.path.dirname(__file__), "charts")
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    "font.family":      ["PingFang SC","Heiti TC","Microsoft YaHei","SimHei","DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.dpi":       150,
})

CITIES = list(RULES.keys())          # 25 cities
INTEREST_CATS = ["culture","history","food","nature","shopping","nightlife"]
INTEREST_ZH   = ["文化", "历史", "美食", "自然", "购物", "夜生活"]
PALETTE = ["#4F6EF7","#7C3AED","#059669","#D97706","#DC2626","#0891B2"]

# Chart 1 · 景点库覆盖热力图
def chart_attraction_coverage():
    """cities × interest categories → attraction count"""
    matrix = np.zeros((len(CITIES), len(INTEREST_CATS)), dtype=int)
    for i, city in enumerate(CITIES):
        for j, cat in enumerate(INTEREST_CATS):
            atts = RULES[city]["attractions"].get(cat, [])
            matrix[i, j] = len(atts)

    fig, ax = plt.subplots(figsize=(8, 10))
    cmap = LinearSegmentedColormap.from_list("blue_purple", ["#EFF6FF","#93C5FD","#4F6EF7","#3730A3"])
    im = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0, vmax=matrix.max())

    for i in range(len(CITIES)):
        for j in range(len(INTEREST_CATS)):
            v = matrix[i, j]
            col = "white" if v >= 4 else "#1F2937"
            ax.text(j, i, str(v), ha="center", va="center", fontsize=9,
                    color=col, fontweight="bold")

    ax.set_xticks(range(len(INTEREST_CATS)))
    ax.set_xticklabels(INTEREST_ZH, fontsize=10)
    ax.set_yticks(range(len(CITIES)))
    ax.set_yticklabels(CITIES, fontsize=8.5)
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position("top")
    ax.set_title("景点规则库覆盖热力图\n25 城市 × 6 兴趣分类（数字=景点数量）",
                 fontsize=11, pad=14)

    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.ax.tick_params(labelsize=8)
    cbar.set_label("景点数量", fontsize=8, color="#6B7280")

    fig.tight_layout()
    path = os.path.join(OUT, "R1_attraction_coverage.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[R1] Attraction coverage → {path}")


# Chart 2 · 城市每日预算对比（低 / 中 / 高）
def chart_city_daily_budget():
    """Grouped horizontal bar chart: budget for each city at 3 levels."""
    cities = CITIES
    low_v  = [RULES[c]["daily_budget"]["低"] for c in cities]
    mid_v  = [RULES[c]["daily_budget"]["中"] for c in cities]
    high_v = [RULES[c]["daily_budget"]["高"] for c in cities]

    y = np.arange(len(cities))
    h = 0.25

    fig, ax = plt.subplots(figsize=(9, 10))
    ax.barh(y + h,   low_v,  height=h, label="低档", color="#10B981", alpha=0.85)
    ax.barh(y,       mid_v,  height=h, label="中档", color="#4F6EF7", alpha=0.85)
    ax.barh(y - h,   high_v, height=h, label="高档", color="#7C3AED", alpha=0.85)

    # value labels on high bars only
    for i, (city, hv) in enumerate(zip(cities, high_v)):
        ax.text(hv + 30, i - h, f"¥{hv:,}", va="center", ha="left", fontsize=7, color="#7C3AED")

    ax.set_yticks(y)
    ax.set_yticklabels(cities, fontsize=8.5)
    ax.set_xlabel("每日人均预算 (¥)", fontsize=9, color="#6B7280")
    ax.set_title("25 城市每日人均预算 · 经典规划规则库\n(低 / 中 / 高 三档对比)", fontsize=11, pad=10)
    ax.legend(fontsize=9, loc="lower right", framealpha=0.85)
    ax.spines[["top","right"]].set_visible(False)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"¥{int(x):,}"))
    ax.grid(axis="x", color="#E5E7EB", linewidth=0.5)

    fig.tight_layout()
    path = os.path.join(OUT, "R2_city_daily_budget.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[R2] City daily budget → {path}")


# Chart 3 · 气候适游评分矩阵
def chart_climate_score():
    """
    Parse CITY_CLIMATE text for season quality signals.
    +2 keywords (最佳/旺季/宜人/舒适) → good
    -2 keywords (极热/严寒/风浪/高温/暴雨) → bad
    Result: −2 .. +2 score per city × season
    """
    GOOD = ["最佳", "旺季", "宜人", "舒适", "温暖", "晴朗", "明媚", "温和"]
    BAD  = ["极热", "严寒", "风浪", "暴雨", "高温", "阴冷", "寒冷", "雨季", "潮湿"]
    seasons = ["spring","summer","autumn","winter"]
    season_zh = ["春", "夏", "秋", "冬"]

    cities_c = [c for c in CITIES if c in CITY_CLIMATE]
    matrix   = np.zeros((len(cities_c), 4))

    for i, city in enumerate(cities_c):
        for j, s in enumerate(seasons):
            desc = CITY_CLIMATE[city].get(s, "")
            score = sum(1 for kw in GOOD if kw in desc) - sum(1 for kw in BAD if kw in desc)
            matrix[i, j] = max(-2, min(2, score))

    fig, ax = plt.subplots(figsize=(5, 10))
    cmap = LinearSegmentedColormap.from_list("rg", ["#DC2626","#FCA5A5","#FEF9C3","#86EFAC","#059669"])
    im = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=-2, vmax=2)

    labels = {-2:"差", -1:"一般", 0:"可以", 1:"好", 2:"最佳"}
    for i in range(len(cities_c)):
        for j in range(4):
            v = int(round(matrix[i, j]))
            col = "white" if abs(v) == 2 else "#1F2937"
            ax.text(j, i, labels.get(v, ""), ha="center", va="center",
                    fontsize=8.5, color=col, fontweight="bold")

    ax.set_xticks(range(4))
    ax.set_xticklabels(season_zh, fontsize=11)
    ax.set_yticks(range(len(cities_c)))
    ax.set_yticklabels(cities_c, fontsize=8.5)
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position("top")
    ax.set_title("25 城市四季适游评分\n(基于 CITY_CLIMATE 关键词自动评分)",
                 fontsize=10, pad=14)

    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02,
                        ticks=[-2,-1,0,1,2])
    cbar.ax.set_yticklabels(["差","一般","可以","好","最佳"], fontsize=8)
    cbar.set_label("适游程度", fontsize=8, color="#6B7280")

    fig.tight_layout()
    path = os.path.join(OUT, "R3_climate_score.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[R3] Climate score → {path}")


# Chart 4 · 兴趣优先级 & 覆盖率
def chart_interest_stats():
    """
    Left: bar of INTEREST_PRIORITY (hardcoded engine order).
    Right: total attractions per category across all 25 cities.
    """
    cats    = list(INTEREST_PRIORITY.keys())     # culture, history, food, nature, shopping, nightlife
    prios   = [INTEREST_PRIORITY[c] for c in cats]
    cats_zh = [INTEREST_ZH[INTEREST_CATS.index(c)] for c in cats]

    totals = []
    for cat in cats:
        t = sum(len(RULES[city]["attractions"].get(cat, [])) for city in CITIES)
        totals.append(t)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    # Left: priority (lower number = higher priority → invert bar)
    ax = axes[0]
    inv_prio = [max(prios) + 1 - p for p in prios]   # invert so priority 1 is tallest
    colours = [PALETTE[i] for i in range(len(cats))]
    bars = ax.bar(cats_zh, inv_prio, color=colours, width=0.6, zorder=3)
    for bar, p in zip(bars, prios):
        ax.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + 0.05,
                f"优先级 {p}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_ylim(0, max(inv_prio) * 1.2)
    ax.set_ylabel("优先权重（越高越优先）", fontsize=9, color="#6B7280")
    ax.set_title("行程规划兴趣优先级\n(INTEREST_PRIORITY 固定顺序)", fontsize=10, pad=8)
    ax.spines[["top","right"]].set_visible(False)
    ax.grid(axis="y", color="#E5E7EB", linewidth=0.5, zorder=0)
    ax.set_yticks([])

    # Right: total attraction count per category
    ax2 = axes[1]
    bars2 = ax2.bar(cats_zh, totals, color=colours, width=0.6, zorder=3)
    for bar, t in zip(bars2, totals):
        ax2.text(bar.get_x() + bar.get_width()/2, t + 1,
                 str(t), ha="center", va="bottom", fontsize=9.5, fontweight="bold")
    ax2.set_ylim(0, max(totals) * 1.15)
    ax2.set_ylabel("全库景点总数（25城合计）", fontsize=9, color="#6B7280")
    ax2.set_title("各兴趣分类景点总量\n(RULES 规则库统计)", fontsize=10, pad=8)
    ax2.spines[["top","right"]].set_visible(False)
    ax2.grid(axis="y", color="#E5E7EB", linewidth=0.5, zorder=0)

    fig.suptitle("经典规划 · 兴趣分类统计", fontsize=12, y=1.02)
    fig.tight_layout()
    path = os.path.join(OUT, "R4_interest_stats.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[R4] Interest stats → {path}")


if __name__ == "__main__":
    chart_attraction_coverage()
    chart_city_daily_budget()
    chart_climate_score()
    chart_interest_stats()
    print(f"\n✓ 4 charts saved to {OUT}/")
    print("  R1_attraction_coverage.png")
    print("  R2_city_daily_budget.png")
    print("  R3_climate_score.png")
    print("  R4_interest_stats.png")
