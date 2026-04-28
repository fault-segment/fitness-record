"""Agent 工具回归测试"""
import asyncio
import json
import pytest


def _ainvoke(tool, args: dict) -> str:
    """Helper: 同步调用异步工具"""
    return asyncio.run(tool.ainvoke(args))


class TestToolsExist:
    """工具注册"""

    def test_all_tools_registered(self):
        from app.agent.tools import ALL_TOOLS
        assert len(ALL_TOOLS) == 8

    def test_tool_names(self):
        from app.agent.tools import ALL_TOOLS
        names = {t.name for t in ALL_TOOLS}
        expected = {"search_food", "save_record", "get_daily_summary", "query_history",
                    "show_confirm_card", "delete_record", "update_record", "refuse"}
        assert names == expected


class TestRefuse:
    """拒绝工具"""

    def test_refuse_returns_message(self):
        from app.agent.tools import refuse
        result = _ainvoke(refuse, {})
        assert "抱歉" in result
        assert "饮食" in result


class TestShowConfirmCard:
    """确认卡片工具"""

    def test_accepts_json_strings(self):
        from app.agent.tools import show_confirm_card
        foods = json.dumps([{"name": "米饭", "amount": "200g", "kcal": 232}])
        totals = json.dumps({"kcal": 232, "protein": 5, "carbs": 52, "fat": 0.6})
        result = _ainvoke(show_confirm_card, {"foods_json": foods, "totals_json": totals})
        assert "确认" in result or "卡片" in result


class TestSearchFood:
    """食物搜索工具"""

    def test_search_rice(self):
        pytest.importorskip("chromadb")
        pytest.importorskip("sentence_transformers")
        from app.agent.tools import search_food
        result = _ainvoke(search_food, {"food_name": "米饭"})
        assert "白米饭" in result
        assert "kcal" in result

    def test_search_unknown(self):
        pytest.importorskip("chromadb")
        pytest.importorskip("sentence_transformers")
        from app.agent.tools import search_food
        result = _ainvoke(search_food, {"food_name": "毒蘑菇xyz"})
        # 要么未找到，要么低置信度
        assert "未找到" in result or "低" in result
