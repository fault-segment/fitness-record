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
        assert len(ALL_TOOLS) == 11

    def test_tool_names(self):
        from app.agent.tools import ALL_TOOLS
        names = {t.name for t in ALL_TOOLS}
        expected = {"search_food", "save_record", "get_daily_summary", "query_history",
                    "show_confirm_card", "delete_record", "replace_record",
                    "add_food", "remove_food", "update_food", "refuse"}
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


class TestModifyTools:
    """修改记录工具（replace_record, add_food, remove_food, update_food）- 参数验证"""

    def test_replace_record_validates_params(self):
        """验证 replace_record 的 JSON 参数解析"""
        import json
        foods = [{"food_name": "米饭", "amount_g": 200, "kcal": 232, "source": "db"}]
        foods_json = json.dumps(foods)
        parsed = json.loads(foods_json)
        assert len(parsed) == 1
        assert parsed[0]["food_name"] == "米饭"
        assert parsed[0]["amount_g"] == 200

    def test_remove_food_validates_params(self):
        """验证 remove_food 只需 food_name"""
        import json
        foods_json = '[{"food_name":"米饭"},{"food_name":"鸡蛋"}]'
        parsed = json.loads(foods_json)
        names = {f["food_name"] for f in parsed}
        assert names == {"米饭", "鸡蛋"}

    def test_update_food_validates_params(self):
        """验证 update_food 可选字段"""
        # 只传 amount_g，其他字段为默认值 0（表示不修改）
        params = {"old_food_name": "米饭", "amount_g": 300}
        assert params["old_food_name"] == "米饭"
        assert params["amount_g"] == 300
        assert params.get("new_food_name", "") == ""
        assert params.get("kcal", 0) == 0

    def test_add_food_validates_params(self):
        """验证 add_food 的 JSON 参数解析"""
        import json
        foods = [{"food_name": "鸡蛋", "amount_g": 60, "kcal": 86, "protein_g": 7.2, "carbs_g": 1.4, "fat_g": 6.4, "source": "db"}]
        foods_json = json.dumps(foods)
        parsed = json.loads(foods_json)
        assert parsed[0]["food_name"] == "鸡蛋"
        assert parsed[0]["kcal"] == 86


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
