#!/usr/bin/env python3
"""
测试用例生成器
用于生成1000+个旅行行程规划器的测试用例
"""

import os
import json
import random
from typing import List, Dict
from itertools import product

class TestCaseGenerator:
    """旅行规划器测试用例生成器"""

    def __init__(self):
        # 定义测试变量的选项
        self.cities = ["巴黎", "东京", "纽约", "伦敦", "罗马"]
        self.days = [1, 2, 3, 5, 7]
        self.budget_levels = ["低", "中", "高"]
        self.interests_list = {
            "文化": ["博物馆", "艺术", "历史遗迹"],
            "自然": ["公园", "花园", "自然景观"],
            "美食": ["当地特色菜", "米其林餐厅", "街头小吃"],
            "购物": ["购物中心", "特色商店", "奢侈品"],
            "历史": ["古建筑", "历史街区", "纪念碑"]
        }
        self.group_types = ["单人", "情侣", "家庭", "朋友"]
        self.special_needs = ["无", "有儿童", "有老人", "轮椅友好"]

    def generate_standard_cases(self, count: int = 700) -> List[Dict]:
        """
        生成标准测试用例
        覆盖常见的用户需求组合
        """
        cases = []

        for i in range(count):
            case = {
                "id": f"S{i+1:04d}",
                "type": "standard",
                "input": self._generate_natural_request(
                    random.choice(self.cities),
                    random.choice(self.days),
                    random.choice(self.budget_levels),
                    self._generate_interests(random.choice([1, 2])),
                    random.choice(self.group_types),
                    random.choice(self.special_needs)
                ),
                "metadata": {
                    "city": random.choice(self.cities),
                    "days": random.choice(self.days),
                    "budget": random.choice(self.budget_levels),
                    "interests": self._generate_interests(random.choice([1, 2])),
                    "group": random.choice(self.group_types),
                    "special": random.choice(self.special_needs)
                }
            }
            cases.append(case)

        return cases

    def generate_boundary_cases(self, count: int = 200) -> List[Dict]:
        """
        生成边界测试用例
        测试极端条件和边界值
        """
        cases = []

        # 极端天数组合
        boundary_days = [1, 7]  # 最短和最长

        for i in range(count):
            days = random.choice(boundary_days)
            # 边界用例通常伴随低预算
            budget = "低" if days == 1 else random.choice(self.budget_levels)

            case = {
                "id": f"B{i+1:04d}",
                "type": "boundary",
                "input": self._generate_natural_request(
                    random.choice(self.cities),
                    days,
                    budget,
                    self._generate_interests(1),  # 单一兴趣
                    random.choice(self.group_types),
                    random.choice(self.special_needs)
                ),
                "metadata": {
                    "city": random.choice(self.cities),
                    "days": days,
                    "budget": budget,
                    "interests": self._generate_interests(1),
                    "group": random.choice(self.group_types),
                    "special": random.choice(self.special_needs),
                    "boundary_condition": f"extreme_days={days}"
                }
            }
            cases.append(case)

        return cases

    def generate_edge_cases(self, count: int = 100) -> List[Dict]:
        """
        生成异常/边缘测试用例
        测试模糊请求、冲突偏好等
        """
        edge_scenarios = [
            {
                "scenario_name": "模糊兴趣",
                "city": "巴黎",
                "days": 3,
                "budget": "中",
                "interests": ["什么都想看看"],
                "group": "单人",
                "special": "无"
            },
            {
                "scenario_name": "冲突预算",
                "city": "东京",
                "days": 5,
                "budget": "低",
                "interests": ["奢华体验", "米其林餐厅"],
                "group": "情侣",
                "special": "无"
            },
            {
                "scenario_name": "极端时间",
                "city": "纽约",
                "days": 1,
                "budget": "高",
                "interests": ["文化", "美食", "购物", "历史"],  # 4个兴趣
                "group": "单人",
                "special": "无"
            },
            {
                "scenario_name": "模糊预算",
                "city": "伦敦",
                "days": 3,
                "budget": "不太确定",
                "interests": ["文化"],
                "group": "朋友",
                "special": "无"
            },
            {
                "scenario_name": "多重特殊需求",
                "city": "罗马",
                "days": 4,
                "budget": "中",
                "interests": ["历史"],
                "group": "家庭",
                "special": "有儿童和老人"
            }
        ]

        cases = []
        for i in range(count):
            scenario = random.choice(edge_scenarios)
            case = {
                "id": f"E{i+1:04d}",
                "type": "edge",
                "input": self._generate_natural_request(
                    scenario["city"],
                    scenario["days"],
                    scenario["budget"],
                    scenario["interests"],
                    scenario["group"],
                    scenario["special"]
                ),
                "metadata": {
                    "city": scenario["city"],
                    "days": scenario["days"],
                    "budget": scenario["budget"],
                    "interests": scenario["interests"],
                    "group": scenario["group"],
                    "special": scenario["special"],
                    "edge_condition": scenario["scenario_name"]
                }
            }
            cases.append(case)

        return cases

    def _generate_interests(self, num_interests: int) -> List[str]:
        """生成兴趣组合"""
        available = list(self.interests_list.keys())
        selected = random.sample(available, min(num_interests, len(available)))
        return selected

    def _generate_natural_request(
        self,
        city: str,
        days: int,
        budget: str,
        interests: List[str],
        group_type: str,
        special_needs: str
    ) -> str:
        """生成自然语言形式的请求"""
        request_parts = []

        # 城市和天数
        request_parts.append(f"我想去{city}玩{days}天")

        # 群体类型
        if group_type == "情侣":
            request_parts.append("，和爱人一起")
        elif group_type == "家庭":
            request_parts.append("，和家人一起")
        elif group_type == "朋友":
            request_parts.append("，和朋友一起")
        # 单人不特别说明

        # 兴趣
        if interests:
            interest_desc = "、".join(interests)
            request_parts.append(f"，我们喜欢{interest_desc}")

        # 预算
        if budget == "低":
            request_parts.append("，预算比较有限")
        elif budget == "中":
            request_parts.append("，预算中等")
        elif budget == "高":
            request_parts.append("，预算比较宽裕")
        else:
            request_parts.append(f"，{budget}")

        # 特殊需求
        if special_needs == "有儿童":
            request_parts.append("，有小孩子")
        elif special_needs == "有老人":
            request_parts.append("，有老人")
        elif special_needs == "轮椅友好":
            request_parts.append("，需要轮椅无障碍设施")

        request_parts.append("。")

        return "".join(request_parts)

    def generate_all_cases(self) -> List[Dict]:
        """生成所有测试用例（1000+个）"""
        standard = self.generate_standard_cases(700)
        boundary = self.generate_boundary_cases(200)
        edge = self.generate_edge_cases(100)

        all_cases = standard + boundary + edge

        # 打乱顺序以避免系统偏差
        random.shuffle(all_cases)

        return all_cases

    def save_to_file(self, cases: List[Dict], filepath: str):
        """保存测试用例到JSON文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(cases, f, ensure_ascii=False, indent=2)

        print(f"✅ 已生成 {len(cases)} 个测试用例")
        print(f"📁 保存到: {filepath}")

        # 打印统计信息
        type_counts = {}
        for case in cases:
            case_type = case["type"]
            type_counts[case_type] = type_counts.get(case_type, 0) + 1

        print("\n📊 测试用例统计:")
        for case_type, count in type_counts.items():
            print(f"  - {case_type}: {count} 个")


def main():
    """主函数"""
    print("🧪 旅行规划器测试用例生成器")
    print("=" * 60)

    generator = TestCaseGenerator()
    cases = generator.generate_all_cases()

    # 保存到文件
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_file = os.path.join(base_dir, "assets", "test_cases.json")
    generator.save_to_file(cases, output_file)

    # 生成CSV格式（便于查看）
    csv_file = os.path.join(base_dir, "assets", "test_cases.csv")
    with open(csv_file, 'w', encoding='utf-8') as f:
        f.write("ID,Type,Input,City,Days,Budget,Interests,Group,Special\n")
        for case in cases:
            meta = case["metadata"]
            interests_str = ";".join(meta["interests"])
            line = f"{case['id']},{case['type']},{case['input']}," \
                   f"{meta['city']},{meta['days']},{meta['budget']}," \
                   f"{interests_str},{meta['group']},{meta['special']}\n"
            f.write(line)

    print(f"📁 CSV格式保存到: {csv_file}")


if __name__ == "__main__":
    main()
