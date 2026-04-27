"""
公平性分析 — Phase 2B + Phase 3

独立于推荐算法代码，通过调用各系统的 generate() 接口进行对比分析：
1. 生成 1200 条多样化测试用例
2. 分别运行规则系统、监督系统、目标导向系统
3. 比较相同条件下不同群体的推荐差异
4. 跨三系统对比响应一致性

不修改任何推荐算法代码。
"""

import json
import random
import time
import sys
import os
from datetime import datetime
from typing import Dict, List
from collections import Counter

# 确保能找到项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from systems.supervised.inference import (
    generate as supervised_generate,
    RECOMMENDATION_LABELS_ZH,
)
from systems.rule_based.engine import (
    generate as rule_based_generate,
)

# ── 统一推荐类型标签 ──────────────────────────────────────────

# 监督系统的 8 种推荐类型
SUPERVISED_LABELS = {v: v for v in RECOMMENDATION_LABELS_ZH.values()}
SUPERVISED_LABELS["unknown"] = "未知"

# 规则系统的输出推荐类型映射（从行程标题提取）
RULE_BASED_TYPES = {
    "经济观光": "经济观光",
    "文化深度游": "文化深度游",
    "奢华体验": "奢华体验",
    "亲子家庭游": "亲子家庭游",
    "美食购物游": "美食购物游",
    "户外探险游": "户外探险游",
    "情侣浪漫游": "情侣浪漫游",
    "团队社交游": "团队社交游",
}


# ── 测试用例生成 ─────────────────────────────────────────────

INTERESTS = ["文化", "自然", "美食", "购物", "历史", "夜生活", "户外"]
CITIES = ["巴黎", "东京", "纽约", "伦敦", "罗马", "首尔", "迪拜",
           "曼谷", "新加坡", "悉尼", "巴塞罗那", "阿姆斯特丹", "维也纳"]
BUDGETS = ["低", "中", "高"]
GROUPS = ["单人", "情侣", "夫妻", "朋友", "家庭"]
TRAVEL_MODES = ["飞机", "高铁", "自驾", "邮轮"]
SPECIALS = ["无", "有儿童", "有老人", "轮椅友好"]


def generate_test_cases(n: int = 1200, seed: int = 2026) -> List[dict]:
    """
    生成 n 条多样化测试用例，覆盖各群体组合。
    保证每个 (group, special) 组合至少有一定数量的样本。
    """
    random.seed(seed)
    cases = []

    # 分层采样：确保每个 (group, special) 组合有足够样本
    for group in GROUPS:
        for special in SPECIALS:
            per_combo = max(10, n // (len(GROUPS) * len(SPECIALS)))
            for _ in range(per_combo):
                city = random.choice(CITIES)
                days = random.randint(1, 7)
                budget = random.choice(BUDGETS)
                mode = random.choice(TRAVEL_MODES)
                num_people = random.randint(1, 8)
                if group in ("情侣", "夫妻"):
                    num_people = min(num_people, 2)
                elif group == "家庭":
                    num_people = max(num_people, 2)
                n_interests = random.randint(1, 4)
                interests = random.sample(INTERESTS, n_interests)

                cases.append({
                    "id": f"TEST_{len(cases)+1:05d}",
                    "metadata": {
                        "city": city,
                        "days": days,
                        "budget": budget,
                        "interests": interests,
                        "group": group,
                        "num_people": num_people,
                        "travel_mode": mode,
                        "special": special,
                    },
                })

    # 不足 n 条的补充随机样本
    while len(cases) < n:
        city = random.choice(CITIES)
        days = random.randint(1, 7)
        budget = random.choice(BUDGETS)
        group = random.choice(GROUPS)
        num_people = random.randint(1, 8)
        if group in ("情侣", "夫妻"):
            num_people = min(num_people, 2)
        elif group == "家庭":
            num_people = max(num_people, 2)
        special = random.choice(SPECIALS)
        mode = random.choice(TRAVEL_MODES)
        interests = random.sample(INTERESTS, random.randint(1, 4))
        cases.append({
            "id": f"TEST_{len(cases)+1:05d}",
            "metadata": {
                "city": city, "days": days, "budget": budget,
                "interests": interests, "group": group,
                "num_people": num_people, "travel_mode": mode,
                "special": special,
            },
        })

    return cases[:n]


# ── 批量运行 ─────────────────────────────────────────────────

def run_system(system_name: str, cases: List[dict]) -> List[dict]:
    """批量运行某个系统，返回结果列表"""
    results = []
    start = time.time()

    for i, case in enumerate(cases):
        try:
            if system_name == "rule_based":
                result = rule_based_generate(case)
            elif system_name == "supervised":
                result = supervised_generate(case)
            else:
                continue

            results.append({
                "id": case["id"],
                "metadata": case["metadata"],
                "output": result,
            })
        except Exception as e:
            results.append({
                "id": case["id"],
                "metadata": case["metadata"],
                "error": str(e),
            })

        if (i + 1) % 200 == 0:
            elapsed = time.time() - start
            print(f"  {system_name}: {i+1}/{len(cases)} ({elapsed:.1f}s)")

    return results


# ── 推荐类型提取 ─────────────────────────────────────────────

def extract_rec_type(system_name: str, output: dict) -> str:
    """从各系统输出中提取统一的推荐类型标签"""
    if system_name == "supervised":
        rec_type = output.get("prediction", -1)
        return RECOMMENDATION_LABELS_ZH.get(rec_type, "未知")

    elif system_name == "rule_based":
        itinerary = output.get("itinerary", "")
        # 规则系统输出格式： "# {城市} {天数}日行程 · {推荐类型}"
        lines = itinerary.split("\n")
        if lines:
            title = lines[0]
            if "·" in title:
                return title.split("·")[-1].strip()
        return "未知"

    return "未知"


# ── 分析函数 ─────────────────────────────────────────────────

def _distribution(lst: list) -> dict:
    """计算标签比例分布"""
    if not lst:
        return {}
    counts = Counter(lst)
    total = len(lst)
    return {k: round(v / total, 4) for k, v in sorted(counts.items())}


def _entropy(dist: dict) -> float:
    """计算分布的信息熵（越高越多样化）"""
    import math
    if not dist:
        return 0.0
    return round(-sum(p * math.log2(p) for p in dist.values() if p > 0), 4)


def _js_divergence(d1: dict, d2: dict) -> float:
    """Jensen-Shannon 散度（0=完全相同，1=完全不同）"""
    import math
    all_keys = set(d1.keys()) | set(d2.keys())
    p = [d1.get(k, 0) for k in all_keys]
    q = [d2.get(k, 0) for k in all_keys]
    # 归一化
    p_sum = sum(p)
    q_sum = sum(q)
    if p_sum == 0 or q_sum == 0:
        return 0.0
    p = [x / p_sum for x in p]
    q = [x / q_sum for x in q]
    m = [(pi + qi) / 2 for pi, qi in zip(p, q)]
    js = 0.0
    for pi, qi, mi in zip(p, q, m):
        if mi > 0:
            if pi > 0:
                js += pi * math.log2(pi / mi)
            if qi > 0:
                js += qi * math.log2(qi / mi)
    return round(js / 2, 4)


# ── 主分析流程 ───────────────────────────────────────────────

def analyze_system(results: List[dict], system_name: str) -> Dict:
    """对某系统的运行结果做分析"""
    rec_by_group = {}
    rec_by_budget = {}
    rec_by_group_budget = {}
    rec_by_special = {}
    errors = 0

    for r in results:
        if "error" in r:
            errors += 1
            continue
        meta = r["metadata"]
        rec_label = extract_rec_type(system_name, r["output"])
        group = meta["group"]
        budget = meta["budget"]
        special = meta["special"]

        rec_by_group.setdefault(group, []).append(rec_label)
        rec_by_budget.setdefault(budget, []).append(rec_label)
        key_gb = f"{budget}|{group}"
        rec_by_group_budget.setdefault(key_gb, []).append(rec_label)
        rec_by_special.setdefault(special, []).append(rec_label)

    # 群体分布
    group_dists = {g: _distribution(v) for g, v in rec_by_group.items()}
    group_entropy = {g: _entropy(d) for g, d in group_dists.items()}

    # 预算分布
    budget_dists = {b: _distribution(v) for b, v in rec_by_budget.items()}

    # 特殊需求分布
    special_dists = {s: _distribution(v) for s, v in rec_by_special.items()}

    return {
        "system": system_name,
        "total_cases": len(results),
        "errors": errors,
        "group_distributions": group_dists,
        "group_entropy": group_entropy,
        "budget_distributions": budget_dists,
        "special_distributions": special_dists,
        "group_budget_distributions": {
            k: _distribution(v) for k, v in rec_by_group_budget.items()
        },
    }


def compare_systems(analyses: List[Dict]) -> Dict:
    """跨系统对比分析"""
    comparison = {}

    # 1. 各系统的群体推荐多样性对比（熵值）
    diversity_comparison = {}
    for analysis in analyses:
        sys_name = analysis["system"]
        diversity_comparison[sys_name] = analysis.get("group_entropy", {})
    comparison["diversity_comparison"] = diversity_comparison

    # 2. 各系统间群体分布的 JS 散度（分布差异越大越不公平）
    if len(analyses) >= 2:
        js_matrix = {}
        groups = set()
        for a in analyses:
            groups.update(a.get("group_distributions", {}).keys())

        for a1 in analyses:
            for a2 in analyses:
                if a1["system"] == a2["system"]:
                    continue
                key = f"{a1['system']} vs {a2['system']}"
                js_matrix[key] = {}
                for g in sorted(groups):
                    d1 = a1.get("group_distributions", {}).get(g, {})
                    d2 = a2.get("group_distributions", {}).get(g, {})
                    js_matrix[key][g] = _js_divergence(d1, d2)
        comparison["cross_system_js"] = js_matrix

    # 3. 群体间推荐差异（同一系统内不同群体的 JS 散度）
    for analysis in analyses:
        sys_name = analysis["system"]
        group_dists = analysis.get("group_distributions", {})
        group_list = sorted(group_dists.keys())
        within_system_js = {}
        for i in range(len(group_list)):
            for j in range(i + 1, len(group_list)):
                g1, g2 = group_list[i], group_list[j]
                within_system_js[f"{g1} vs {g2}"] = _js_divergence(
                    group_dists[g1], group_dists[g2]
                )
        comparison.setdefault("within_system_js", {})[sys_name] = within_system_js

    return comparison


# ── 主流程 ───────────────────────────────────────────────────

def main():
    output_dir = os.path.dirname(os.path.abspath(__file__))

    print("=" * 60)
    print("公平性分析 — Phase 2B + Phase 3")
    print("=" * 60)

    # Step 1: 生成测试用例
    print("\n[1] 生成测试用例...")
    cases = generate_test_cases(n=1200)
    print(f"  共 {len(cases)} 条测试用例")

    cases_path = os.path.join(output_dir, "test_cases.json")
    with open(cases_path, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)

    # Step 2: 运行规则系统
    print("\n[2] 运行规则系统...")
    t0 = time.time()
    rule_results = run_system("rule_based", cases)
    print(f"  规则系统完成: {time.time()-t0:.1f}s")

    rule_path = os.path.join(output_dir, "results_rule_based.json")
    with open(rule_path, "w", encoding="utf-8") as f:
        json.dump(rule_results, f, ensure_ascii=False, indent=2)

    # Step 3: 运行监督系统
    print("\n[3] 运行监督系统...")
    t0 = time.time()
    super_results = run_system("supervised", cases)
    print(f"  监督系统完成: {time.time()-t0:.1f}s")

    super_path = os.path.join(output_dir, "results_supervised.json")
    with open(super_path, "w", encoding="utf-8") as f:
        json.dump(super_results, f, ensure_ascii=False, indent=2)

    # Step 4: 各系统分析
    print("\n[4] 公平性分析...")
    rule_analysis = analyze_system(rule_results, "rule_based")
    super_analysis = analyze_system(super_results, "supervised")

    # Step 5: 跨系统对比
    print("\n[5] 跨系统对比...")
    comparison = compare_systems([rule_analysis, super_analysis])

    # Step 6: 生成报告
    print("\n[6] 生成报告...")
    report = {
        "generated_at": datetime.now().isoformat(),
        "test_cases": len(cases),
        "rule_based": rule_analysis,
        "supervised": super_analysis,
        "cross_system_comparison": comparison,
    }

    report_path = os.path.join(output_dir, "fairness_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print(f"  报告已保存: {report_path}")

    # ── 打印摘要 ─────────────────────────────────────
    print("\n" + "=" * 60)
    print("公平性分析摘要")
    print("=" * 60)

    # 群体推荐多样性
    print("\n群体推荐多样性（熵值，越高越多样化）:")
    for analysis in [rule_analysis, super_analysis]:
        sys_name = analysis["system"]
        print(f"\n  [{sys_name}]")
        for group, ent in sorted(analysis["group_entropy"].items()):
            print(f"    {group}: {ent:.4f}")

    # 各系统内群体间差异
    print("\n群体间推荐差异（JS散度，越高差异越大）:")
    for sys_name, js_pairs in comparison.get("within_system_js", {}).items():
        print(f"\n  [{sys_name}]")
        for pair, js_val in sorted(js_pairs.items()):
            flag = "⚠" if js_val > 0.3 else "✓"
            print(f"    {pair}: {js_val:.4f} {flag}")

    print("\n" + "=" * 60)
    print("分析完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
