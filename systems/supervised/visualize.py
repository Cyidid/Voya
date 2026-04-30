"""
visualize.py — Model visualizations for SupervisedEngine
Generates 6 charts grounded in the actual model structure and data.
Run: python visualize.py
Outputs: ./charts/ directory with PNG files
"""

import os, sys, json, itertools
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
from matplotlib.colors import LinearSegmentedColormap
import warnings
warnings.filterwarnings("ignore")

# ── make sure inference.py is importable ─────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from inference import (
    SupervisedEngine, _expert_label,
    CITY_DAILY_BUDGET, RECOMMENDATION_TYPES, RECOMMENDATION_LABELS_ZH,
    FEATURE_NAMES, FEATURE_NAMES_ZH,
)

OUT = os.path.join(os.path.dirname(__file__), "charts")
os.makedirs(OUT, exist_ok=True)

# ── colour palette ────────────────────────────────────────────────────────────
PALETTE   = ["#4F6EF7","#7C3AED","#059669","#D97706","#DC2626","#0891B2","#BE185D","#64748B"]
TYPE_COLS = {i: PALETTE[i] for i in range(8)}

REC_LABELS = [RECOMMENDATION_LABELS_ZH[i] for i in range(8)]   # 8 type names

# Chinese font (best-effort)
plt.rcParams.update({
    "font.family":      ["PingFang SC","Heiti TC","Microsoft YaHei","SimHei","DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.dpi":       150,
})

print("Training model (first run may take ~10 s)…")
engine = SupervisedEngine()
print(f"Model ready. Accuracy: {engine.model_accuracy:.1%}  Dataset: {engine.dataset_size:,} samples")
print()

# ═══════════════════════════════════════════════════════════════════════════════
# Chart 1 · Feature Importance
# ═══════════════════════════════════════════════════════════════════════════════
def chart_feature_importance():
    fi = engine.feature_importances          # {feature_name: float}
    names_en = list(FEATURE_NAMES)
    names_zh = [FEATURE_NAMES_ZH.get(n, n) for n in names_en]
    vals     = [fi.get(n, 0.0) for n in names_en]

    order = np.argsort(vals)                 # ascending → plot bottom→top
    names_sorted = [names_zh[i] for i in order]
    vals_sorted  = [vals[i]     for i in order]

    # colour by magnitude
    cmap = LinearSegmentedColormap.from_list("blueviolet", ["#93C5FD","#4F6EF7","#7C3AED"])
    colours = [cmap(v / max(vals_sorted)) for v in vals_sorted]

    fig, ax = plt.subplots(figsize=(8, 6))
    bars = ax.barh(names_sorted, vals_sorted, color=colours, height=0.65)

    for bar, v in zip(bars, vals_sorted):
        ax.text(v + 0.0005, bar.get_y() + bar.get_height()/2,
                f"{v:.3f}", va="center", ha="left", fontsize=8, color="#374151")

    ax.set_xlabel("Feature Importance (averaged GBT + RF + ET)", fontsize=9, color="#6B7280")
    ax.set_title("特征重要性分布\nVoting Classifier — GBT · RandomForest · ExtraTrees 平均", fontsize=11, pad=10)
    ax.tick_params(labelsize=9)
    ax.spines[["top","right","left"]].set_visible(False)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))
    ax.set_xlim(0, max(vals_sorted) * 1.15)
    ax.grid(axis="x", color="#E5E7EB", linewidth=0.6)

    fig.tight_layout()
    path = os.path.join(OUT, "1_feature_importance.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[1] Feature importance → {path}")


# ═══════════════════════════════════════════════════════════════════════════════
# Chart 2 · Expert-label distribution across training set
# ═══════════════════════════════════════════════════════════════════════════════
def chart_label_distribution():
    """Re-run the expert labeler on the actual 10 k training samples to show
    the true class distribution that the model learned from."""
    from inference import generate_training_dataset
    _X, y, _records = generate_training_dataset(10_000)
    counts = [int((y == i).sum()) for i in range(8)]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    xs = range(8)
    bars = ax.bar(xs, counts, color=[PALETTE[i] for i in range(8)], width=0.6, zorder=3)

    for bar, c in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 30,
                f"{c:,}", ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax.set_xticks(list(xs))
    ax.set_xticklabels(REC_LABELS, fontsize=9, rotation=20, ha="right")
    ax.set_ylabel("样本数 (N=10,000)", fontsize=9, color="#6B7280")
    ax.set_title("训练集标签分布\n专家规则在 10,000 个合成样本上的覆盖情况", fontsize=11, pad=10)
    ax.spines[["top","right"]].set_visible(False)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"{int(x):,}"))
    ax.grid(axis="y", color="#E5E7EB", linewidth=0.6, zorder=0)
    ax.set_ylim(0, max(counts) * 1.15)

    fig.tight_layout()
    path = os.path.join(OUT, "2_label_distribution.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[2] Label distribution → {path}")


# ═══════════════════════════════════════════════════════════════════════════════
# Chart 3 · CITY_DAILY_BUDGET heatmap (25 cities × 3 levels)
# ═══════════════════════════════════════════════════════════════════════════════
def chart_city_budget_heatmap():
    cities = list(CITY_DAILY_BUDGET.keys())
    levels = ["低", "中", "高"]
    matrix = np.array([[CITY_DAILY_BUDGET[c][lv] for lv in levels] for c in cities])

    fig, ax = plt.subplots(figsize=(5, 9))
    cmap = LinearSegmentedColormap.from_list("green_amber", ["#D1FAE5","#10B981","#065F46"])
    im = ax.imshow(matrix, aspect="auto", cmap=cmap)

    # cell labels
    for i, city in enumerate(cities):
        for j, lv in enumerate(levels):
            val = matrix[i, j]
            txt_col = "white" if val > matrix.max()*0.55 else "#1F2937"
            ax.text(j, i, f"¥{val:,}", ha="center", va="center",
                    fontsize=8, color=txt_col, fontweight="bold")

    ax.set_xticks([0,1,2])
    ax.set_xticklabels(["低档预算\n(Low)", "中档预算\n(Mid)", "高档预算\n(High)"],
                       fontsize=9)
    ax.set_yticks(range(len(cities)))
    ax.set_yticklabels(cities, fontsize=8.5)
    ax.set_title("25城市每日人均预算参考 (¥)\nCITY_DAILY_BUDGET 完整地图", fontsize=10, pad=10)
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position("top")

    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.ax.tick_params(labelsize=8)
    cbar.set_label("每日人均 (¥)", fontsize=8, color="#6B7280")

    fig.tight_layout()
    path = os.path.join(OUT, "3_city_budget_heatmap.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[3] City budget heatmap → {path}")


# ═══════════════════════════════════════════════════════════════════════════════
# Chart 4 · Group × Budget → Predicted Recommendation Type
# ═══════════════════════════════════════════════════════════════════════════════
def chart_group_budget_matrix():
    """Sweep group_type (0–4) × budget_level (0–2) with fixed other features
    and show what the trained model predicts."""
    group_names  = ["单人", "情侣", "夫妻", "家庭", "朋友"]
    budget_names = ["低预算", "中预算", "高预算"]
    g_vals = [0, 1, 2, 3, 4]
    b_vals = [0, 1, 2]

    pred_matrix = np.zeros((len(g_vals), len(b_vals)), dtype=int)
    prob_matrix  = np.zeros_like(pred_matrix, dtype=float)

    base_features = {n: 0 for n in FEATURE_NAMES}
    base_features["days"]         = 5
    base_features["num_people"]   = 2
    base_features["has_special"]  = 0
    base_features["travel_mode"]  = 1     # 飞机
    base_features["interest_food"]    = 1
    base_features["interest_culture"] = 1

    for i, g in enumerate(g_vals):
        for j, b in enumerate(b_vals):
            f = base_features.copy()
            f["group_type"]   = g
            f["budget_level"] = b
            pred, conf = engine._predict(f)
            pred_matrix[i, j] = pred
            prob_matrix[i, j] = conf

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))

    # left: recommendation type as colour
    ax = axes[0]
    im = ax.imshow(pred_matrix, aspect="auto",
                   cmap=matplotlib.colors.ListedColormap(PALETTE), vmin=0, vmax=7)

    for i in range(len(g_vals)):
        for j in range(len(b_vals)):
            ax.text(j, i, REC_LABELS[pred_matrix[i, j]],
                    ha="center", va="center", fontsize=8.5,
                    color="white", fontweight="bold")

    ax.set_xticks(range(len(b_vals))); ax.set_xticklabels(budget_names, fontsize=9)
    ax.set_yticks(range(len(g_vals))); ax.set_yticklabels(group_names,  fontsize=9)
    ax.set_title("群体 × 预算 → 推荐类型\n(模型预测)", fontsize=10, pad=8)
    legend_patches = [mpatches.Patch(color=PALETTE[i], label=f"{i} {REC_LABELS[i]}") for i in range(8)]
    ax.legend(handles=legend_patches, loc="lower right", fontsize=6.5,
              framealpha=0.85, ncol=2)

    # right: confidence heat
    ax2 = axes[1]
    im2 = ax2.imshow(prob_matrix, aspect="auto",
                     cmap="YlGn", vmin=0.5, vmax=1.0)
    for i in range(len(g_vals)):
        for j in range(len(b_vals)):
            ax2.text(j, i, f"{prob_matrix[i,j]:.0%}",
                     ha="center", va="center", fontsize=10, fontweight="bold",
                     color="#1F2937" if prob_matrix[i,j] < 0.85 else "white")

    ax2.set_xticks(range(len(b_vals))); ax2.set_xticklabels(budget_names, fontsize=9)
    ax2.set_yticks(range(len(g_vals))); ax2.set_yticklabels(group_names,  fontsize=9)
    ax2.set_title("预测置信度\n(Confidence)", fontsize=10, pad=8)
    cbar2 = fig.colorbar(im2, ax=ax2, fraction=0.04, pad=0.02)
    cbar2.ax.tick_params(labelsize=8)
    cbar2.set_label("Confidence", fontsize=8, color="#6B7280")

    fig.suptitle("群体类型 × 预算档次：推荐类型矩阵", fontsize=12, y=1.02)
    fig.tight_layout()
    path = os.path.join(OUT, "4_group_budget_matrix.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[4] Group × Budget matrix → {path}")


# ═══════════════════════════════════════════════════════════════════════════════
# Chart 5 · Probability distribution for a sample prediction
# ═══════════════════════════════════════════════════════════════════════════════
def chart_proba_distribution():
    """Show full 8-class probability distribution for 4 representative personas."""
    personas = [
        {
            "label": "家庭游·中预算·7天\n(东京，有儿童)",
            "features": dict(days=7, budget_level=1, num_people=4, group_type=3,
                             has_special=1, travel_mode=1,
                             interest_food=1, interest_culture=0, interest_outdoor=0,
                             interest_history=0, interest_nightlife=0, interest_shopping=0,
                             city_paris=0, city_tokyo=1, city_newyork=0,
                             city_london=0, city_rome=0, city_seoul=0, city_dubai=0),
        },
        {
            "label": "情侣游·高预算·5天\n(巴黎)",
            "features": dict(days=5, budget_level=2, num_people=2, group_type=1,
                             has_special=0, travel_mode=1,
                             interest_food=1, interest_culture=1, interest_outdoor=0,
                             interest_history=0, interest_nightlife=1, interest_shopping=1,
                             city_paris=1, city_tokyo=0, city_newyork=0,
                             city_london=0, city_rome=0, city_seoul=0, city_dubai=0),
        },
        {
            "label": "单人游·低预算·4天\n(首尔)",
            "features": dict(days=4, budget_level=0, num_people=1, group_type=0,
                             has_special=0, travel_mode=1,
                             interest_food=1, interest_culture=0, interest_outdoor=0,
                             interest_history=0, interest_nightlife=1, interest_shopping=1,
                             city_paris=0, city_tokyo=0, city_newyork=0,
                             city_london=0, city_rome=0, city_seoul=1, city_dubai=0),
        },
        {
            "label": "朋友团·中预算·3天\n(伦敦)",
            "features": dict(days=3, budget_level=1, num_people=5, group_type=4,
                             has_special=0, travel_mode=1,
                             interest_food=1, interest_culture=1, interest_outdoor=0,
                             interest_history=1, interest_nightlife=1, interest_shopping=0,
                             city_paris=0, city_tokyo=0, city_newyork=0,
                             city_london=1, city_rome=0, city_seoul=0, city_dubai=0),
        },
    ]

    fig, axes = plt.subplots(2, 2, figsize=(12, 7))
    axes = axes.flatten()

    for ax, persona in zip(axes, personas):
        f = {n: persona["features"].get(n, 0) for n in FEATURE_NAMES}
        proba_list = engine._predict_proba(f)          # [(zh_name, prob), …]
        # reorder to match type index 0-7
        name_to_prob = dict(proba_list)
        probs = [name_to_prob.get(RECOMMENDATION_LABELS_ZH[i], 0.0) for i in range(8)]

        colours = [PALETTE[i] for i in range(8)]
        bars = ax.bar(range(8), probs, color=colours, width=0.65, zorder=3)
        top_idx = int(np.argmax(probs))
        bars[top_idx].set_edgecolor("#1F2937")
        bars[top_idx].set_linewidth(2)

        for bar, p in zip(bars, probs):
            if p > 0.03:
                ax.text(bar.get_x() + bar.get_width()/2, p + 0.005,
                        f"{p:.0%}", ha="center", va="bottom", fontsize=7.5)

        ax.set_xticks(range(8))
        ax.set_xticklabels(REC_LABELS, fontsize=7.5, rotation=25, ha="right")
        ax.set_ylim(0, 1.0)
        ax.set_ylabel("Probability", fontsize=8, color="#6B7280")
        ax.set_title(persona["label"], fontsize=9, pad=6)
        ax.spines[["top","right"]].set_visible(False)
        ax.grid(axis="y", color="#E5E7EB", linewidth=0.5, zorder=0)
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))

    fig.suptitle("8类推荐类型概率分布 — 4种典型旅客画像", fontsize=12, y=1.01)
    fig.tight_layout()
    path = os.path.join(OUT, "5_proba_distribution.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[5] Probability distribution → {path}")


# ═══════════════════════════════════════════════════════════════════════════════
# Chart 6 · Budget breakdown for a sample trip
# ═══════════════════════════════════════════════════════════════════════════════
def chart_budget_breakdown():
    """Illustrate the budget breakdown formula used in _build_itinerary for
    several cities and budget levels side by side."""
    sample_cities  = ["东京", "巴黎", "首尔", "新加坡", "曼谷", "迪拜"]
    budget_levels  = ["低", "中", "高"]
    days, n_people = 5, 2

    flight_base = {"低": 3000, "中": 6000, "高": 18000}

    fig, axes = plt.subplots(1, 3, figsize=(14, 5), sharey=False)

    for ax, bud in zip(axes, budget_levels):
        flight_costs   = []
        hotel_costs    = []
        food_costs     = []
        attract_costs  = []
        totals         = []

        for city in sample_cities:
            bpd = CITY_DAILY_BUDGET.get(city, {}).get(bud, 900)
            fc  = flight_base[bud] * n_people
            hc  = int(bpd * 0.4) * days * n_people
            fdc = int(bpd * 0.3) * days * n_people
            ac  = int(bpd * 0.2) * days * n_people
            flight_costs.append(fc)
            hotel_costs.append(hc)
            food_costs.append(fdc)
            attract_costs.append(ac)
            totals.append(fc + hc + fdc + ac)

        x    = np.arange(len(sample_cities))
        w    = 0.55
        bot1 = np.zeros(len(sample_cities))
        bot2 = np.array(flight_costs)
        bot3 = bot2 + np.array(hotel_costs)
        bot4 = bot3 + np.array(food_costs)

        ax.bar(x, flight_costs,   width=w, label="交通",   color="#4F6EF7", bottom=bot1)
        ax.bar(x, hotel_costs,    width=w, label="住宿",   color="#7C3AED", bottom=bot2)
        ax.bar(x, food_costs,     width=w, label="餐饮",   color="#059669", bottom=bot3)
        ax.bar(x, attract_costs,  width=w, label="景点",   color="#D97706", bottom=bot4)

        for xi, tot in zip(x, totals):
            ax.text(xi, tot + max(totals)*0.01, f"¥{tot//1000}k",
                    ha="center", va="bottom", fontsize=8, fontweight="bold")

        ax.set_xticks(x)
        ax.set_xticklabels(sample_cities, fontsize=9, rotation=15, ha="right")
        ax.set_title(f"{bud}档预算\n{n_people}人×{days}天", fontsize=10, pad=6)
        ax.set_ylabel("总费用 (¥)", fontsize=8, color="#6B7280")
        ax.spines[["top","right"]].set_visible(False)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"¥{int(x)//1000}k" if x >= 1000 else f"¥{int(x)}"))
        ax.grid(axis="y", color="#E5E7EB", linewidth=0.5)
        if ax is axes[0]:
            ax.legend(fontsize=8, loc="upper left", framealpha=0.85)

    fig.suptitle("出行预算构成估算 (交通 40% · 住宿 30% · 餐饮 20% · 景点 10%)\n_build_itinerary 费用拆分逻辑", fontsize=11, y=1.02)
    fig.tight_layout()
    path = os.path.join(OUT, "6_budget_breakdown.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[6] Budget breakdown → {path}")


# ── run all ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    chart_feature_importance()
    chart_label_distribution()
    chart_city_budget_heatmap()
    chart_group_budget_matrix()
    chart_proba_distribution()
    chart_budget_breakdown()

    print(f"\n✓ All 6 charts saved to {OUT}/")
    print("  1_feature_importance.png")
    print("  2_label_distribution.png")
    print("  3_city_budget_heatmap.png")
    print("  4_group_budget_matrix.png")
    print("  5_proba_distribution.png")
    print("  6_budget_breakdown.png")
