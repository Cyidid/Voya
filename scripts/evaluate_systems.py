#!/usr/bin/env python3
"""
旅行规划器评估工具
用于评估三种系统的输出质量
"""

import json
from typing import Dict, List, Any
from collections import Counter
import math


class ItineraryEvaluator:
    """行程规划评估器"""

    def __init__(self, test_cases_path: str):
        """初始化评估器"""
        self.test_cases = self._load_test_cases(test_cases_path)

    def _load_test_cases(self, filepath: str) -> List[Dict]:
        """加载测试用例"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def evaluate_system_output(
        self,
        system_name: str,
        outputs: List[Dict]
    ) -> Dict[str, Any]:
        """
        评估系统输出

        Args:
            system_name: 系统名称（如"rule-based", "supervised", "goal-based"）
            outputs: 系统输出列表，每个输出对应一个测试用例

        Returns:
            评估结果字典
        """
        results = {
            "system_name": system_name,
            "total_cases": len(self.test_cases),
            "metrics": {},
            "dimension_scores": {}
        }

        # 确保输出数量匹配
        if len(outputs) != len(self.test_cases):
            print(f"⚠️  警告: 输出数量({len(outputs)})与测试用例数量({len(self.test_cases)})不匹配")
            return results

        # 评估每个维度
        results["dimension_scores"]["user_experience"] = self._evaluate_user_experience(outputs)
        results["dimension_scores"]["fairness"] = self._evaluate_fairness(outputs)
        results["dimension_scores"]["accountability"] = self._evaluate_accountability(system_name)
        results["dimension_scores"]["transparency"] = self._evaluate_transparency(system_name)
        results["dimension_scores"]["robustness"] = self._evaluate_robustness(outputs)

        # 计算综合评分
        results["overall_score"] = self._calculate_overall_score(
            results["dimension_scores"]
        )

        return results

    def _evaluate_user_experience(self, outputs: List[Dict]) -> Dict[str, Any]:
        """评估用户体验维度"""
        scores = []

        for i, output in enumerate(outputs):
            test_case = self.test_cases[i]

            # 1. 输入便利性（模拟评估）
            # 对于规则系统：需要高度结构化输入，便利性低
            # 对于监督学习：可处理自然语言，便利性中等
            # 对于目标AI：完全自然语言，便利性高
            input_score = self._assess_input_convenience(output, test_case)
            scores.append(input_score)

        return {
            "average_score": sum(scores) / len(scores) if scores else 0,
            "details": {
                "input_convenience": scores[0] if scores else 0,
                "response_time": 0.8,  # 模拟数据
                "output_quality": 0.85,  # 模拟数据
                "error_handling": 0.75   # 模拟数据
            }
        }

    def _assess_input_convenience(self, output: Dict, test_case: Dict) -> float:
        """评估输入便利性"""
        # 这里可以根据实际的输入形式评估
        # 目前使用模拟数据
        return 0.75

    def _evaluate_fairness(self, outputs: List[Dict]) -> Dict[str, Any]:
        """评估公平性维度"""
        # 按不同维度分组评估
        budget_groups = {"低": [], "中": [], "高": []}
        interest_groups = {"文化": [], "自然": [], "美食": [], "购物": [], "历史": []}

        for i, output in enumerate(outputs):
            test_case = self.test_cases[i]
            meta = test_case["metadata"]

            # 按预算分组（处理未知值）
            budget = meta.get("budget", "中")
            if budget not in budget_groups:
                budget = "中"  # 默认归为中等预算
            budget_groups[budget].append(output)

            # 按兴趣分组（处理未知值）
            interests = meta.get("interests", [])
            for interest in interests:
                if interest in interest_groups:
                    interest_groups[interest].append(output)

        # 计算各组的质量差异
        budget_variance = self._calculate_group_variance(budget_groups)
        interest_variance = self._calculate_group_variance(interest_groups)

        return {
            "average_score": 1.0 - (budget_variance + interest_variance) / 2,
            "details": {
                "budget_fairness": 1.0 - budget_variance,
                "interest_fairness": 1.0 - interest_variance,
                "group_size_fairness": 0.85  # 模拟数据
            }
        }

    def _calculate_group_variance(self, groups: Dict[str, List]) -> float:
        """计算组间差异（简化版）"""
        # 在实际实现中，这里应该计算各组质量的统计差异
        # 目前使用模拟数据
        return 0.15

    def _evaluate_accountability(self, system_name: str) -> Dict[str, Any]:
        """评估问责性维度"""
        scores = {
            "rule-based": {
                "average_score": 0.9,
                "details": {
                    "designer_responsibility": 1.0,
                    "traceability": 0.95,
                    "error_attribution": 0.85
                }
            },
            "supervised": {
                "average_score": 0.6,
                "details": {
                    "designer_responsibility": 0.7,
                    "traceability": 0.5,
                    "error_attribution": 0.6
                }
            },
            "goal-based": {
                "average_score": 0.3,
                "details": {
                    "designer_responsibility": 0.4,
                    "traceability": 0.2,
                    "error_attribution": 0.3
                }
            }
        }

        return scores.get(system_name, {"average_score": 0.5, "details": {}})

    def _evaluate_transparency(self, system_name: str) -> Dict[str, Any]:
        """评估透明度与可解释性维度"""
        scores = {
            "rule-based": {
                "average_score": 0.95,
                "details": {
                    "user_understanding": 0.95,
                    "debug_ease": 1.0,
                    "decision_clarity": 0.9
                }
            },
            "supervised": {
                "average_score": 0.5,
                "details": {
                    "user_understanding": 0.4,
                    "debug_ease": 0.6,
                    "decision_clarity": 0.5
                }
            },
            "goal-based": {
                "average_score": 0.2,
                "details": {
                    "user_understanding": 0.1,
                    "debug_ease": 0.3,
                    "decision_clarity": 0.2
                }
            }
        }

        return scores.get(system_name, {"average_score": 0.5, "details": {}})

    def _evaluate_robustness(self, outputs: List[Dict]) -> Dict[str, Any]:
        """评估鲁棒性维度"""
        # 按测试用例类型分组评估
        type_scores = {
            "standard": [],
            "boundary": [],
            "edge": []
        }

        for i, output in enumerate(outputs):
            test_case = self.test_cases[i]
            case_type = test_case["type"]

            # 模拟成功率评分
            if case_type == "standard":
                score = 0.9
            elif case_type == "boundary":
                score = 0.7
            else:  # edge
                score = 0.5

            type_scores[case_type].append(score)

        # 计算平均分
        avg_scores = {
            case_type: sum(scores) / len(scores) if scores else 0
            for case_type, scores in type_scores.items()
        }

        return {
            "average_score": sum(avg_scores.values()) / len(avg_scores),
            "details": avg_scores
        }

    def _calculate_overall_score(self, dimension_scores: Dict) -> float:
        """计算综合评分"""
        # 权重：用户体验20%，公平性25%，问责性20%，透明度20%，鲁棒性15%
        weights = {
            "user_experience": 0.20,
            "fairness": 0.25,
            "accountability": 0.20,
            "transparency": 0.20,
            "robustness": 0.15
        }

        total_score = 0
        for dimension, score_data in dimension_scores.items():
            if dimension in weights:
                total_score += score_data["average_score"] * weights[dimension]

        return round(total_score * 100, 2)  # 转换为百分制

    def generate_comparison_report(
        self,
        system_results: List[Dict]
    ) -> str:
        """
        生成比较分析报告

        Args:
            system_results: 多个系统的评估结果列表

        Returns:
            Markdown格式的报告
        """
        report = []
        report.append("# 旅行规划器系统比较分析报告\n")
        report.append(f"测试用例总数: {self.test_cases[0]['id'].split('_')[0] if self.test_cases else 'N/A'}\n")
        report.append("---\n")

        # 生成评分表格
        report.append("## 综合评分对比\n")
        report.append("| 系统 | 综合评分 | 用户体验 | 公平性 | 问责性 | 透明度 | 鲁棒性 |\n")
        report.append("|------|----------|----------|--------|--------|--------|--------|\n")

        for result in system_results:
            system_name = result["system_name"]
            overall = result["overall_score"]
            dims = result["dimension_scores"]

            report.append(f"| {system_name} | {overall:.1f}/100 |")
            for dim_name, dim_data in dims.items():
                score = dim_data["average_score"] * 100
                report.append(f" {score:.0f} |")
            report.append("\n")

        # 详细分析
        report.append("\n## 各维度详细分析\n")

        dimensions = ["user_experience", "fairness", "accountability", "transparency", "robustness"]
        dim_names = {
            "user_experience": "用户体验",
            "fairness": "公平性",
            "accountability": "问责性",
            "transparency": "透明度与可解释性",
            "robustness": "鲁棒性"
        }

        for dim in dimensions:
            report.append(f"### {dim_names[dim]}\n")
            report.append("**核心问题**:\n")

            # 添加维度分析
            if dim == "user_experience":
                report.append("- 输入便利性：用户需要提供多少结构化信息？\n")
                report.append("- 输出质量：行程的实用性和吸引力\n")
                report.append("- 响应速度：系统生成行程的时间\n")
            elif dim == "fairness":
                report.append("- 系统是否对不同用户群体提供同等质量的服务？\n")
                report.append("- 是否存在系统性的偏见？\n")
            elif dim == "accountability":
                report.append("- 如果推荐的行程出现问题，责任由谁承担？\n")
                report.append("- 是否可以追溯决策过程？\n")
            elif dim == "transparency":
                report.append("- 用户能否理解为什么推荐这个行程？\n")
                report.append("- 开发者能否理解和修正问题？\n")
            elif dim == "robustness":
                report.append("- 处理模糊输入的能力\n")
                report.append("- 边界条件下的表现\n")
                report.append("- 新场景的泛化能力\n")

            report.append("\n**各系统表现**:\n")
            for result in system_results:
                system_name = result["system_name"]
                score_data = result["dimension_scores"][dim]
                score = score_data["average_score"] * 100

                # 生成星级
                stars = "⭐" * int(score / 20)

                report.append(f"- **{system_name}**: {score:.0f}/100 {stars}\n")
                if "details" in score_data:
                    for detail_key, detail_value in score_data["details"].items():
                        report.append(f"  - {detail_key}: {detail_value * 100:.0f}%\n")
            report.append("\n")

        # 结论与建议
        report.append("## 结论与建议\n")

        # 找出最佳系统
        best_system = max(system_results, key=lambda x: x["overall_score"])
        report.append(f"**综合最佳**: {best_system['system_name']} ({best_system['overall_score']:.1f}/100)\n\n")

        report.append("### 核心发现\n")
        report.append("1. **用户体验**: 目标AI系统最佳，但缺乏控制和解释\n")
        report.append("2. **公平性**: 规则系统最可控，监督学习取决于数据\n")
        report.append("3. **问责性**: 规则系统责任明确，AI系统责任模糊\n")
        report.append("4. **透明度**: 规则系统完全透明，AI系统是黑盒\n")
        report.append("5. **鲁棒性**: 各有优劣，需根据应用场景选择\n\n")

        report.append("### 推荐方案\n")
        report.append("**混合架构**:\n")
        report.append("- 规则系统作为基础层：确保安全和可解释性\n")
        report.append("- 监督学习作为优化层：提供个性化排序\n")
        report.append("- AI系统作为创意层：生成多样化建议\n\n")

        return "".join(report)


def main():
    """主函数 - 演示评估流程"""
    print("📊 旅行规划器评估工具")
    print("=" * 60)

    # 加载测试用例
    test_cases_path = "/workspace/projects/assets/test_cases.json"
    evaluator = ItineraryEvaluator(test_cases_path)

    # 模拟三个系统的输出（实际使用时替换为真实输出）
    print("\n⚠️  注意：当前使用模拟数据进行演示")
    print("   实际使用时，请替换为真实的系统输出\n")

    # 模拟输出（每个系统对应1000个测试用例）
    mock_outputs = {
        "rule-based": [{"output": f"Rule output for case {i}"} for i in range(1000)],
        "supervised": [{"output": f"ML output for case {i}"} for i in range(1000)],
        "goal-based": [{"output": f"AI output for case {i}"} for i in range(1000)]
    }

    # 评估每个系统
    system_results = []
    for system_name, outputs in mock_outputs.items():
        print(f"🔍 正在评估 {system_name} 系统...")
        result = evaluator.evaluate_system_output(system_name, outputs)
        system_results.append(result)
        print(f"✅ {system_name} 综合评分: {result['overall_score']:.1f}/100\n")

    # 生成比较报告
    print("📝 生成比较报告...")
    report = evaluator.generate_comparison_report(system_results)

    # 保存报告
    report_path = "/workspace/projects/assets/comparison_report.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"✅ 报告已保存到: {report_path}\n")

    # 打印报告摘要
    print("=" * 60)
    print("📊 评估结果摘要")
    print("=" * 60)
    for result in system_results:
        print(f"\n{result['system_name']}: {result['overall_score']:.1f}/100")
        for dim_name, dim_data in result["dimension_scores"].items():
            print(f"  - {dim_name}: {dim_data['average_score'] * 100:.0f}%")

    print("\n" + "=" * 60)
    print("💡 提示：请查看完整的对比报告以获取详细分析")
    print("=" * 60)


if __name__ == "__main__":
    main()
