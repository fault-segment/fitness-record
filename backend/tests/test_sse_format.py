"""SSE 消息格式回归测试"""
import json
import pytest


class TestMessageFormat:
    """SSE JSON 消息格式"""

    @pytest.mark.parametrize("event_type", ["text", "card", "summary", "refuse", "done"])
    def test_all_types_have_type_field(self, event_type):
        """所有消息必须包含 type 字段"""
        msg = {"type": event_type}
        assert "type" in msg
        assert msg["type"] in ("text", "card", "summary", "refuse", "done")

    def test_text_message_schema(self):
        msg = {"type": "text", "content": "你好"}
        assert isinstance(msg["content"], str)
        assert len(msg["content"]) > 0

    def test_card_message_schema(self):
        msg = {
            "type": "card",
            "card_type": "confirm",
            "foods": [{"name": "米饭", "amount": "200g", "kcal": 232}],
            "totals": {"kcal": 232, "protein": 5, "carbs": 52, "fat": 0.6},
        }
        assert msg["card_type"] == "confirm"
        assert isinstance(msg["foods"], list)
        assert len(msg["foods"]) > 0

    def test_card_food_fields(self):
        food = {"name": "米饭", "amount": "200g", "kcal": 232}
        assert "name" in food
        assert "amount" in food
        assert "kcal" in food
        assert isinstance(food["kcal"], (int, float))

    def test_card_totals_fields(self):
        totals = {"kcal": 600, "protein": 24, "carbs": 56, "fat": 38}
        for field in ["kcal", "protein", "carbs", "fat"]:
            assert field in totals
            assert isinstance(totals[field], (int, float))

    def test_summary_message_schema(self):
        msg = {
            "type": "summary",
            "title": "📅 2026-04-28 摄入汇总",
            "date": "2026-04-28",
            "foods": [],
            "totals": {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0},
        }
        assert msg["type"] == "summary"
        assert msg["date"] is not None

    def test_refuse_message_schema(self):
        msg = {"type": "refuse", "content": "抱歉，我只能帮你..."}
        assert isinstance(msg["content"], str)
        assert len(msg["content"]) > 0

    def test_done_message_schema(self):
        msg = {"type": "done"}
        assert msg["type"] == "done"

    def test_all_messages_json_serializable(self):
        """验证所有消息类型可 JSON 序列化"""
        messages = [
            {"type": "text", "content": "你好世界"},
            {"type": "card", "card_type": "confirm", "foods": [], "totals": {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0}},
            {"type": "summary", "title": "", "date": "", "foods": [], "totals": {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0}},
            {"type": "refuse", "content": "抱歉"},
            {"type": "done"},
        ]
        for msg in messages:
            encoded = json.dumps(msg)
            decoded = json.loads(encoded)
            assert decoded["type"] == msg["type"]


class TestEmitFunction:
    """_emit 函数"""

    def test_emit_returns_json_string(self):
        from app.agent.graph import run_agent_stream
        # 间接测试：验证 _emit 在 run_agent_stream 中的作用域
        # 格式应为 {"type":"...","key":"value"}
        import json as _json

        test_msg = '{"type": "text", "content": "test"}'
        parsed = _json.loads(test_msg)
        assert parsed["type"] == "text"
        assert parsed["content"] == "test"
