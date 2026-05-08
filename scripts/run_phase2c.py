#!/usr/bin/env python3
"""
Phase 2C：Goal-Based (Agentic AI) 多次运行测试
每个请求运行 3 次（use_cache=False），记录非确定性变化。
因 LLM 调用耗时较长，默认测试 20 条有代表性的用例（可用 --all 跑全部）。

提交物：results/phase2c_outputs.csv + results/phase2c_outputs.json
        包含每条用例的 3 次独立响应，以及跨运行的差异分析

使用方法：
  python scripts/run_phase2c.py              # 运行 20 条 × 3次
  python scripts/run_phase2c.py --count 10   # 运行 10 条 × 3次
"""

import os
import sys
import json
import csv
import time
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# 加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass

TEST_CASES_FILE = os.path.join(BASE_DIR, "assets", "test_cases.json")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
CSV_OUT = os.path.join(RESULTS_DIR, "phase2c_outputs.csv")
JSON_OUT = os.path.join(RESULTS_DIR, "phase2c_outputs.json")

RUNS_PER_CASE = 3  # 课程要求：每个请求至少跑 3 次


def select_representative_cases(test_cases: list, count: int) -> list:
    """从 1000 条中选出多样性最好的 count 条（覆盖不同城市/预算/兴趣/群体）"""
    seen = set()
    selected = []
    # 优先覆盖所有城市+预算组合
    for tc in test_cases:
        meta = tc["metadata"]
        key = (meta.get("city"), meta.get("budget"), tc.get("type", "standard"))
        if key not in seen:
            seen.add(key)
            selected.append(tc)
        if len(selected) >= count:
            break
    # 不足时从 edge 类型补充
    for tc in test_cases:
        if tc.get("type") == "edge" and tc not in selected:
            selected.append(tc)
        if len(selected) >= count:
            break
    return selected[:count]


def run(count: int = 20):
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print("Phase 2C: Goal-Based System 多次运行测试")
    print("-" * 40)
    print(f"每条用例跑 {RUNS_PER_CASE} 次（禁用缓存，观察非确定性）")
    print("-" * 40)

    # 使用 agent_agentic（主智能体）
    try:
        from systems.goal_based.agent_agentic import TravelPlanningAgent
        print("使用 Goal-Based Agent（qwen3.6-plus + 工具链）")
    except ImportError as e:
        print(f"导入 Goal-Based Agent 失败: {e}")
        sys.exit(1)

    with open(TEST_CASES_FILE, "r", encoding="utf-8") as f:
        all_cases = json.load(f)

    selected = select_representative_cases(all_cases, count)
    print(f"\n已选 {len(selected)} 条代表性用例（覆盖不同城市/预算/类型）\n")

    # 初始化 Agent（一次，避免重复初始化）
    agent = TravelPlanningAgent(enable_knowledge=True, enable_web_search=True)

    json_records = []
    csv_rows = []

    for i, tc in enumerate(selected):
        meta = tc["metadata"]
        user_request = tc["input"]
        print(f"\n[{i+1}/{len(selected)}] {tc['id']} | {meta.get('city')} "
              f"{meta.get('days')}天 预算:{meta.get('budget')}")
        print(f"  输入: {user_request}")

        run_results = []
        for run_idx in range(1, RUNS_PER_CASE + 1):
            print(f"  → 第 {run_idx} 次运行...", end=" ", flush=True)
            t0 = time.time()
            # 重试逻辑：网络断开最多重试3次
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    result = agent.generate_itinerary(user_request, meta, use_cache=False)
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait = (attempt + 1) * 15
                        print(f"\n    {type(e).__name__}，{wait}s 后重试...", end=" ", flush=True)
                        time.sleep(wait)
                    else:
                        print(f"\n    重试{max_retries}次仍失败，跳过此次运行")
                        result = {"itinerary": f"[ERROR: {e}]", "source": "error"}
            elapsed = round(time.time() - t0, 2)
            output = result.get("itinerary", "")
            print(f"完成 ({elapsed}s, {len(output)} 字)")
            run_results.append({
                "run": run_idx,
                "output": output,
                "source": result.get("source", "llm"),
                "time_s": elapsed,
            })

        # 简单差异分析：计算各次输出的字符数差异
        lengths = [len(r["output"]) for r in run_results]
        variation = max(lengths) - min(lengths)

        record = {
            "id": tc["id"],
            "type": tc.get("type", "standard"),
            "input": user_request,
            "city": meta.get("city", ""),
            "days": meta.get("days", 0),
            "budget": meta.get("budget", ""),
            "interests": ",".join(meta.get("interests", [])),
            "group": meta.get("group", ""),
            "special": meta.get("special", ""),
            "runs": run_results,
            "output_lengths": lengths,
            "length_variation": variation,
            "avg_time_s": round(sum(r["time_s"] for r in run_results) / RUNS_PER_CASE, 2),
        }
        json_records.append(record)

        # CSV 每次跑一行
        for r in run_results:
            csv_rows.append({
                "id": tc["id"],
                "type": tc.get("type", ""),
                "input": user_request,
                "city": meta.get("city", ""),
                "days": meta.get("days", 0),
                "budget": meta.get("budget", ""),
                "interests": ",".join(meta.get("interests", [])),
                "run": r["run"],
                "output_length": len(r["output"]),
                "source": r["source"],
                "time_s": r["time_s"],
                "output_preview": r["output"][:300].replace("\n", " "),
                "output_full": r["output"],
            })

    # 保存 JSON（包含完整输出）
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(json_records, f, ensure_ascii=False, indent=2)
    print(f"\nJSON 已保存: {JSON_OUT}")

    # 保存 CSV
    if csv_rows:
        fieldnames = list(csv_rows[0].keys())
        with open(CSV_OUT, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"CSV 已保存: {CSV_OUT}")

    # 统计摘要
    avg_variation = sum(r["length_variation"] for r in json_records) / len(json_records)
    avg_time = sum(r["avg_time_s"] for r in json_records) / len(json_records)
    print(f"\n统计:")
    print(f"   测试用例数: {len(json_records)}")
    print(f"   每用例运行次数: {RUNS_PER_CASE}")
    print(f"   平均响应时间: {avg_time:.1f}s")
    print(f"   平均输出长度变化（非确定性）: {avg_variation:.0f} 字符")
    print(f"\nPhase 2C 提交物已就绪（见 results/ 目录）")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 2C: Goal-Based 多次运行")
    parser.add_argument("--count", type=int, default=20,
                        help="测试用例数量（默认20，每条跑3次）")
    args = parser.parse_args()
    run(args.count)
