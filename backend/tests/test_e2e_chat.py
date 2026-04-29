"""端到端对话流程测试 — 模拟小程序完整交互链路"""
import json
import httpx
import pytest

BASE = "http://localhost:8000"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxfQ.mG-MW0IbX8IGl0a1BpQzqg1FlsEp0Z3OvE6ath50Nj4"


def collect_sse(message: str) -> list[dict]:
    """发送消息，收集所有 SSE 事件"""
    events = []
    with httpx.Client(timeout=120) as client:
        with client.stream(
            "POST",
            f"{BASE}/api/chat",
            json={"message": message},
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Content-Type": "application/json",
            },
        ) as response:
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data.strip():
                        events.append(json.loads(data))
    return events


def message_types(events: list[dict]) -> set[str]:
    return {e["type"] for e in events}


class TestE2E:
    """端到端对话流程"""

    def test_hello_returns_text(self):
        """用户打招呼 → 文本回复"""
        events = collect_sse("你好")
        assert any(e["type"] == "text" for e in events)
        assert any(e["type"] == "done" for e in events)

    def test_food_search(self):
        """食物查询 → 文本回复含营养信息"""
        events = collect_sse("米饭热量多少")
        text_content = "".join(e.get("content", "") for e in events if e["type"] == "text")
        assert len(text_content) > 0
        assert "kcal" in text_content.lower() or "热量" in text_content or "卡" in text_content

    def test_record_flow_shows_confirm_card(self):
        """记录饮食 → 展示确认卡片"""
        events = collect_sse("我今天中午吃了200g米饭和150g红烧肉")
        types = message_types(events)
        assert "card" in types, f"应该展示确认卡片，实际消息类型: {types}"

    def test_confirm_saves_record(self):
        """用户确认 → 保存记录"""
        events = collect_sse("确认：中午吃了200g米饭和150g红烧肉，共约700kcal")
        text_content = "".join(e.get("content", "") for e in events if e["type"] == "text")
        # 应该保存成功或已经是确认操作
        assert len(text_content) > 0

    def test_query_todays_summary(self):
        """查询今天汇总 → summary 消息"""
        events = collect_sse("我今天吃了什么")
        types = message_types(events)
        assert "summary" in types, f"应该返回汇总卡片，实际消息类型: {types}"

    def test_add_food(self):
        """追加食物"""
        events = collect_sse("午餐再加一个鸡蛋")
        text_content = "".join(e.get("content", "") for e in events if e["type"] == "text")
        assert len(text_content) > 0

    def test_refuse_unrelated(self):
        """拒绝无关话题"""
        events = collect_sse("今天天气怎么样")
        types = message_types(events)
        assert "refuse" in types or any(
            "抱歉" in e.get("content", "") for e in events if e["type"] == "text"
        ), f"应该拒绝，实际消息类型: {types}"
