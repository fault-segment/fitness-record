"""LangGraph ReAct Agent graph"""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.agent.prompt import get_system_prompt
from app.agent.tools import ALL_TOOLS
from app.llm import get_llm


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    user_id: int


llm_with_tools = get_llm().bind_tools(ALL_TOOLS)


def agent_node(state: AgentState) -> dict:
    """LLM 推理 + 工具选择"""
    messages = state["messages"]
    # 确保 system prompt 在最前面
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=get_system_prompt())] + list(messages)
    resp = llm_with_tools.invoke(messages)
    return {"messages": [resp]}


def tool_node(state: AgentState) -> dict:
    """执行工具调用"""
    import asyncio
    messages = state["messages"]
    last_msg = messages[-1]

    tool_msgs = []
    for tc in last_msg.tool_calls:
        tool_name = tc["name"]
        tool_args = tc["args"]
        tool_args["user_id"] = state["user_id"]

        tool_map = {t.name: t for t in ALL_TOOLS}
        tool_fn = tool_map.get(tool_name)
        if tool_fn:
            try:
                result = asyncio.run(tool_fn.ainvoke(tool_args))
            except Exception as e:
                result = f"工具调用失败: {e}"
        else:
            result = f"未知工具: {tool_name}"

        tool_msgs.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

    return {"messages": tool_msgs}


def should_continue(state: AgentState) -> str:
    """判断是否继续调用工具"""
    last_msg = state["messages"][-1]
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        return "tools"
    return END


# 构建图
workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)
workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
workflow.add_edge("tools", "agent")

memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)


async def run_agent_stream(user_id: int, user_message: str):
    """流式运行 Agent，yield JSON 结构化消息。

    消息类型: text, card, summary, refuse, done
    """
    import json
    from langchain_core.messages import AIMessage, AIMessageChunk

    config = {"configurable": {"thread_id": str(user_id)}}
    input_state = {
        "messages": [HumanMessage(content=user_message)],
        "user_id": user_id,
    }

    def _extract_text(msg) -> str | None:
        """从 AIMessage 或 AIMessageChunk 中提取文本内容"""
        content = msg.content
        if not content:
            return None
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block["text"])
            return "".join(parts) if parts else None
        return None

    def _emit(event_type: str, **kwargs) -> str:
        """构建 SSE JSON 行"""
        msg = {"type": event_type, **kwargs}
        return json.dumps(msg, ensure_ascii=False)

    async for msg, metadata in graph.astream(input_state, config=config, stream_mode="messages"):
        if isinstance(msg, (AIMessage, AIMessageChunk)):
            # 检查 tool_calls，识别结构化消息
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                for tc in tool_calls:
                    tc_name = tc.get("name", "")
                    tc_args = tc.get("args", {})

                    if tc_name == "show_confirm_card":
                        try:
                            foods = json.loads(tc_args.get("foods_json", "[]"))
                            totals = json.loads(tc_args.get("totals_json", "{}"))
                            yield _emit("card", card_type="confirm",
                                        foods=foods, totals=totals)
                        except (json.JSONDecodeError, KeyError):
                            pass

                    elif tc_name == "refuse":
                        yield _emit("refuse",
                                    content="抱歉，我只能帮你记录饮食和回答食物相关的问题哦～")

                    elif tc_name == "get_daily_summary":
                        yield _emit("summary",
                                    title=f"📅 {tc_args.get('date_str', '')} 摄入汇总",
                                    date=tc_args.get("date_str", ""),
                                    foods=[], totals={})

            # 文本内容
            text = _extract_text(msg)
            if text:
                yield _emit("text", content=text)

    yield _emit("done")
