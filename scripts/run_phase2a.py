#!/usr/bin/env python3
"""
Phase 2A：Rule-Based System 批量测试
运行全部 1000 条测试用例，将 inputs/outputs 记录到 CSV 和 JSON。
提交物：results/phase2a_outputs.csv + results/phase2a_outputs.json
"""

import os
import sys
import json
import csv
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from systems.rule_based.engine import generate as rule_based_generate

TEST_CASES_FILE = os.path.join(BASE_DIR, "assets", "test_cases.json")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
CSV_OUT = os.path.join(RESULTS_DIR, "phase2a_outputs.csv")
JSON_OUT = os.path.join(RESULTS_DIR, "phase2a_outputs.json")


def format_itinerary(result: dict) -> str:
    """将行程结果格式化为可读文本"""
    lines = []
    meta = result.get("metadata", {})
    lines.append(f"[{meta.get('city', '')} {meta.get('days', '')}天 "
                 f"预算:{meta.get('budget', '')} 兴趣:{','.join(meta.get('interests', []))}]")
    itinerary = result.get("itinerary", "")
    if isinstance(itinerary, str):
        lines.append(itinerary)
    lines.append(f"  预算合计: ¥{result.get('total_budget_estimate', 0)}")
    return "\n".join(lines)


def run():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print("=" * 60)
    print("Phase 2A: Rule-Based System 批量测试")
    print("=" * 60)

    with open(TEST_CASES_FILE, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    print(f"📋 加载测试用例: {len(test_cases)} 条")

    records = []
    csv_rows = []

    for i, tc in enumerate(test_cases):
        t0 = time.time()
        result = rule_based_generate(tc)
        elapsed = round(time.time() - t0, 4)

        meta = tc["metadata"]
        output_text = format_itinerary(result)

        record = {
            "id": tc["id"],
            "type": tc.get("type", "standard"),
            "input": tc["input"],
            "city": meta.get("city", ""),
            "days": meta.get("days", 0),
            "budget": meta.get("budget", ""),
            "interests": ",".join(meta.get("interests", [])),
            "group": meta.get("group", ""),
            "special": meta.get("special", ""),
            "recommendation": result.get("city_used", ""),
            "total_budget": result.get("total_budget_estimate", 0),
            "output_summary": output_text,
            "processing_time_s": elapsed,
        }
        records.append(record)
        csv_rows.append(record)

        if (i + 1) % 100 == 0:
            print(f"  ✅ 已处理 {i+1}/{len(test_cases)} 条")

    # 保存 JSON
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"\n💾 JSON 已保存: {JSON_OUT}")

    # 保存 CSV
    fieldnames = list(csv_rows[0].keys())
    with open(CSV_OUT, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"💾 CSV 已保存: {CSV_OUT}")

    # 统计
    avg_time = sum(r["processing_time_s"] for r in records) / len(records)
    print(f"\n📊 统计:")
    print(f"   总用例数: {len(records)}")
    print(f"   平均响应时间: {avg_time*1000:.1f}ms")
    print(f"   城市分布: {_count(records, 'city')}")
    print(f"   预算分布: {_count(records, 'budget')}")


def _count(records, key):
    counts = {}
    for r in records:
        v = r.get(key, "")
        counts[v] = counts.get(v, 0) + 1
    return counts


if __name__ == "__main__":
    run()
