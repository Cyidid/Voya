"""
visualize_goal.py — 实时规划（GoalBasedAgent）可视化
生成 4 张图，来自 agent_agentic.py 的实际结构和提示词逻辑。
Run: python visualize_goal.py
Outputs: ../rule_based/charts/ (与其他图统一目录)
"""
import os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import warnings
warnings.filterwarnings("ignore")

OUT = os.path.join(os.path.dirname(__file__), "..", "rule_based", "charts")
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    "font.family":      ["PingFang SC","Heiti TC","Microsoft YaHei","SimHei","DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.dpi":       150,
})

# ── constants from agent_agentic.py ──────────────────────────────────────────
KB_CITIES = [
    "巴黎","东京","纽约","伦敦","罗马","悉尼","巴塞罗那","曼谷",
    "新加坡","首尔","迪拜","阿姆斯特丹","维也纳","布拉格","普吉岛",
    "马尔代夫","伊斯坦布尔","里斯本","巴厘岛","大阪","京都","广州"
]
MAX_TOOL_ROUNDS  = 3
TOOLS = ["query_knowledge_base", "search_web"]

# 4维规划框架（来自系统提示词）
DIMENSIONS = {
    "天气维度":   {"score": 5, "subs": ["当月气候", "高温/严寒处理", "雨天备选", "穿衣建议"]},
    "人员维度":   {"score": 5, "subs": ["有儿童", "有老人", "情侣/夫妻", "单人", "大团队"]},
    "兴趣维度":   {"score": 4, "subs": ["自然/户外", "人文/历史", "购物", "美食/夜生活"]},
    "实用信息":   {"score": 4, "subs": ["开放时间", "预约建议", "门票信息", "节庆活动"]},
}

PALETTE = ["#4F6EF7","#7C3AED","#059669","#D97706","#DC2626","#0891B2"]

# ─── Chart G1 · Agent 工具调用决策流程 ────────────────────────────────────────
def chart_agent_flow():
    """Flowchart showing the agent's tool-calling decision process."""
    fig, ax = plt.subplots(figsize=(9, 6.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8)
    ax.axis("off")

    def box(ax, x, y, w, h, text, color="#4F6EF7", text_color="white", fontsize=9.5, radius=0.25):
        bbox = FancyBboxPatch((x - w/2, y - h/2), w, h,
                              boxstyle=f"round,pad=0.1,rounding_size={radius}",
                              facecolor=color, edgecolor="white", linewidth=1.5, zorder=3)
        ax.add_patch(bbox)
        ax.text(x, y, text, ha="center", va="center", fontsize=fontsize,
                color=text_color, fontweight="bold", zorder=4,
                wrap=True, multialignment="center")

    def arrow(ax, x1, y1, x2, y2, label="", color="#6B7280"):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=1.5),
                    zorder=2)
        if label:
            mx, my = (x1+x2)/2, (y1+y2)/2
            ax.text(mx + 0.15, my, label, fontsize=8, color=color, va="center")

    # nodes
    box(ax, 5, 7.2, 3.0, 0.7, "用户输入旅行请求", "#1E293B")

    box(ax, 5, 6.0, 3.0, 0.7, "目的地在知识库中？\n(22个城市已覆盖)", "#0891B2", fontsize=9)

    box(ax, 2.5, 4.7, 2.8, 0.7, "query_knowledge_base\n本地知识库检索", "#059669", fontsize=9)
    box(ax, 7.5, 4.7, 2.2, 0.7, "search_web\n联网实时搜索", "#D97706", fontsize=9)

    box(ax, 5, 3.5, 3.5, 0.7, "信息是否充分？\n(最多 3 轮工具调用)", "#0891B2", fontsize=9)

    box(ax, 2.5, 2.3, 2.5, 0.65, "再次调用工具\n(补充细节)", "#6B7280", fontsize=9)

    box(ax, 5, 1.1, 3.8, 0.75, "Qwen 大模型生成\nMarkdown 行程", "#7C3AED", fontsize=9.5)

    # arrows
    arrow(ax, 5, 6.85, 5, 6.35)
    arrow(ax, 3.8, 5.65, 2.9, 5.05, "是")
    arrow(ax, 6.2, 5.65, 7.2, 5.05, "否")
    arrow(ax, 2.5, 4.35, 3.5, 3.85)
    arrow(ax, 7.5, 4.35, 6.5, 3.85)
    arrow(ax, 3.8, 3.15, 2.5, 2.63, "不足 & 轮次<3")
    arrow(ax, 2.5, 1.98, 3.5, 1.48)
    arrow(ax, 5, 3.15, 5, 1.48, "充分")

    # annotation: max rounds
    ax.text(0.4, 2.3, "最多\n3轮", fontsize=8, color="#6B7280", ha="center",
            style="italic")
    ax.annotate("", xy=(1.2, 2.3), xytext=(2.2, 2.3),
                arrowprops=dict(arrowstyle="<-", color="#6B7280", lw=1))

    ax.set_title("实时规划 · Agent 工具调用决策流程\n(GoalBasedAgent — agent_agentic.py)",
                 fontsize=11, pad=8)
    fig.tight_layout()
    path = os.path.join(OUT, "G1_agent_flow.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[G1] Agent flow → {path}")


# ─── Chart G2 · 知识库 vs 联网搜索城市覆盖 ───────────────────────────────────
def chart_kb_coverage():
    """Donut + annotation showing KB cities vs web-search-only cities."""
    KB_COUNT   = len(KB_CITIES)          # 22
    WEB_COUNT  = 200                     # effectively unlimited; use symbolic number

    fig, axes = plt.subplots(1, 2, figsize=(11, 5.5))

    # Left: donut
    ax = axes[0]
    sizes  = [KB_COUNT, WEB_COUNT - KB_COUNT]
    labels = [f"知识库覆盖\n{KB_COUNT} 城市", f"仅联网搜索\n(全球其余城市)"]
    colors = ["#4F6EF7", "#E5E7EB"]
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors,
        autopct=lambda p: f"{p:.0f}%" if p > 10 else "",
        startangle=90, pctdistance=0.75,
        wedgeprops=dict(width=0.5, edgecolor="white", linewidth=2),
    )
    for t in texts:       t.set_fontsize(10)
    for t in autotexts:   t.set_fontsize(11); t.set_fontweight("bold"); t.set_color("white")
    ax.set_title("城市知识库覆盖范围\n22城预存 · 其余城市实时联网", fontsize=10, pad=8)

    # Right: list of KB cities as chips
    ax2 = axes[1]
    ax2.axis("off")
    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1)
    ax2.set_title("知识库已覆盖城市列表", fontsize=10, pad=8, loc="left", x=0.05)

    cols = 4
    rows_n = (len(KB_CITIES) + cols - 1) // cols
    chip_w, chip_h = 0.22, 0.07
    pad_x, pad_y   = 0.015, 0.015
    start_y        = 0.93

    for idx, city in enumerate(KB_CITIES):
        row = idx // cols
        col = idx  % cols
        x = 0.04 + col * (chip_w + pad_x)
        y = start_y - row * (chip_h + pad_y)
        bg = FancyBboxPatch((x, y - chip_h), chip_w, chip_h,
                            boxstyle="round,pad=0.01,rounding_size=0.02",
                            facecolor="#EFF6FF", edgecolor="#4F6EF7", linewidth=1, zorder=3,
                            transform=ax2.transAxes, clip_on=False)
        ax2.add_patch(bg)
        ax2.text(x + chip_w/2, y - chip_h/2, city, ha="center", va="center",
                 fontsize=8.5, color="#1E40AF", fontweight="bold",
                 transform=ax2.transAxes)

    fig.suptitle("实时规划 · 知识库与联网搜索覆盖策略", fontsize=12, y=1.01)
    fig.tight_layout()
    path = os.path.join(OUT, "G2_kb_coverage.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[G2] KB coverage → {path}")


# ─── Chart G3 · 4维规划框架 Radar chart ──────────────────────────────────────
def chart_planning_dimensions():
    """Spider chart of the 4 planning dimensions, with sub-items annotated."""
    dim_names = list(DIMENSIONS.keys())
    scores    = [DIMENSIONS[d]["score"] for d in dim_names]
    N = len(dim_names)

    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]
    scores_plot = scores + scores[:1]

    fig, axes = plt.subplots(1, 2, figsize=(11, 5.5),
                             subplot_kw=dict(polar=True) if False else {})
    plt.close(fig)

    fig = plt.figure(figsize=(11, 5.5))
    ax_radar = fig.add_axes([0.03, 0.05, 0.44, 0.9], polar=True)
    ax_text  = fig.add_axes([0.50, 0.0,  0.50, 1.0])
    ax_text.axis("off")

    # radar
    ax_radar.set_theta_offset(np.pi / 2)
    ax_radar.set_theta_direction(-1)
    ax_radar.set_ylim(0, 5.5)
    ax_radar.set_yticks([1,2,3,4,5])
    ax_radar.set_yticklabels(["","","","",""], fontsize=0)
    ax_radar.set_xticks(angles[:-1])
    ax_radar.set_xticklabels(dim_names, fontsize=11, fontweight="bold", color="#1E293B")

    ax_radar.plot(angles, scores_plot, color="#4F6EF7", linewidth=2.5, linestyle="solid", zorder=3)
    ax_radar.fill(angles, scores_plot, color="#4F6EF7", alpha=0.18)
    for angle, score in zip(angles[:-1], scores):
        ax_radar.plot(angle, score, "o", color="#4F6EF7", markersize=9, zorder=4)
        ax_radar.text(angle, score + 0.45, str(score), ha="center", va="center",
                      fontsize=10, fontweight="bold", color="#1E40AF")

    ax_radar.grid(color="#E5E7EB", linewidth=0.8)
    ax_radar.set_title("4维规划框架\n(来自系统提示词设计)", fontsize=10, pad=18)

    # right: sub-items list
    ax_text.set_xlim(0, 1)
    ax_text.set_ylim(0, 1)
    colors_dim = ["#4F6EF7","#7C3AED","#059669","#D97706"]
    y_pos = 0.92
    for di, (dim, info) in enumerate(DIMENSIONS.items()):
        ax_text.text(0.04, y_pos, f"● {dim}", fontsize=11, fontweight="bold",
                     color=colors_dim[di], transform=ax_text.transAxes)
        y_pos -= 0.07
        for sub in info["subs"]:
            ax_text.text(0.10, y_pos, f"· {sub}", fontsize=9.5, color="#374151",
                         transform=ax_text.transAxes)
            y_pos -= 0.055
        y_pos -= 0.02

    ax_text.set_title("各维度规划要素", fontsize=10, pad=8, loc="left", x=0.04)

    fig.suptitle("实时规划 · 多维度规划框架 (系统提示词结构)", fontsize=12, y=1.01)
    path = os.path.join(OUT, "G3_planning_dimensions.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[G3] Planning dimensions → {path}")


# ─── Chart G4 · 工具调用轮次与策略 ───────────────────────────────────────────
def chart_tool_rounds():
    """
    Horizontal swimlane diagram: 3 scenarios × up to 3 tool rounds.
    Uses figure-level normalized coordinates to avoid tight_layout issues.
    """
    fig = plt.figure(figsize=(10, 4.2))
    ax  = fig.add_axes([0, 0, 1, 1])   # full-figure axes, no margins
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # ── layout constants (all in normalized 0-1 figure coords) ──────────────
    ROW_Y   = [0.72, 0.47, 0.22]          # centre y for each scenario row
    ROW_H   = 0.18                         # row height
    COL_X   = [0.22, 0.42, 0.62]          # centre x for tool rounds 1-3
    BOX_W   = 0.165
    BOX_H   = 0.12
    LABEL_X = 0.05                         # scenario label x

    COLOR_KB  = "#059669"
    COLOR_WEB = "#D97706"
    COLOR_GEN = "#7C3AED"

    scenarios = ["知识库城市", "未知城市", "复杂需求"]
    s_colors  = [COLOR_KB, COLOR_WEB, "#7C3AED"]

    def rbox(cx, cy, text, color, fontsize=8):
        """Draw a rounded box centred at (cx, cy) in axes-norm coords."""
        x0, y0 = cx - BOX_W/2, cy - BOX_H/2
        patch = FancyBboxPatch((x0, y0), BOX_W, BOX_H,
                               boxstyle="round,pad=0.01,rounding_size=0.015",
                               facecolor=color, edgecolor="white",
                               linewidth=1.5, zorder=4, transform=ax.transAxes,
                               clip_on=False)
        ax.add_patch(patch)
        ax.text(cx, cy, text, ha="center", va="center", fontsize=fontsize,
                color="white", fontweight="bold", zorder=5,
                transform=ax.transAxes, multialignment="center")

    def harrow(x1, x2, cy):
        """Horizontal arrow from right edge of box 1 to left edge of box 2."""
        ax.annotate("",
                    xy=(x2 - BOX_W/2 - 0.005, cy),
                    xytext=(x1 + BOX_W/2 + 0.005, cy),
                    xycoords="axes fraction", textcoords="axes fraction",
                    arrowprops=dict(arrowstyle="-|>", color="#9CA3AF",
                                    lw=1.4, mutation_scale=12),
                    zorder=3)

    def gen_label(cx, cy, short=False):
        txt = "→ 生成" if short else "→ 生成行程"
        ax.text(cx, cy, txt, ha="left", va="center", fontsize=8.5,
                color="#1F2937", fontweight="bold", transform=ax.transAxes)

    # ── header row ───────────────────────────────────────────────────────────
    ax.text(0.5, 0.95, "实时规划 · 工具调用轮次策略  (max_tool_rounds = 3，Agent 自主决策)",
            ha="center", va="center", fontsize=11, fontweight="bold",
            color="#1E293B", transform=ax.transAxes)

    for xi, label in enumerate(["第 1 轮", "第 2 轮", "第 3 轮"]):
        ax.text(COL_X[xi], 0.86, label, ha="center", va="center",
                fontsize=9.5, color="#6B7280", fontweight="bold",
                transform=ax.transAxes)

    # column dividers
    for xi in range(3):
        x_div = COL_X[xi] - BOX_W/2 - 0.01
        ax.plot([x_div, x_div], [0.08, 0.83], color="#E5E7EB",
                linewidth=0.8, transform=ax.transAxes, zorder=0)

    # ── scenario swimlanes ───────────────────────────────────────────────────
    for ri, (label, cy, sc) in enumerate(zip(scenarios, ROW_Y, s_colors)):
        # shaded lane
        lane = FancyBboxPatch((0.01, cy - ROW_H/2), 0.98, ROW_H,
                              boxstyle="round,pad=0.005,rounding_size=0.01",
                              facecolor="#F8FAFC", edgecolor="#E2E8F0",
                              linewidth=1, zorder=1, transform=ax.transAxes,
                              clip_on=False)
        ax.add_patch(lane)
        ax.text(LABEL_X, cy, label, ha="center", va="center",
                fontsize=9.5, color=sc, fontweight="bold",
                transform=ax.transAxes)

    # ── Row 0: 知识库城市 — 1 round KB, then generate ────────────────────────
    ry = ROW_Y[0]
    rbox(COL_X[0], ry, "query_knowledge_base", COLOR_KB)
    gen_label(COL_X[0] + BOX_W/2 + 0.015, ry)

    # ── Row 1: 未知城市 — web × 2, then generate ─────────────────────────────
    ry = ROW_Y[1]
    rbox(COL_X[0], ry, "search_web", COLOR_WEB)
    harrow(COL_X[0], COL_X[1], ry)
    rbox(COL_X[1], ry, "search_web\n(补充细节)", COLOR_WEB)
    gen_label(COL_X[1] + BOX_W/2 + 0.015, ry)

    # ── Row 2: 复杂需求 — KB + web × 2, then generate ────────────────────────
    ry = ROW_Y[2]
    rbox(COL_X[0], ry, "query_knowledge_base", COLOR_KB)
    harrow(COL_X[0], COL_X[1], ry)
    rbox(COL_X[1], ry, "search_web\n(实时票价)", COLOR_WEB)
    harrow(COL_X[1], COL_X[2], ry)
    rbox(COL_X[2], ry, "search_web\n(住宿/天气)", COLOR_WEB)
    gen_label(COL_X[2] + BOX_W/2 + 0.015, ry, short=True)

    # ── legend ───────────────────────────────────────────────────────────────
    kb_patch  = mpatches.Patch(color=COLOR_KB,  label="query_knowledge_base")
    web_patch = mpatches.Patch(color=COLOR_WEB, label="search_web")
    ax.legend(handles=[kb_patch, web_patch], loc="lower right",
              fontsize=8.5, framealpha=0.9,
              bbox_to_anchor=(0.99, 0.03), bbox_transform=ax.transAxes)

    path = os.path.join(OUT, "G4_tool_rounds.png")
    fig.savefig(path, dpi=150, bbox_inches=None)   # no tight_layout, fixed axes
    plt.close(fig)
    print(f"[G4] Tool rounds → {path}")


if __name__ == "__main__":
    chart_agent_flow()
    chart_kb_coverage()
    chart_planning_dimensions()
    chart_tool_rounds()
    print(f"\n✓ 4 charts saved to {OUT}/")
    print("  G1_agent_flow.png")
    print("  G2_kb_coverage.png")
    print("  G3_planning_dimensions.png")
    print("  G4_tool_rounds.png")
