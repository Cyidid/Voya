"""
基于规则的行程规划引擎
"""

import sys
import os


# 规则库（key 统一使用中文城市名）
RULES = {
    "巴黎": {
        "attractions": {
            "culture": ["卢浮宫", "奥赛博物馆", "凯旋门", "蒙马特高地", "蓬皮杜艺术中心"],
            "nature": ["塞纳河畔", "凡尔赛花园", "卢森堡公园", "布洛涅森林"],
            "food": ["塞纳河餐厅", "蒙马特咖啡馆", "马卡龙工坊", "圣日耳曼德佩市集"],
            "shopping": ["香榭丽舍大街", "老佛爷百货", "玛莱区精品店", "蚤市"],
            "history": ["凡尔赛宫", "巴黎圣母院", "荣军院", "巴士底广场"],
            "nightlife": ["玛莱区酒吧", "拉丁区夜生活", "塞纳河游船夜景"],
        },
        "restaurants": {
            "低": ["小酒馆", "面包房早餐", "午市特价套餐"],
            "中": ["法式小餐馆", "特色餐厅"],
            "高": ["米其林餐厅", "豪华酒店餐厅"],
        },
        "daily_budget": {"低": 500, "中": 1200, "高": 3500},
        "transport": "地铁（Métro）交通便利，推荐购买 Navigo 周票",
        "tips": ["博物馆周日部分免费", "景点提前网上预约省时间"],
    },
    "东京": {
        "attractions": {
            "culture": ["浅草寺", "皇居", "东京国立博物馆", "teamLab 数字艺术馆"],
            "nature": ["上野公园", "新宿御苑", "隅田川", "高尾山"],
            "food": ["筑地市场", "寿司吧", "拉面街", "新宿御苑附近居酒屋"],
            "shopping": ["涩谷109", "银座", "秋叶原", "原宿竹下通"],
            "history": ["明治神宫", "增上寺", "江户东京博物馆"],
            "nightlife": ["新宿歌舞伎町", "六本木夜生活", "浅草花屋敷"],
        },
        "restaurants": {
            "低": ["便利店美食", "拉面店", "牛丼连锁"],
            "中": ["居酒屋", "回转寿司", "烧肉"],
            "高": ["高级料亭", "米其林餐厅", "天妇罗老店"],
        },
        "daily_budget": {"低": 400, "中": 900, "高": 2800},
        "transport": "地铁+JR线全面覆盖，推荐 Suica 卡",
        "tips": ["购买 24/48/72h 地铁通票划算", "便利店是日本饮食体验的一部分"],
    },
    "纽约": {
        "attractions": {
            "culture": ["大都会博物馆", "现代艺术博物馆（MoMA）", "百老汇", "古根海姆博物馆"],
            "nature": ["中央公园", "高线公园", "布鲁克林大桥公园"],
            "food": ["切尔西市场", "法拉盛美食", "小意大利餐厅", "布鲁克林美食街"],
            "shopping": ["第五大道", "苏豪区", "时代广场", "布鲁克林跳蚤市场"],
            "history": ["自由女神像", "帝国大厦", "9/11纪念馆"],
            "nightlife": ["哈莱姆爵士乐", "布鲁克林酒吧", "屋顶酒吧夜景"],
        },
        "restaurants": {
            "低": ["街头热狗", "披萨切片", "唐人街平价"],
            "中": ["美式餐馆", "布鲁克林咖啡馆"],
            "高": ["米其林餐厅", "高端牛排馆"],
        },
        "daily_budget": {"低": 550, "中": 1300, "高": 3800},
        "transport": "地铁24小时运营，推荐购买多次卡",
        "tips": ["许多博物馆支持自愿定价", "百老汇可当天购折扣票（TKTS亭）"],
    },
    "伦敦": {
        "attractions": {
            "culture": ["大英博物馆", "国家美术馆", "泰特现代美术馆", "维多利亚与艾伯特博物馆"],
            "nature": ["海德公园", "摄政公园", "肯辛顿花园"],
            "food": ["博罗市场", "布里克巷美食街", "科芬园"],
            "shopping": ["牛津街", "摄政街", "哈罗德百货", "波多贝罗路市集"],
            "history": ["大本钟", "伦敦塔", "威斯敏斯特教堂", "格林尼治天文台"],
            "nightlife": ["索霍区酒吧", "肖尔迪奇艺术夜生活", "爵士乐俱乐部"],
        },
        "restaurants": {
            "低": ["Fish and Chips", "酒吧午餐", "超市三明治"],
            "中": ["多元文化餐厅", "英式下午茶（茶馆）"],
            "高": ["米其林餐厅", "高级酒店下午茶"],
        },
        "daily_budget": {"低": 520, "中": 1200, "高": 3500},
        "transport": "地铁（The Tube）覆盖全市，牡蛎卡（Oyster）最便宜",
        "tips": ["大英博物馆、国家美术馆均免费", "Oyster 卡有每日封顶限额"],
    },
    "罗马": {
        "attractions": {
            "culture": ["梵蒂冈博物馆", "西斯廷教堂", "波各赛美术馆"],
            "nature": ["博格赛别墅花园", "台伯河畔", "阿皮亚古道"],
            "food": ["特莱维许愿池附近餐厅", "Campo de' Fiori 早市", "传统意式餐厅"],
            "shopping": ["西班牙广场", "Via del Corso", "特斯塔奇奥市场"],
            "history": ["罗马斗兽场", "古罗马广场", "万神殿", "卡拉卡拉浴场"],
            "nightlife": ["特拉斯提弗列夜生活", "纳沃纳广场酒吧"],
        },
        "restaurants": {
            "低": ["街头披萨", "小酒馆（Trattoria）"],
            "中": ["传统意式餐厅", "特色小馆"],
            "高": ["高级餐厅", "景观餐厅"],
        },
        "daily_budget": {"低": 450, "中": 1000, "高": 3000},
        "transport": "公交+地铁，步行也可游览大部分景点",
        "tips": ["梵蒂冈博物馆务必提前网上预约", "罗马通行证可省门票费"],
    },
    "悉尼": {
        "attractions": {
            "culture": ["悉尼歌剧院", "新南威尔士州立美术馆", "达令港"],
            "nature": ["邦迪海滩", "皇家植物园", "蓝山国家公园"],
            "food": ["岩石区海鲜市场", "萨里山咖啡街", "帕迪斯市场"],
            "shopping": ["皇后维多利亚大厦（QVB）", "皮特街购物中心", "纽曼购物中心"],
            "history": ["悉尼海港大桥", "岩石区殖民历史", "悉尼天文台"],
            "nightlife": ["国王十字区夜生活", "纽顿酒吧街", "悉尼港夜景游轮"],
        },
        "restaurants": {
            "低": ["食品市场", "咖啡馆"],
            "中": ["海鲜餐厅", "现代澳式料理"],
            "高": ["港湾景观餐厅", "高端主厨料理"],
        },
        "daily_budget": {"低": 450, "中": 1000, "高": 3000},
        "transport": "公交+火车+轮渡，Opal 卡通用",
        "tips": ["Bondi to Coogee 海滨步道免费且景色绝美", "悉尼歌剧院导览需提前预约"],
    },
    "巴塞罗那": {
        "attractions": {
            "culture": ["圣家堂", "毕加索博物馆", "米罗基金会美术馆"],
            "nature": ["蒙特惠奇山", "海滨大道（Barceloneta）", "帕劳雷亚尔公园"],
            "food": ["博盖利亚市场", "El Born 美食街", "格拉西亚街区小馆"],
            "shopping": ["格拉西亚大道奢侈品", "波恩区设计品店", "圣卡特里纳市场"],
            "history": ["哥特区", "王广场", "圣佩雷德雷斯修道院"],
            "nightlife": ["拉塞乌广场弗拉门戈", "Port Olímpic 俱乐部区", "Raval 区酒吧"],
        },
        "restaurants": {
            "低": ["Bocadillo 三明治", "塔帕斯小吃"],
            "中": ["特色菜馆", "海鲜饭餐厅"],
            "高": ["米其林餐厅", "港口景观餐厅"],
        },
        "daily_budget": {"低": 380, "中": 850, "高": 2600},
        "transport": "地铁+公交，推荐 T-Casual 多次票",
        "tips": ["圣家堂必须网上提前购票", "午餐套餐（Menú del día）性价比极高"],
    },
    "曼谷": {
        "attractions": {
            "culture": ["大皇宫", "玉佛寺", "卧佛寺", "暹罗博物馆"],
            "nature": ["素万那普公园", "考艾国家公园（近郊）", "湄南河游船"],
            "food": ["考山路夜市", "中国城街头美食", "Or Tor Kor 市场"],
            "shopping": ["暹罗百丽宫", "恰图恰周末市集", "MBK 购物中心"],
            "history": ["大城府历史遗址", "邦巴因夏宫", "郑王庙"],
            "nightlife": ["Patpong 夜市", "RCA 俱乐部街", "考山路酒吧"],
        },
        "restaurants": {
            "低": ["街头小吃", "路边摊泰式炒面"],
            "中": ["空调餐厅", "河畔餐厅"],
            "高": ["屋顶景观餐厅", "高端泰式料理"],
        },
        "daily_budget": {"低": 180, "中": 450, "高": 1500},
        "transport": "BTS 轻轨+MRT 地铁+突突车，交通多样",
        "tips": ["参观寺庙需着长裤/长裙", "Grab 打车比出租车便宜"],
    },
    "新加坡": {
        "attractions": {
            "culture": ["国家博物馆", "艺术科学博物馆", "滨海艺术中心", "新加坡美术馆"],
            "nature": ["滨海湾花园（擎天树林）", "圣淘沙岛海滩", "麦里芝蓄水池公园", "双溪布洛湿地保护区"],
            "food": ["老巴刹小贩中心", "牛车水美食街", "麦士威熟食中心", "武吉知马美食广场"],
            "shopping": ["乌节路购物带", "滨海湾金沙购物中心", "克拉码头", "义安城购物中心"],
            "history": ["莱佛士酒店", "牛车水唐人街", "小印度区", "甘榜格南马来区"],
            "nightlife": ["克拉码头酒吧街", "滨海湾金沙屋顶无边泳池观景", "哈芝巷精酿酒吧"],
        },
        "restaurants": {
            "低": ["小贩中心海南鸡饭", "椰浆饭", "肉骨茶"],
            "中": ["珍宝海鲜辣椒螃蟹", "Jumbo Seafood", "328加东叻沙"],
            "高": ["滨海湾金沙 CUT 牛排馆", "Odette 米其林三星", "焰餐厅（Waku Ghin）"],
        },
        "daily_budget": {"低": 380, "中": 900, "高": 2800},
        "transport": "地铁（MRT）覆盖全岛，EZ-Link 卡通用公交地铁",
        "tips": ["小贩中心是新加坡饮食文化精髓，物美价廉", "滨海湾花园光影秀每晚免费，建议提前占位"],
    },
    "首尔": {
        "attractions": {
            "culture": ["国立中央博物馆", "国立现代美术馆", "韩国民俗村", "DDP 东大门设计广场"],
            "nature": ["北汉山国立公园", "汉江公园", "南山公园N首尔塔", "仁王山城郭路"],
            "food": ["广藏市场", "东大门综合市场夜食", "弘大街头小吃", "鹰峰洞炸鸡一条街"],
            "shopping": ["明洞购物街", "东大门DOOTA购物中心", "弘大街区", "狎鸥亭罗德奥街"],
            "history": ["景福宫", "昌德宫秘苑", "北村韩屋村", "水原华城"],
            "nightlife": ["弘大夜生活区", "梨泰院国际酒吧街", "江南清潭洞夜场"],
        },
        "restaurants": {
            "低": ["便利店套餐", "街头辣炒年糕", "순대国产血肠汤"],
            "中": ["三清洞韩定食", "明洞烤肉", "鸡肋年糕火锅"],
            "高": ["韩牛（韩国和牛）烤肉", "Gaon 米其林三星", "高档韩式料理（韩定食）"],
        },
        "daily_budget": {"低": 280, "中": 650, "高": 2000},
        "transport": "地铁网络发达，T-Money 交通卡通用地铁公交",
        "tips": ["景福宫穿韩服入场免费", "明洞化妆品店可砍价，多家比价再购买"],
    },
    "迪拜": {
        "attractions": {
            "culture": ["迪拜艺术区（Alserkal Avenue）", "阿联酋购物中心内部艺术装置", "迪拜设计区（d3）", "迪拜博物馆（Al Fahidi堡垒）"],
            "nature": ["朱美拉公共海滩", "迪拜沙漠保护区沙丘", "迪拜溪流红树林", "赫塔沙漠徒步"],
            "food": ["迪拜老城区香料市场", "Ravi Restaurant（巴基斯坦菜）", "Al Ustad Special Kabab", "全球美食村（Global Village）"],
            "shopping": ["迪拜购物中心（Dubai Mall）", "黄金市场（Gold Souk）", "香料市场（Spice Souk）", "Mall of the Emirates（含室内滑雪场）"],
            "history": ["阿法迪历史街区（Al Fahidi）", "迪拜老城区Bastakiya", "沙迦考古博物馆（近郊）", "艾尔巴迪宫"],
            "nightlife": ["Burj Khalifa 128层酒吧At.mosphere", "JBR海滩酒吧街", "棕榈岛 Nobu 餐厅夜场"],
        },
        "restaurants": {
            "低": ["沙瓦尔马摊（Shawarma）", "Al Mallah 餐厅", "Ravi Restaurant"],
            "中": ["海滨餐厅海鲜", "国际连锁餐厅", "黎巴嫩餐厅"],
            "高": ["Nobu Dubai（棕榈岛）", "Pierchic（海上餐厅）", "Zuma（日式摩登料理）"],
        },
        "daily_budget": {"低": 450, "中": 1200, "高": 4000},
        "transport": "地铁红线/绿线覆盖主要景点，出租车/Careem（打车软件）便利",
        "tips": ["迪拜购物节（1月）和美食节折扣极大", "进入清真寺需着装保守，女性需佩戴头巾"],
    },
    "阿姆斯特丹": {
        "attractions": {
            "culture": ["国立博物馆（Rijksmuseum）", "梵高博物馆", "市立现代艺术博物馆（Stedelijk）", "安妮之家"],
            "nature": ["阿姆斯特丹森林公园", "凯肯霍夫郁金香园（春季）", "运河游船", "芳登德尔公园（Vondelpark）"],
            "food": ["Albert Cuyp 市集", "Noordermarkt 有机市场", "运河边露天咖啡馆", "Pijp 街区美食"],
            "shopping": ["P.C. Hooftstraat 奢侈品街", "Nine Streets（九条街）精品小店", "Waterlooplein 跳蚤市场", "Kalverstraat 步行购物街"],
            "history": ["约旦区（Jordaan）历史街区", "安妮·弗兰克之家", "西教堂（Westerkerk）", "阿姆斯特丹皇宫"],
            "nightlife": ["莱茵广场（Leidseplein）酒吧区", "伦勃朗广场（Rembrandtplein）夜场", "爵士咖啡馆Bimhuis"],
        },
        "restaurants": {
            "低": ["Stroopwafel 街头华夫饼", "荷式炸薯条（Vlaamse Frites）", "超市熟食"],
            "中": ["运河餐厅", "荷兰传统菜（Stamppot）", "印尼料理（Rijsttafel）"],
            "高": ["Ciel Bleu 米其林二星", "The Jane 高级料理", "Restaurant Vinkeles"],
        },
        "daily_budget": {"低": 520, "中": 1100, "高": 3200},
        "transport": "自行车是最地道的出行方式，GVB 公交/地铁/有轨电车均可用 OV 卡",
        "tips": ["梵高博物馆和国立博物馆务必提前网上购票", "租自行车游览运河区是必体验项目"],
    },
    "维也纳": {
        "attractions": {
            "culture": ["艺术史博物馆（KHM）", "维也纳国家歌剧院", "阿尔贝蒂娜博物馆", "利奥波德博物馆（席勒/克里姆特）"],
            "nature": ["维也纳森林徒步", "普拉特公园（Prater）", "多瑙河岛", "美泉宫花园"],
            "food": ["纳市场（Naschmarkt）", "维也纳咖啡馆文化（中央咖啡馆）", "Brunnenmarkt 市集", "第七区美食街"],
            "shopping": ["格拉本大街（Graben）", "玛丽亚希尔弗大街（Mariahilfer Str.）", "科尔马克特珠宝街", "多摩亚纳百货"],
            "history": ["美泉宫（Schönbrunn）", "霍夫堡皇宫", "圣史蒂芬大教堂", "维也纳墓地（中央公墓）"],
            "nightlife": ["第七区酒吧街（Spittelberg）", "维也纳音乐会（金色大厅附近）", "多瑙河畔夏季露天派对"],
        },
        "restaurants": {
            "低": ["Würstelstand 香肠摊", "咖啡馆套餐（含维也纳咖啡）", "Beisl 小酒馆午市"],
            "中": ["维也纳炸猪排（Wiener Schnitzel）餐厅", "Meixner's Gastwirtschaft", "传统维也纳菜馆"],
            "高": ["Steirereck im Stadtpark 米其林二星", "维也纳国家歌剧院附近高级餐厅", "Konstantin Filippou"],
        },
        "daily_budget": {"低": 450, "中": 1000, "高": 3000},
        "transport": "地铁（U-Bahn）+有轨电车+公交，维也纳城市卡（Vienna City Card）含无限次乘车",
        "tips": ["音乐会/歌剧院当晚站票很便宜，提前1小时排队可购", "维也纳博物馆月票性价比高"],
    },
    "布拉格": {
        "attractions": {
            "culture": ["国家剧院", "布拉格国家博物馆", "穆夏博物馆（新艺术风格）", "DOX当代艺术中心"],
            "nature": ["迪文公园（Divoká Šárka）", "维谢赫拉德公园", "布拉格动物园", "波西米亚喀斯特自然保护区（近郊）"],
            "food": ["共和国广场农贸市场", "布拉格中央市场（Manifesto Market）", "老城广场街头小吃", "Lokál 捷克传统菜馆"],
            "shopping": ["帕拉迪乌姆购物中心", "帕利斯购物中心", "老城区纪念品街", "Dlouhá 街精品店"],
            "history": ["布拉格城堡", "查理大桥", "老城广场天文钟", "犹太区（Josefov）"],
            "nightlife": ["瓦茨拉夫广场酒吧街", "克罗斯俱乐部（Klub Cross）", "老城区地下酒吧"],
        },
        "restaurants": {
            "低": ["Trdelník 糖筒街头", "捷克猪肘套餐", "超市熟食"],
            "中": ["Lokál 捷克传统餐厅", "La Degustation 波西米亚料理", "Café Savoy 维也纳式咖啡馆"],
            "高": ["Field 米其林一星", "Alcron 高级餐厅", "Čestr 高档牛肉料理"],
        },
        "daily_budget": {"低": 250, "中": 600, "高": 1800},
        "transport": "地铁A/B/C线+有轨电车，24小时通票划算",
        "tips": ["布拉格城堡区面积庞大，建议安排半天游览", "捷克啤酒（Pilsner Urquell/Kozel）比矿泉水便宜"],
    },
    "普吉岛": {
        "attractions": {
            "culture": ["普吉老城葡萄牙式骑楼建筑", "查龙寺（Wat Chalong）", "大佛（Big Buddha）", "普吉艺术村"],
            "nature": ["攀牙湾皮划艇（James Bond Island）", "珊瑚岛浮潜", "甲米四岛一日游", "西蒙山观景台日落"],
            "food": ["芭东夜市", "普吉老城周末夜市", "卡伦海鲜码头", "Bang Rong 码头海鲜餐厅"],
            "shopping": ["Jung Ceylon 购物中心（芭东）", "普吉老城精品纪念品店", "周末市场手工艺品", "中央节日广场"],
            "history": ["普吉老城（Sino-Portuguese建筑群）", "泰华博物馆", "辛哈克林纪念碑"],
            "nightlife": ["芭东海滩Bangla Road夜生活街", "卡隆海滩酒吧", "苏林海滩露天酒吧"],
        },
        "restaurants": {
            "低": ["路边摊炒河粉", "当地粥店", "7-11便利店"],
            "中": ["海鲜餐厅（卡隆码头）", "老城Kopitiam咖啡馆", "泰式火锅"],
            "高": ["Suay Restaurant 创意泰菜", "Mom Tri's Kitchen 悬崖餐厅", "Acqua 意大利海景餐厅"],
        },
        "daily_budget": {"低": 180, "中": 450, "高": 1600},
        "transport": "出租车/摩托车出租/Grab 打车为主，岛内无公共交通",
        "tips": ["雨季（5-10月）价格便宜但海况不佳，旱季（11-4月）最适合出游", "Grab 比路边出租车便宜一半以上"],
    },
    "马尔代夫": {
        "attractions": {
            "culture": ["马累国家博物馆", "马累大清真寺（Islamic Centre）", "马累鱼市场", "当地渔村文化体验（Maafushi岛）"],
            "nature": ["珊瑚礁浮潜（North Male Atoll）", "鲨鱼湾浮潜（Rasdhoo Atoll）", "水下餐厅体验（Ithaa）", "海豚湾观豚游船"],
            "food": ["马累当地鱼市烤金枪鱼", "Maafushi岛街头小吃", "度假村海滩BBQ", "水上餐厅"],
            "shopping": ["马累本岛纪念品街", "Chandhani Magu 商业街", "度假村精品店", "潜水装备店"],
            "history": ["Hukuru Miskiy古清真寺（17世纪）", "马累国家博物馆（苏丹王朝文物）", "乌泰姆古宅"],
            "nightlife": ["度假岛沙滩星空鸡尾酒会", "水上屋日落观赏", "生物发光浮游生物夜游"],
        },
        "restaurants": {
            "低": ["Maafushi本地岛街头餐厅", "当地人经营咖啡馆（hedhika小吃）", "鱼市附近平价餐馆"],
            "中": ["客栈（guesthouse）含早晚餐", "当地风味海鲜餐厅", "Maafushi Street Food"],
            "高": ["水下餐厅Ithaa（Conrad Hilton）", "四季度假村沙滩烛光晚餐", "One&Only Reethi Rah高级料理"],
        },
        "daily_budget": {"低": 600, "中": 1800, "高": 6000},
        "transport": "水上飞机/快艇在各岛间穿梭，马累市内步行即可",
        "tips": ["本地岛（guesthouse）比度假村便宜80%，性价比极高", "务必提前预订水上飞机，旺季一票难求"],
    },
    "伊斯坦布尔": {
        "attractions": {
            "culture": ["伊斯坦布尔现代艺术博物馆", "佩拉博物馆", "土耳其伊斯兰艺术博物馆", "卡里耶博物馆（科拉教堂）"],
            "nature": ["博斯普鲁斯海峡游船", "王子群岛一日游", "贝尔格莱德森林徒步", "Emirgan公园郁金香节（春季）"],
            "food": ["卡帕利市集香料区", "贝西克塔斯鱼市", "卡德柯伊美食市场", "Karaköy码头烤鱼三明治"],
            "shopping": ["大巴扎（Kapalıçarşı）", "埃及香料市集（Mısır Çarşısı）", "尼尚塔什精品区", "Kanyon购物中心"],
            "history": ["圣索菲亚大教堂", "蓝色清真寺", "托普卡珀皇宫", "地下宫殿（Basilica Cistern）"],
            "nightlife": ["贝伊奥卢İstiklal大道酒吧街", "Karaköy精酿酒吧区", "博斯普鲁斯海峡夜游船"],
        },
        "restaurants": {
            "低": ["Simit（芝麻圆面包）街头摊", "Döner卷饼", "当地börek馅饼店"],
            "中": ["Karaköy传统土耳其菜馆", "卡德柯伊海鲜餐厅", "Balıkçı Sabahattin烤鱼"],
            "高": ["Mikla 屋顶全景餐厅（米其林推荐）", "Sunset Grill & Bar博斯普鲁斯景观", "Neolokal 现代土耳其料理"],
        },
        "daily_budget": {"低": 220, "中": 550, "高": 1800},
        "transport": "Istanbulkart 交通卡通用地铁/电车/公交/渡轮，跨洲渡轮是特色体验",
        "tips": ["圣索菲亚目前为清真寺，进入需脱鞋并着装保守", "博斯普鲁斯渡轮是最便宜的跨洲方式，风景极佳"],
    },
    "广州": {
        "attractions": {
            "culture": ["陈家祠", "广州博物馆（镇海楼）", "南越王博物院", "广州大剧院"],
            "nature": ["越秀公园", "白云山", "珠江夜游", "海珠湿地公园"],
            "food": ["上下九步行街", "北京路美食街", "广州酒家", "莲香楼早茶"],
            "shopping": ["天河城", "正佳广场", "太古汇", "北京路步行街"],
            "history": ["陈家祠", "南越王博物院", "沙面岛租界历史建筑", "黄埔军校旧址"],
            "nightlife": ["珠江新城夜生活", "珠江夜游", "琶醍啤酒文化创意艺术区"],
        },
        "restaurants": {
            "低": ["街头肠粉摊", "云吞面小馆", "大排档夜宵"],
            "中": ["陶陶居早茶", "莲香楼", "深井烧鹅"],
            "高": ["广州酒家", "泮溪酒家", "富临饭店"],
        },
        "daily_budget": {"低": 200, "中": 500, "高": 1500},
        "transport": "地铁14条线路全覆盖，推荐岭南通交通卡或扫码乘车，高铁枢纽广州南站连接全国",
        "tips": ["广式早茶文化体验不可错过，建议9:00-11:00前往老字号茶楼", "上下九和北京路夜市人多注意随身财物"],
    },
    "里斯本": {
        "attractions": {
            "culture": ["古尔本基安博物馆（Gulbenkian）", "里斯本当代艺术博物馆（MOCA）", "法多音乐博物馆", "阿祖莱霍瓷砖博物馆（Museu do Azulejo）"],
            "nature": ["辛特拉山宫（Sintra宫殿群）", "卡斯凯什海滨（Cascais）", "阿里茹达自然公园", "蒙桑图城市森林公园"],
            "food": ["时代市场（Mercado da Ribeira/Time Out Market）", "阿尔法马区烤沙丁鱼摊", "Campo de Ourique菜市场", "贝伦区蛋塔店（Pastéis de Belém）"],
            "shopping": ["希亚多区精品街（Rua Garrett）", "阿尔法马跳蚤市场（Feira da Ladra）", "Baixa商业区", "LX Factory创意市集"],
            "history": ["热罗尼莫斯修道院（贝伦区）", "贝伦塔", "圣乔治城堡（Castelo de São Jorge）", "阿尔法马老城区"],
            "nightlife": ["巴侯区（Bairro Alto）酒吧街", "Cais do Sodré粉红街（Pink Street）", "法多表演（Alfama区）"],
        },
        "restaurants": {
            "低": ["Pastel de nata 蛋塔咖啡馆", "Tasca平价葡式小馆", "超市Pingo Doce熟食区"],
            "中": ["Time Out Market 多元美食", "阿尔法马烤沙丁鱼餐厅", "Zé da Mouraria葡式传统菜"],
            "高": ["Belcanto 米其林二星（José Avillez）", "Alma 高级葡式创意料理", "Sea Me 高档海鲜餐厅"],
        },
        "daily_budget": {"低": 300, "中": 750, "高": 2200},
        "transport": "电车28号线是标志性游览方式，地铁+公交覆盖全市，Viva Viagem 卡通用",
        "tips": ["贝伦蛋塔原创店（Pastéis de Belém）排队值得等待", "里斯本7座山丘城市，穿着舒适鞋子至关重要"],
    },
    "大阪": {
        "attractions": {
            "culture": ["大阪城公园", "海游馆（鲸鲨水族馆）", "环球影城（USJ）", "国立民族学博物馆"],
            "nature": ["万博纪念公园", "天保山海滨", "长居植物园", "住吉大社"],
            "food": ["道顿堀美食街", "黑门市场（海鲜直采）", "心斋桥筋商店街", "新世界串炸一带"],
            "shopping": ["心斋桥筋", "美国村（Amerika Mura）", "梅田地下街", "难波City"],
            "history": ["大阪城天守阁", "住吉大社", "四天王寺（日本最古老寺院之一）", "适塾（史迹）"],
            "nightlife": ["道顿堀格力高看板夜景", "北新地酒吧街", "南船场酒吧区", "难波夜生活"],
        },
        "restaurants": {
            "低": ["章鱼烧（Wanaka道顿堀）", "金龙拉面24小时", "551蓬莱猪肉包"],
            "中": ["鶴橋風月大阪烧", "串炸Daruma（新世界）", "回转寿司海鲜丸"],
            "高": ["黑门市场金枪鱼/海胆丼", "梅田高层餐厅景观怀石", "Conrad大阪顶层餐厅"],
        },
        "daily_budget": {"低": 400, "中": 900, "高": 2800},
        "transport": "大阪Metro御堂筋线贯通南北，JR环状线连通主要景点，推荐ICOCA卡或大阪周游卡",
        "tips": ["道顿堀格力高看板傍晚6-7点光线最佳，是必拍打卡地", "USJ任天堂世界须提前官网抢预约券，限量入场"],
    },
    "京都": {
        "attractions": {
            "culture": ["伏见稻荷大社（千本鸟居）", "金阁寺", "清水寺舞台", "岚山竹林小径"],
            "nature": ["哲学之道（春樱秋叶）", "嵐山渡月桥", "贵船神社", "大原三千院"],
            "food": ["锦市场（京都厨房）", "南禅寺附近汤豆腐", "祇园周边抹茶甜品店", "出町柳豆饼"],
            "shopping": ["祇园花见小路周边", "清水坂参道", "新京极商店街", "锦市场"],
            "history": ["二条城（莺声地板）", "龙安寺枯山水石庭", "银阁寺", "下鸭神社"],
            "nightlife": ["祇园白川南通傍晚散步", "先斗町小酒馆", "高台寺夜间特别参观（秋）"],
        },
        "restaurants": {
            "低": ["锦市场章鱼蛋/玉子烧", "出町ふたば豆饼（¥210）", "拉面小路（京都站）"],
            "中": ["南禅寺奥丹汤豆腐（400年老店）", "祇园咖啡馆套餐", "中村藤吉抹茶套餐"],
            "高": ["祇园 さゝ木 懐石料理（需预约）", "菊乃井（米其林）", "俵屋旅馆会席料理"],
        },
        "daily_budget": {"低": 350, "中": 850, "高": 2600},
        "transport": "市巴士一日券¥700可无限次乘坐，206路连通清水寺/祇园/金阁寺；嵐電复古电车直达岚山",
        "tips": ["清晨7:00-9:00游览伏见稻荷、嵐山竹林，人少且光线最美", "祇园花见小路禁止私人小巷拍摄，请尊重舞妓文化"],
    },
    "巴厘岛": {
        "attractions": {
            "culture": ["乌布猴子森林", "皮雅庙（Pura Tirta Empul圣水庙）", "乌布皇宫", "巴厘岛艺术中心"],
            "nature": ["金巴兰日落海滩", "梯田（德哥拉朗梯田）", "布拉坦湖（湖上神庙）", "情人崖（Uluwatu）"],
            "food": ["乌布夜市", "金巴兰海鲜烧烤滩", "努沙杜阿高档餐厅区", "Warung本地小馆"],
            "shopping": ["乌布艺术市场", "水明漾精品街（Seminyak）", "Deus神庙潮流概念店", "Kuta海滩周边纪念品街"],
            "history": ["情人崖海神庙（Pura Luhur Uluwatu）", "贝萨基母庙（巴厘岛最神圣庙宇）", "塔那罗特庙（海上神庙）"],
            "nightlife": ["库塔/水明漾酒吧街", "Sky Garden夜店（库塔）", "情人崖Kecak火舞（日落表演）"],
        },
        "restaurants": {
            "低": ["Warung印尼炒饭（Nasi Goreng）", "Babi Guling（烤乳猪）小馆", "沙嗲街头摊位"],
            "中": ["乌布夜市现炒海鲜", "金巴兰海滩烧烤套餐", "Locavore有机餐厅（乌布）"],
            "高": ["Mozaic 米其林（乌布）", "Rock Bar（悬崖酒吧）晚餐", "努沙杜阿五星酒店餐厅"],
        },
        "daily_budget": {"低": 200, "中": 600, "高": 2000},
        "transport": "租摩托车（约¥50/天）或包车（约¥200/天）是主要出行方式，南部景区可用Grab打车",
        "tips": ["进入庙宇须穿纱笼（可现场租借），尊重宗教习俗", "旱季（5-9月）海况最佳，适合冲浪和浮潜；雨季（11-3月）价格低30%"],
    },
    "开罗": {
        "attractions": {
            "culture": ["开罗伊斯兰历史区（联合国教科文组织遗址）", "科普特开罗（科普特博物馆/悬挂教堂）", "艾资哈尔清真寺", "萨拉丁城堡"],
            "nature": ["尼罗河游船日落", "法尤姆绿洲（骆驼沙漠体验）", "西奈红海海岸（日间游）"],
            "food": ["哈利利市场（Khan el-Khalili）街头小吃", "老城区拱廊餐厅", "开罗街头库沙里（Koshari）", "尼罗河畔河鱼料理"],
            "shopping": ["哈利利市场（香料/手工艺品）", "马尔科亚购物中心", "伊斯兰集市（纸莎草画/铜器）", "Zamalek精品街"],
            "history": ["吉萨大金字塔与狮身人面像", "埃及博物馆（图坦卡蒙黄金面具）", "孟菲斯露天博物馆（萨卡拉阶梯金字塔）", "路克索神庙（日游）"],
            "nightlife": ["尼罗河游艇夜宴", "Zamalek区酒吧与爵士", "老城区咖啡馆水烟文化（Shisha）"],
        },
        "restaurants": {
            "低": ["街头库沙里（Koshary）", "Hawawshi肉饼摊", "哈利利市场茶馆"],
            "中": ["Abou El Sid传统埃及菜", "Naguib Mahfouz咖啡馆", "尼罗河畔烤鱼馆"],
            "高": ["Sequoia尼罗河景观餐厅", "Four Seasons Nile Plaza顶层餐厅", "Tamarai屋顶酒吧"],
        },
        "daily_budget": {"低": 150, "中": 450, "高": 1600},
        "transport": "打车（Uber/Careem）是最便捷方式，地铁覆盖市中心三条线，景区间建议包车",
        "tips": ["吉萨金字塔建议清晨7:00-9:00前往，避开热浪与人潮", "博物馆内严禁拍摄，如需摄影需额外购票"],
    },
    "哥本哈根": {
        "attractions": {
            "culture": ["国家博物馆（丹麦历史）", "路易斯安纳现代艺术博物馆", "腓特烈堡城堡", "嘉士伯啤酒博物馆"],
            "nature": ["丹麦海岸线自行车道", "克伦堡城堡（哈姆雷特城堡）", "腓特烈松花园", "海峡浴场（夏季户外游泳）"],
            "food": ["纽哈温运河餐厅区（Nyhavn）", "托维霍尔斯哈伦美食市场（Torvehallerne）", "北欧新料理餐厅聚集区", "嘉士伯啤酒馆"],
            "shopping": ["斯特罗伊耶步行街（Strøget）", "Illum百货", "Designmuseum设计精品", "蒂沃里公园纪念品"],
            "history": ["克里斯蒂安堡宫（议会/皇室）", "罗森堡城堡（王冠珠宝）", "小美人鱼雕像（Langelinie码头）", "纽哈温彩色木屋（17世纪商船码头）"],
            "nightlife": ["纽哈温夜间酒吧街", "蒂沃里游乐园夜场", "Vesterbro区时髦酒吧", "爵士音乐现场（Copenhagen Jazz）"],
        },
        "restaurants": {
            "低": ["Torvehallerne市场小吃", "Smørrebrød开放式三明治外卖", "连锁烘焙连锁店"],
            "中": ["传统斯堪的纳维亚餐厅", "纽哈温河边中价海鲜馆", "植物性北欧料理（Ark）"],
            "高": ["Noma（全球最佳餐厅之一，需提前数月预订）", "Kadeau北欧新料理", "AOC 米其林二星"],
        },
        "daily_budget": {"低": 600, "中": 1400, "高": 4200},
        "transport": "地铁（Metro）+公交（S-tog）覆盖全市，Rejsekort充值卡通用；哥本哈根自行车道世界一流，骑行是本地人最常用出行方式",
        "tips": ["自行车是本地首选交通工具，机场/各大景点均有 Donkey Republic 共享单车", "小美人鱼雕像体型较小，建议工作日清晨前往拍照避免拥挤"],
    },
    "苏黎世": {
        "attractions": {
            "culture": ["苏黎世美术馆（Kunsthaus Zürich）", "瑞士国家博物馆（Landesmuseum）", "苏黎世歌剧院", "设计博物馆（Museum für Gestaltung）"],
            "nature": ["苏黎世湖游船", "乌特里贝格山（Uetliberg，城市全景）", "莱茵瀑布（日间游，欧洲最大瀑布）", "格拉鲁斯阿尔卑斯山徒步"],
            "food": ["班霍夫大街美食（Bahnhofstrasse）", "大市场（Markthalle）周六早市", "旧城区芥末黄油鱼（Zürcher Geschnetzeltes）正宗餐厅", "林登霍夫广场咖啡馆"],
            "shopping": ["班霍夫大街（世界顶级购物街）", "旧城区独立精品店", "手表/巧克力/瑞士刀专卖店", "Jelmoli百货"],
            "history": ["苏黎世旧城区（Altstadt）", "大教堂（Grossmünster）", "女修道院教堂（Fraumünster，夏加尔彩绘玻璃）", "Lindenhügel要塞遗址"],
            "nightlife": ["旧城区Niederdorf夜生活街区", "湖畔露天酒吧（Badi，夏季）", "工业区Zürich-West创意酒吧", "爵士音乐节（7月）"],
        },
        "restaurants": {
            "低": ["超市Coop/Migros外卖熟食", "面包房午餐套餐", "市场摊位Wurst香肠"],
            "中": ["Zürcher Geschnetzeltes（传统苏黎世炒小牛肉）正宗馆", "旧城区法式小馆", "湖边Strandbar简餐"],
            "高": ["Kronenhalle（百年老店，毕加索/马蒂斯真迹装饰）", "The Restaurant（四季酒店，米其林）", "Pavillon Baur au Lac湖边高级餐厅"],
        },
        "daily_budget": {"低": 700, "中": 1600, "高": 4800},
        "transport": "ZVV公共交通系统整合地铁/电车/公交/游船，Tageskarte日票推荐；苏黎世卡含免费公交+博物馆",
        "tips": ["瑞士联邦铁路（SBB）可直达日内瓦、因特拉肯、卢塞恩等城市，建议购买Swiss Travel Pass", "巧克力/瑞士刀/手表在机场免税店通常无法享有本地精品店的折扣"],
    },
}

# 英文版交通贴士与城市小贴士（前端英文模式使用）
RULES_EN = {
    "巴黎":      {"transport": "Metro (Métro) is easiest; get a weekly Navigo pass",
                  "tips": ["Many museums are free on Sundays", "Pre-book popular sights online to skip queues"]},
    "东京":      {"transport": "Metro + JR lines cover everything; use a Suica IC card",
                  "tips": ["24/48/72 h metro passes offer great value", "Convenience stores are a core part of the Japanese food experience"]},
    "纽约":      {"transport": "Subway runs 24/7; get a multi-ride MetroCard",
                  "tips": ["Many museums accept pay-what-you-wish", "Same-day Broadway discount tickets at the TKTS booth"]},
    "伦敦":      {"transport": "The Tube covers the whole city; Oyster card gives the cheapest fares",
                  "tips": ["British Museum & National Gallery are free", "Oyster card has a daily spending cap"]},
    "罗马":      {"transport": "Bus + metro; most sights are walkable",
                  "tips": ["Vatican Museums must be booked online in advance", "Roma Pass saves on admission fees"]},
    "悉尼":      {"transport": "Bus + train + ferry; use an Opal card for all modes",
                  "tips": ["The Bondi-to-Coogee coastal walk is free and stunning", "Sydney Opera House tours need advance booking"]},
    "巴塞罗那":  {"transport": "Metro + bus; T-Casual multi-trip pass is best value",
                  "tips": ["Sagrada Família tickets must be purchased online", "Set lunch (Menú del día) offers outstanding value"]},
    "曼谷":      {"transport": "BTS Skytrain + MRT + tuk-tuk; diverse options",
                  "tips": ["Cover shoulders and legs when visiting temples", "Grab is significantly cheaper than taxis"]},
    "新加坡":    {"transport": "MRT covers the whole island; EZ-Link card works on bus & metro",
                  "tips": ["Hawker centres are the heart of Singapore's food culture and great value", "Gardens by the Bay light show is free nightly — arrive early for good spots"]},
    "首尔":      {"transport": "Excellent metro network; T-Money card works on subway and bus",
                  "tips": ["Free entry to Gyeongbokgung Palace when wearing hanbok", "Compare prices across multiple shops in Myeongdong before buying cosmetics"]},
    "迪拜":      {"transport": "Metro Red/Green line + Careem/taxi; air-conditioned malls are a welcome escape",
                  "tips": ["Dubai Shopping Festival (Jan) offers major discounts", "Dress conservatively in mosques; women must cover their hair"]},
    "阿姆斯特丹":{"transport": "Cycling is the authentic way; GVB trams/metro/bus accept OV-chipkaart",
                  "tips": ["Pre-book Van Gogh Museum & Rijksmuseum online — they sell out fast", "Renting a bike to explore the canal district is a must"]},
    "维也纳":    {"transport": "U-Bahn + tram + bus; Vienna City Card includes unlimited public transport",
                  "tips": ["Same-evening standing tickets for opera are very cheap — queue 1 hour early", "Vienna museum monthly pass offers great value"]},
    "布拉格":    {"transport": "Metro A/B/C + trams; 24-hour pass is good value",
                  "tips": ["Prague Castle is huge — budget half a day to explore it", "Czech beer (Pilsner Urquell / Kozel) is cheaper than bottled water"]},
    "普吉岛":    {"transport": "Taxi / motorbike rental / Grab are the main options; no public transit on the island",
                  "tips": ["Dry season (Nov–Apr) is best; rainy season (May–Oct) brings rough seas", "Grab is usually more than 50 % cheaper than roadside taxis"]},
    "马尔代夫":  {"transport": "Seaplanes and speedboats connect islands; Malé itself is walkable",
                  "tips": ["Local island guesthouses are ~80 % cheaper than resort islands", "Book seaplane transfers early — high-season seats sell out fast"]},
    "伊斯坦布尔":{"transport": "Istanbulkart covers metro/tram/bus/ferry; the cross-continental ferry is a unique experience",
                  "tips": ["Hagia Sophia is now a mosque — remove shoes and dress modestly", "The Bosphorus ferry is the cheapest and most scenic cross-continental trip"]},
    "里斯本":    {"transport": "Iconic tram 28 is a must-ride; metro + bus cover the city; use a Viva Viagem card",
                  "tips": ["The original Pastéis de Belém custard tart shop is worth the queue", "Lisbon has 7 hills — wear comfortable shoes"]},
    "广州":      {"transport": "14-line metro covers every major sight; use a Lingnan Tong transit card or scan-to-pay; Guangzhou South station connects high-speed rail nationwide",
                  "tips": ["Cantonese dim sum (Yum Cha) is a must — head to a classic teahouse 9–11 am", "Watch your belongings in the busy Shangxiajiu and Beijing Road night markets"]},
    "大阪":      {"transport": "Osaka Metro Midosuji line runs north-south; JR Loop circles key spots; ICOCA card or Osaka Amazing Pass recommended",
                  "tips": ["The Glico Running Man sign at Dotonbori is best photographed at dusk (6–7 pm)", "Pre-book Nintendo World entry tickets online — they're limited and sell out quickly"]},
    "京都":      {"transport": "City bus day pass (¥700) is best value; Route 206 links Kiyomizudera, Gion and Kinkakuji; Randen tram goes to Arashiyama",
                  "tips": ["Visit Fushimi Inari and the Arashiyama bamboo grove before 8 am — quieter and beautiful in soft morning light", "Photography in private Gion alleyways is prohibited; please respect the maiko culture"]},
    "巴厘岛":    {"transport": "Motorbike rental (~¥50/day) or private driver (~¥200/day) are standard; Grab works in southern Bali",
                  "tips": ["Wear a sarong when entering temples — they can be rented at the gate", "Dry season (May–Sep) is best for surfing and snorkelling; wet season (Nov–Mar) is 30 % cheaper"]},
    "开罗":      {"transport": "Uber/Careem ride-hailing is most convenient; metro has 3 lines covering downtown; charter a car for Giza / Saqqara",
                  "tips": ["Visit the Pyramids at 7–9 am to beat the heat and crowds", "Photography inside the Egyptian Museum requires an extra ticket"]},
    "哥本哈根":  {"transport": "Copenhagen Metro + S-tog rail + Rejsekort card covers everything; cycling infrastructure is world-class — rent a Donkey Republic bike",
                  "tips": ["The Little Mermaid statue is smaller than expected — visit on a weekday morning for photos without crowds", "Noma-style restaurants require booking months ahead; check cancellation lists for last-minute seats"]},
    "苏黎世":    {"transport": "ZVV integrated transit (tram/metro/bus/lake boat) is excellent; Zürich Card includes free transit + museum entry; SBB trains reach Geneva, Lucerne, Interlaken",
                  "tips": ["Swiss Travel Pass offers unlimited rail travel across the country — worth it for trips longer than 3 days", "Chocolates and Swiss knives are cheaper in dedicated shops in the Altstadt than at the airport"]},
}

# 城市名标准化（支持多种写法）
CITY_NORMALIZE = {
    "巴黎": "巴黎", "paris": "巴黎", "Paris": "巴黎",
    "东京": "东京", "tokyo": "东京", "Tokyo": "东京",
    "纽约": "纽约", "new york": "纽约", "NewYork": "纽约",
    "伦敦": "伦敦", "london": "伦敦", "London": "伦敦",
    "罗马": "罗马", "rome": "罗马", "Rome": "罗马",
    "悉尼": "悉尼", "sydney": "悉尼", "Sydney": "悉尼",
    "巴塞罗那": "巴塞罗那", "barcelona": "巴塞罗那",
    "曼谷": "曼谷", "bangkok": "曼谷", "Bangkok": "曼谷",
    # 新增城市
    "新加坡": "新加坡", "singapore": "新加坡", "Singapore": "新加坡",
    "首尔": "首尔", "seoul": "首尔", "Seoul": "首尔", "서울": "首尔",
    "迪拜": "迪拜", "dubai": "迪拜", "Dubai": "迪拜",
    "阿姆斯特丹": "阿姆斯特丹", "amsterdam": "阿姆斯特丹", "Amsterdam": "阿姆斯特丹",
    "维也纳": "维也纳", "vienna": "维也纳", "Vienna": "维也纳", "Wien": "维也纳",
    "布拉格": "布拉格", "prague": "布拉格", "Prague": "布拉格", "Praha": "布拉格",
    "普吉岛": "普吉岛", "phuket": "普吉岛", "Phuket": "普吉岛", "普吉": "普吉岛",
    "马尔代夫": "马尔代夫", "maldives": "马尔代夫", "Maldives": "马尔代夫",
    "伊斯坦布尔": "伊斯坦布尔", "istanbul": "伊斯坦布尔", "Istanbul": "伊斯坦布尔",
    "里斯本": "里斯本", "lisbon": "里斯本", "Lisbon": "里斯本", "Lisboa": "里斯本",
    "广州": "广州", "guangzhou": "广州", "Guangzhou": "广州", "广州市": "广州",
    "大阪": "大阪", "osaka": "大阪", "Osaka": "大阪",
    "京都": "京都", "kyoto": "京都", "Kyoto": "京都",
    "巴厘岛": "巴厘岛", "bali": "巴厘岛", "Bali": "巴厘岛", "巴厘": "巴厘岛",
    "开罗": "开罗", "cairo": "开罗", "Cairo": "开罗", "القاهرة": "开罗",
    "哥本哈根": "哥本哈根", "copenhagen": "哥本哈根", "Copenhagen": "哥本哈根", "København": "哥本哈根",
    "苏黎世": "苏黎世", "zurich": "苏黎世", "Zurich": "苏黎世", "Zürich": "苏黎世",
}

# 城市月份气候特征（供行程建议参考）
CITY_CLIMATE = {
    "巴黎":   {"spring":"温和多雨(12-18°C)，建议带伞", "summer":"温暖(20-28°C)，日照充足", "autumn":"凉爽多雨(10-18°C)", "winter":"阴冷(2-8°C)，需厚外套"},
    "东京":   {"spring":"樱花季(12-20°C)，人潮拥挤", "summer":"高温潮湿(28-35°C)，注意防暑", "autumn":"红叶季(15-22°C)，最佳旅游季", "winter":"寒冷干燥(2-10°C)"},
    "纽约":   {"spring":"多变(10-20°C)", "summer":"炎热(25-33°C)，注意防晒", "autumn":"凉爽舒适(12-22°C)，最佳旅游季", "winter":"严寒(-3-5°C)，大雪频繁"},
    "伦敦":   {"spring":"多云有雨(8-15°C)", "summer":"温暖(18-24°C)", "autumn":"多雨(10-16°C)，常备雨伞", "winter":"阴冷(2-8°C)"},
    "罗马":   {"spring":"温暖(16-24°C)，最佳旅游季", "summer":"炎热(28-35°C)，注意高温", "autumn":"温和(16-24°C)", "winter":"温凉(5-13°C)"},
    "悉尼":   {"spring":"温和(15-22°C)", "summer":"炎热(22-30°C)，海滨旺季", "autumn":"舒适(15-22°C)", "winter":"温凉(8-17°C)"},
    "曼谷":   {"spring":"炎热潮湿(30-38°C)", "summer":"雨季(28-33°C)，午后暴雨", "autumn":"雨季末(28-33°C)", "winter":"旱季凉爽(25-32°C)，最佳旅游季"},
    "首尔":   {"spring":"春暖花开(10-20°C)，樱花季", "summer":"高温多雨(25-33°C)", "autumn":"红叶期(12-22°C)，最佳旅游季", "winter":"严寒(-6-3°C)，需厚装"},
    "迪拜":   {"spring":"温暖(22-30°C)", "summer":"极热(38-45°C)，户外活动受限", "autumn":"温热(28-36°C)", "winter":"温暖宜人(18-26°C)，最佳旅游季"},
    "新加坡": {"spring":"全年炎热多雨(27-33°C)，午后雷雨常见", "summer":"全年炎热多雨(27-33°C)", "autumn":"全年炎热多雨(27-33°C)", "winter":"全年炎热多雨(27-33°C)，12-1月稍凉"},
    "阿姆斯特丹": {"spring":"多云有风(8-15°C)，郁金香盛开", "summer":"温暖(18-24°C)", "autumn":"多雨(8-15°C)", "winter":"阴冷潮湿(0-6°C)"},
    "维也纳": {"spring":"温暖(12-20°C)", "summer":"温热(22-28°C)", "autumn":"凉爽(10-18°C)", "winter":"寒冷(-2-5°C)，可赏雪景"},
    "布拉格": {"spring":"温和(10-18°C)", "summer":"温暖(20-26°C)", "autumn":"凉爽(8-16°C)", "winter":"寒冷(-2-4°C)，圣诞市集"},
    "普吉岛": {"spring":"旱季尾(28-33°C)", "summer":"雨季(27-32°C)，风浪大", "autumn":"雨季(27-32°C)", "winter":"旱季(27-32°C)，最佳旅游季"},
    "马尔代夫": {"spring":"过渡季(28-32°C)", "summer":"雨季(27-31°C)", "autumn":"雨季(27-31°C)", "winter":"旱季(28-31°C)，最佳旅游季"},
    "伊斯坦布尔": {"spring":"温和(14-20°C)", "summer":"炎热(25-32°C)", "autumn":"温凉(12-20°C)", "winter":"阴冷(3-9°C)"},
    "里斯本": {"spring":"温暖(16-22°C)", "summer":"炎热干燥(24-32°C)", "autumn":"温和(16-22°C)", "winter":"温凉多雨(8-15°C)"},
    "巴塞罗那": {"spring":"温暖(16-22°C)", "summer":"炎热(26-32°C)，海滨旺季", "autumn":"温和(16-22°C)", "winter":"温凉(8-15°C)"},
    "广州":    {"spring":"温暖潮湿(18-25°C)，多阴雨，常备雨伞", "summer":"高温多雨(30-37°C)，注意防暑防晒，午后雷阵雨频繁", "autumn":"最佳旅游季(22-28°C)，晴朗干爽", "winter":"温凉(8-15°C)，偶有寒流，外套即可"},
    "大阪":    {"spring":"樱花季(12-20°C)，3月末至4月初最美", "summer":"高温潮湿(28-35°C)，注意防暑", "autumn":"红叶期(15-22°C)，最佳旅游季", "winter":"寒冷(2-10°C)，偶有降雪"},
    "京都":    {"spring":"樱花盛开(12-20°C)，旺季需提前数月预订住宿", "summer":"高温多湿(28-35°C)，祇园祭7月全月", "autumn":"红叶季(14-22°C)，全年最美", "winter":"淡季(2-8°C)，人少价低，偶有积雪极美"},
    "巴厘岛":  {"spring":"旱季(27-33°C)，海况好，适合出行", "summer":"雨季(26-32°C)，午后阵雨，价格较低", "autumn":"雨季渐退(27-32°C)", "winter":"旱季旺季(27-32°C)，12-1月最佳旅游季"},
    "开罗":    {"spring":"温热(22-30°C)，春风沙尘暴季节", "summer":"极热(35-42°C)，高温干燥，建议清晨出行", "autumn":"温和(18-28°C)，最佳旅游季", "winter":"温凉(10-20°C)，白天温暖，夜间凉爽"},
    "哥本哈根":{"spring":"温和(8-15°C)，春光明媚，郁金香盛开", "summer":"舒适(18-24°C)，最佳旅游季，白昼极长", "autumn":"凉爽多雨(8-15°C)", "winter":"阴冷(0-5°C)，圣诞市集氛围浓厚"},
    "苏黎世":  {"spring":"温和(10-18°C)，湖区风光迷人", "summer":"温暖(20-26°C)，户外露天活动旺季", "autumn":"凉爽(8-16°C)，葡萄酒庄园收获季", "winter":"寒冷(-2-5°C)，滑雪旺季，圣诞市集"},
}

def _get_season(month: int) -> str:
    """根据月份返回季节key"""
    if month in (3, 4, 5): return "spring"
    if month in (6, 7, 8): return "summer"
    if month in (9, 10, 11): return "autumn"
    return "winter"


BUDGET_RULES = {
    "低": {"price_factor": 1.0},
    "中": {"price_factor": 2.5},
    "高": {"price_factor": 5.0}
}

INTEREST_PRIORITY = {
    "culture": 1,
    "history": 2,
    "food": 3,
    "nature": 4,
    "shopping": 5,
    "nightlife": 6,
}

# 兴趣词（中文→英文key）
INTEREST_MAP = {
    "文化": "culture", "历史": "history", "美食": "food",
    "自然": "nature", "购物": "shopping", "夜生活": "nightlife",
    "艺术": "culture", "户外运动": "nature",
}

# 保留旧 CITY_MAP 用于兼容
CITY_MAP = {k: v for k, v in CITY_NORMALIZE.items()}


class RuleBasedEngine:
    """基于规则的行程规划引擎"""

    def __init__(self):
        self.rules = RULES

    def generate_itinerary(self, test_case: dict) -> dict:
        """生成行程"""
        meta = test_case['metadata']

        # 标准化城市名
        city_raw = meta.get('city', '巴黎')
        city_key = CITY_NORMALIZE.get(city_raw, city_raw)
        days = meta['days']
        budget = meta['budget']
        interests = meta.get('interests', ['文化'])
        special = meta.get('special', '无')
        group = meta.get('group', '朋友')
        num_people = meta.get('num_people', 2)
        origin = meta.get('origin', '')
        travel_mode = meta.get('travel_mode', '飞机')

        # 获取城市规则（不支持时默认巴黎）
        if city_key not in self.rules:
            city_key = "巴黎"

        city_rules = self.rules[city_key]

        # 提取出行月份 / 季节，获取气候信息
        start_date = meta.get('start_date', '')
        month = None
        if start_date:
            try:
                import re as _re2
                m = _re2.search(r'(\d{4})[/-](\d{1,2})', start_date)
                if m:
                    month = int(m.group(2))
            except Exception:
                pass
        if month is None:
            import datetime
            month = datetime.datetime.now().month

        season = _get_season(month)
        climate_info = CITY_CLIMATE.get(city_key, {})
        climate_desc = climate_info.get(season, "气候宜人，适合旅游")
        weather_note = f"{month}月{city_key}气候：{climate_desc}"

        # 将中文兴趣转为规则库 key
        interest_keys = []
        for i in interests:
            mapped = INTEREST_MAP.get(i, i)
            if mapped in city_rules["attractions"]:
                interest_keys.append(mapped)
        if not interest_keys:
            interest_keys = ["culture"]

        # 生成行程（各天叙述文本）
        day_narratives = []
        for day in range(1, days + 1):
            day_text = self._generate_day_plan(
                city_rules, budget, interest_keys, special, day, city_key,
                num_people=num_people, group=group, weather_note=weather_note
            )
            day_narratives.append(day_text)

        daily_cost = city_rules["daily_budget"].get(budget, 150)
        activity_budget = daily_cost * days * max(1, int(num_people))
        # 交通费估算（飞机/高铁/自驾按预算档次，邮轮另计）
        _flight_est = {"低": 3000, "中": 6000, "高": 18000}.get(budget, 6000)
        _train_est  = {"低": 800,  "中": 1500, "高": 4000 }.get(budget, 1500)
        _drive_est  = {"低": 500,  "中": 1000, "高": 2500 }.get(budget, 1000)
        _cruise_est = {"低": 5000, "中": 12000,"高": 35000}.get(budget, 12000)
        _mode = (travel_mode or "飞机").strip()
        if "高铁" in _mode or "火车" in _mode or "动车" in _mode:
            transport_per_person = _train_est
        elif "自驾" in _mode or "开车" in _mode:
            transport_per_person = _drive_est
        elif "游轮" in _mode or "邮轮" in _mode:
            transport_per_person = _cruise_est
        else:
            transport_per_person = _flight_est
        transport_total = transport_per_person * max(1, int(num_people))
        total_budget = activity_budget + transport_total

        # 构建人员说明
        people_note = f"{num_people}人"
        if special and special != '无':
            people_note += f"（{special}）"

        # 构建出行方式说明
        mode_note = travel_mode if travel_mode else "飞机"

        # 构建住宿建议
        budget_hotel = {
            "低": f"推荐经济型酒店或青旅，{city_key}市中心附近，人均约¥{int(city_rules['daily_budget'].get('低',500)*0.7)}/晚",
            "中": f"推荐三至四星品牌酒店，{city_key}主要景区周边，人均约¥{int(city_rules['daily_budget'].get('中',1200)*0.65)}/晚",
            "高": f"推荐五星酒店或精品酒店，{city_key}核心地带，人均约¥{int(city_rules['daily_budget'].get('高',3500)*0.75)}/晚",
        }.get(budget, f"推荐{city_key}市中心标准酒店")

        tips_lines = "\n".join(f"- {t}" for t in city_rules.get("tips", []))

        # 构建 Markdown 行程字符串
        md_lines = [
            f"# {city_key} {days}日行程 · {group}{mode_note}游",
            "",
            "## 行程概览",
            f"本次行程为 {people_note} {group}出行，共 {days} 天，预算档次：{budget}。",
            f"**天气提示**：{weather_note}。请根据实际天气灵活调整户外/室内活动安排。",
            "",
            "---",
            "",
        ]

        for day_text in day_narratives:
            md_lines.append(day_text)
            md_lines.append("")

        md_lines += [
            "---",
            "",
            "## 住宿建议",
            budget_hotel,
            "",
            "## 实用信息",
            f"- **交通**：{city_rules.get('transport', '')}",
            f"- **气候**：{weather_note}",
            f"- **小贴士**：",
            tips_lines,
            "",
            "## 预算参考",
            f"| 费用项目 | 估算（{num_people}人合计）|",
            "|---------|------------|",
            f"| 往返交通（{_mode}）| 约 ¥{transport_total:,} |",
            f"| 住宿（{days}晚）| 约 ¥{int(daily_cost * 0.4 * days * max(1, int(num_people))):,} |",
            f"| 餐饮 | 约 ¥{int(daily_cost * 0.3 * days * max(1, int(num_people))):,} |",
            f"| 景点门票 | 约 ¥{int(daily_cost * 0.2 * days * max(1, int(num_people))):,} |",
            f"| 当地交通 & 杂项 | 约 ¥{int(daily_cost * 0.1 * days * max(1, int(num_people))):,} |",
            f"| **合计（{budget}档次）** | **约 ¥{total_budget:,}** |",
        ]

        itinerary_md = "\n".join(md_lines)

        city_fallback = city_key != city_raw and city_raw not in CITY_NORMALIZE
        result = {
            "system": "rule-based",
            "itinerary": itinerary_md,
            "output": itinerary_md,
            "total_budget_estimate": activity_budget,   # 不含交通，前端侧边栏会自行叠加
            "metadata": meta,
            "city_used": city_key,
            "transport_tip": city_rules.get("transport", ""),
            "city_tips": city_rules.get("tips", []),
            "transport_tip_en": RULES_EN.get(city_key, {}).get("transport", city_rules.get("transport", "")),
            "city_tips_en": RULES_EN.get(city_key, {}).get("tips", city_rules.get("tips", [])),
            "weather_note": weather_note,
            "responsible_ai": {
                "transparency": "完全可解释：每条推荐均可追溯至规则库中的具体条目",
                "fairness_warning": (f"城市覆盖限于18个热门目的地；输入城市'{city_raw}'不在规则库中，已回退至'{city_key}'" if city_fallback else f"城市'{city_key}'在规则库覆盖范围内"),
                "coverage_gap": city_fallback,
                "deterministic": True,
                "data_source": "人工专家编写规则库，存在专家主观偏差",
            },
        }
        if origin:
            result["origin"] = origin
        return result

    def _generate_day_plan(self, city_rules, budget, interest_keys, special, day, city_name,
                           num_people=2, group="朋友", weather_note=""):
        """生成单日计划，返回富文本 Markdown 叙述字符串"""
        # 选择活动
        morning = self._select_activity(city_rules, interest_keys, budget, special, "morning", day)
        afternoon = self._select_activity(city_rules, interest_keys, budget, special, "afternoon", day)
        lunch = self._select_meal(city_rules, budget, day)
        dinner = self._select_meal(city_rules, budget, day + 1)

        # 备选景点（取不同兴趣分类的下一个景点）
        alt_idx = (day * 2 + 1) % len(interest_keys)
        alt_interest = interest_keys[alt_idx]
        alt_pool = city_rules["attractions"].get(alt_interest, [])
        alt_activity = alt_pool[(day * 3) % len(alt_pool)] if alt_pool else "城市漫步"

        # 根据人员组合生成贴士
        group_tip = ""
        if special == "有儿童":
            group_tip = f"  > 🧒 亲子提示：{morning['activity']}设有儿童互动区，注意儿童票价优惠；避免连续游览超过1小时，可在附近休息区小憩。"
        elif special == "有老人":
            group_tip = f"  > 👴 老人提示：{morning['activity']}请确认无障碍通道，行程间隔安排休息，避免暴晒/严寒时段户外停留过长。"
        elif group == "单人":
            group_tip = f"  > 🔒 单人安全提示：游览{morning['activity']}时建议跟随导览团，保管好随身物品，晚间返回住所走光线充足的街道。"
        elif group in ("情侣", "夫妻"):
            group_tip = f"  > 💑 情侣推荐：{afternoon['activity']}是拍照绝佳地点，傍晚时分光线最美。"
        elif int(num_people) >= 5:
            group_tip = f"  > 👥 大团队提示：{int(num_people)}人出行建议提前团体预约，景区高峰期（10:00-14:00）可分批入场。"

        # 天气相关建议
        weather_advice = ""
        if weather_note:
            if any(kw in weather_note for kw in ["雨", "多雨", "暴雨", "风浪"]):
                weather_advice = f"  > ☔ 天气备选：若遇降雨，上午户外活动可替换为室内博物馆或商场文创园参观。"
            elif any(kw in weather_note for kw in ["极热", "高温", "炎热", "38", "35"]):
                weather_advice = f"  > 🌡️ 高温提示：午间（12:00-15:00）避免长时间户外暴晒，安排室内餐厅或博物馆休息，携带防晒用品及充足饮水。"
            elif any(kw in weather_note for kw in ["严寒", "寒冷", "-6", "-3"]):
                weather_advice = f"  > 🧥 严寒提示：注意保暖，露天活动时间不宜过长，携带厚外套及防滑鞋。"

        # 日主题
        interest_label = {"culture":"文化探索", "history":"历史寻踪", "food":"美食之旅",
                          "nature":"自然漫游", "shopping":"购物体验", "nightlife":"夜游体验"}.get(
            interest_keys[(day - 1) % len(interest_keys)], "城市探索")
        theme = f"{city_name}{interest_label} Day {day}"

        lines = [
            f"## 第{day}天：{theme}",
            "> 发现城市的另一面，在每个转角遇见惊喜。",
            "",
            f"**上午**  ",
            f"参观 **{morning['activity']}**（建议游览约 {morning['duration']} 小时，参考费用约 ¥{morning['cost_estimate']}）",
        ]
        if group_tip:
            lines.append(group_tip)
        lines += [
            "",
            f"**午餐推荐**  ",
            f"前往 **{lunch['activity']}**，人均约 ¥{lunch['cost_estimate']}，菜品丰富适合{group}聚餐。",
            "",
            f"**下午**  ",
            f"游览 **{afternoon['activity']}**（建议约 {afternoon['duration']} 小时，参考费用约 ¥{afternoon['cost_estimate']}）",
        ]
        if weather_advice:
            lines.append(weather_advice)
        lines += [
            "",
            f"**晚餐 & 夜间**  ",
            f"品尝 **{dinner['activity']}**，人均约 ¥{dinner['cost_estimate']}。餐后可在附近散步感受城市夜晚氛围。",
            "",
            f"> 💡 备选：**{alt_activity}**——若上午景点人流过多或天气不佳，可作为替换选项。",
        ]
        return "\n".join(lines)

    def _select_activity(self, city_rules, interest_keys, budget, special, time_slot, day):
        """选择活动 —— 双步长轮换，避免相邻时段（上午/下午/跨天）出现重复景点。
        step 公式：AM = (day-1)*2, PM = (day-1)*2+1
        同一天上午/下午 step 相差1，相邻两天同时段 step 相差2，不会命中同一索引。
        """
        step = (day - 1) * 2 + (1 if time_slot == "afternoon" else 0)
        interest_index = step % len(interest_keys)
        interest = interest_keys[interest_index]

        if interest in city_rules["attractions"]:
            activities = city_rules["attractions"][interest]
            if activities:
                activity_index = step % len(activities)
                activity = activities[activity_index]
                price_factor = BUDGET_RULES[budget]["price_factor"]
                # 给门票费用加一点变化（活动序号作为微调），避免每个景点价格完全相同
                cost_base = int(city_rules["daily_budget"].get(budget, 150) * 0.22)
                cost_delta = [0, 10, -10, 20, 5][activity_index % 5]
                cost = max(0, cost_base + cost_delta)
                duration = [2, 3, 2, 3, 4][activity_index % 5]  # 游览时长也有变化

                return {
                    "activity": activity,
                    "category": interest,
                    "duration": duration,
                    "cost_estimate": cost
                }

        # 默认活动
        return {
            "activity": f"城市漫步 Day {day}",
            "category": "nature",
            "duration": 2,
            "cost_estimate": 0
        }

    def _select_meal(self, city_rules, budget, day=1):
        """选择餐厅 —— 按天轮换，避免每晚相同餐厅"""
        restaurants = city_rules["restaurants"][budget]
        price_factor = BUDGET_RULES[budget]["price_factor"]
        restaurant = restaurants[(day - 1) % len(restaurants)]
        # 用餐费用按预算有差别
        cost_base = int(city_rules["daily_budget"].get(budget, 150) * 0.16)
        cost_delta = [0, 20, -15, 30][( day - 1) % 4]
        cost = max(0, cost_base + cost_delta)

        return {
            "activity": restaurant,
            "category": "food",
            "duration": 2,
            "cost_estimate": cost
        }


_engine: RuleBasedEngine | None = None


# ── 自然语言预处理 ─────────────────────────────────────────────
import re as _re

def parse_natural_language(text: str) -> dict:
    """
    从自由文本中提取结构化旅行参数。
    返回值可直接用作 test_case["metadata"]。
    支持关键词匹配：城市名、天数、预算词、兴趣标签、出行类型、人数、出发地。
    """
    text_lower = text.lower()

    # ── 1. 城市名：先查规则库别名，再 regex 提取 ──
    city = "巴黎" # 默认
    for alias, canonical in sorted(CITY_NORMALIZE.items(), key=lambda x: -len(x[0])):
        if alias in text or alias in text_lower:
            city = canonical
            break
    else:
        m = _re.search(r"去(.{2,8}?)(?:玩|旅游|游玩|度假|旅行|看看)", text)
        if m:
            raw = m.group(1).strip().replace("一下", "").replace("一趟", "")
            city = CITY_NORMALIZE.get(raw, raw)

    # ── 2. 天数 ──
    days = 3
    m = _re.search(r"(\d+)\s*(?:天|日)", text)
    if m:
        days = min(14, max(1, int(m.group(1))))

    # ── 3. 预算：关键词匹配 ──
    budget = "中"
    high_kw = ["高", "充裕", "宽裕", "奢华", "豪华", "不差钱", "土豪", "商务舱", "头等"]
    low_kw = ["低", "省钱", "便宜", "经济", "节省", "穷游", "背包", "预算有限"]
    if any(k in text for k in high_kw):
        budget = "高"
    elif any(k in text for k in low_kw):
        budget = "低"

    # ── 4. 兴趣标签：关键词列表扫描 ──
    interest_kw = {
        "文化": ["文化", "博物馆", "艺术", "展览", "gallery"],
        "历史": ["历史", "古迹", "遗址", "城堡", "宫殿"],
        "美食": ["美食", "吃", "餐厅", "料理", "小吃", "food", "饮食"],
        "自然": ["自然", "风景", "风光", "山", "湖", "海", "公园", "森林"],
        "购物": ["购物", "买", "商场", "市集", "奢侈品", "shopping"],
        "夜生活": ["夜生活", "酒吧", "夜店", "club", "夜晚", "夜游"],
        "户外运动": ["户外", "徒步", "运动", "滑雪", "冲浪", "爬山", "骑行"],
    }
    interests = [tag for tag, kws in interest_kw.items() if any(k in text for k in kws)]
    if not interests:
        interests = ["文化", "美食"]

    # ── 5. 出行类型 ──
    group_kw = {
        "情侣": ["情侣", "约会", "恋人"],
        "夫妻": ["夫妻", "老婆", "老公", "爱人", "太太", "先生"],
        "朋友": ["朋友", "好友", "闺蜜", "兄弟", "伙伴", "同学", "同事"],
        "家庭": ["家庭", "家人", "父母", "孩子", "儿童", "小孩", "家里"],
        "单人": ["独自", "一个人", "单人", "solo", "一人"],
    }
    group = "朋友"
    for g, kws in group_kw.items():
        if any(k in text for k in kws):
            group = g
            break

    # ── 6. 人数 ──
    num_people = 2 if group in ("情侣", "夫妻") else 2
    m = _re.search(r"(\d+)\s*(?:人|位|个人)", text)
    if m and group not in ("情侣", "夫妻"):
        num_people = max(1, min(20, int(m.group(1))))

    # ── 7. 出发地 ──
    origin = ""
    # 先匹配 "从/由 X 出发/飞" 形式
    m = _re.search(r"(?:从|由|自)\s*(.{2,6}?)\s*(?:出发|乘|飞|坐|起飞|前往)", text)
    if m:
        raw_origin = m.group(1).strip()
        origin = CITY_NORMALIZE.get(raw_origin, raw_origin)
    else:
        # 匹配 "X飞Y" / "X乘机飞Y" / "X直飞Y" 格式，X为出发地
        m2 = _re.search(r"(.{2,4}?)(?:飞|乘机飞|直飞)(.{2,4})", text)
        if m2:
            raw_origin = m2.group(1).strip()
            raw_dest_raw = m2.group(2).strip()
            # 目的地只取前2-3字（中文城市名通常2-3字），去掉后续旅游词汇
            raw_dest = _re.sub(r'[玩旅游逛游旅行出发看看].*$', '', raw_dest_raw).strip()
            raw_dest = _re.sub(r'\d.*$', '', raw_dest).strip()
            # 限制最多3个汉字
            raw_dest = raw_dest[:4]
            # 尝试规范化（在字典中精确查找）
            raw_dest = CITY_NORMALIZE.get(raw_dest, raw_dest)
            # 出发地
            origin = CITY_NORMALIZE.get(raw_origin, raw_origin)
            # 若城市尚未被识别到（仍是默认值），将飞行目的地作为 city
            if city == "巴黎" and raw_dest and raw_dest != raw_origin:
                city = raw_dest

    # ── 8. 出行方式 ──
    travel_mode = "飞机"
    if any(k in text for k in ["高铁", "火车", "动车", "高速铁路"]):
        travel_mode = "高铁"
    elif any(k in text for k in ["自驾", "开车", "驾车", "汽车"]):
        travel_mode = "自驾"
    elif any(k in text for k in ["邮轮", "游轮", "轮船"]):
        travel_mode = "邮轮"

    # ── 9. 特殊需求 ──
    special = "无"
    if any(k in text for k in ["儿童", "小孩", "孩子", "宝宝", "婴儿"]):
        special = "有儿童"
    elif any(k in text for k in ["老人", "老年", "父母", "长辈", "爸妈"]):
        special = "有老人"
    elif any(k in text for k in ["轮椅", "无障碍", "残疾"]):
        special = "轮椅友好"

    return {
        "city": city, "days": days, "budget": budget,
        "interests": interests, "group": group,
        "num_people": num_people, "origin": origin,
        "travel_mode": travel_mode, "special": special,
    }


def generate(test_case: dict) -> dict:
    """
    生成行程（供统一接口调用）。
    支持两种输入模式：
      1. 结构化：test_case["metadata"] 已有完整字段（正常表单提交）
      2. 自然语言：test_case["metadata"] 缺失或不完整时，
         自动从 test_case["input"] 解析关键词补全 metadata。
    """
    global _engine
    if _engine is None:
        _engine = RuleBasedEngine()

    # 自然语言预处理：若 metadata 不完整则从 input 文本补全
    raw_input = test_case.get("input", "")
    meta = test_case.get("metadata", {})
    if raw_input and not meta.get("city"):
        # 纯自然语言模式：完整解析
        parsed = parse_natural_language(raw_input)
        # 已有字段优先（结构化字段覆盖解析结果）
        merged = {**parsed, **{k: v for k, v in meta.items() if v}}
        test_case = {**test_case, "metadata": merged}
    elif raw_input and meta.get("city"):
        # 混合模式：用 NLP 补全缺失字段
        parsed = parse_natural_language(raw_input)
        for key, val in parsed.items():
            if not meta.get(key):
                meta[key] = val

    return _engine.generate_itinerary(test_case)


if __name__ == "__main__":
    # 测试
    import json

    test_case = {
        "id": "TEST_001",
        "input": "我想去巴黎玩5天，和爱人一起，我们喜欢文化、美食，预算比较宽裕。",
        "metadata": {
            "city": "巴黎",
            "days": 5,
            "budget": "高",
            "interests": ["文化", "美食"],
            "group": "情侣",
            "special": "无"
        }
    }

    result = generate(test_case)
    print(json.dumps(result, ensure_ascii=False, indent=2))
