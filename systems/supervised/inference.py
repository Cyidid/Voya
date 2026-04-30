"""
监督学习行程规划引擎（推理模块）
使用 sklearn VotingClassifier（集成学习）训练真实模型
训练数据：10000 条专家标注数据（程序生成）
"""

import os
import json
import pickle
import random
import logging

logger = logging.getLogger(__name__)
import numpy as np
from typing import Optional, List, Tuple

try:
    from sklearn.ensemble import (
        GradientBoostingClassifier,
        RandomForestClassifier,
        ExtraTreesClassifier,
        VotingClassifier,
    )
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("sklearn 未安装，请运行: pip install scikit-learn")

# 推荐类型定义
RECOMMENDATION_TYPES = {
    0: "budget_sightseeing", # 经济观光
    1: "cultural_deep_dive", # 文化深度游
    2: "luxury_experience", # 奢华体验
    3: "family_friendly", # 亲子家庭
    4: "foodie_adventure", # 美食购物
    5: "adventure_outdoor", # 户外探险
    6: "romantic_couple", # 情侣浪漫
    7: "group_social", # 团队社交
}

RECOMMENDATION_LABELS_ZH = {
    0: "经济观光",
    1: "文化深度游",
    2: "奢华体验",
    3: "亲子家庭游",
    4: "美食购物游",
    5: "户外探险游",
    6: "情侣浪漫游",
    7: "团队社交游",
}

#  特征列表（用于可解释性）
FEATURE_NAMES = [
    "days", "budget_level", "num_people", "group_type",
    "has_special", "travel_mode",
    "interest_culture", "interest_nature", "interest_food",
    "interest_shopping", "interest_history", "interest_nightlife", "interest_outdoor",
    "city_paris", "city_tokyo", "city_newyork", "city_london", "city_rome",
    "city_seoul", "city_dubai",
]

FEATURE_NAMES_ZH = {
    "days": "旅行天数",
    "budget_level": "预算等级",
    "num_people": "出行人数",
    "group_type": "出行类型",
    "has_special": "特殊需求",
    "travel_mode": "出行方式",
    "interest_culture": "文化兴趣",
    "interest_nature": "自然兴趣",
    "interest_food": "美食兴趣",
    "interest_shopping": "购物兴趣",
    "interest_history": "历史兴趣",
    "interest_nightlife": "夜生活兴趣",
    "interest_outdoor": "户外兴趣",
    "city_paris": "城市=巴黎",
    "city_tokyo": "城市=东京",
    "city_newyork": "城市=纽约",
    "city_london": "城市=伦敦",
    "city_rome": "城市=罗马",
    "city_seoul": "城市=首尔",
    "city_dubai": "城市=迪拜",
}

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")
DATASET_PATH = os.path.join(os.path.dirname(__file__), "training_dataset.json")

CITY_DAILY_BUDGET = {
    "巴黎": {"低": 500, "中": 1200, "高": 3500}, "东京": {"低": 400, "中": 900, "高": 2800},
    "纽约": {"低": 550, "中": 1300, "高": 3800}, "伦敦": {"低": 520, "中": 1200, "高": 3500},
    "罗马": {"低": 450, "中": 1000, "高": 3000}, "悉尼": {"低": 450, "中": 1000, "高": 3000},
    "巴塞罗那": {"低": 380, "中": 850, "高": 2600}, "曼谷": {"低": 180, "中": 450, "高": 1500},
    "新加坡": {"低": 380, "中": 900, "高": 2800}, "首尔": {"低": 280, "中": 650, "高": 2000},
    "迪拜": {"低": 450, "中": 1200, "高": 4000}, "阿姆斯特丹": {"低": 520, "中": 1100, "高": 3200},
    "维也纳": {"低": 450, "中": 1000, "高": 3000}, "布拉格": {"低": 250, "中": 600, "高": 1800},
    "普吉岛": {"低": 180, "中": 450, "高": 1600}, "马尔代夫": {"低": 600, "中": 1800, "高": 6000},
    "伊斯坦布尔": {"低": 220, "中": 550, "高": 1800}, "里斯本": {"低": 300, "中": 750, "高": 2200},
    "大阪": {"低": 380, "中": 850, "高": 2600}, "京都": {"低": 350, "中": 800, "高": 2400},
    "广州": {"低": 150, "中": 380, "高": 1200}, "开罗": {"低": 120, "中": 350, "高": 1200},
    "哥本哈根": {"低": 600, "中": 1400, "高": 4200}, "苏黎世": {"低": 700, "中": 1600, "高": 4800},
    "巴厘岛": {"低": 150, "中": 400, "高": 1400},
}

# 城市 × 推荐类型 → 具体真实景点
CITY_TYPE_ACTIVITIES = {
    "东京": {
        1: {
            "mornings": [
                ("东京国立博物馆", "上野公园内的日本最大综合性博物馆，馆藏11万件国宝级文物"),
                ("浅草寺·雷门", "东京最古老的寺庙，仲见世通商业街淘和果子伴手礼"),
                ("根津美术馆", "隈研吾设计的竹林步道庭院，禅意与艺术的完美结合"),
                ("江户东京博物馆", "实景还原江户时代街景，沉浸式体验日本历史"),
            ],
            "afternoons": [
                ("上野公园漫步", "博物馆西侧的百年公园，樱花季和红叶季美不胜收"),
                ("根津神社·千本鸟居", "隐藏在居民区的神社，迷你版伏见稻荷大社"),
                ("谷中银座商店街", "下町风情的百年老街，可乐饼和烤团子必吃"),
            ],
        },
        3: {
            "mornings": [
                ("台场TeamLab Borderless", "全球最大沉浸式数字艺术馆，孩子可以触摸光影互动"),
                ("上野动物园", "亚洲现存最古老的动物园，大熊猫'香香'是人气明星"),
                ("东京迪士尼乐园", "全球唯一拥有海洋和陆地两大主题园区的迪士尼"),
            ],
            "afternoons": [
                ("台场海滨公园", "自由女神像前拍全家福，彩虹大桥海景尽收眼底"),
                ("葛西临海水族馆", "金枪鱼大水槽和企鹅漫步，孩子最爱的水族馆"),
            ],
        },
        5: {
            "mornings": [
                ("高尾山徒步", "东京近郊最热门登山路线，山顶可远眺富士山"),
                ("多摩川骑行", "沿河岸骑行30km，春天樱花隧道美不胜收"),
                ("箱根温泉徒步", "穿越箱根国立公园原始林道，徒步后泡露天温泉"),
            ],
            "afternoons": [
                ("奥多摩湖皮划艇", "在东京最清澈的高山湖泊划独木舟"),
                ("御岳溪谷溯溪", "东京都内难得的溯溪体验，夏季避暑首选"),
            ],
        },
    },
    "巴黎": {
        1: {
            "mornings": [
                ("卢浮宫深度参观", "世界最大博物馆，蒙娜丽莎、断臂维纳斯必看馆藏"),
                ("奥赛博物馆", "印象派殿堂，莫奈睡莲、梵高星空尽收眼底"),
                ("蓬皮杜艺术中心", "当代艺术旗舰展馆，顶层餐厅俯瞰巴黎全景"),
                ("玛黑区文艺复兴馆", "雨果故居博物馆，隐藏的文艺复兴庭院"),
            ],
            "afternoons": [
                ("拉丁区漫步", "先贤祠到莎士比亚书店的文学朝圣之路"),
                ("蒙马特画家广场", "小丘广场看街头画家写生，圣心堂俯瞰全城"),
                ("杜乐丽花园", "卢浮宫与协和广场之间的皇家花园"),
            ],
        },
        3: {
            "mornings": [
                ("巴黎迪士尼乐园", "欧洲唯一迪士尼，睡美人城堡和加勒比海盗必玩"),
                ("卢森堡公园木马", "百年旋转木马+帆船池，巴黎人周末遛娃首选"),
                ("自然历史博物馆", "大画廊的恐龙化石和进化馆让孩子大开眼界"),
            ],
            "afternoons": [
                ("凡尔赛宫花园", "法式园林巅峰，镜宫和小特里亚农宫漫步"),
                ("科学工业城", "欧洲最大科技馆，潜艇实体和互动实验室超好玩"),
            ],
        },
        5: {
            "mornings": [
                ("凡尔赛宫花园骑行", "租自行车穿越法式园林，镜宫和大运河不可错过"),
                ("枫丹白露森林徒步", "巴黎人最爱的近郊徒步地，枫丹白露宫半日联游"),
            ],
            "afternoons": [
                ("塞纳河皮划艇", "从埃菲尔铁塔下划船穿过，最独特的巴黎视角"),
                ("蒙马特高地徒步", "艺术家聚集地，圣心堂俯瞰巴黎全城"),
            ],
        },
    },
    "首尔": {
        1: {
            "mornings": [
                ("景福宫深度游览", "朝鲜王朝最宏伟宫殿，换上韩服免费入场，正点换岗仪式必看"),
                ("国立中央博物馆", "韩国最大博物馆，馆藏40万件文物，常设展览免费开放"),
                ("北村韩屋村", "保存最完好的朝鲜时代民居群，晨间人少，适合漫步拍照"),
                ("昌德宫秘苑", "联合国世界遗产，需提前预约，朝鲜王室后花园禁苑"),
            ],
            "afternoons": [
                ("仁寺洞文化街", "传统工艺品与现代艺术廊混搭，淘传统茶具和手工纸的好去处"),
                ("益善洞韩屋咖啡街", "旧韩屋改建的网红咖啡区，传统建筑与精品咖啡的完美融合"),
                ("首尔历史博物馆", "从朝鲜时代到现代首尔的城市变迁，免费参观"),
            ],
        },
        3: {
            "mornings": [
                ("乐天世界", "室内外结合的主题乐园，冰上溜冰场和魔幻岛是孩子最爱"),
                ("爱宝乐园", "韩国最大主题乐园，玫瑰花节和雪橇坡道各季节主题丰富"),
                ("首尔儿童大公园", "免费动物园+植物园，适合7岁以下小朋友的轻松半日游"),
            ],
            "afternoons": [
                ("63大厦水族馆", "汉江边地标建筑，顶层观景台360度俯瞰首尔全景"),
                ("汉江公园亲子骑行", "租用四人自行车沿汉江骑行，野餐垫+便利店炸鸡是标配"),
                ("롯데月드 水族馆", "室内大型水族馆，企鹅和白鲸是孩子们的人气明星"),
            ],
        },
        4: {
            "mornings": [
                ("广藏市场", "首尔现存最古老的传统市场，绿豆煎饼和麻药紫菜包饭是必吃招牌"),
                ("通仁市场铜钱便当", "用古代铜钱换取各摊位小吃，拼出独一无二的便当午餐"),
                ("망원시장", "当地人气集市，年糕、炒码面和血肠比游客区便宜一半"),
            ],
            "afternoons": [
                ("明洞购物街", "韩国美妆集中地，护肤品打折力度大，街头小吃摊贩密集"),
                ("东大门设计广场", "扎哈·哈迪德设计的未来感建筑，周边批发市场24小时营业"),
                ("弘大自由市场", "周末艺术家摆摊的创意市集，独立品牌和手工饰品是挖宝好去处"),
            ],
        },
    },
    "新加坡": {
        1: {
            "mornings": [
                ("新加坡国家博物馆", "新加坡历史最久的博物馆，玻璃穹顶建筑本身就是艺术品"),
                ("牛车水历史街区", "保存完好的华人聚居地，佛牙寺和斯里玛里安曼兴都庙相距百米"),
                ("小印度区漫步", "穆斯塔法购物中心和竹脚市场是感受南亚文化的最佳入口"),
                ("甘榜格南马来文化区", "苏丹回教堂和哈芝巷壁画街，多元文化在此交汇"),
            ],
            "afternoons": [
                ("国家美术馆", "前最高法院改建，东南亚最大现代艺术展馆，建筑本身值得参观"),
                ("福康宁公园历史步道", "从莱佛士登陆地到二战历史的城市核心绿地徒步路线"),
                ("土生华人博物馆", "娘惹文化的最佳展示地，精美瓷器和刺绣工艺令人叹为观止"),
            ],
        },
        3: {
            "mornings": [
                ("圣淘沙环球影城", "东南亚唯一环球影城，变形金刚和哈利波特区孩子最爱"),
                ("新加坡动物园", "开放式无笼设计，长鼻猿和红毛猩猩可近距离互动，早餐与猩猩同乐"),
                ("滨海湾花园", "擎天树丛和花穹温室是网红打卡地，夜间灯光秀免费观看"),
            ],
            "afternoons": [
                ("S.E.A.水族馆", "世界最大水族馆之一，鲸鲨大水槽震撼人心"),
                ("新加坡科学馆", "700+互动展项，适合6岁以上儿童深度探索半天"),
                ("飞禽公园", "新加坡最大鸟园，企鹅冰域和犀鸟展区是孩子的最爱"),
            ],
        },
        4: {
            "mornings": [
                ("老巴刹", "维多利亚时代铸铁建筑内的熟食中心，沙爹和炒粿条是必点招牌"),
                ("麦士威熟食中心", "天天海南鸡饭总店所在地，需早到排队，营业到下午2点"),
                ("牛车水美食街", "正宗叻沙、肉骨茶和炒萝卜糕集中地，早市尤其热闹"),
            ],
            "afternoons": [
                ("乌节路购物带", "ION Orchard到313地下商城无缝连接，覆盖全价位品牌"),
                ("哈芝巷", "改建仓库群聚集独立设计师店和精品咖啡馆，拍照和购物兼得"),
                ("新达城双螺旋桥", "滨海湾周边逛精品店，结束前在金沙观景台俯瞰夜景"),
            ],
        },
    },
    "迪拜": {
        2: {
            "mornings": [
                ("帆船酒店水疗体验", "全球唯一七星酒店，非住客可预订下午茶或水疗套餐入场"),
                ("迪拜购物中心私人导购", "全球最大购物中心，预约高端VIP购物顾问享私享折扣"),
                ("沙漠豪华营地热气球", "清晨飞越红色沙丘，着陆后享受贝都因风情早餐和骆驼骑乘"),
            ],
            "afternoons": [
                ("棕榈岛游艇游览", "包租私人游艇环绕棕榈岛，亚特兰蒂斯酒店正面视角最佳"),
                ("哈利法塔顶层观景台", "160层At the Top Sky，日落前30分钟入场光线最美"),
                ("阿联酋宫殿酒店下午茶", "阿布扎比黄金宫殿内的奢华下午茶，金箔装饰甜品"),
            ],
        },
        3: {
            "mornings": [
                ("IMG世界冒险乐园", "室内全球最大主题乐园，漫威和卡通频道主题区孩子疯狂"),
                ("迪拜乐高乐园", "专为10岁以下孩子设计，20000块乐高砖还原迪拜地标"),
                ("Green Planet热带雨林", "室内生物穹顶，蝙蝠和懒树熊近距离接触，雨林生态体验"),
            ],
            "afternoons": [
                ("迪拜购物中心水族馆", "33000只海洋生物的巨型水槽，玻璃通道穿越鲨鱼群"),
                ("Ski Dubai室内滑雪", "沙漠中的真实滑雪场，提供全套装备，适合初学者体验"),
                ("迪拜溪畔水上出租车", "传统Abra木船横渡迪拜溪，金光闪闪的黄金市场就在对岸"),
            ],
        },
        4: {
            "mornings": [
                ("黄金市场", "全球最大黄金珠宝集散地，砍价是规矩，建议多家比价"),
                ("香料市场", "藏红花、乳香和阿拉伯香料一条街，价格是超市的三分之一"),
                ("迪拜溪畔老市场", "传统织物市场和皮革制品集散地，Abra渡船连接两岸市场"),
            ],
            "afternoons": [
                ("全球美食广场·迪拜购物中心", "汇聚全球200+餐厅，能俯瞰哈利法塔喷泉秀的座位最抢手"),
                ("JBR海滩漫步", "朱美拉海滨步道餐厅和街头小吃并存，网红沙滩打卡地"),
                ("阿拉伯夜市", "City Walk或La Mer海滨市集，阿拉伯烤肉和甜点摊位错落有致"),
            ],
        },
    },
}


# 训练数据生成
def _expert_label(f: dict) -> int:
    """
    专家规则：根据特征生成训练标签。
    这模拟了"人工标注"的过程，让模型从这些模式中学习。

    优化：引入软规则，减少硬性优先级导致的群体锁定问题。
    每个规则增加更多条件分支，避免单一条件直接决定结果。
    """
    budget = f["budget_level"] # 0=低, 1=中, 2=高
    has_special = f["has_special"] # 1=有特殊需求
    group_type = f["group_type"] # 0=单人, 1=情侣, 2=朋友, 3=家庭
    num_people = f["num_people"] # 1-12 人
    culture = f["interest_culture"]
    history = f["interest_history"]
    food = f["interest_food"]
    shopping = f["interest_shopping"]
    nature = f["interest_nature"]
    outdoor = f["interest_outdoor"]
    nightlife = f["interest_nightlife"]
    days = f["days"]

    if group_type == 1 and budget == 2:
        return 6
    if group_type == 3 and has_special == 1:
        if culture + history >= 1 and food + shopping == 0:
            return 1
        if food + shopping >= 1 and culture + history == 0:
            return 4
        if outdoor + nature >= 1 and days >= 3:
            return 5
        return 3
    if group_type == 3:  # 家庭出行（无特殊需求）→ 亲子家庭游
        return 3
    # 优先级3：户外/自然兴趣 + 天数>=3 → 户外探险游
    if (outdoor + nature) >= 1 and days >= 3:
        return 5
    # 优先级4：夜生活 + 人数>=4 → 团队社交游
    if nightlife == 1 and num_people >= 4:
        return 7
    # 优先级5：高预算 → 奢华体验
    if budget == 2:
        return 2
    # 优先级6：文化/历史为主 → 文化深度游
    if (culture + history) >= 1 and (food + shopping) == 0:
        return 1
    # 优先级7：美食/购物为主 → 美食购物游
    if (food + shopping) >= 1 and (culture + history) == 0:
        return 4
    # 优先级8：低预算 → 经济观光
    if budget == 0:
        return 0
    # 默认：文化深度游
    return 1


def generate_training_dataset(n_samples: int = 10000, noise_rate: float = 0.0) -> Tuple[np.ndarray, np.ndarray, list]:
    """
    生成 n_samples 条训练数据（标签为专家规则生成的"真实"标签）。
    noise_rate：对标签添加噪声的概率（0.0 = 不加噪声，用于生成干净数据集）。
    返回 (X, y, records)。
    """
    random.seed(42)
    np.random.seed(42)

    cities = ["巴黎", "东京", "纽约", "伦敦", "罗马", "首尔", "迪拜"]
    interests_all = ["文化", "自然", "美食", "购物", "历史", "夜生活", "户外"]
    budget_map = {"低": 0, "中": 1, "高": 2}
    budget_names = ["低", "中", "高"]
    # group_type: 0=单人, 1=情侣, 2=朋友, 3=家庭
    group_type_names = ["单人", "情侣", "朋友", "家庭"]
    group_type_weights = [0.25, 0.25, 0.25, 0.25] # 公平性：各出行群体等权采样
    special_names = ["无", "有儿童", "有老人", "轮椅友好"]
    # travel_mode: 0=飞机, 1=高铁, 2=自驾, 3=邮轮
    travel_mode_names = ["飞机", "高铁", "自驾", "邮轮"]

    X, y, records = [], [], []

    for i in range(n_samples):
        city = random.choice(cities)
        days = random.randint(1, 7)
        budget_name = random.choice(budget_names)
        budget_level = budget_map[budget_name]
        group_type = int(np.random.choice([0, 1, 2, 3], p=group_type_weights))
        group_type_name = group_type_names[group_type]
        num_people = random.randint(1, 12)
        travel_mode = random.randint(0, 3)
        special = random.choice(special_names)
        has_special = 0 if special == "无" else 1
        selected = random.sample(interests_all, random.randint(1, 4))

        f = {
            "days": days,
            "budget_level": budget_level,
            "num_people": num_people,
            "group_type": group_type,
            "has_special": has_special,
            "travel_mode": travel_mode,
            "interest_culture": 1 if "文化" in selected else 0,
            "interest_nature": 1 if "自然" in selected else 0,
            "interest_food": 1 if "美食" in selected else 0,
            "interest_shopping": 1 if "购物" in selected else 0,
            "interest_history": 1 if "历史" in selected else 0,
            "interest_nightlife": 1 if "夜生活" in selected else 0,
            "interest_outdoor": 1 if "户外" in selected else 0,
            "city_paris": 1 if city == "巴黎" else 0,
            "city_tokyo": 1 if city == "东京" else 0,
            "city_newyork": 1 if city == "纽约" else 0,
            "city_london": 1 if city == "伦敦" else 0,
            "city_rome": 1 if city == "罗马" else 0,
            "city_seoul": 1 if city == "首尔" else 0,
            "city_dubai": 1 if city == "迪拜" else 0,
        }
        label = _expert_label(f)

        # 可选标签噪声（只在训练集中注入，测试集保持干净）
        if noise_rate > 0 and random.random() < noise_rate:
            label = random.randint(0, 7)

        X.append([f[name] for name in FEATURE_NAMES])
        y.append(label)
        records.append({
            "id": f"TRAIN_{i+1:05d}",
            "city": city,
            "days": days,
            "budget": budget_name,
            "group": group_type_name,
            "num_people": num_people,
            "travel_mode": travel_mode_names[travel_mode],
            "special": special,
            "interests": selected,
            "label": label,
            "label_zh": RECOMMENDATION_LABELS_ZH[label],
        })

    return np.array(X), np.array(y), records


# 引擎主类
class SupervisedEngine:
    """监督学习引擎 - VotingClassifier (GBT + RF + ExtraTrees)"""

    def __init__(self):
        self.model = None
        self.model_type = "VotingClassifier(GBT+RF+ExtraTrees)"
        self.dataset_size = 10000
        self.model_accuracy = 0.0
        self.feature_importances: dict = {}
        self._load_or_train()

    def _load_or_train(self):
        """加载已有模型，否则训练新模型"""
        if os.path.exists(MODEL_PATH):
            try:
                with open(MODEL_PATH, "rb") as f:
                    saved = pickle.load(f)
                # 检查模型类型是否匹配，否则重新训练
                saved_type = saved.get("model_type", "")
                if saved_type != self.model_type:
                    logger.warning(f"已有模型类型 ({saved_type}) 与当前不匹配，重新训练")
                    os.remove(MODEL_PATH)
                    raise ValueError("model type mismatch")
                self.model = saved["model"]
                self.feature_importances = saved["feature_importances"]
                self.model_accuracy = saved["accuracy"]
                self.dataset_size = saved.get("dataset_size", self.dataset_size)
                logger.info(f"监督学习模型已加载 (训练集: {self.dataset_size} 条, "
                      f"准确率: {self.model_accuracy:.1%})")
                return
            except Exception as e:
                logger.warning(f"加载模型失败: {e}，重新训练")

        self._train()

    def _train(self):
        """生成数据集并训练 VotingClassifier 集成模型"""
        if not SKLEARN_AVAILABLE:
            logger.warning("sklearn 未安装，回退到规则推理")
            self.model = None
            return

        # 如果存在旧模型文件，先删除
        if os.path.exists(MODEL_PATH):
            os.remove(MODEL_PATH)
            logger.info(f"已删除旧模型文件: {MODEL_PATH}")

        logger.info(f"生成训练数据集 ({self.dataset_size} 条)...")
        # 全数据集加入 15% 标签噪声，模拟真实用户标注不确定性
        # 这样测试集也包含现实噪声，准确率反映真实世界性能而非规则完美复现
        X, y, records = generate_training_dataset(self.dataset_size, noise_rate=0.15)

        # 保存数据集（供课程提交）
        try:
            with open(DATASET_PATH, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            logger.debug(f"训练数据集已保存: {DATASET_PATH}")
        except Exception:
            pass

        # 80/20 分割训练测试集
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        logger.info(f"训练集: {len(X_train)} 条，测试集: {len(X_test)} 条（均含15%标签噪声）")

        logger.info(f"训练 {self.model_type}...")
        gbt = GradientBoostingClassifier(
            n_estimators=120, learning_rate=0.08, max_depth=3,
            subsample=0.75, random_state=42
        )
        rf = RandomForestClassifier(
            n_estimators=120, max_depth=6, min_samples_leaf=5, random_state=42
        )
        et = ExtraTreesClassifier(
            n_estimators=100, max_depth=6, min_samples_leaf=5, random_state=42
        )
        self.model = VotingClassifier(
            estimators=[("gbt", gbt), ("rf", rf), ("et", et)],
            voting="soft",
        )
        self.model.fit(X_train, y_train)

        self.model_accuracy = self.model.score(X_test, y_test)

        # 从子模型聚合特征重要性（RF + ET 支持；GBT 也支持）
        fi_gbt = self.model.estimators_[0].feature_importances_
        fi_rf = self.model.estimators_[1].feature_importances_
        fi_et = self.model.estimators_[2].feature_importances_
        fi_avg = (fi_gbt + fi_rf + fi_et) / 3.0
        self.feature_importances = dict(zip(FEATURE_NAMES, fi_avg))

        logger.info(f"训练完成 - 准确率: {self.model_accuracy:.1%}")
        logger.info(f"Top-3 重要特征: {self._top_features(3)}")

        # 保存模型
        try:
            with open(MODEL_PATH, "wb") as f:
                pickle.dump({
                    "model": self.model,
                    "model_type": self.model_type,
                    "feature_importances": self.feature_importances,
                    "accuracy": self.model_accuracy,
                    "dataset_size": self.dataset_size,
                }, f)
            logger.info(f"模型已保存: {MODEL_PATH}")
        except Exception as e:
            logger.warning(f"保存模型失败: {e}")

    def _extract_features(self, meta: dict) -> dict:
        """从用户元数据提取特征向量"""
        city = meta.get("city", "巴黎")
        interests = meta.get("interests", [])
        budget_map = {"低": 0, "中": 1, "高": 2}
        group_type_map = {"单人": 0, "情侣": 1, "夫妻": 1, "朋友": 2, "家庭": 3}
        travel_mode_map = {"飞机": 0, "高铁": 1, "自驾": 2, "邮轮": 3}

        return {
            "days": meta.get("days", 3),
            "budget_level": budget_map.get(meta.get("budget", "中"), 1),
            "num_people": int(meta.get("num_people", 2)),
            "group_type": group_type_map.get(meta.get("group", "情侣"), 1),
            "has_special": 0 if meta.get("special", "无") == "无" else 1,
            "travel_mode": travel_mode_map.get(meta.get("travel_mode", "飞机"), 0),
            # 注意：前端标签"艺术"归并到文化维度；"户外运动"含"户外"前缀需用 any()
            "interest_culture": 1 if ("文化" in interests or "艺术" in interests) else 0,
            "interest_nature": 1 if "自然" in interests else 0,
            "interest_food": 1 if "美食" in interests else 0,
            "interest_shopping": 1 if "购物" in interests else 0,
            "interest_history": 1 if "历史" in interests else 0,
            "interest_nightlife": 1 if "夜生活" in interests else 0,
            "interest_outdoor": 1 if any("户外" in i for i in interests) else 0,
            "city_paris": 1 if city == "巴黎" else 0,
            "city_tokyo": 1 if city == "东京" else 0,
            "city_newyork": 1 if city == "纽约" else 0,
            "city_london": 1 if city == "伦敦" else 0,
            "city_rome": 1 if city == "罗马" else 0,
            "city_seoul": 1 if city == "首尔" else 0,
            "city_dubai": 1 if city == "迪拜" else 0,
        }

    def _predict(self, features: dict) -> Tuple[int, float]:
        """预测推荐类型及置信度"""
        if self.model and SKLEARN_AVAILABLE:
            X = np.array([[features[n] for n in FEATURE_NAMES]])
            pred = int(self.model.predict(X)[0])
            proba = float(self.model.predict_proba(X)[0].max())
            return pred, proba
        # Fallback：用专家规则直接标注
        return _expert_label(features), 0.80

    def _predict_proba(self, features: dict) -> List[Tuple[str, float]]:
        """返回所有推荐类型的概率分布"""
        if not self.model or not SKLEARN_AVAILABLE:
            return []
        X = np.array([[features[n] for n in FEATURE_NAMES]])
        probas = self.model.predict_proba(X)[0]
        result = []
        for i, prob in enumerate(probas):
            result.append((RECOMMENDATION_LABELS_ZH.get(i, "未知"), round(float(prob), 4)))
        result.sort(key=lambda x: x[1], reverse=True)
        return result

    def _decision_path(self, features: dict) -> List[Tuple[str, float]]:
        """返回决策路径：哪些特征推动了本次预测"""
        # 使用特征重要性 + 实际特征值，估算每个特征的贡献度
        contributions = []
        for name in FEATURE_NAMES:
            importance = self.feature_importances.get(name, 0)
            value = features.get(name, 0)
            # 仅考虑有值特征（非零）
            if value != 0 and importance > 0:
                contributions.append((FEATURE_NAMES_ZH.get(name, name), round(importance * 100, 1)))
        contributions.sort(key=lambda x: x[1], reverse=True)
        return contributions[:5]

    def _top_features(self, n: int = 3) -> List[Tuple[str, float]]:
        """返回最重要的 n 个特征（中文名+权重）"""
        sorted_f = sorted(
            self.feature_importances.items(), key=lambda x: x[1], reverse=True
        )
        return [(FEATURE_NAMES_ZH.get(k, k), round(v, 4)) for k, v in sorted_f[:n]]

    def generate_itinerary(self, test_case: dict) -> dict:
        """生成行程"""
        meta = test_case["metadata"]
        features = self._extract_features(meta)
        rec_type, confidence = self._predict(features)
        rec_name = RECOMMENDATION_TYPES.get(rec_type, "cultural_deep_dive")
        rec_name_zh = RECOMMENDATION_LABELS_ZH.get(rec_type, "文化深度游")

        # 方案3：增强可解释性输出
        proba_dist = self._predict_proba(features)
        decision_path = self._decision_path(features)
        is_uncertain = len(proba_dist) >= 2 and (proba_dist[0][1] - proba_dist[1][1] < 0.1)

        itinerary = self._build_itinerary(meta, rec_type)

        days = meta.get("days", 3)
        num_people = int(meta.get("num_people", 2))
        city_budget_map = CITY_DAILY_BUDGET.get(meta.get("city", ""), {"低": 400, "中": 900, "高": 2800})
        budget_per_day_val = city_budget_map.get(meta.get("budget", "中"), 900)
        total_budget = budget_per_day_val * days * max(1, num_people)

        city = meta.get("city", "")

        result = {
            "system": "supervised",
            "itinerary": itinerary,
            "output": itinerary,
            "total_budget_estimate": total_budget,
            "prediction": rec_type,
            "recommendation_type": rec_name,
            "recommendation_type_zh": rec_name_zh,
            "model_confidence": round(confidence, 2),
            "features": features,
            "top_features": self._top_features(3),
            "model_type": self.model_type,
            "model_accuracy": round(self.model_accuracy, 4),
            "dataset_size": self.dataset_size,
            "metadata": meta,
            # 增强可解释性
            "proba_distribution": proba_dist,
            "decision_path": decision_path,
            "is_uncertain": is_uncertain,
        }
        return result

    def _build_itinerary(self, meta: dict, rec_type: int) -> str:
        """根据推荐类型生成每日行程，返回 Markdown 格式字符串"""
        city = meta.get("city", "")
        days = meta.get("days", 3)
        budget = meta.get("budget", "中")
        num_people = int(meta.get("num_people", 2))
        group = meta.get("group", "朋友")
        special = meta.get("special", "无")
        rec_name_zh = RECOMMENDATION_LABELS_ZH.get(rec_type, "文化深度游")
        interests = meta.get("interests", [])

        # 优先用城市-类型真实景点，无数据则退回通用模板
        city_activities = CITY_TYPE_ACTIVITIES.get(city, {}).get(rec_type, {})

        # 每种推荐类型的活动模板（每个 key 对应一个列表，按天轮换，避免重复）
        templates = {
            0: {
                "overview": "以经济实惠为原则，充分利用免费景点和公共设施，体验城市最真实的日常面貌。",
                "mornings": [
                    ("参观免费景点和城市广场", "漫步城市广场，欣赏建筑风貌，感受当地生活气息"),
                    ("社区公园 / 街道漫步", "走进居民生活区，逛早市、看街头涂鸦，感受城市真实节奏"),
                    ("城市图书馆 / 公共展览", "就近参观免费公共图书馆或市政展览馆，了解当地人文背景"),
                    ("免费海滨 / 江滨步道", "沿水岸步道漫行，欣赏自然风光，感受清晨城市的宁静"),
                    ("城市观景台 / 高地漫步", "前往免费制高点，俯瞰城市全貌，拍摄绝佳风光照"),
                ],
                "afternoons": [
                    ("城市徒步 / 公共博物馆", "步行探索历史街区或参观公共博物馆，深度了解城市文化"),
                    ("社区集市 / 跳蚤市场", "淘一淘当地二手好物和手工艺品，与摊贩闲聊感受生活气息"),
                    ("免费美术馆 / 文化中心", "欣赏免费对外开放的当代艺术展，票价为零、收获满满"),
                    ("城市街头艺术 / 涂鸦墙", "按图索骥探索城市街头艺术区，拍照打卡，解码城市个性"),
                    ("公共交通换乘游览", "乘坐当地公交/有轨电车打卡沿途景点，性价比最高的城市游览方式"),
                ],
                "evenings": ["街头小吃 / 夜市", "夜间免费音乐表演广场", "夜间步行老城区", "江/海边夜景散步", "当地居民常去的社区酒馆"],
                "lunches": [
                    ("当地平价餐馆或市场小吃", "选择本地人聚集的平价馆子，性价比极高"),
                    ("便利店 / 超市熟食", "体验当地便利店文化，超市熟食区往往藏有高品质本地特产"),
                    ("路边摊炒菜套餐", "跟着当地上班族排队，两三道菜加主食，饱腹又经济"),
                    ("菜市场内小馆", "在菜市场二楼或内场寻觅小餐馆，原材料新鲜、价格亲民"),
                    ("学生街 / 背包客区餐厅", "背包客聚集地往往有全城最划算的用餐选择，信息量超大"),
                ],
            },
            1: {
                "overview": "以文化深度体验为核心，博物馆、历史街区、传统表演一样不少，带你真正读懂这座城市。",
                "mornings": [
                    ("国家级博物馆深度参观", "提前在官网预约，建议9:00开馆即入场，留足2-3小时细品馆藏精华"),
                    ("当代美术馆 / 艺术中心", "欣赏城市最具活力的当代艺术创作，感受本地艺术生态"),
                    ("历史宫殿 / 古城堡参观", "深入皇室或贵族历史遗存，跟随音频导览穿越时间长廊"),
                    ("传统手工艺工坊体验", "亲手参与陶瓷、织物或传统食品制作，带走独一无二的纪念品"),
                    ("地方文化博物馆", "聚焦城市地方史的小型博物馆，往往比大馆更有惊喜和深度"),
                ],
                "afternoons": [
                    ("历史街区徒步 / 文化体验", "跟随专业导览或自助地图，穿越历史街区，探寻城市记忆"),
                    ("传统表演 / 音乐会", "欣赏当地剧场的传统戏剧或民俗音乐演出，沉浸感十足"),
                    ("宗教建筑 / 圣地参观", "走进大教堂、清真寺或古寺庙，感受信仰与建筑之美"),
                    ("古旧书市 / 文化商业街", "在旧书摊和文化商店淘宝，探寻城市的文字与精神积淀"),
                    ("城市历史图书馆 / 档案馆", "参观地标性历史建筑内的图书馆，探索知识与建筑的双重魅力"),
                ],
                "evenings": ["当地传统餐厅用餐", "传统民俗表演 + 晚餐套餐", "城市历史街区夜游", "古典音乐 / 爵士酒吧", "老字号酒馆文化夜话"],
                "lunches": [
                    ("传统风味午餐", "选择当地口碑老店，品尝最正宗的地方风味"),
                    ("博物馆内餐厅 / 咖啡馆", "许多博物馆餐厅提供精致套餐，在艺术氛围中享用午餐"),
                    ("文化街区特色小馆", "挑一家装潢有故事的街区小馆，边用餐边感受城市历史"),
                    ("历史市场美食摊位", "逛古老食品市场，现点现做地道美食，是了解当地饮食文化最直接的方式"),
                    ("当地学者 / 作家常去的咖啡馆", "坐在充满人文气息的老咖啡馆里，用一份套餐开启下午的文化探索"),
                ],
            },
            2: {
                "overview": "奢华体验之旅，从精品酒店到米其林餐厅，每一处都是精心之选，让旅途成为难忘的高端享受。",
                "mornings": [
                    ("精品酒店 SPA 体验", "享受精品酒店的顶级服务，预约专属 SPA 套餐（建议提前1周预订）"),
                    ("私人直升机 / 游艇观光", "俯瞰城市或游览水岸，以最奢华的视角解锁城市之美"),
                    ("高端美食工作坊", "向米其林星级厨师学习烹饪技艺，带走一份专属食谱与美好记忆"),
                    ("私人博物馆 VIP 参观", "预约私人导览，在无人打扰的环境中欣赏顶级艺术珍品"),
                    ("城市高端高尔夫 / 网球俱乐部", "在奢华运动俱乐部开启美好清晨，配套设施一流"),
                ],
                "afternoons": [
                    ("奢侈品购物 / 私人购物顾问", "在顶级购物街探索国际大牌，可预约私人购物顾问服务"),
                    ("高端温泉 / 疗愈中心", "沉浸在五星级水疗设施中，彻底放松身心，焕然一新"),
                    ("私人城市专车导览", "定制专属路线，让私人司机和导游带你探索城市隐秘角落"),
                    ("精品酒庄 / 茶道 / 高端品鉴会", "参加专业品鉴活动，深度感受当地顶级风土与工艺"),
                    ("高端会员俱乐部 / 屋顶泳池", "在俯瞰城市的无边泳池悠然享受午后阳光"),
                ],
                "evenings": ["米其林餐厅 / 景观餐厅晚宴", "豪华游船私人晚宴", "城市顶级屋顶酒吧鸡尾酒会", "歌剧 / 交响乐专场", "私人宴会厅套房夜宴"],
                "lunches": [
                    ("高端商务午餐", "于景观餐厅享用精致午餐，欣赏城市全景"),
                    ("米其林推荐午市套餐", "米其林午市套餐比晚市性价比高许多，同等品质更实惠"),
                    ("精品酒店私人泳池畔午餐", "悠享泳池边的精致轻食服务，奢华午后从这里开始"),
                    ("高端海鲜 / 牛排馆午市", "预约城市最负盛名的海鲜楼或牛排馆午市，品质与服务无可挑剔"),
                    ("私人厨师定制午餐", "在高端民宿或精品酒店预约私厨，享受量身定制的美食体验"),
                ],
            },
            3: {
                "overview": "专为家庭出行打造，寓教于乐，亲子互动项目丰富，节奏舒适，让大小朋友都玩得尽兴、住得安心。",
                "mornings": [
                    ("儿童友好科学博物馆", "选择有互动展区的科学馆，激发孩子好奇心（注意儿童票价优惠及免费年龄段）"),
                    ("动物园 / 水族馆", "带孩子近距离认识动植物，寓教于乐，家长小孩都能享受"),
                    ("儿童主题乐园半日游", "趁上午人少进园，玩遍热门项目，避开下午高峰人流"),
                    ("家庭烹饪 / 手工课体验", "亲子一起参加本地特色手工或烹饪课，留下合作制作的独特纪念品"),
                    ("城市自然历史博物馆", "走进自然博物馆探索恐龙化石与自然奥秘，孩子眼里充满好奇"),
                ],
                "afternoons": [
                    ("城市公园 / 亲子骑行", "在宽阔公园自由玩耍，可选择亲子骑行、野餐或小型游乐设施，注意防晒补水"),
                    ("水上乐园 / 游泳馆", "孩子们的最爱！选择安全规范的水上设施，家长休息孩子尽情玩"),
                    ("农场 / 采摘体验", "城郊农场采摘应季水果，接触大自然，让孩子了解食物的来源"),
                    ("少儿剧场 / 木偶戏", "当地专为儿童设计的表演节目，互动性强，孩子全程参与其中"),
                    ("沙滩 / 湖边亲水活动", "家庭戏水放松，带上遮阳帽和防晒霜，让孩子在大自然中撒欢"),
                ],
                "evenings": ["家庭餐厅 / 轻松娱乐活动", "亲子冰淇淋 / 甜品探店", "城市夜间动物园（开放时）", "户外电影放映会", "家庭桌游咖啡馆"],
                "lunches": [
                    ("儿童友好家庭餐厅", "选择提供儿童套餐、高脚椅和涂色纸的家庭友好餐厅"),
                    ("公园野餐便当", "在超市采购食材，带上野餐垫在公园草坪享用，孩子们最喜欢"),
                    ("主题餐厅 / 角色扮演餐厅", "让孩子在有趣主题环境中用餐，吃饭也是一场冒险"),
                    ("儿童友好海鲜 / 本地特色馆", "选择可以让孩子亲眼看到食材的餐馆，激发好奇心和食欲"),
                    ("面包房 / 甜品工坊自助午餐", "亲子一起挑选糕点，坐在窗边悠然用餐，简单而幸福"),
                ],
            },
            4: {
                "overview": "吃货与购物爱好者的天堂之旅，从清晨早市到深夜夜市，用味蕾和购物袋丈量这座城市的魅力。",
                "mornings": [
                    ("当地特色早市 / 早餐探店", "赶早市是感受当地饮食文化的最佳方式，网红早餐店建议8:00前到达"),
                    ("精品咖啡街区 / 手冲咖啡体验", "在精品咖啡馆与咖啡师聊聊当地咖啡文化，品一杯匠心手冲"),
                    ("本地有机农夫市集", "周末农夫集市是寻找本地食材和手工制品的宝藏之地"),
                    ("网红烘焙坊 / 甜品工坊早餐", "打卡城市知名烘焙名店，品尝限定口味糕点，元气满满开启一天"),
                    ("渔港 / 码头早市海鲜", "清晨码头最新鲜的海鲜直接上桌，是当地人才知道的隐藏美食地图"),
                ],
                "afternoons": [
                    ("美食市场 / 特色购物街区", "穿越特色美食市场和购物街，边走边尝，带走心仪伴手礼"),
                    ("当地百货 / 设计师集合店", "逛本地特色百货和设计师品牌，挖掘独一无二的本土好物"),
                    ("手工艺品市集 / 创意街区", "寻找本地匠人手作，每一件都是承载城市文化的独特纪念品"),
                    ("传统食品工厂 / 调味料市场", "探访老字号食品工厂或香料集市，用嗅觉和味觉深度了解当地饮食"),
                    ("街头美食巡游", "按照美食博主地图，徒步打卡数家高口碑街头小吃，满足感爆棚"),
                ],
                "evenings": ["网红餐厅 / 夜市美食体验", "当地特色酒吧配本地啤酒", "深夜食堂 / 宵夜文化体验", "高端海鲜楼 / 烤肉晚宴", "夜市购物 + 边走边吃"],
                "lunches": [
                    ("市场小吃拼盘", "在美食市场集中品尝多种特色小吃，性价比最高的午餐方式"),
                    ("当地老字号名菜馆", "预约一家百年老字号，品尝最有历史积淀的招牌菜"),
                    ("创意料理 / 融合餐厅", "体验将本地食材与国际烹饪技法结合的创意美食，味觉新探索"),
                    ("路边车仔档 / 小吃一条街", "深入当地人的街巷，找到那家只有本地人知道的绝味小吃"),
                    ("美食商场顶层 / 美食广场", "一站式品尝多家风味，效率最高的美食探索方式"),
                ],
            },
            5: {
                "overview": "户外探险者的专属行程，徒步、骑行、皮划艇……大自然是最好的舞台，挑战自我，释放活力。",
                "mornings": [
                    ("国家公园 / 自然保护区晨跑徒步", "清晨出发，享受最清新的空气和最少的人流，建议携带足够饮水"),
                    ("山地骑行 / 城市骑行探索", "租一辆自行车，按照骑行地图解锁城市郊野风光"),
                    ("海上皮划艇 / 独木舟", "在专业教练陪同下挑战皮划艇，感受海浪或河流的自然力量"),
                    ("攀岩 / 高空缆车体验", "挑战户外攀岩墙或自然岩壁，突破自我，俯瞰壮美风光"),
                    ("热气球 / 滑翔伞体验", "在专业团队安全保障下体验高空俯瞰，一生难忘的视角"),
                ],
                "afternoons": [
                    ("户外探险活动（攀岩/骑行/皮划艇）", "选择当地口碑好的户外运动服务商，安全装备齐全，教练全程陪同"),
                    ("溯溪 / 丛林穿越", "在专业向导带领下探索原始溪谷或丛林，充满挑战与惊喜"),
                    ("冲浪 / 风筝冲浪入门体验", "在当地冲浪学校参加2小时体验课，挑战站上浪板的激动时刻"),
                    ("雪地徒步 / 越野滑雪（适合季节）", "穿上雪地装备深入白色世界，体验纯粹的冬季户外运动"),
                    ("定向越野 / 城市探险游戏", "参与专业机构组织的城市或野外定向越野，团队协作、激动人心"),
                ],
                "evenings": ["营地篝火 / 星空观测", "户外电影 / 帐篷露营体验", "山顶日落观赏 + 简餐", "当地运动酒吧看球赛", "户外温泉 / 泡汤放松"],
                "lunches": [
                    ("户外能量补给 / 三明治", "自带三明治、能量棒，或就近选择自然区域内的简餐服务"),
                    ("登山小屋 / 山间木屋午餐", "户外运动后在山间小屋补充能量，简单美味，风景绝佳"),
                    ("海边 / 湖边野餐", "自带食材在绝美自然风光中野餐，是户外旅途的完美中场休息"),
                    ("当地运动员聚集餐厅", "补充碳水和蛋白质为下午活动续能，运动员常去的馆子料足价实"),
                    ("营地便携炉具自炊", "使用便携装备自炊，体验户外烹饪乐趣，这本身就是一种冒险"),
                ],
            },
            6: {
                "overview": "为情侣量身定制的浪漫行程，精品住宿、双人 SPA、烛光晚餐，每一刻都是专属于你们的甜蜜记忆。",
                "mornings": [
                    ("精品民宿慢醒 / 浪漫早餐", "赖床到9点，享受精品民宿的精致早餐，慢下来感受两人世界"),
                    ("花卉市场 / 公园晨间散步", "手牵手逛花卉市场，挑一束应季鲜花，漫步在晨光公园中"),
                    ("双人陶艺 / 手作课", "一起参加双人手工课，合力制作专属纪念品，满满的参与感和成就感"),
                    ("浪漫观景台 / 海湾日出", "清晨赶赴制高点，共同迎接第一缕阳光，留下最美的双人剪影"),
                    ("精品温泉 / 双人护理早场", "在宁静清晨享受专业双人水疗护理，轻松开启甜蜜一天"),
                ],
                "afternoons": [
                    ("双人 SPA / 游船观光", "预约双人 SPA 套餐（建议提前2天预约），或乘坐游船欣赏城市水岸风光"),
                    ("当地特色博物馆 / 美术馆", "在艺术氛围中携手欣赏珍品，互相分享各自的审美与感受"),
                    ("骑行 / 电动车双人漫游", "租借双人自行车或电动车，自由穿梭城市街巷，随停随拍"),
                    ("电影或剧场日场", "两人携手走进当地影院或小剧场，相互依偎享受共同的故事"),
                    ("私房花园 / 庄园茶歇", "在清幽私房花园或庄园咖啡馆享受下午茶，氛围浪漫又私密"),
                ],
                "evenings": ["烛光晚餐 / 城市夜景观赏", "浪漫游船晚宴", "屋顶鸡尾酒会看日落", "小剧场或音乐会 + 宵夜", "夜间摩天轮 / 观景台双人专属时光"],
                "lunches": [
                    ("浪漫格调午餐", "选择装潢精致、氛围私密的小餐馆，推荐阳台或窗边座位"),
                    ("网红咖啡馆双人套餐", "打卡城市最美咖啡馆，拍一组精美照片留存甜蜜记忆"),
                    ("景观餐厅海景 / 山景午餐", "在绝佳视角享用午餐，让风景成为最浪漫的背景"),
                    ("隐秘庭院小馆", "探访藏在胡同或巷弄里的私房餐厅，安静优雅，只属于你们"),
                    ("双人甜品下午茶", "在优雅茶馆品尝精致甜点和茶饮，度过慵懒又甜蜜的午后时光"),
                ],
            },
            7: {
                "overview": "专为团队出行设计，从破冰游戏到集体晚宴，活动丰富多样，凝聚团队默契，共创美好回忆。",
                "mornings": [
                    ("城市定向越野 / 团队破冰", "城市定向越野是团队出行的绝佳破冰项目，可提前联系当地旅行社定制方案"),
                    ("团队运动 / 沙滩排球", "在开阔户外场地组织团队运动，促进协作精神，欢声笑语不断"),
                    ("团队文化参观 / 导览游", "集体参加专业导览，统一了解目的地历史，团队知识储备齐头并进"),
                    ("逃脱室 / 团队解谜游戏", "沉浸式团队解谜挑战，考验默契与智慧，激发集体创造力"),
                    ("团队早间瑜伽 / 冥想课", "由专业教练带领全员户外晨练，以平和、专注的状态开启新一天"),
                ],
                "afternoons": [
                    ("集体文化工坊 / DIY 课", "参加陶艺、烹饪或传统工艺 DIY 课程，全员参与，共同留下手作纪念品"),
                    ("城市观光大巴 / 游船集体游", "包下游览车或游船，笑谈间完成高效全景观光"),
                    ("团队烹饪挑战赛", "分组竞赛烹制当地特色菜，趣味十足，最终集体享用成果"),
                    ("集体购物 / 市集淘宝", "组队逛市集，互相帮忙挑选伴手礼，团购还可享折扣"),
                    ("户外团建拓展 / 卡丁车", "挑战专业拓展项目或卡丁车竞速，释放压力、增进情谊"),
                ],
                "evenings": ["酒吧 / 音乐现场 + 团队聚餐", "包场 KTV / 娱乐中心夜场", "团队篝火晚会", "当地特色大排档集体宵夜", "屋顶派对 + 城市夜景"],
                "lunches": [
                    ("团队包餐 / 大桌聚餐", "提前预订可容纳全团的包间，推荐当地特色菜系套餐"),
                    ("自助餐 / 烤肉团队聚餐", "烤肉或自助形式最适合多人用餐，随意取用、气氛热烈"),
                    ("当地特色团餐", "联系餐厅预定特色团体套餐，地道风味满足所有人"),
                    ("户外野餐 + 团队游戏", "在公园草地集体野餐，趁着午饭间隙来一轮飞盘或接力赛"),
                    ("街边美食大赏 + 分享分享", "分几组分头觅食，各自打卡不同小吃后汇合分享，乐趣翻倍"),
                ],
            },
        }
        tmpl = templates.get(rec_type, templates[1])
        cost = {"低": (60, 80, 100), "中": (180, 220, 280), "高": (500, 600, 800)}.get(budget, (180, 220, 280))

        # 预算明细估算
        budget_per_day = CITY_DAILY_BUDGET.get(city, {"低": 400, "中": 900, "高": 2800}).get(budget, 900)
        flight_cost = {"低": 3000, "中": 6000, "高": 18000}.get(budget, 6000) * num_people
        hotel_cost = int(budget_per_day * 0.4) * days * num_people
        food_cost = int(budget_per_day * 0.3) * days * num_people
        attraction_cost = int(budget_per_day * 0.2) * days * num_people
        total = flight_cost + hotel_cost + food_cost + attraction_cost

        # 人员说明
        special_note = f"（{special}）" if special and special != "无" else ""

        # 构建 Markdown
        md_lines = [
            f"# {city} {days}日行程 · {rec_name_zh}",
            "",
            "## 行程概览",
            tmpl["overview"],
            f"本次行程为 **{num_people}人{group}出行{special_note}**，预算档次：**{budget}**，推荐旅行类型：**{rec_name_zh}**（模型置信度参见下方）。",
            "",
            "---",
            "",
        ]

        for day in range(1, days + 1):
            # 每天的主题微调
            day_moods = [
                "开启旅程，感受城市第一印象",
                "深入探索，发现隐藏的城市角落",
                "慢下来，用心感受当地生活节奏",
                "打卡必游地标，留下难忘照片",
                "自由时间，随心而行",
                "临别前的最后冲刺，不留遗憾",
                "圆满收尾，满载而归",
            ]
            mood = day_moods[(day - 1) % len(day_moods)]

            city_key = city_activities.get("mornings", [])
            if city_key:
                idx_c = (day - 1) % len(city_key)
                morning_act, morning_detail = city_key[idx_c]
            else:
                idx = (day - 1) % len(tmpl["mornings"])
                morning_act, morning_detail = tmpl["mornings"][idx]

            city_key_a = city_activities.get("afternoons", [])
            if city_key_a:
                idx_ca = (day - 1) % len(city_key_a)
                afternoon_act, afternoon_detail = city_key_a[idx_ca]
            else:
                idx_a = (day - 1) % len(tmpl["afternoons"])
                afternoon_act, afternoon_detail = tmpl["afternoons"][idx_a]
            idx_e = (day - 1) % len(tmpl["evenings"])
            evening_act = tmpl["evenings"][idx_e]
            idx_l = (day - 1) % len(tmpl["lunches"])
            lunch_act, lunch_detail = tmpl["lunches"][idx_l]

            # 特殊需求提示
            special_tip = ""
            if special == "有儿童":
                special_tip = "\n> 🧒 **亲子提示**：景区设有儿童互动区，注意确认儿童票价；避免连续游览超过1小时，适时安排休息补水。"
            elif special == "有老人":
                special_tip = "\n> 👴 **老人关怀**：请确认景区无障碍通道，全天行程节奏放缓，每1-2小时安排休息，避免长时间暴晒或严寒环境。"

            day_section = [
                f"## 第{day}天：{city} · {rec_name_zh} Day {day}",
                f"> {mood}",
                "",
                "**上午**  ",
                f"{morning_detail}（参考费用：¥{cost[0]}，建议 3 小时）",
                f"- 活动：**{morning_act}**",
            ]
            if special_tip:
                day_section.append(special_tip)
            day_section += [
                "",
                "**午餐推荐**  ",
                f"**{lunch_act}** — {lunch_detail}，人均约 ¥{cost[2]}",
                "",
                "**下午**  ",
                f"{afternoon_detail}（参考费用：¥{cost[1]}，建议 3 小时）",
                f"- 活动：**{afternoon_act}**",
                "",
                "**晚餐 & 夜间**  ",
                f"**{evening_act}** — 晚餐人均约 ¥{cost[2] + 20}，饭后可在周边漫步感受城市夜晚魅力。",
                "",
                "---",
                "",
            ]
            md_lines.extend(day_section)

        # 住宿建议
        hotel_suggestions = {
            "低": f"推荐青旅或经济型连锁酒店，{city}市中心附近，交通便利，人均约 ¥{int(budget_per_day*0.4)}/晚",
            "中": f"推荐三至四星品牌酒店，靠近主要景区，设施齐全，人均约 ¥{int(budget_per_day*0.6)}/晚",
            "高": f"推荐五星酒店或精品设计酒店，{city}核心地带，顶级服务，人均约 ¥{int(budget_per_day*1.2)}/晚",
        }.get(budget, f"{city}标准酒店")

        md_lines += [
            "## 住宿建议",
            hotel_suggestions,
            "",
            f"## 预算参考（{num_people}人，{days}天）",
            f"- 交通：¥{flight_cost:,}",
            f"- 住宿（{days}晚）：¥{hotel_cost:,}",
            f"- 餐饮：¥{food_cost:,}",
            f"- 景点：¥{attraction_cost:,}",
            f"- **合计约：¥{total:,}**",
        ]

        return "\n".join(md_lines)


_engine: SupervisedEngine | None = None

def generate(test_case: dict) -> dict:
    """生成行程（供统一接口调用）"""
    global _engine
    if _engine is None:
        _engine = SupervisedEngine()
    return _engine.generate_itinerary(test_case)


if __name__ == "__main__":
    test_case = {
        "id": "TEST_002",
        "input": "我想去东京玩3天，和家人一起，我们喜欢自然、美食，预算中等，有儿童。",
        "metadata": {
            "city": "东京", "days": 3, "budget": "中",
            "interests": ["自然", "美食"], "group": "家庭",
            "num_people": 4, "travel_mode": "飞机", "special": "有儿童",
        },
    }
    result = generate(test_case)
    print(f"推荐类型：{result['recommendation_type_zh']} (置信度: {result['model_confidence']:.0%})")
    print(f"Top特征：{result['top_features']}")
    print(json.dumps(result["itinerary"], ensure_ascii=False, indent=2))
