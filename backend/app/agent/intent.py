"""意图分类 + 快速路由

对可确定性路由的意图，关键词匹配后直接调工具，跳过 LLM ReAct 循环。
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Literal


# ———— 关键词定义 ————

# 非饮食话题（最高优先级）
REFUSE_KEYWORDS = [
    "天气", "新闻", "股票", "电影", "音乐", "游戏",
    "足球", "篮球", "综艺", "电视剧", "动漫", "小说",
    "旅游", "酒店", "机票", "火车票",
]

# 查询某日汇总
QUERY_SUMMARY_PATTERNS = [
    # 精确: "今天/昨天/前天 + 吃了什么/吃了啥"
    r"(今天|昨天|前天|今儿|今个).*吃了?(什么|啥|啥子)",
    # "看看 + 今天/昨天/前天 + 汇总/记录/吃了什么"
    r"看看.*(今天|昨天|前天).*(汇总|记录|吃了什么|吃了啥|吃了)",
    # "今天/昨天/前天 + 吃了" 后跟问号或句尾（无具体食物）
    r"(今天|昨天|前天)吃了[^什么啥米饭面菜肉蛋鱼虾汤粥粉包饺饼糕果豆奶水茶酒汤]*(?:吗|呢|没|了没|了吧)?[\?？。\s]*$",
    # 饮食汇总 / 摄入汇总
    r"(饮食|摄入|今天|今日)(汇总|记录|情况|报告)",
    # 查询今天吃了什么
    r"(查|看|显示|展示).*(今天|昨天|前天|今日).*(饮食|吃了|记录|汇总)",
    # "吃什么了" → query
    r"吃什么[了啦]",
]

# 查询历史
QUERY_HISTORY_PATTERNS = [
    r"最近(一|两|三|几|多|N?\d+)?(个)?(天|周|星期|月)",
    r"(过去|这|本)(几天|周|星期|月)",
    r"(历史|过往).*(记录|饮食|汇总|统计)",
    r"(统计|汇总|总结).*(最近|这|过去|一周|几天)",
]

# 食物营养搜索 — 包含营养关键词但不包含记录意图
NUTRITION_KEYWORDS = [
    "热量", "营养", "多少卡", "kcal", "卡路里",
    "脂肪", "蛋白", "碳水", "膳食纤维", "维生素",
    "含.*量", "成分", "GI", "血糖",
]

# 食物名提取时忽略的前缀/后缀
FOOD_NAME_STRIP_WORDS = [
    "查询", "搜索", "查一下", "搜一下", "帮我查", "帮我搜",
    "什么是", "什么", "多少", "有没有", "有哪些",
]

# 记录意图标记 — 命中则回退 LLM
RECORD_MARKERS = [
    "吃了", "记录了", "记录一下", "记一下",
    "确认", "好的", "可以", "行", "OK", "ok",
    "修改", "删除", "去掉", "换成", "改成", "再加",
    "替换", "追加", "移除", "更新",
    "保存", "存储",
    # 具体食物+分量模式
    r"\d+\s*(克|g|G|斤|两|kg|KG|毫升|ml|ML|碗|份|个|只|条|块|杯|盘|勺)",
]


def _extract_date(message: str) -> date:
    """从消息中提取日期引用，默认返回今天。"""
    today = date.today()
    if any(w in message for w in ["昨天", "昨日"]):
        return today - timedelta(days=1)
    if any(w in message for w in ["前天", "前日"]):
        return today - timedelta(days=2)
    if any(w in message for w in ["今天", "今日", "今儿", "今个"]):
        return today
    return today


def _extract_days(message: str) -> int | None:
    """从消息中提取天数范围。「最近一周」→ 7，「最近3天」→ 3。"""
    # 中文数字映射
    cn_num = {"一": 1, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "几": 7, "多": 7}
    m = re.search(r"最近\s*(\d+|[一二两三四五六七八九十几多])\s*(天|日)", message)
    if m:
        num_str = m.group(1)
        return int(num_str) if num_str.isdigit() else cn_num.get(num_str)
    # 中文数字 + 个月
    m = re.search(r"最近\s*(\d+|[一二两三四五六七八九十几多])\s*个?\s*月", message)
    if m:
        num_str = m.group(1)
        months = int(num_str) if num_str.isdigit() else cn_num.get(num_str, 1)
        return months * 30
    if re.search(r"(最近|过去|这|本)\s*一?周", message):
        return 7
    if re.search(r"(最近|过去|这|本)\s*一?(个)?月", message):
        return 30
    return None


def _extract_food_name(message: str) -> str:
    """从营养查询消息中提取食物名称。"""
    name = message
    # 移除营养关键词
    for kw in NUTRITION_KEYWORDS:
        name = name.replace(kw, "")
    # 移除常见问句词
    for w in FOOD_NAME_STRIP_WORDS:
        name = re.sub(rf"\s*{w}\s*", " ", name)
    # 移除标点和问句尾
    name = re.sub(r"[？?？吗呢吧啊呀的么]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name if name else message


def _has_record_intent(message: str) -> bool:
    """检测是否包含记录/修改意图，需要 LLM 解析。"""
    # 具体食物+分量模式（数字+单位）
    if re.search(r"\d+\s*(克|g|G|斤|两|kg|KG|毫升|ml|ML|碗|份|个|只|条|块|杯|盘|勺)", message):
        return True
    # 确认/修改类动词
    record_verbs = ["确认", "好的", "可以", "行", "修改", "删除", "删掉", "去掉", "换成",
                    "改成", "再加", "替换", "追加", "移除", "更新", "保存", "记录一下", "记一下"]
    return any(v in message for v in record_verbs)


def classify_intent(message: str) -> tuple[Literal["fast", "agent"], str | None, dict | None]:
    """对用户消息进行意图分类。

    Returns:
        ("fast", tool_name, tool_args) — 快速路由，直接调工具
        ("agent", None, None) — 回退 LLM ReAct
    """
    msg = message.strip()

    # 1. query_summary — 查询某日汇总
    for pattern in QUERY_SUMMARY_PATTERNS:
        if re.search(pattern, msg):
            if _has_record_intent(message):
                return ("agent", None, None)
            query_date = _extract_date(msg).isoformat()
            return ("fast", "get_daily_summary", {"date_str": query_date, "user_id": 0})

    # 2. query_history — 历史范围查询
    for pattern in QUERY_HISTORY_PATTERNS:
        if re.search(pattern, msg):
            days = _extract_days(msg) or 7
            today = date.today()
            start = (today - timedelta(days=days)).isoformat()
            end = today.isoformat()
            return ("fast", "query_history", {"start_date": start, "end_date": end, "user_id": 0})

    # refuse / search_food 不再快速路由 — 正则多匹配风险高，交给 LLM 判断
    return ("agent", None, None)
