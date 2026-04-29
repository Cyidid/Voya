"""
公平性分析 — Phase 2C：目标导向系统（AI/LLM）

采样策略：
- 从 1200 条测试用例中采样 N 条（默认 50），分层覆盖各群体
- 每条用例运行 3 次，检测 LLM 非确定性
- 结果与规则系统、监督系统统一格式保存

"""

import json
import random
import time
import sys
import os
from collections import Counter
from datetime import datetime

# 必须在其他导入之前加载 .env
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# 手动加载 .env
_env_path = os.path.join(PROJECT_ROOT, ".env")
if os.path.exists(_env_path):
    with open(_env_path, "r", encoding="utf-8") as _ef:
        for _eline in _ef:
            _eline = _eline.strip()
            if _eline and not _eline.startswith("#") and "=" in _eline:
                _k, _v = _eline.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

from systems.goal_based.agent_agentic import generate as goal_based_generate
from fairness_analysis.run_fairness_analysis import (
    extract_rec_type as _extract_rec_type_supervised,
    _distribution, _entropy, _js_divergence,
)
from systems.supervised.inference import RECOMMENDATION_LABELS_ZH

# ── 推荐类型提取（目标导向系统）───────────────────────────────────

def extract_goal_rec_type(output: dict) -> str:
    """从目标导向系统输出中提取并归一化推荐类型"""
    itinerary = output.get("itinerary", "") or output.get("output", "")
    if "·" in itinerary:
        title_line = itinerary.split("\n")[0]
        if "·" in title_line:
            raw_label = title_line.split("·")[-1].strip()
            return _normalize_label(raw_label)
    return _normalize_label(itinerary[:200])


def _normalize_label(text: str) -> str:
    """将自由标签归一化到 8 种标准推荐类型"""
    # 优先级匹配：多标签场景下按权重判断
    rules = [
        ("亲子家庭游", ["亲子", "家庭", "儿童", "小朋友", "敬老", "银发"]),
        ("情侣浪漫游", ["情侣", "夫妻", "浪漫", "烛光", "日落"]),
        ("奢华体验",   ["奢华", "高端", "轻奢", "米其林", "私人"]),
        ("经济观光",   ["经济", "省钱", "性价比", "实惠", "预算"]),
        ("户外探险游", ["户外", "探险", "徒步", "登山", "自然"]),
        ("美食购物游", ["美食", "购物", "餐厅", "商场"]),
        ("文化深度游", ["文化", "博物馆", "历史", "艺术"]),
        ("团队社交游", ["团队", "社交", "团体", "聚会", "结伴"]),
    ]
    scores = {}
    for rec_type, keywords in rules:
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[rec_type] = score
    if not scores:
        return "未知"
    return max(scores, key=scores.get)


# ── 构建自然语言输入 ──────────────────────────────────────────────

def build_user_request(metadata: dict) -> str:
    """从 metadata 构建自然语言请求（目标导向系统需要自然语言）"""
    group_map = {
        "单人": "我一个人",
        "情侣": "我和爱人/另一半",
        "夫妻": "我和伴侣",
        "朋友": "我和朋友们",
        "家庭": "我和家人",
    }
    budget_map = {"低": "预算有限/经济实惠", "中": "预算适中", "高": "预算宽裕"}

    parts = [f"我想去{metadata['city']}玩{metadata['days']}天"]
    parts.append(group_map.get(metadata["group"], metadata["group"]))
    interests = metadata.get("interests", [])
    if interests:
        parts.append(f"喜欢{','.join(interests)}")
    parts.append(budget_map.get(metadata["budget"], "预算适中"))
    if metadata.get("special", "无") != "无":
        parts.append(f"需要{metadata['special']}的便利设施")

    return "，".join(parts) + "。"


# ── 采样 ──────────────────────────────────────────────────────────

def sample_cases(cases: list, n_per_group: int = 10, seed: int = 2026) -> list:
    """分层采样：每个群体选 n_per_group 条"""
    random.seed(seed)
    grouped = {}
    for c in cases:
        g = c["metadata"]["group"]
        grouped.setdefault(g, []).append(c)

    sampled = []
    for g, group_cases in sorted(grouped.items()):
        k = min(n_per_group, len(group_cases))
        sampled.extend(random.sample(group_cases, k))
    return sampled


# ── 批量运行 ──────────────────────────────────────────────────────

def run_goal_system(cases: list, runs_per_case: int = 3) -> list:
    """运行目标导向系统，每条用例跑 runs_per_case 次"""
    results = []
    start = time.time()

    for i, case in enumerate(cases):
        case_results = []
        user_request = build_user_request(case["metadata"])

        for run_idx in range(runs_per_case):
            try:
                t0 = time.time()
                result = goal_based_generate(
                    {"input": user_request, "metadata": case["metadata"]},
                    enable_knowledge=False,    # 关闭知识库，避免 ChromaDB 初始化拖慢速度
                    enable_web_search=False,   # 纯 LLM 生成，保证速度
                )
                elapsed = time.time() - t0
                result["run_index"] = run_idx
                result["processing_time"] = elapsed
                case_results.append(result)
            except Exception as e:
                case_results.append({
                    "run_index": run_idx,
                    "error": str(e),
                    "metadata": case["metadata"],
                })

        results.append({
            "id": case["id"],
            "metadata": case["metadata"],
            "user_request": user_request,
            "runs": case_results,
        })

        elapsed_total = time.time() - start
        print(f"  [{i+1}/{len(cases)}] {case['id']} | "
              f"{case['metadata']['group']} | "
              f"耗时: {elapsed_total:.0f}s")

        # 保存中间结果（防止长时间运行中断丢失）
        if (i + 1) % 10 == 0:
            save_intermediate(results, i + 1)

    return results


def save_intermediate(results: list, count: int):
    """保存中间结果"""
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"results_goal_partial_{count}.json"
    )
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"    → 中间结果已保存: {path}")


# ── 分析 ──────────────────────────────────────────────────────────

def analyze_goal_results(results: list) -> dict:
    """分析目标导向系统结果"""
    rec_by_group = {}
    rec_by_budget = {}
    rec_by_special = {}
    non_determinism = []  # 同一条用例3次运行结果不一致的计数
    errors = 0
    total_runs = 0
    rec_types_all = []

    for r in results:
        runs = r["runs"]
        run_types = []
        for run in runs:
            total_runs += 1
            if "error" in run:
                errors += 1
                continue
            meta = r["metadata"]
            rec_label = extract_goal_rec_type(run)
            run_types.append(rec_label)
            rec_types_all.append(rec_label)

            group = meta["group"]
            budget = meta["budget"]
            special = meta["special"]

            rec_by_group.setdefault(group, []).append(rec_label)
            rec_by_budget.setdefault(budget, []).append(rec_label)
            rec_by_special.setdefault(special, []).append(rec_label)

        # 非确定性检测：3次运行是否一致
        valid_types = [t for t in run_types if t != "未知"]
        if len(valid_types) >= 2:
            unique = set(valid_types)
            non_determinism.append({
                "id": r["id"],
                "group": r["metadata"]["group"],
                "consistent": len(unique) == 1,
                "unique_types": list(unique),
                "all_types": valid_types,
            })

    # 计算比例
    consistent_count = sum(1 for nd in non_determinism if nd["consistent"])
    total_checked = len(non_determinism)

    group_dists = {g: _distribution(v) for g, v in rec_by_group.items()}
    group_entropy = {g: _entropy(d) for g, d in group_dists.items()}
    budget_dists = {b: _distribution(v) for b, v in rec_by_budget.items()}
    special_dists = {s: _distribution(v) for s, v in rec_by_special.items()}

    return {
        "system": "goal_based",
        "total_cases": len(results),
        "total_runs": total_runs,
        "errors": errors,
        "group_distributions": group_dists,
        "group_entropy": group_entropy,
        "budget_distributions": budget_dists,
        "special_distributions": special_dists,
        "non_determinism": {
            "total_checked": total_checked,
            "consistent": consistent_count,
            "inconsistent": total_checked - consistent_count,
            "consistency_rate": round(consistent_count / total_checked, 4) if total_checked > 0 else 0,
            "inconsistent_cases": [
                nd for nd in non_determinism if not nd["consistent"]
            ][:20],  # 只保留前 20 个不一致案例
        },
    }


# ── 主流程 ────────────────────────────────────────────────────────

def main():
    output_dir = os.path.dirname(os.path.abspath(__file__))

    print("=" * 60)
    print("公平性分析 — Phase 2C：目标导向系统（AI）")
    print("=" * 60)

    # Step 1: 加载已有测试用例
    cases_path = os.path.join(output_dir, "test_cases.json")
    with open(cases_path, "r", encoding="utf-8") as f:
        all_cases = json.load(f)
    print(f"\n[1] 已加载 {len(all_cases)} 条测试用例")

    # Step 2: 分层采样
    n_per_group = 10
    cases = sample_cases(all_cases, n_per_group=n_per_group)
    print(f"    采样 {len(cases)} 条（每个群体 {n_per_group} 条）")

    sample_path = os.path.join(output_dir, "sampled_cases_goal.json")
    with open(sample_path, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)

    # Step 3: 运行目标导向系统（每条 3 次）
    runs_per_case = 3
    print(f"\n[2] 运行目标导向系统（每条运行 {runs_per_case} 次）...")
    t0 = time.time()
    results = run_goal_system(cases, runs_per_case=runs_per_case)
    total_time = time.time() - t0
    print(f"\n  目标导向系统完成: {total_time:.0f}s ({total_time/60:.1f}分钟)")

    # Step 4: 保存结果
    goal_path = os.path.join(output_dir, "results_goal_based.json")
    with open(goal_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n[3] 结果已保存: {goal_path}")

    # Step 5: 分析
    print("\n[4] 分析目标导向系统结果...")
    goal_analysis = analyze_goal_results(results)

    # Step 6: 加载其他系统的分析结果，做三系统对比
    print("\n[5] 三系统对比...")
    report_path = os.path.join(output_dir, "fairness_report.json")
    with open(report_path, "r", encoding="utf-8") as f:
        old_report = json.load(f)

    rule_analysis = old_report.get("rule_based", {})
    super_analysis = old_report.get("supervised", {})

    all_analyses = [rule_analysis, super_analysis, goal_analysis]

    # 重新计算跨系统 JS 散度
    from fairness_analysis.run_fairness_analysis import compare_systems
    comparison = compare_systems(all_analyses)

    # 更新报告
    updated_report = {
        "generated_at": datetime.now().isoformat(),
        "test_cases_total": len(all_cases),
        "goal_based_sample": len(cases),
        "runs_per_case": runs_per_case,
        "rule_based": rule_analysis,
        "supervised": super_analysis,
        "goal_based": goal_analysis,
        "cross_system_comparison": comparison,
        "summary": {
            "rule_time_s": old_report.get("rule_time_s", "N/A"),
            "supervised_time_s": old_report.get("supervised_time_s", "N/A"),
            "goal_based_time_s": round(total_time, 1),
        }
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(updated_report, f, ensure_ascii=False, indent=2, default=str)
    print(f"  更新报告已保存: {report_path}")

    # ── 打印摘要 ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("目标导向系统分析摘要")
    print("=" * 60)

    print("\n群体推荐多样性（熵值）:")
    for group, ent in sorted(goal_analysis["group_entropy"].items()):
        print(f"  {group}: {ent:.4f}")

    print("\n非确定性检测（每条运行 3 次）:")
    nd = goal_analysis["non_determinism"]
    print(f"  一致性: {nd['consistent']}/{nd['total_checked']} "
          f"({nd['consistency_rate']*100:.1f}%)")
    print(f"  不一致: {nd['inconsistent']}")
    if nd["inconsistent_cases"]:
        print("  不一致案例示例:")
        for ic in nd["inconsistent_cases"][:5]:
            print(f"    {ic['id']} ({ic['group']}): {ic['all_types']}")

    print("\n三系统群体分布对比（熵值）:")
    print(f"  {'群体':<8} | {'规则系统':>10} | {'监督系统':>10} | {'目标导向':>10}")
    print(f"  {'-'*8} | {'-'*10} | {'-'*10} | {'-'*10}")
    all_groups = set()
    for a in all_analyses:
        all_groups.update(a.get("group_entropy", {}).keys())
    for g in sorted(all_groups):
        rule_ent = rule_analysis.get("group_entropy", {}).get(g, "N/A")
        super_ent = super_analysis.get("group_entropy", {}).get(g, "N/A")
        goal_ent = goal_analysis.get("group_entropy", {}).get(g, "N/A")
        rule_str = f"{rule_ent:.4f}" if isinstance(rule_ent, float) else "N/A"
        super_str = f"{super_ent:.4f}" if isinstance(super_ent, float) else "N/A"
        goal_str = f"{goal_ent:.4f}" if isinstance(goal_ent, float) else "N/A"
        print(f"  {g:<8} | {rule_str:>10} | {super_str:>10} | {goal_str:>10}")

    print("\n" + "=" * 60)
    print("分析完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
