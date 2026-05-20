"""意图分类 + 快速路由单元测试"""
import pytest
from datetime import date, timedelta

from app.agent.intent import classify_intent, _extract_date, _extract_days, _extract_food_name


class TestClassifyIntent:
    """意图分类正确性"""

    # ———— query_summary ————

    @pytest.mark.parametrize("msg", [
        "今天吃了什么",
        "我今天吃了什么",
        "今天吃了啥",
        "昨天吃了什么",
        "前天吃了啥",
        "看看今天的汇总",
        "看看昨天吃了什么",
        "饮食汇总",
        "摄入汇总",
        "今天的饮食记录",
        "查看今天的记录",
    ])
    def test_query_summary_fast_route(self, msg):
        intent, tool_name, tool_args = classify_intent(msg)
        assert intent == "fast", f"'{msg}' should be fast route"
        assert tool_name == "get_daily_summary"
        assert "date_str" in tool_args

    def test_query_summary_date_today(self):
        _, _, args = classify_intent("今天吃了什么")
        assert args["date_str"] == date.today().isoformat()

    def test_query_summary_date_yesterday(self):
        _, _, args = classify_intent("昨天吃了什么")
        assert args["date_str"] == (date.today() - timedelta(days=1)).isoformat()

    def test_query_summary_date_2days_ago(self):
        _, _, args = classify_intent("前天吃了啥")
        assert args["date_str"] == (date.today() - timedelta(days=2)).isoformat()

    # ———— query_history ————

    @pytest.mark.parametrize("msg", [
        "最近一周吃了什么",
        "过去几天的情况",
        "这周的饮食统计",
        "最近3天",
        "历史记录",
        "统计最近一周的饮食",
        "最近一个月",
    ])
    def test_query_history_fast_route(self, msg):
        intent, tool_name, tool_args = classify_intent(msg)
        assert intent == "fast", f"'{msg}' should be fast route"
        assert tool_name == "query_history"
        assert "start_date" in tool_args
        assert "end_date" in tool_args

    def test_query_history_default_7_days(self):
        _, _, args = classify_intent("最近一周")
        start = args["start_date"]
        end = args["end_date"]
        expected_start = (date.today() - timedelta(days=7)).isoformat()
        assert start == expected_start
        assert end == date.today().isoformat()

    def test_query_history_custom_days(self):
        _, _, args = classify_intent("最近3天的情况")
        expected_start = (date.today() - timedelta(days=3)).isoformat()
        assert args["start_date"] == expected_start

    # ———— search_food ————

    @pytest.mark.parametrize("msg", [
        "米饭热量多少",
        "鸡蛋的蛋白质含量",
        "红烧肉多少卡",
        "查询米饭的营养成分",
        "牛奶脂肪含量",
        "面包的碳水多少",
        "鸡胸肉kcal",
    ])
    def test_search_food_fast_route(self, msg):
        intent, tool_name, tool_args = classify_intent(msg)
        assert intent == "fast", f"'{msg}' should be fast route"
        assert tool_name == "search_food"
        assert "food_name" in tool_args
        assert len(tool_args["food_name"]) > 0

    # ———— refuse ————

    @pytest.mark.parametrize("msg", [
        "今天天气怎么样",
        "最新新闻",
        "推荐一只股票",
        "有什么好看的电影",
        "播放音乐",
        "打游戏",
    ])
    def test_refuse_fast_route(self, msg):
        intent, tool_name, tool_args = classify_intent(msg)
        assert intent == "fast", f"'{msg}' should be fast route"
        assert tool_name == "refuse"

    # ———— fallback to agent ————

    @pytest.mark.parametrize("msg", [
        "我今天中午吃了200g米饭和150g红烧肉",
        "确认：中午吃了米饭红烧肉",
        "好的，保存吧",
        "修改米饭为200g",
        "删除今天的午餐记录",
        "把米饭换成面条",
        "午餐再加一个鸡蛋",
        "",
        "你好",
        "谢谢",
    ])
    def test_fallback_to_agent(self, msg):
        intent, tool_name, tool_args = classify_intent(msg)
        assert intent == "agent", f"'{msg}' should fallback to agent"
        assert tool_name is None
        assert tool_args is None


class TestDateExtraction:
    """日期解析"""

    def test_today(self):
        assert _extract_date("今天吃了什么") == date.today()

    def test_yesterday(self):
        assert _extract_date("昨天吃了什么") == date.today() - timedelta(days=1)

    def test_2days_ago(self):
        assert _extract_date("前天吃了什么") == date.today() - timedelta(days=2)

    def test_default_today(self):
        """无日期关键词默认今天"""
        assert _extract_date("吃饭记录") == date.today()


class TestDaysExtraction:
    """天数范围提取"""

    def test_recent_week(self):
        assert _extract_days("最近一周") == 7

    def test_recent_3_days_digit(self):
        assert _extract_days("最近3天") == 3

    def test_recent_3_days_cn(self):
        assert _extract_days("最近三天") == 3

    def test_recent_month(self):
        assert _extract_days("最近一月") == 30

    def test_no_match(self):
        assert _extract_days("今天吃了什么") is None


class TestFoodNameExtraction:
    """食物名提取"""

    def test_simple(self):
        assert "米饭" in _extract_food_name("米饭热量多少")

    def test_with_query_word(self):
        name = _extract_food_name("查询红烧肉的热量")
        assert "红烧肉" in name

    def test_protein_query(self):
        name = _extract_food_name("鸡蛋的蛋白质含量")
        assert "鸡蛋" in name
