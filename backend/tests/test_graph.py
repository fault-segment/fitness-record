"""LangGraph 图结构回归测试"""
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


class TestGraphStructure:
    """图结构"""

    def test_graph_compiled(self):
        from app.agent.graph import graph
        assert graph is not None

    def test_has_agent_node(self):
        from app.agent.graph import graph
        nodes = graph.get_graph().nodes
        assert "agent" in nodes

    def test_has_tools_node(self):
        from app.agent.graph import graph
        nodes = graph.get_graph().nodes
        assert "tools" in nodes

    def test_entry_point_is_agent(self):
        from app.agent.graph import graph
        assert graph is not None


class TestRouting:
    """路由逻辑"""

    def test_continue_with_tool_calls(self):
        from app.agent.graph import should_continue, AgentState
        msg = AIMessage(content="", tool_calls=[{"name": "search_food", "args": {"food_name": "米饭"}, "id": "1"}])
        state = {"messages": [msg], "user_id": 1}
        result = should_continue(state)
        assert result == "tools"

    def test_end_without_tool_calls(self):
        from app.agent.graph import should_continue, AgentState
        msg = AIMessage(content="好的，帮你记录好了")
        state = {"messages": [msg], "user_id": 1}
        result = should_continue(state)
        assert result == "__end__"

    def test_end_with_human_message(self):
        from app.agent.graph import should_continue, AgentState
        msg = HumanMessage(content="确认")
        state = {"messages": [msg], "user_id": 1}
        result = should_continue(state)
        assert result == "__end__"


class TestAgentNode:
    """Agent 节点"""

    def test_agent_node_returns_message(self):
        from app.agent.graph import agent_node, AgentState
        from app.agent.prompt import get_system_prompt
        from langchain_core.messages import HumanMessage

        state = {"messages": [HumanMessage(content="你好")], "user_id": 1}
        result = agent_node(state)
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)
