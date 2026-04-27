"""LangGraph ReAct Agent graph"""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.agent.prompt import SYSTEM_PROMPT
from app.agent.tools import ALL_TOOLS
from app.config import settings


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    user_id: int


llm = ChatOpenAI(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
    model=settings.llm_model,
    temperature=0.3,
)

llm_with_tools = llm.bind_tools(ALL_TOOLS)


def agent_node(state: AgentState) -> dict:
    """LLM 推理 + 工具选择"""
    messages = state["messages"]
    # 确保 system prompt 在最前面
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)
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
                if asyncio.iscoroutinefunction(tool_fn.func):
                    result = asyncio.run(tool_fn.ainvoke(tool_args))
                else:
                    result = tool_fn.invoke(tool_args)
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
    """流式运行 Agent，yield 每个 token。"""
    config = {"configurable": {"thread_id": str(user_id)}}
    input_state = {
        "messages": [HumanMessage(content=user_message)],
        "user_id": user_id,
    }
    async for event in graph.astream_events(input_state, config=config, version="v2"):
        kind = event["event"]
        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if chunk.content:
                yield chunk.content
