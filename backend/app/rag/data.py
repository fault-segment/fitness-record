# backend/app/rag/data.py
# 常见食物营养数据（每100g），来源：中国食物成分表 + USDA
FOOD_DATA = [
    # 主食类
    {"name": "白米饭", "kcal": 116, "protein": 2.6, "carbs": 25.9, "fat": 0.3, "desc": "蒸熟的粳米饭"},
    {"name": "馒头", "kcal": 223, "protein": 7.0, "carbs": 44.2, "fat": 1.1, "desc": "小麦粉蒸制"},
    {"name": "面条", "kcal": 110, "protein": 3.5, "carbs": 22.0, "fat": 0.5, "desc": "煮熟的白面条"},
    {"name": "小米粥", "kcal": 46, "protein": 1.4, "carbs": 8.4, "fat": 0.7, "desc": "小米加水煮制的粥"},
    {"name": "全麦面包", "kcal": 247, "protein": 13.0, "carbs": 41.3, "fat": 3.4, "desc": "全麦粉烘焙面包"},
    {"name": "燕麦片", "kcal": 367, "protein": 13.5, "carbs": 66.3, "fat": 6.7, "desc": "即食燕麦片"},
    {"name": "红薯", "kcal": 86, "protein": 1.1, "carbs": 20.1, "fat": 0.1, "desc": "蒸熟的红薯"},
    {"name": "玉米", "kcal": 112, "protein": 4.0, "carbs": 22.8, "fat": 1.2, "desc": "煮熟的甜玉米"},

    # 肉类
    {"name": "猪瘦肉", "kcal": 143, "protein": 20.3, "carbs": 1.5, "fat": 6.2, "desc": "猪里脊肉"},
    {"name": "红烧肉", "kcal": 245, "protein": 15.3, "carbs": 5.2, "fat": 19.8, "desc": "五花肉红烧，含糖和酱油"},
    {"name": "鸡胸肉", "kcal": 133, "protein": 31.0, "carbs": 0.0, "fat": 1.2, "desc": "去皮鸡胸肉，水煮"},
    {"name": "鸡腿肉", "kcal": 181, "protein": 20.0, "carbs": 0.0, "fat": 11.0, "desc": "带皮鸡腿肉"},
    {"name": "牛肉", "kcal": 125, "protein": 22.0, "carbs": 2.0, "fat": 4.2, "desc": "牛瘦肉，煮熟的"},
    {"name": "羊肉", "kcal": 203, "protein": 19.0, "carbs": 0.0, "fat": 14.1, "desc": "羊瘦肉"},
    {"name": "猪排骨", "kcal": 264, "protein": 18.3, "carbs": 0.0, "fat": 20.4, "desc": "猪小排"},
    {"name": "培根", "kcal": 541, "protein": 12.0, "carbs": 1.0, "fat": 55.0, "desc": "烟熏培根肉"},

    # 蛋奶类
    {"name": "鸡蛋", "kcal": 155, "protein": 12.6, "carbs": 1.1, "fat": 11.0, "desc": "煮熟的鸡蛋"},
    {"name": "牛奶", "kcal": 65, "protein": 3.0, "carbs": 4.9, "fat": 3.6, "desc": "全脂牛奶"},
    {"name": "酸奶", "kcal": 72, "protein": 2.5, "carbs": 9.3, "fat": 2.7, "desc": "原味酸奶"},
    {"name": "奶酪", "kcal": 350, "protein": 25.0, "carbs": 1.3, "fat": 27.0, "desc": "切达奶酪"},

    # 蔬菜类
    {"name": "西红柿", "kcal": 18, "protein": 0.9, "carbs": 3.9, "fat": 0.2, "desc": "新鲜西红柿"},
    {"name": "黄瓜", "kcal": 16, "protein": 0.7, "carbs": 2.9, "fat": 0.1, "desc": "新鲜黄瓜"},
    {"name": "菠菜", "kcal": 23, "protein": 2.9, "carbs": 3.6, "fat": 0.4, "desc": "焯水菠菜"},
    {"name": "白菜", "kcal": 13, "protein": 1.5, "carbs": 2.2, "fat": 0.2, "desc": "大白菜"},
    {"name": "西兰花", "kcal": 35, "protein": 3.7, "carbs": 7.2, "fat": 0.4, "desc": "煮熟的西兰花"},
    {"name": "土豆", "kcal": 76, "protein": 2.0, "carbs": 17.5, "fat": 0.1, "desc": "煮熟的土豆"},
    {"name": "胡萝卜", "kcal": 41, "protein": 0.9, "carbs": 10.0, "fat": 0.2, "desc": "新鲜胡萝卜"},
    {"name": "豆腐", "kcal": 76, "protein": 8.1, "carbs": 1.9, "fat": 3.7, "desc": "嫩豆腐"},
    {"name": "豆芽", "kcal": 18, "protein": 2.1, "carbs": 2.6, "fat": 0.2, "desc": "绿豆芽"},

    # 水果类
    {"name": "苹果", "kcal": 52, "protein": 0.3, "carbs": 13.8, "fat": 0.2, "desc": "新鲜苹果"},
    {"name": "香蕉", "kcal": 89, "protein": 1.1, "carbs": 22.8, "fat": 0.3, "desc": "新鲜香蕉"},
    {"name": "橙子", "kcal": 47, "protein": 0.9, "carbs": 11.8, "fat": 0.1, "desc": "新鲜橙子"},
    {"name": "葡萄", "kcal": 69, "protein": 0.7, "carbs": 18.1, "fat": 0.2, "desc": "新鲜葡萄"},
    {"name": "西瓜", "kcal": 30, "protein": 0.6, "carbs": 7.6, "fat": 0.2, "desc": "新鲜西瓜"},
    {"name": "草莓", "kcal": 32, "protein": 0.7, "carbs": 7.7, "fat": 0.3, "desc": "新鲜草莓"},
    {"name": "牛油果", "kcal": 160, "protein": 2.0, "carbs": 8.5, "fat": 14.7, "desc": "新鲜牛油果"},

    # 水产类
    {"name": "三文鱼", "kcal": 208, "protein": 20.4, "carbs": 0.0, "fat": 13.4, "desc": "养殖三文鱼"},
    {"name": "虾仁", "kcal": 99, "protein": 24.0, "carbs": 0.2, "fat": 0.5, "desc": "去壳虾仁，煮熟"},
    {"name": "带鱼", "kcal": 205, "protein": 18.5, "carbs": 0.0, "fat": 14.0, "desc": "煎带鱼"},
    {"name": "鲫鱼", "kcal": 135, "protein": 18.0, "carbs": 0.0, "fat": 7.0, "desc": "清蒸鲫鱼"},

    # 饮品/汤类
    {"name": "豆浆", "kcal": 31, "protein": 3.0, "carbs": 1.2, "fat": 1.6, "desc": "无糖豆浆"},
    {"name": "可乐", "kcal": 42, "protein": 0.0, "carbs": 10.6, "fat": 0.0, "desc": "可口可乐"},
    {"name": "橙汁", "kcal": 45, "protein": 0.7, "carbs": 10.4, "fat": 0.2, "desc": "鲜榨橙汁"},
    {"name": "啤酒", "kcal": 43, "protein": 0.5, "carbs": 3.6, "fat": 0.0, "desc": "普通啤酒"},
    {"name": "紫菜蛋花汤", "kcal": 32, "protein": 3.0, "carbs": 2.0, "fat": 1.5, "desc": "紫菜+鸡蛋花汤"},
    {"name": "西红柿蛋汤", "kcal": 38, "protein": 2.5, "carbs": 3.0, "fat": 2.0, "desc": "西红柿+鸡蛋汤"},

    # 零食/调料
    {"name": "巧克力", "kcal": 546, "protein": 4.9, "carbs": 59.4, "fat": 31.3, "desc": "牛奶巧克力"},
    {"name": "薯片", "kcal": 536, "protein": 6.0, "carbs": 53.0, "fat": 34.0, "desc": "油炸薯片"},
    {"name": "花生", "kcal": 567, "protein": 25.8, "carbs": 16.1, "fat": 49.2, "desc": "炒花生仁"},
    {"name": "核桃", "kcal": 654, "protein": 15.2, "carbs": 13.7, "fat": 65.2, "desc": "干核桃仁"},
    {"name": "食用油", "kcal": 899, "protein": 0.0, "carbs": 0.0, "fat": 99.9, "desc": "常用烹调油"},
    {"name": "白糖", "kcal": 400, "protein": 0.0, "carbs": 100.0, "fat": 0.0, "desc": "白砂糖"},
    {"name": "蜂蜜", "kcal": 304, "protein": 0.3, "carbs": 82.4, "fat": 0.0, "desc": "天然蜂蜜"},
]
