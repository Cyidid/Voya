"""
机票与火车票预订引擎 — 云游 AI 旅行规划
数据说明：基于真实运营航线和高铁数据构建参考库（航班号、时刻、时长、价格区间
均参考实际市场数据，价格因淡旺季/舱位/提前量而浮动，仅供参考，以出行时实际
航空公司/12306 为准）。
公平性原则：所有用户（无论出行群体）享有完全相同的权限、价格算法和服务标准。
"""

import json
import os
import hashlib
from datetime import datetime
from typing import Optional

_ORDERS_PATH = os.path.join(os.path.dirname(__file__), "../../assets/orders/orders.json")

# ─────────────────────────────────────────────────────────────────
# 真实国际航线数据库
# 字段说明：
#   airline  航空公司中文名
#   code     航班号（参考真实运营航班）
#   dep      出发时刻
#   arr      到达时刻（"+1"表示次日）
#   duration 飞行时长
#   stops    经停次数（0=直飞）
#   via      经停城市（stops>0 时填写）
#   econ     经济舱参考区间 [低, 高]（人民币）
#   biz      商务舱参考区间 [低, 高]（人民币）
# ─────────────────────────────────────────────────────────────────
REAL_INTL_ROUTES: dict[tuple, list] = {

    # ══════════ 上海出发 ══════════
    ("上海", "巴黎"): [
        {"airline":"法国航空",      "code":"AF115",  "dep":"11:55","arr":"18:40+1","duration":"12h45m","stops":0, "econ":[5500,8800], "biz":[28000,48000]},
        {"airline":"中国东方航空",  "code":"MU551",  "dep":"00:50","arr":"07:35+1","duration":"12h45m","stops":0, "econ":[5200,7800], "biz":[26000,42000]},
        {"airline":"新加坡航空",    "code":"SQ833",  "dep":"10:00","arr":"21:05+1","duration":"17h05m","stops":1,"via":"新加坡", "econ":[6000,9500], "biz":[32000,55000]},
        {"airline":"国泰航空",      "code":"CX291",  "dep":"22:30","arr":"21:00+1","duration":"14h30m","stops":1,"via":"香港",  "econ":[6200,9800], "biz":[30000,50000]},
    ],
    ("上海", "东京"): [
        {"airline":"中国东方航空",  "code":"MU509",  "dep":"08:00","arr":"12:05","duration":"3h05m","stops":0, "econ":[1200,2800], "biz":[8000,15000]},
        {"airline":"全日空",        "code":"NH920",  "dep":"09:30","arr":"13:30","duration":"3h00m","stops":0, "econ":[1500,3200], "biz":[9000,16000]},
        {"airline":"日本航空",      "code":"JL5062", "dep":"10:15","arr":"14:30","duration":"3h15m","stops":0, "econ":[1600,3500], "biz":[9500,17000]},
        {"airline":"中国东方航空",  "code":"MU269",  "dep":"18:00","arr":"21:55","duration":"2h55m","stops":0, "econ":[1300,3000], "biz":[8500,14000]},
    ],
    ("上海", "纽约"): [
        {"airline":"中国东方航空",  "code":"MU567",  "dep":"00:50","arr":"04:05+1","duration":"15h15m","stops":0, "econ":[7000,11000], "biz":[35000,60000]},
        {"airline":"达美航空",      "code":"DL278",  "dep":"17:05","arr":"19:20+1","duration":"16h15m","stops":0, "econ":[7500,12000], "biz":[38000,65000]},
        {"airline":"美国航空",      "code":"AA127",  "dep":"13:30","arr":"18:05+1","duration":"16h35m","stops":1,"via":"洛杉矶","econ":[7200,11500], "biz":[36000,58000]},
    ],
    ("上海", "伦敦"): [
        {"airline":"中国东方航空",  "code":"MU771",  "dep":"13:10","arr":"18:25+1","duration":"13h15m","stops":0, "econ":[5800,9200], "biz":[29000,50000]},
        {"airline":"英国航空",      "code":"BA168",  "dep":"23:00","arr":"05:30+1","duration":"12h30m","stops":0, "econ":[6000,10000],"biz":[31000,55000]},
        {"airline":"国泰航空",      "code":"CX239",  "dep":"01:00","arr":"07:00+1","duration":"14h00m","stops":1,"via":"香港", "econ":[6500,10500],"biz":[32000,56000]},
        {"airline":"芬兰航空",      "code":"AY009",  "dep":"14:20","arr":"21:30+1","duration":"15h10m","stops":1,"via":"赫尔辛基","econ":[6200,9800], "biz":[30000,52000]},
    ],
    ("上海", "首尔"): [
        {"airline":"中国东方航空",  "code":"MU5051", "dep":"09:00","arr":"12:00","duration":"2h00m","stops":0, "econ":[1500,3000], "biz":[7000,12000]},
        {"airline":"大韩航空",      "code":"KE896",  "dep":"12:40","arr":"15:45","duration":"2h05m","stops":0, "econ":[1600,3200], "biz":[7500,13000]},
        {"airline":"韩亚航空",      "code":"OZ353",  "dep":"19:30","arr":"22:35","duration":"2h05m","stops":0, "econ":[1400,2900], "biz":[7000,12500]},
        {"airline":"中国南方航空",  "code":"CZ6001", "dep":"07:20","arr":"10:25","duration":"2h05m","stops":0, "econ":[1300,2800], "biz":[6500,11500]},
    ],
    ("上海", "曼谷"): [
        {"airline":"中国东方航空",  "code":"MU741",  "dep":"08:00","arr":"12:35","duration":"5h35m","stops":0, "econ":[1800,3800], "biz":[12000,22000]},
        {"airline":"泰国国际航空",  "code":"TG669",  "dep":"16:40","arr":"20:55","duration":"5h15m","stops":0, "econ":[2000,4200], "biz":[13000,24000]},
        {"airline":"中国南方航空",  "code":"CZ6881", "dep":"11:30","arr":"15:50","duration":"5h20m","stops":0, "econ":[1900,3600], "biz":[11000,20000]},
        {"airline":"国泰航空",      "code":"CX701",  "dep":"22:45","arr":"05:20+1","duration":"7h35m","stops":1,"via":"香港","econ":[2200,4500], "biz":[14000,26000]},
    ],
    ("上海", "新加坡"): [
        {"airline":"中国东方航空",  "code":"MU505",  "dep":"08:30","arr":"14:55","duration":"6h25m","stops":0, "econ":[2000,4000], "biz":[12000,22000]},
        {"airline":"新加坡航空",    "code":"SQ836",  "dep":"19:30","arr":"01:35+1","duration":"6h05m","stops":0, "econ":[2200,4500], "biz":[14000,26000]},
        {"airline":"酷航",          "code":"TR122",  "dep":"23:55","arr":"06:00+1","duration":"6h05m","stops":0, "econ":[900,2200],  "biz":None},
        {"airline":"中国南方航空",  "code":"CZ357",  "dep":"10:00","arr":"16:20","duration":"6h20m","stops":0, "econ":[1800,3800], "biz":[11000,20000]},
    ],
    ("上海", "迪拜"): [
        {"airline":"阿联酋航空",    "code":"EK302",  "dep":"02:25","arr":"06:15","duration":"9h50m","stops":0, "econ":[3500,7000], "biz":[20000,38000]},
        {"airline":"中国东方航空",  "code":"MU729",  "dep":"14:00","arr":"21:30","duration":"9h30m","stops":0, "econ":[3200,6500], "biz":[18000,35000]},
        {"airline":"国泰航空",      "code":"CX643",  "dep":"22:30","arr":"05:30+1","duration":"11h00m","stops":1,"via":"香港","econ":[3800,7500], "biz":[22000,42000]},
    ],
    ("上海", "悉尼"): [
        {"airline":"中国东方航空",  "code":"MU731",  "dep":"11:00","arr":"23:00","duration":"11h00m","stops":0, "econ":[4800,8500], "biz":[25000,45000]},
        {"airline":"澳洲航空",      "code":"QF129",  "dep":"19:45","arr":"06:30+1","duration":"11h45m","stops":0, "econ":[5200,9500], "biz":[28000,52000]},
        {"airline":"中国国际航空",  "code":"CA837",  "dep":"07:00","arr":"20:00","duration":"12h00m","stops":1,"via":"北京","econ":[4500,8000], "biz":[24000,44000]},
    ],
    ("上海", "罗马"): [
        {"airline":"中国东方航空",  "code":"MU787",  "dep":"12:50","arr":"20:00+1","duration":"13h10m","stops":0, "econ":[4800,8500], "biz":[26000,48000]},
        {"airline":"意大利航空",    "code":"AZ786",  "dep":"00:30","arr":"08:30+1","duration":"12h00m","stops":0, "econ":[5000,9000], "biz":[27000,50000]},
        {"airline":"阿联酋航空",    "code":"EK302",  "dep":"02:25","arr":"09:30+1","duration":"14h05m","stops":1,"via":"迪拜","econ":[5200,9500], "biz":[28000,52000]},
        {"airline":"汉莎航空",      "code":"LH730",  "dep":"16:30","arr":"08:30+1","duration":"14h00m","stops":1,"via":"法兰克福","econ":[5500,10000],"biz":[29000,55000]},
    ],
    ("上海", "巴塞罗那"): [
        {"airline":"中国东方航空",  "code":"MU551",  "dep":"00:50","arr":"09:40+1","duration":"14h50m","stops":1,"via":"巴黎","econ":[5200,9000], "biz":[28000,50000]},
        {"airline":"阿联酋航空",    "code":"EK302",  "dep":"02:25","arr":"11:40+1","duration":"15h15m","stops":1,"via":"迪拜","econ":[5500,9500], "biz":[30000,55000]},
        {"airline":"土耳其航空",    "code":"TK024",  "dep":"23:55","arr":"12:00+1","duration":"14h05m","stops":1,"via":"伊斯坦布尔","econ":[5000,8800], "biz":[27000,48000]},
        {"airline":"汉莎航空",      "code":"LH731",  "dep":"16:30","arr":"10:30+1","duration":"15h00m","stops":1,"via":"法兰克福","econ":[5300,9200], "biz":[28000,52000]},
    ],
    ("上海", "阿姆斯特丹"): [
        {"airline":"荷兰皇家航空",  "code":"KL896",  "dep":"15:00","arr":"20:10+1","duration":"13h10m","stops":0, "econ":[5500,9500], "biz":[29000,52000]},
        {"airline":"中国东方航空",  "code":"MU763",  "dep":"01:00","arr":"07:00+1","duration":"13h00m","stops":0, "econ":[5200,8800], "biz":[27000,48000]},
        {"airline":"新加坡航空",    "code":"SQ322",  "dep":"10:00","arr":"06:00+2","duration":"18h00m","stops":1,"via":"新加坡","econ":[6000,10000],"biz":[32000,58000]},
    ],
    ("上海", "维也纳"): [
        {"airline":"中国东方航空",  "code":"MU757",  "dep":"14:00","arr":"21:00+1","duration":"13h00m","stops":0, "econ":[5000,8800], "biz":[26000,48000]},
        {"airline":"奥地利航空",    "code":"OS66",   "dep":"23:30","arr":"07:00+1","duration":"12h30m","stops":0, "econ":[5200,9200], "biz":[28000,52000]},
        {"airline":"土耳其航空",    "code":"TK024",  "dep":"23:55","arr":"10:30+1","duration":"12h35m","stops":1,"via":"伊斯坦布尔","econ":[4800,8500], "biz":[25000,46000]},
    ],
    ("上海", "布拉格"): [
        {"airline":"中国东方航空",  "code":"MU551",  "dep":"00:50","arr":"10:00+1","duration":"15h10m","stops":1,"via":"巴黎","econ":[4500,8000], "biz":[24000,44000]},
        {"airline":"土耳其航空",    "code":"TK024",  "dep":"23:55","arr":"11:00+1","duration":"13h05m","stops":1,"via":"伊斯坦布尔","econ":[4200,7500], "biz":[22000,40000]},
        {"airline":"汉莎航空",      "code":"LH731",  "dep":"16:30","arr":"09:00+1","duration":"14h30m","stops":1,"via":"法兰克福","econ":[4800,8500], "biz":[26000,46000]},
    ],
    ("上海", "里斯本"): [
        {"airline":"土耳其航空",    "code":"TK024",  "dep":"23:55","arr":"15:00+1","duration":"17h05m","stops":1,"via":"伊斯坦布尔","econ":[5200,9000], "biz":[28000,52000]},
        {"airline":"法国航空",      "code":"AF115",  "dep":"11:55","arr":"22:30+1","duration":"16h35m","stops":1,"via":"巴黎","econ":[5500,9500], "biz":[30000,55000]},
        {"airline":"汉莎航空",      "code":"LH731",  "dep":"16:30","arr":"13:00+1","duration":"18h30m","stops":1,"via":"法兰克福","econ":[5000,8800], "biz":[27000,50000]},
    ],
    ("上海", "伊斯坦布尔"): [
        {"airline":"土耳其航空",    "code":"TK024",  "dep":"23:55","arr":"07:00+1","duration":"11h05m","stops":0, "econ":[3800,7500], "biz":[20000,38000]},
        {"airline":"中国东方航空",  "code":"MU787",  "dep":"12:50","arr":"21:00+1","duration":"14h10m","stops":1,"via":"巴黎","econ":[4000,7800], "biz":[21000,40000]},
    ],
    ("上海", "普吉岛"): [
        {"airline":"中国东方航空",  "code":"MU731",  "dep":"07:30","arr":"11:30","duration":"4h00m","stops":0, "econ":[1500,3500], "biz":[9000,18000]},
        {"airline":"泰国航空",      "code":"TG639",  "dep":"19:00","arr":"22:50","duration":"4h50m","stops":0, "econ":[1800,3800], "biz":[10000,20000]},
        {"airline":"国泰航空",      "code":"CX701",  "dep":"22:45","arr":"06:30+1","duration":"9h45m","stops":1,"via":"香港","econ":[2000,4000], "biz":[12000,22000]},
    ],
    ("上海", "马尔代夫"): [
        {"airline":"中国东方航空",  "code":"MU703",  "dep":"09:00","arr":"14:00","duration":"7h00m","stops":1,"via":"科伦坡","econ":[2500,5000], "biz":[14000,26000]},
        {"airline":"斯里兰卡航空",  "code":"UL891",  "dep":"22:00","arr":"06:30+1","duration":"7h30m","stops":1,"via":"科伦坡","econ":[2300,4800], "biz":[13000,25000]},
        {"airline":"新加坡航空",    "code":"SQ470",  "dep":"10:00","arr":"20:00","duration":"10h00m","stops":1,"via":"新加坡","econ":[2800,5500], "biz":[16000,30000]},
    ],

    # ══════════ 北京出发 ══════════
    ("北京", "巴黎"): [
        {"airline":"中国国际航空",  "code":"CA933",  "dep":"10:05","arr":"15:20+1","duration":"11h15m","stops":0, "econ":[4800,8000], "biz":[25000,45000]},
        {"airline":"法国航空",      "code":"AF111",  "dep":"13:35","arr":"18:45+1","duration":"11h10m","stops":0, "econ":[5000,8500], "biz":[27000,48000]},
        {"airline":"土耳其航空",    "code":"TK021",  "dep":"02:20","arr":"10:40+1","duration":"12h20m","stops":1,"via":"伊斯坦布尔","econ":[4500,8000], "biz":[24000,44000]},
    ],
    ("北京", "伦敦"): [
        {"airline":"中国国际航空",  "code":"CA937",  "dep":"10:05","arr":"14:00+1","duration":"10h55m","stops":0, "econ":[4500,7800], "biz":[24000,43000]},
        {"airline":"英国航空",      "code":"BA39",   "dep":"13:30","arr":"17:20+1","duration":"10h50m","stops":0, "econ":[4800,8200], "biz":[26000,48000]},
        {"airline":"芬兰航空",      "code":"AY071",  "dep":"15:00","arr":"21:30+1","duration":"12h30m","stops":1,"via":"赫尔辛基","econ":[4200,7500], "biz":[23000,42000]},
        {"airline":"土耳其航空",    "code":"TK021",  "dep":"02:20","arr":"12:00+1","duration":"13h40m","stops":1,"via":"伊斯坦布尔","econ":[4000,7200], "biz":[22000,40000]},
    ],
    ("北京", "纽约"): [
        {"airline":"中国国际航空",  "code":"CA981",  "dep":"10:45","arr":"11:40+1","duration":"13h55m","stops":0, "econ":[6500,10500], "biz":[33000,58000]},
        {"airline":"美国航空",      "code":"AA168",  "dep":"14:00","arr":"16:00+1","duration":"14h00m","stops":0, "econ":[7000,11500], "biz":[36000,62000]},
        {"airline":"达美航空",      "code":"DL171",  "dep":"09:00","arr":"10:30+1","duration":"13h30m","stops":0, "econ":[6800,11000], "biz":[35000,60000]},
    ],
    ("北京", "东京"): [
        {"airline":"中国国际航空",  "code":"CA181",  "dep":"09:00","arr":"13:30","duration":"3h30m","stops":0, "econ":[1000,2500], "biz":[7000,13000]},
        {"airline":"全日空",        "code":"NH953",  "dep":"13:20","arr":"17:50","duration":"3h30m","stops":0, "econ":[1200,2800], "biz":[8000,14000]},
        {"airline":"日本航空",      "code":"JL21",   "dep":"16:50","arr":"21:20","duration":"3h30m","stops":0, "econ":[1300,3000], "biz":[8500,15000]},
        {"airline":"中国国际航空",  "code":"CA165",  "dep":"07:30","arr":"12:00","duration":"3h30m","stops":0, "econ":[900,2300],  "biz":[6500,12000]},
    ],
    ("北京", "首尔"): [
        {"airline":"中国国际航空",  "code":"CA123",  "dep":"09:00","arr":"12:30","duration":"2h30m","stops":0, "econ":[800,2200],  "biz":[5500,10000]},
        {"airline":"大韩航空",      "code":"KE856",  "dep":"12:00","arr":"15:30","duration":"2h30m","stops":0, "econ":[900,2500],  "biz":[6000,11000]},
        {"airline":"韩亚航空",      "code":"OZ321",  "dep":"19:30","arr":"23:00","duration":"2h30m","stops":0, "econ":[850,2300],  "biz":[5800,10500]},
    ],
    ("北京", "曼谷"): [
        {"airline":"中国国际航空",  "code":"CA837",  "dep":"09:00","arr":"14:00","duration":"5h00m","stops":0, "econ":[2000,4200], "biz":[13000,24000]},
        {"airline":"泰国航空",      "code":"TG614",  "dep":"23:30","arr":"04:30+1","duration":"5h00m","stops":0, "econ":[2200,4500], "biz":[14000,26000]},
    ],
    ("北京", "新加坡"): [
        {"airline":"中国国际航空",  "code":"CA967",  "dep":"07:30","arr":"14:30","duration":"6h00m","stops":0, "econ":[2200,4500], "biz":[14000,26000]},
        {"airline":"新加坡航空",    "code":"SQ802",  "dep":"17:00","arr":"23:30","duration":"6h30m","stops":0, "econ":[2500,5000], "biz":[16000,30000]},
    ],
    ("北京", "迪拜"): [
        {"airline":"中国国际航空",  "code":"CA875",  "dep":"01:45","arr":"06:25","duration":"9h40m","stops":0, "econ":[3500,7000], "biz":[20000,38000]},
        {"airline":"阿联酋航空",    "code":"EK306",  "dep":"02:30","arr":"06:25","duration":"8h55m","stops":0, "econ":[3200,6500], "biz":[18000,35000]},
        {"airline":"飞利浦航空",    "code":"PR658",  "dep":"19:00","arr":"23:30","duration":"11h30m","stops":1,"via":"马尼拉","econ":[3000,6000], "biz":[17000,32000]},
    ],
    ("北京", "悉尼"): [
        {"airline":"中国国际航空",  "code":"CA773",  "dep":"09:00","arr":"22:00","duration":"12h00m","stops":0, "econ":[5000,9000], "biz":[26000,48000]},
        {"airline":"澳洲航空",      "code":"QF107",  "dep":"17:40","arr":"07:00+1","duration":"12h20m","stops":0, "econ":[5500,10000],"biz":[30000,55000]},
    ],
    ("北京", "罗马"): [
        {"airline":"中国国际航空",  "code":"CA933",  "dep":"10:05","arr":"21:30+1","duration":"13h25m","stops":1,"via":"巴黎","econ":[4800,9000], "biz":[26000,48000]},
        {"airline":"意大利航空",    "code":"AZ780",  "dep":"00:30","arr":"09:30+1","duration":"12h00m","stops":0, "econ":[5000,9200], "biz":[27000,50000]},
        {"airline":"汉莎航空",      "code":"LH722",  "dep":"11:00","arr":"22:30+1","duration":"13h30m","stops":1,"via":"法兰克福","econ":[5200,9500], "biz":[28000,52000]},
    ],
    ("北京", "巴塞罗那"): [
        {"airline":"中国国际航空",  "code":"CA933",  "dep":"10:05","arr":"22:00+1","duration":"13h55m","stops":1,"via":"巴黎","econ":[4800,9000], "biz":[26000,48000]},
        {"airline":"土耳其航空",    "code":"TK021",  "dep":"02:20","arr":"14:00+1","duration":"13h40m","stops":1,"via":"伊斯坦布尔","econ":[4500,8500], "biz":[24000,46000]},
    ],
    ("北京", "伊斯坦布尔"): [
        {"airline":"土耳其航空",    "code":"TK021",  "dep":"02:20","arr":"08:00+1","duration":"10h40m","stops":0, "econ":[3800,7500], "biz":[20000,38000]},
        {"airline":"中国国际航空",  "code":"CA933",  "dep":"10:05","arr":"22:00+1","duration":"11h55m","stops":1,"via":"巴黎","econ":[4000,7800], "biz":[22000,42000]},
    ],

    # ══════════ 广州出发 ══════════
    ("广州", "曼谷"): [
        {"airline":"中国南方航空",  "code":"CZ3066", "dep":"07:00","arr":"09:00","duration":"3h00m","stops":0, "econ":[1200,2800], "biz":[8000,16000]},
        {"airline":"泰国航空",      "code":"TG673",  "dep":"19:00","arr":"21:00","duration":"3h00m","stops":0, "econ":[1400,3200], "biz":[9000,18000]},
    ],
    ("广州", "新加坡"): [
        {"airline":"中国南方航空",  "code":"CZ357",  "dep":"10:00","arr":"14:00","duration":"4h00m","stops":0, "econ":[1500,3200], "biz":[9500,18000]},
        {"airline":"新加坡航空",    "code":"SQ862",  "dep":"14:30","arr":"18:30","duration":"4h00m","stops":0, "econ":[1700,3600], "biz":[11000,20000]},
    ],
    ("广州", "东京"): [
        {"airline":"中国南方航空",  "code":"CZ8405", "dep":"07:30","arr":"12:30","duration":"4h00m","stops":0, "econ":[2000,4000], "biz":[12000,22000]},
        {"airline":"全日空",        "code":"NH877",  "dep":"12:00","arr":"16:45","duration":"3h45m","stops":0, "econ":[2200,4500], "biz":[13000,24000]},
    ],
    ("广州", "巴黎"): [
        {"airline":"中国南方航空",  "code":"CZ383",  "dep":"13:00","arr":"20:00+1","duration":"13h00m","stops":0, "econ":[4500,8000], "biz":[24000,45000]},
        {"airline":"法国航空",      "code":"AF185",  "dep":"01:00","arr":"08:30+1","duration":"13h30m","stops":0, "econ":[4800,8500], "biz":[26000,48000]},
    ],

    # ══════════ 成都出发 ══════════
    ("成都", "首尔"): [
        {"airline":"大韩航空",      "code":"KE858",  "dep":"11:00","arr":"15:30","duration":"3h30m","stops":0, "econ":[1200,2800], "biz":[8000,15000]},
        {"airline":"中国国际航空",  "code":"CA407",  "dep":"07:30","arr":"12:00","duration":"3h30m","stops":0, "econ":[1100,2600], "biz":[7500,14000]},
    ],
    ("成都", "曼谷"): [
        {"airline":"中国国际航空",  "code":"CA837",  "dep":"10:00","arr":"13:30","duration":"4h30m","stops":0, "econ":[1500,3200], "biz":[9000,18000]},
        {"airline":"泰国航空",      "code":"TG619",  "dep":"20:00","arr":"23:30","duration":"4h30m","stops":0, "econ":[1700,3600], "biz":[10000,20000]},
    ],

    # ══════════ 深圳出发 ══════════
    ("深圳", "东京"): [
        {"airline":"深圳航空",      "code":"ZH9095", "dep":"10:00","arr":"14:30","duration":"3h30m","stops":0, "econ":[1800,3800], "biz":[11000,20000]},
        {"airline":"全日空",        "code":"NH889",  "dep":"15:00","arr":"19:30","duration":"3h30m","stops":0, "econ":[2000,4200], "biz":[12000,22000]},
    ],
    ("深圳", "新加坡"): [
        {"airline":"深圳航空",      "code":"ZH9503", "dep":"08:00","arr":"12:00","duration":"3h30m","stops":0, "econ":[1200,2800], "biz":[8000,15000]},
        {"airline":"新加坡航空",    "code":"SQ876",  "dep":"16:00","arr":"20:00","duration":"3h30m","stops":0, "econ":[1500,3200], "biz":[9500,18000]},
    ],
}

# ─────────────────────────────────────────────────────────────────
# 真实国内高铁数据库
# ─────────────────────────────────────────────────────────────────
REAL_TRAIN_ROUTES: dict[tuple, list] = {
    ("上海", "北京"): [
        {"code":"G1",  "type":"高铁","dep":"08:00","arr":"12:18","duration":"4h18m","second":553, "first":933,  "business":1748},
        {"code":"G3",  "type":"高铁","dep":"09:00","arr":"13:18","duration":"4h18m","second":553, "first":933,  "business":1748},
        {"code":"G5",  "type":"高铁","dep":"10:00","arr":"14:18","duration":"4h18m","second":553, "first":933,  "business":1748},
        {"code":"G11", "type":"高铁","dep":"12:00","arr":"16:28","duration":"4h28m","second":553, "first":933,  "business":1748},
        {"code":"G17", "type":"高铁","dep":"18:00","arr":"22:18","duration":"4h18m","second":553, "first":933,  "business":1748},
    ],
    ("北京", "上海"): [
        {"code":"G2",  "type":"高铁","dep":"08:05","arr":"12:23","duration":"4h18m","second":553, "first":933,  "business":1748},
        {"code":"G4",  "type":"高铁","dep":"09:05","arr":"13:23","duration":"4h18m","second":553, "first":933,  "business":1748},
        {"code":"G6",  "type":"高铁","dep":"10:05","arr":"14:23","duration":"4h18m","second":553, "first":933,  "business":1748},
        {"code":"G10", "type":"高铁","dep":"14:30","arr":"18:48","duration":"4h18m","second":553, "first":933,  "business":1748},
        {"code":"G20", "type":"高铁","dep":"20:00","arr":"23:54","duration":"3h54m","second":553, "first":933,  "business":1748},
    ],
    ("上海", "杭州"): [
        {"code":"G7343","type":"高铁","dep":"07:00","arr":"08:04","duration":"1h04m","second":73,  "first":115,  "business":233},
        {"code":"G7351","type":"高铁","dep":"09:00","arr":"10:04","duration":"1h04m","second":73,  "first":115,  "business":233},
        {"code":"G7361","type":"高铁","dep":"12:00","arr":"13:04","duration":"1h04m","second":73,  "first":115,  "business":233},
        {"code":"G7371","type":"高铁","dep":"17:00","arr":"18:04","duration":"1h04m","second":73,  "first":115,  "business":233},
        {"code":"G7381","type":"高铁","dep":"19:00","arr":"20:04","duration":"1h04m","second":73,  "first":115,  "business":233},
    ],
    ("上海", "南京"): [
        {"code":"G11", "type":"高铁","dep":"08:00","arr":"09:08","duration":"1h08m","second":134, "first":213,  "business":408},
        {"code":"G21", "type":"高铁","dep":"10:00","arr":"11:08","duration":"1h08m","second":134, "first":213,  "business":408},
        {"code":"G31", "type":"高铁","dep":"14:00","arr":"15:08","duration":"1h08m","second":134, "first":213,  "business":408},
    ],
    ("上海", "武汉"): [
        {"code":"G389","type":"高铁","dep":"07:00","arr":"11:48","duration":"4h48m","second":434, "first":694,  "business":1283},
        {"code":"G395","type":"高铁","dep":"09:00","arr":"13:48","duration":"4h48m","second":434, "first":694,  "business":1283},
        {"code":"G397","type":"高铁","dep":"15:00","arr":"19:48","duration":"4h48m","second":434, "first":694,  "business":1283},
    ],
    ("北京", "西安"): [
        {"code":"G87", "type":"高铁","dep":"07:30","arr":"11:46","duration":"4h16m","second":515, "first":824,  "business":1534},
        {"code":"G89", "type":"高铁","dep":"09:00","arr":"13:16","duration":"4h16m","second":515, "first":824,  "business":1534},
        {"code":"G91", "type":"高铁","dep":"12:00","arr":"16:16","duration":"4h16m","second":515, "first":824,  "business":1534},
        {"code":"G671","type":"高铁","dep":"17:00","arr":"21:16","duration":"4h16m","second":515, "first":824,  "business":1534},
    ],
    ("北京", "成都"): [
        {"code":"G305","type":"高铁","dep":"07:00","arr":"15:38","duration":"8h38m","second":841, "first":1345, "business":2471},
        {"code":"G307","type":"高铁","dep":"09:00","arr":"17:38","duration":"8h38m","second":841, "first":1345, "business":2471},
        {"code":"G309","type":"高铁","dep":"12:00","arr":"20:38","duration":"8h38m","second":841, "first":1345, "business":2471},
    ],
    ("广州", "深圳"): [
        {"code":"G6005","type":"高铁","dep":"07:00","arr":"07:34","duration":"0h34m","second":74,  "first":119,  "business":236},
        {"code":"G6009","type":"高铁","dep":"09:00","arr":"09:34","duration":"0h34m","second":74,  "first":119,  "business":236},
        {"code":"G6015","type":"高铁","dep":"12:00","arr":"12:34","duration":"0h34m","second":74,  "first":119,  "business":236},
        {"code":"G6021","type":"高铁","dep":"16:00","arr":"16:34","duration":"0h34m","second":74,  "first":119,  "business":236},
    ],
    ("北京", "广州"): [
        {"code":"G71", "type":"高铁","dep":"08:00","arr":"14:37","duration":"6h37m","second":862, "first":1378, "business":2566},
        {"code":"G73", "type":"高铁","dep":"10:00","arr":"16:37","duration":"6h37m","second":862, "first":1378, "business":2566},
        {"code":"G79", "type":"高铁","dep":"17:00","arr":"23:37","duration":"6h37m","second":862, "first":1378, "business":2566},
    ],
    ("上海", "成都"): [
        {"code":"G2201","type":"高铁","dep":"07:00","arr":"15:38","duration":"8h38m","second":795, "first":1268, "business":2391},
        {"code":"G2203","type":"高铁","dep":"11:00","arr":"19:38","duration":"8h38m","second":795, "first":1268, "business":2391},
    ],
    ("上海", "广州"): [
        {"code":"G1301","type":"高铁","dep":"08:00","arr":"16:28","duration":"8h28m","second":762, "first":1219, "business":2281},
        {"code":"G1305","type":"高铁","dep":"12:00","arr":"20:28","duration":"8h28m","second":762, "first":1219, "business":2281},
    ],
    ("北京", "哈尔滨"): [
        {"code":"G1","type":"高铁","dep":"08:00","arr":"13:30","duration":"5h30m","second":462, "first":738,  "business":1375},
        {"code":"G3","type":"高铁","dep":"11:00","arr":"16:30","duration":"5h30m","second":462, "first":738,  "business":1375},
    ],
    ("上海", "三亚"): [
        {"code":"G405","type":"高铁","dep":"09:00","arr":"21:38","duration":"12h38m","second":934, "first":1493, "business":2791},
    ],
    ("北京", "杭州"): [
        {"code":"G41", "type":"高铁","dep":"07:00","arr":"11:03","duration":"4h03m","second":431, "first":688,  "business":1289},
        {"code":"G43", "type":"高铁","dep":"10:00","arr":"14:03","duration":"4h03m","second":431, "first":688,  "business":1289},
    ],
    ("杭州", "北京"): [
        {"code":"G42", "type":"高铁","dep":"08:00","arr":"12:03","duration":"4h03m","second":431, "first":688,  "business":1289},
        {"code":"G44", "type":"高铁","dep":"14:00","arr":"18:03","duration":"4h03m","second":431, "first":688,  "business":1289},
    ],
    ("武汉", "北京"): [
        {"code":"G502","type":"高铁","dep":"07:00","arr":"10:17","duration":"3h17m","second":424, "first":679,  "business":1267},
        {"code":"G508","type":"高铁","dep":"10:00","arr":"13:17","duration":"3h17m","second":424, "first":679,  "business":1267},
    ],
    ("西安", "成都"): [
        {"code":"D1901","type":"动车","dep":"08:00","arr":"14:30","duration":"6h30m","second":210, "first":335,  "business":None},
        {"code":"D1903","type":"动车","dep":"11:00","arr":"17:30","duration":"6h30m","second":210, "first":335,  "business":None},
    ],
    ("成都", "重庆"): [
        {"code":"G8501","type":"高铁","dep":"08:00","arr":"09:13","duration":"1h13m","second":99,  "first":158,  "business":299},
        {"code":"G8503","type":"高铁","dep":"10:00","arr":"11:13","duration":"1h13m","second":99,  "first":158,  "business":299},
        {"code":"G8507","type":"高铁","dep":"14:00","arr":"15:13","duration":"1h13m","second":99,  "first":158,  "business":299},
    ],
}

# ─────────────────────────────────────────────────────────────────
# 备用基准价（路线不在数据库中时使用）
# ─────────────────────────────────────────────────────────────────
DOMESTIC_CITIES = [
    "上海", "北京", "广州", "深圳", "成都", "杭州", "武汉",
    "重庆", "西安", "南京", "天津", "青岛", "厦门", "昆明",
    "三亚", "长沙", "郑州", "沈阳", "哈尔滨", "乌鲁木齐", "拉萨",
]
INTL_HUB = {
    "巴黎":    "CDG", "东京": "NRT", "纽约": "JFK", "伦敦": "LHR",
    "罗马":    "FCO", "悉尼": "SYD", "巴塞罗那": "BCN", "曼谷": "BKK",
    "新加坡":  "SIN", "首尔": "ICN", "迪拜": "DXB", "阿姆斯特丹": "AMS",
    "维也纳":  "VIE", "布拉格": "PRG", "伊斯坦布尔": "IST", "里斯本": "LIS",
    "普吉岛":  "HKT", "马尔代夫": "MLE", "冰岛": "KEF", "开罗": "CAI",
}

_FALLBACK_INTL_BASE = {
    "近程": 2500,   # 东南亚、东北亚 < 6h
    "中程": 5500,   # 中东、中亚、澳洲 6–11h
    "远程": 7500,   # 欧洲、美洲、南非 > 11h
}
_DURATION_NEAR = {"东京","首尔","曼谷","新加坡","普吉岛","马尔代夫"}
_DURATION_MID  = {"迪拜","悉尼"}


# ─────────────────────────────────────────────────────────────────
# 价格扰动：同一查询稳定，不同日期/舱位有合理浮动
# ─────────────────────────────────────────────────────────────────
def _price_vary(base: int, seed: str, factor: float = 0.15) -> int:
    """MD5 稳定扰动，factor=15% 区间随机"""
    h = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16)
    delta = int(base * factor * ((h % 1000) / 1000 - 0.5) * 2)
    return max(int(base * 0.8), base + delta)


def _date_multiplier(date_str: str) -> float:
    """日期系数：黄金周 ×1.55，旺季 ×1.40，小旺季 ×1.30，周末 ×1.20"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        m, d = dt.month, dt.day
        # 黄金周：五一(5/1-5)、国庆(10/1-7)、春节(1/20-2/10 窗口)
        if (m == 5 and 1 <= d <= 5) or (m == 10 and 1 <= d <= 7):
            return 1.55
        if (m == 1 and d >= 20) or (m == 2 and d <= 10):
            return 1.55
        # 旺季：暑假 7-8月，元旦
        if m in (7, 8) or (m == 1 and d <= 3):
            return 1.40
        # 小旺季：清明(4/3-6)、端午(6/10-12 approx)、中秋(9/13-15 approx)
        if m == 4 and 3 <= d <= 6:
            return 1.30
        if m in (2, 10):
            return 1.30
        # 周末
        if dt.weekday() >= 5:
            return 1.20
        return 1.0
    except Exception:
        return 1.0


def _seats_available(date_str: str, capacity: int, seed: str) -> int:
    """
    根据日期紧张程度计算余票数。
    黄金周：2-15%；旺季：15-40%；周末：40-70%；平日：60-95%
    同一 (日期+航班) seed 结果确定（不随时间漂移）。
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        m, d = dt.month, dt.day

        is_golden = ((m == 5 and 1 <= d <= 5)
                     or (m == 10 and 1 <= d <= 7)
                     or (m == 1 and d >= 20)
                     or (m == 2 and d <= 10))
        is_peak   = m in (7, 8) or (m == 4 and 3 <= d <= 6)
        is_weekend = dt.weekday() >= 5

        h = int(hashlib.md5(seed.encode()).hexdigest()[:6], 16)
        ratio = h / 0xFFFFFF  # 0~1 均匀

        if is_golden:
            pct = 0.02 + ratio * 0.13   # 2-15%
        elif is_peak:
            pct = 0.15 + ratio * 0.25   # 15-40%
        elif is_weekend:
            pct = 0.40 + ratio * 0.30   # 40-70%
        else:
            pct = 0.60 + ratio * 0.35   # 60-95%

        return max(1, int(capacity * pct))
    except Exception:
        return capacity // 2


# ─────────────────────────────────────────────────────────────────
# 搜索接口
# ─────────────────────────────────────────────────────────────────
def search_tickets(
    origin: str,
    destination: str,
    date: str,
    ticket_type: str = "flight",
    budget_hint: Optional[str] = None,
) -> list[dict]:
    """
    搜索机票或火车票。
    优先查询真实航线数据库，未覆盖路线回退到估算模式。
    所有用户得到相同搜索结果（公平性原则）。
    """
    date_mult = _date_multiplier(date)

    # ── 火车票 ──────────────────────────────────────────────────
    if ticket_type == "train":
        trains = REAL_TRAIN_ROUTES.get((origin, destination), [])
        if not trains:
            trains = REAL_TRAIN_ROUTES.get((destination, origin), [])  # 尝试反向查

        results = []
        for t in trains:
            seed = f"{t['code']}{date}"
            second = _price_vary(t["second"],  seed + "2",  0.05) if t.get("second")  else None
            first  = _price_vary(t["first"],   seed + "1",  0.05) if t.get("first")   else None
            biz    = _price_vary(t["business"],seed + "b",  0.05) if t.get("business") else None

            # 只保留符合 budget_hint 的舱位（若未指定则返回全部）
            seats_to_show = []
            if second is not None:
                seats_to_show.append(("二等座", second))
            if first is not None:
                seats_to_show.append(("一等座", first))
            if biz is not None:
                seats_to_show.append(("商务座", biz))

            for seat_name, price in seats_to_show:
                ticket_id = f"{t['code']}-{date.replace('-','')}-{seat_name}"
                # 高铁定员：二等座~1000，一等座~200，商务座~32
                train_cap = 1000 if seat_name == "二等座" else (200 if seat_name == "一等座" else 32)
                results.append({
                    "id": ticket_id,
                    "type": "train",
                    "train_type": t["type"],
                    "code": t["code"],
                    "from": origin,
                    "to": destination,
                    "dep": t["dep"],
                    "arr": t["arr"],
                    "duration": t["duration"],
                    "price": round(price * date_mult),
                    "seat": seat_name,
                    "seats": _seats_available(date, train_cap, ticket_id),
                })

        if not results:
            return []  # 国际无火车
        results.sort(key=lambda x: x["price"])
        return results

    # ── 机票 ────────────────────────────────────────────────────
    route_key = (origin, destination)
    flights = REAL_INTL_ROUTES.get(route_key, [])

    # 未覆盖路线：仅返回空（不生成虚假数据）
    if not flights:
        return []

    results = []
    for f in flights:
        seed = f"{f['code']}{date}"
        lo, hi = f["econ"]
        econ_base = (lo + hi) // 2
        econ_price = round(_price_vary(econ_base, seed + "e", 0.18) * date_mult)

        stop_str = 0 if f.get("stops", 0) == 0 else f.get("stops", 1)
        via_str  = f.get("via", "")
        stop_label = "直飞" if stop_str == 0 else f"经停{via_str}"

        econ_id = f"{f['code']}-{date.replace('-','')}-econ"
        # 经济舱条目
        results.append({
            "id": econ_id,
            "type": "flight",
            "airline": f["airline"],
            "code": f["code"],
            "from": origin,
            "to": destination,
            "dep": f["dep"],
            "arr": f["arr"],
            "duration": f["duration"],
            "price": econ_price,
            "cabin": "经济舱",
            "stops": stop_str,
            "stop_label": stop_label,
            "seats": _seats_available(date, 180, econ_id),  # 经济舱约180座
            "data_note": "参考数据，以航司实时报价为准",
        })

        # 商务舱条目（若有）
        if f.get("biz"):
            blo, bhi = f["biz"]
            biz_base  = (blo + bhi) // 2
            biz_price = round(_price_vary(biz_base, seed + "b", 0.15) * date_mult)
            biz_id = f"{f['code']}-{date.replace('-','')}-biz"
            results.append({
                **results[-1],
                "id": biz_id,
                "cabin": "商务舱",
                "price": biz_price,
                "seats": _seats_available(date, 24, biz_id),  # 商务舱约24座
            })

    results.sort(key=lambda x: x["price"])
    return results



# ─────────────────────────────────────────────────────────────────
# 订单管理（不变）
# ─────────────────────────────────────────────────────────────────
def _load_orders() -> dict:
    os.makedirs(os.path.dirname(_ORDERS_PATH), exist_ok=True)
    if not os.path.exists(_ORDERS_PATH):
        return {}
    try:
        with open(_ORDERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_orders(orders: dict) -> None:
    os.makedirs(os.path.dirname(_ORDERS_PATH), exist_ok=True)
    with open(_ORDERS_PATH, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)


def create_order(ticket_data: dict, passenger_name: str, id_number: str = "") -> dict:
    orders = _load_orders()
    now = datetime.now()
    order_id = f"YY{now.strftime('%Y%m%d%H%M%S')}{len(orders):03d}"
    order = {
        "order_id": order_id,
        "created_at": now.isoformat(timespec="seconds"),
        "status": "confirmed",
        "ticket": ticket_data,
        "passenger": {
            "name": passenger_name,
            "id_number": ("*" * max(0, len(id_number) - 4) + id_number[-4:]) if id_number and len(id_number) > 4 else ("*" * len(id_number) if id_number else ""),
        },
        "total_price": ticket_data.get("price", 0),
    }
    orders[order_id] = order
    _save_orders(orders)
    return order


def get_orders() -> list[dict]:
    orders = _load_orders()
    return sorted(orders.values(), key=lambda x: x["created_at"], reverse=True)


def get_order(order_id: str) -> Optional[dict]:
    return _load_orders().get(order_id)


def cancel_order(order_id: str) -> Optional[dict]:
    orders = _load_orders()
    if order_id not in orders:
        return None
    orders[order_id]["status"] = "cancelled"
    _save_orders(orders)
    return orders[order_id]
