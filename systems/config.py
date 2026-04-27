# 系统配置文件
import os

# 基于目标AI系统的配置
GOAL_BASED_CONFIG = {
    # 是否使用真实的LLM API
    "use_real_llm": True, # 改为True，使用真实大模型

    # LLM模型配置
    "model_name": os.getenv("MODEL_NAME", "qwen-plus"), # 从 .env 读取，默认通义千问
    # 可选的通义千问模型:
    # - qwen-plus (均衡，推荐)
    # - qwen-max (旗舰级，效果最好)
    # - qwen-turbo (轻量快速)

    # API提供者标识（用于日志）
    "llm_provider": "qwen",

    # 生成参数（已优化）
    "temperature": 0.75, # 输出随机性 (0-2)，略高以增加内容丰富度
    "max_tokens": 8192,  # 无截断限制，优先输出完整详细内容

    # 是否在API失败时使用模拟输出
    "fallback_to_mock": True # 保留作为备用，确保稳定性
}

# 监督学习系统的配置
SUPERVISED_CONFIG = {
    # 是否使用训练好的模型（model.pkl 存在时自动加载）
    "use_trained_model": True,

    # 模型文件路径
    "model_path": "systems/supervised/model.pkl",

    # 模型类型（VotingClassifier 集成：GBT + RF + ExtraTrees）
    "model_type": "VotingClassifier(GBT+RF+ExtraTrees)",

    # 训练集大小
    "dataset_size": 10000,

    # 推荐类型数量
    "num_classes": 8,
}

# 基于规则系统的配置
RULE_BASED_CONFIG = {
    # 规则库入口
    "rules_file": "systems/rule_based/engine.py",

    # 支持的城市（18个热门目的地）
    "supported_cities": [
        "巴黎", "东京", "纽约", "伦敦", "罗马",
        "悉尼", "巴塞罗那", "曼谷", "新加坡", "首尔",
        "迪拜", "阿姆斯特丹", "维也纳", "布拉格",
        "普吉岛", "马尔代夫", "伊斯坦布尔", "里斯本",
    ],

    # 是否严格模式（不支持的请求返回错误）
    "strict_mode": False,

    # 默认城市（当城市不支持时使用）
    "default_city": "巴黎"
}

# 测试配置
TEST_CONFIG = {
    # 测试用例文件路径
    "test_cases_file": "assets/test_cases.json",

    # 批量测试时每次处理的数量
    "batch_size": 100,

    # 是否保存测试结果
    "save_results": True,

    # 结果保存路径
    "results_dir": "results",

    # 日志级别
    "log_level": "INFO"
}

# 输出配置
OUTPUT_CONFIG = {
    # 是否显示详细输出
    "verbose": True,

    # 输出格式
    "format": "text", # 可选: "text", "json", "markdown"

    # 是否显示处理时间
    "show_timing": True,

    # 是否显示系统元数据
    "show_metadata": True
}
