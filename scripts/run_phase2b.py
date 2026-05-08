#!/usr/bin/env python3
"""
Phase 2B：Supervised System 批量测试
先训练模型（10000条数据集），再运行全部测试用例记录 inputs/outputs。
提交物：results/phase2b_outputs.csv + results/phase2b_outputs.json
         systems/supervised/training_dataset.json（训练数据集）
         systems/supervised/model.pkl（训练好的模型）
"""

import os
import sys
import json
import csv
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from systems.supervised.inference import SupervisedEngine, generate

TEST_CASES_FILE = os.path.join(BASE_DIR, "assets", "test_cases.json")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
CSV_OUT = os.path.join(RESULTS_DIR, "phase2b_outputs.csv")
JSON_OUT = os.path.join(RESULTS_DIR, "phase2b_outputs.json")


def run():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print("Phase 2B: Supervised System 批量测试")
    print("-" * 40)

    # 初始化引擎（会自动训练并保存模型）
    engine = SupervisedEngine()
    print(f"\n模型准确率: {engine.model_accuracy:.1%}")
    print(f"Top 特征重要性: {engine.feature_importances}")

    with open(TEST_CASES_FILE, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    print(f"\n开始测试 {len(test_cases)} 条用例...")

    records = []

    for i, tc in enumerate(test_cases):
        t0 = time.time()
        result = engine.generate_itinerary(tc)
        elapsed = round(time.time() - t0, 4)

        meta = tc["metadata"]
        top_f = result.get("top_features", [])
        top_f_str = "; ".join(f"{name}={score}" for name, score in top_f)

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
            "prediction_type": result.get("recommendation_type_zh", ""),
            "model_confidence": result.get("model_confidence", 0),
            "top_features": top_f_str,
            "total_budget": result.get("total_budget_estimate", 0),
            "model_accuracy": result.get("model_accuracy", 0),
            "processing_time_s": elapsed,
        }
        records.append(record)

        if (i + 1) % 100 == 0:
            print(f"  已处理 {i+1}/{len(test_cases)} 条")

    # 保存 JSON
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"\nJSON 已保存: {JSON_OUT}")

    # 保存 CSV
    fieldnames = list(records[0].keys())
    with open(CSV_OUT, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    print(f"CSV 已保存: {CSV_OUT}")

    # 统计
    avg_time = sum(r["processing_time_s"] for r in records) / len(records)
    type_dist = _count(records, "prediction_type")
    print(f"\n统计:")
    print(f"   总用例数: {len(records)}")
    print(f"   平均响应时间: {avg_time*1000:.1f}ms")
    print(f"   推荐类型分布: {type_dist}")
    print(f"\n训练数据集: systems/supervised/training_dataset.json")
    print(f"训练好的模型: systems/supervised/model.pkl")


def _count(records, key):
    counts = {}
    for r in records:
        v = str(r.get(key, ""))
        counts[v] = counts.get(v, 0) + 1
    return counts


if __name__ == "__main__":
    run()
