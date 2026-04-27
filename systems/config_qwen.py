# 阿里通义千问模型专用配置

# 基于目标AI系统的配置
GOAL_BASED_CONFIG = {
    # 是否使用真实的LLM API
    "use_real_llm": True,

    # 使用阿里通义千问模型
    "model_name": "qwen-3-5-plus-260215",

    # 提供者
    "llm_provider": "qwen",

    # 模型完整名称（用于显示）
    "model_full_name": "通义千问 Qwen 3.5 Plus",

    # 生成参数
    "temperature": 0.7,
    "max_tokens": 2000,

    # 是否在API失败时使用模拟输出
    "fallback_to_mock": True
}

# 监督学习系统的配置
SUPERVISED_CONFIG = {
    "use_trained_model": False,
    "model_path": "systems/supervised/model.pkl",
    "model_type": "random_forest",
    "use_mock_prediction": True
}

# 基于规则系统的配置
RULE_BASED_CONFIG = {
    "rules_file": "systems/rule_based/rules.py",
    "supported_cities": [
        "巴黎", "东京", "纽约", "伦敦", "罗马", "杭州", "北京", "上海"
    ],
    "strict_mode": False,
    "default_city": "巴黎"
}

# 测试配置
TEST_CONFIG = {
    "test_cases_file": "assets/test_cases.json",
    "batch_size": 100,
    "save_results": True,
    "results_dir": "results",
    "log_level": "INFO"
}

# 输出配置
OUTPUT_CONFIG = {
    "verbose": True,
    "format": "text",
    "show_timing": True,
    "show_metadata": True
}
