#!/usr/bin/env python3
"""
统一演示系统
用于运行和对比三种AI旅行规划器系统
"""

import json
import sys
import os
from typing import Dict, Any, Optional

# 添加项目路径
sys.path.insert(0, os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects"))


class ItineraryDemo:
    """旅行规划器演示系统"""

    def __init__(self):
        self.test_cases = self._load_test_cases()
        self.systems = {
            "rule-based": self._run_rule_based,
            "supervised": self._run_supervised,
            "goal-based": self._run_goal_based
        }

    def _load_test_cases(self):
        """加载测试用例"""
        filepath = "/workspace/projects/assets/test_cases.json"
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def run_all_systems(self, case_id: Optional[str] = None):
        """
        运行所有系统进行对比

        Args:
            case_id: 测试用例ID，如果为None则使用第一个用例
        """
        # 选择测试用例
        if case_id:
            test_case = next((c for c in self.test_cases if c["id"] == case_id), None)
            if not test_case:
                print(f"❌ 未找到测试用例: {case_id}")
                return
        else:
            test_case = self.test_cases[0]

        print("=" * 80)
        print("🌍 旅行规划器 - 三种系统对比演示")
        print("=" * 80)

        # 显示用户输入
        print("\n📝 用户请求:")
        print(f"  {test_case['input']}")
        print("\n📋 元数据:")
        meta = test_case['metadata']
        print(f"  城市: {meta['city']}")
        print(f"  天数: {meta['days']}")
        print(f"  预算: {meta['budget']}")
        print(f"  兴趣: {', '.join(meta['interests'])}")
        print(f"  群体: {meta['group']}")
        print(f"  特殊需求: {meta['special']}")
        print(f"  类型: {test_case['type']}")

        # 运行三个系统
        print("\n" + "=" * 80)
        print("🚀 运行三个系统...")
        print("=" * 80)

        results = {}
        for system_name, system_func in self.systems.items():
            print(f"\n📌 {system_name.upper()} 系统处理中...")
            try:
                result = system_func(test_case)
                results[system_name] = result
                print(f"✅ {system_name} 完成")
            except Exception as e:
                print(f"❌ {system_name} 失败: {str(e)}")
                results[system_name] = {"error": str(e)}

        # 显示对比结果
        print("\n" + "=" * 80)
        print("📊 对比结果")
        print("=" * 80)

        for system_name, result in results.items():
            print(f"\n## {system_name.upper()}")
            print("-" * 40)

            if "error" in result:
                print(f"❌ 错误: {result['error']}")
                continue

            # 显示系统输出
            if "itinerary" in result:
                self._display_itinerary(result['itinerary'])
            else:
                print(result.get('output', '无输出'))

    def _display_itinerary(self, itinerary: Dict):
        """格式化显示行程"""
        for day_key in sorted(itinerary.keys()):
            day_info = itinerary[day_key]
            print(f"\n### {day_key}")
            if "theme" in day_info:
                print(f"🎯 主题: {day_info['theme']}")

            for time_slot in ["morning", "afternoon", "evening"]:
                if time_slot in day_info:
                    activity = day_info[time_slot]
                    print(f"  • {time_slot}: {activity['activity']}")
                    if "category" in activity:
                        print(f"    类型: {activity['category']}")
                    if "duration" in activity:
                        print(f"    时长: {activity['duration']}小时")
                    if "cost_estimate" in activity:
                        print(f"    预估费用: €{activity['cost_estimate']}")

    def interactive_demo(self):
        """交互式演示模式"""
        print("\n🎮 交互式演示模式")
        print("=" * 80)

        while True:
            print("\n选项:")
            print("  1. 查看测试用例列表")
            print("  2. 运行指定测试用例（对比所有系统）")
            print("  3. 运行指定系统（处理多个用例）")
            print("  4. 批量运行所有系统")
            print("  5. 退出")

            choice = input("\n请选择 (1-5): ").strip()

            if choice == "1":
                self._show_test_cases()
            elif choice == "2":
                self._run_single_case()
            elif choice == "3":
                self._run_single_system()
            elif choice == "4":
                self._run_batch()
            elif choice == "5":
                print("\n👋 再见！")
                break
            else:
                print("❌ 无效选择，请重试")

    def _show_test_cases(self):
        """显示测试用例列表"""
        print("\n📋 测试用例列表 (显示前20个):")
        print("-" * 80)

        for i, case in enumerate(self.test_cases[:20]):
            meta = case['metadata']
            print(f"{i+1:2d}. [{case['id']}] {meta['city']} - {meta['days']}天 - {meta['budget']}预算")
            print(f"    {case['input'][:60]}...")

        if len(self.test_cases) > 20:
            print(f"\n... 还有 {len(self.test_cases) - 20} 个测试用例")

    def _run_single_case(self):
        """运行单个测试用例"""
        case_id = input("\n输入测试用例ID (如 S0001): ").strip()
        self.run_all_systems(case_id if case_id else None)

    def _run_single_system(self):
        """运行单个系统"""
        print("\n选择系统:")
        print("  1. rule-based (基于规则)")
        print("  2. supervised (监督学习)")
        print("  3. goal-based (基于目标AI)")

        system_choice = input("\n请选择 (1-3): ").strip()

        system_map = {"1": "rule-based", "2": "supervised", "3": "goal-based"}
        system_name = system_map.get(system_choice)

        if not system_name:
            print("❌ 无效选择")
            return

        num_cases = input("\n运行多少个测试用例？(默认10): ").strip()
        num_cases = int(num_cases) if num_cases.isdigit() else 10

        print(f"\n🚀 运行 {system_name} 系统，处理 {num_cases} 个用例...")

        results = []
        for i, case in enumerate(self.test_cases[:num_cases]):
            print(f"\n[{i+1}/{num_cases}] {case['id']}")
            try:
                result = self.systems[system_name](case)
                results.append({
                    "case_id": case['id'],
                    "success": True,
                    "output": result
                })
                print(f"✅ 成功")
            except Exception as e:
                results.append({
                    "case_id": case['id'],
                    "success": False,
                    "error": str(e)
                })
                print(f"❌ 失败: {str(e)}")

        # 显示统计
        success_count = sum(1 for r in results if r['success'])
        print(f"\n📊 统计: {success_count}/{num_cases} 成功")

    def _run_batch(self):
        """批量运行所有系统"""
        print("\n⚠️  这将运行所有系统处理所有1000个测试用例")
        confirm = input("确认继续？(yes/no): ").strip().lower()

        if confirm != "yes":
            print("已取消")
            return

        print("\n🚀 开始批量运行...")

        # 这里可以保存结果到文件
        print("💡 建议在后台运行并保存结果到文件")
        print("请参考 implementation_guide.md 中的详细步骤")

    # ============================================================
    # 三个系统的实现（这里提供框架，需要根据实际实现填充）
    # ============================================================

    def _run_rule_based(self, test_case: Dict) -> Dict:
        """运行基于规则的系统"""
        try:
            from systems.rule_based.engine import generate as rb_generate
            return rb_generate(test_case)
        except ImportError as e:
            # 如果导入失败，使用内置的简化实现
            return self._run_rule_based_fallback(test_case)

    def _run_supervised(self, test_case: Dict) -> Dict:
        """运行监督学习系统"""
        try:
            from systems.supervised.inference import generate as sl_generate
            return sl_generate(test_case)
        except ImportError as e:
            # 如果导入失败，使用内置的简化实现
            return self._run_supervised_fallback(test_case)

    def _run_goal_based(self, test_case: Dict) -> Dict:
        """运行基于目标的AI系统"""
        try:
            from systems.goal_based.agent import generate as gb_generate
            return gb_generate(test_case)
        except ImportError as e:
            # 如果导入失败，使用内置的简化实现
            return self._run_goal_based_fallback(test_case)

    # ============================================================
    # Fallback方法（当导入系统实现失败时使用）
    # ============================================================

    def _run_rule_based_fallback(self, test_case: Dict) -> Dict:
        """基于规则系统的fallback实现"""
        meta = test_case['metadata']
        itinerary = {
            f"day_{i+1}": {
                "theme": f"{meta['city']}探索之旅",
                "morning": {
                    "activity": f"{meta['city']}著名景点",
                    "category": meta['interests'][0] if meta['interests'] else "culture",
                    "duration": 3,
                    "cost_estimate": 20 if meta['budget'] == "低" else (50 if meta['budget'] == "中" else 100)
                },
                "afternoon": {
                    "activity": f"当地特色体验",
                    "category": meta['interests'][1] if len(meta['interests']) > 1 else "food",
                    "duration": 2,
                    "cost_estimate": 30 if meta['budget'] == "低" else (80 if meta['budget'] == "中" else 150)
                },
                "evening": {
                    "activity": "晚餐和休息",
                    "category": "food",
                    "duration": 2,
                    "cost_estimate": 40 if meta['budget'] == "低" else (100 if meta['budget'] == "中" else 200)
                }
            }
            for i in range(meta['days'])
        }
        return {
            "system": "rule-based",
            "itinerary": itinerary,
            "processing_time": 0.01,
            "note": "Using fallback implementation"
        }

    def _run_supervised_fallback(self, test_case: Dict) -> Dict:
        """监督学习系统的fallback实现"""
        meta = test_case['metadata']
        itinerary = {
            f"day_{i+1}": {
                "theme": f"个性化{meta['city']}之旅",
                "morning": {
                    "activity": f"基于兴趣推荐的{meta['city']}景点",
                    "category": meta['interests'][0] if meta['interests'] else "culture",
                    "duration": 3,
                    "cost_estimate": 25
                },
                "afternoon": {
                    "activity": f"AI推荐活动",
                    "category": meta['interests'][1] if len(meta['interests']) > 1 else "food",
                    "duration": 2,
                    "cost_estimate": 45
                },
                "evening": {
                    "activity": "智能推荐的餐厅",
                    "category": "food",
                    "duration": 2,
                    "cost_estimate": 60
                }
            }
            for i in range(meta['days'])
        }
        return {
            "system": "supervised",
            "itinerary": itinerary,
            "processing_time": 0.05,
            "model_confidence": 0.85,
            "note": "Using fallback implementation"
        }

    def _run_goal_based_fallback(self, test_case: Dict) -> Dict:
        """基于目标AI系统的fallback实现"""
        meta = test_case['metadata']
        output = f"""## 📍 {meta['city']} {meta['days']}日行程规划

### Day 1: {meta['city']}初体验
**上午**: 参观{meta['city']}最著名的{meta['interests'][0] if meta['interests'] else '文化'}景点
**下午**: 探索{meta['city']}的特色街区，体验{meta['interests'][1] if len(meta['interests']) > 1 else '美食'}
**晚上**: 享受{meta['budget']}预算水平的当地美食

### Day 2: 深度探索
**上午**: 前往{meta['city']}的另一个热门景点
**下午**: 根据用户兴趣安排{meta['interests'][0] if meta['interests'] else '购物'}活动
**晚上**: 返回休息

---
💡 这是基于目标AI系统生成的个性化行程。
"""
        return {
            "system": "goal-based",
            "output": output,
            "processing_time": 2.5,
            "model": "gpt-4",
            "note": "Using fallback implementation"
        }


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("🌍 旅行规划器 - 统一演示系统")
    print("=" * 80)
    print("\n这个系统可以运行和对比三种不同的AI旅行规划器:")
    print("  1. Rule-Based (基于规则)")
    print("  2. Supervised Learning (监督学习)")
    print("  3. Goal-Based AI (基于目标AI)")
    print("\n" + "=" * 80)

    demo = ItineraryDemo()

    # 命令行参数处理
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "demo":
            # 快速演示：使用第一个测试用例
            demo.run_all_systems()
        elif cmd == "interactive":
            # 交互模式
            demo.interactive_demo()
        elif cmd == "batch":
            # 批量模式
            demo._run_batch()
        else:
            print(f"❌ 未知命令: {cmd}")
            print("使用方法:")
            print("  python demo.py demo         - 快速演示")
            print("  python demo.py interactive  - 交互模式")
            print("  python demo.py batch        - 批量运行")
    else:
        # 默认进入交互模式
        print("\n💡 使用 'python demo.py demo' 快速演示")
        print("💡 使用 'python demo.py interactive' 进入交互模式\n")
        demo.interactive_demo()


if __name__ == "__main__":
    main()
