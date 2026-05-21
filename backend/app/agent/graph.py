"""LangGraph ReAct Agent graph"""
from __future__ import annotations

import json
import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from loguru import logger

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
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=get_system_prompt())] + list(messages)
    resp = llm_with_tools.invoke(messages)
    if resp.tool_calls:
        logger.info(
            "agent_node tool_calls: {tools}",
            tools=[tc["name"] for tc in resp.tool_calls],
        )
    return {"messages": [resp]}


async def tool_node(state: AgentState) -> dict:
    """执行工具调用"""
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
                result = await tool_fn.ainvoke(tool_args)
            except Exception:
                logger.exception("Tool {name} failed", name=tool_name)
                result = f"工具调用失败: {tool_name}"
        else:
            logger.warning("Unknown tool requested: {name}", name=tool_name)
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
    from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
    from app.agent.intent import classify_intent

    def _emit(event_type: str, **kwargs) -> str:
        """构建 SSE JSON 行"""
        msg = {"type": event_type, **kwargs}
        return json.dumps(msg, ensure_ascii=False)

    STATUS_MAP = {
        "search_food": "正在查询食物数据...",
        "get_daily_summary": "正在生成摄入汇总...",
        "save_record": "正在保存记录...",
        "delete_record": "正在删除记录...",
        "replace_record": "正在更新记录...",
        "add_food": "正在添加食物...",
        "remove_food": "正在移除食物...",
        "update_food": "正在修改食物...",
        "show_confirm_card": "正在整理确认卡片...",
        "query_history": "正在查询历史记录...",
    }

    # ———— 快速路由：关键词匹配直接调工具 ————
    intent, tool_name, tool_args = classify_intent(user_message)
    if intent == "fast":
        logger.info("fast_route: tool={tool} msg={msg:.60}", tool=tool_name, msg=user_message)
        tool_args["user_id"] = user_id
        tool_map = {t.name: t for t in ALL_TOOLS}
        tool_fn = tool_map.get(tool_name)
        if tool_fn:
            yield _emit("status", content=STATUS_MAP.get(tool_name, "正在处理..."))
            try:
                result = await tool_fn.ainvoke(tool_args)
            except Exception:
                logger.exception("fast_route tool {name} failed", name=tool_name)
                yield _emit("text", content=f"查询失败，请稍后重试")
                yield _emit("done")
                return

            if tool_name == "get_daily_summary":
                try:
                    data = json.loads(str(result))
                    if data.get("_summary"):
                        yield _emit("summary",
                                    title=data.get("title", ""),
                                    date=data.get("date", ""),
                                    foods=data.get("foods", []),
                                    meals=data.get("meals", []),
                                    totals=data.get("totals", {}))
                except json.JSONDecodeError:
                    yield _emit("text", content=str(result))
            elif tool_name == "refuse":
                yield _emit("refuse", content=str(result))
            else:
                yield _emit("text", content=str(result))

        yield _emit("done")
        return

    config = {"configurable": {"thread_id": str(user_id)}}
    input_state = {
        "messages": [HumanMessage(content=user_message)],
        "user_id": user_id,
    }

    # 根据用户意图，立即发送初始状态提示（不等 LLM 首轮响应）
    _msg = user_message
    if any(kw in _msg for kw in ["确认", "好的", "OK", "行", "可以", "修改", "删除", "去掉", "换成", "改成", "再加", "替换", "追加", "移除", "更新", "保存"]):
        yield _emit("status", content="正在处理...")
    elif any(kw in _msg for kw in ["吃了", "吃了啥", "吃了什么", "记录", "今天吃", "昨天吃", "早上吃", "中午吃", "晚上吃"]):
        yield _emit("status", content="正在查询饮食记录...")
    elif any(kw in _msg for kw in ["热量", "营养", "多少卡", "kcal", "脂肪", "蛋白", "碳水"]):
        yield _emit("status", content="正在查询营养数据...")
    else:
        yield _emit("status", content="正在思考...")

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

    # 这些工具自带结构化输出（卡片/refuse），或工具返回值已承载全部信息
    # 调用它们的消息文本需抑制，避免冗余
    OUTPUT_TOOLS = {"show_confirm_card", "refuse", "get_daily_summary"}

    _suppress_text = False

    async for msg, metadata in graph.astream(input_state, config=config, stream_mode="messages"):
        # 处理 ToolMessage：检测 get_daily_summary 返回的结构化 JSON
        if isinstance(msg, ToolMessage):
            content = msg.content
            if isinstance(content, str):
                try:
                    data = json.loads(content)
                    if data.get("_summary"):
                        yield _emit("summary",
                                    title=data.get("title", ""),
                                    date=data.get("date", ""),
                                    foods=data.get("foods", []),
                                    meals=data.get("meals", []),
                                    totals=data.get("totals", {}))
                        _suppress_text = True
                except json.JSONDecodeError:
                    logger.warning("Failed to parse ToolMessage content as JSON: {content}",
                                   content=content[:100])
            continue

        if isinstance(msg, (AIMessage, AIMessageChunk)):
            tool_calls = getattr(msg, "tool_calls", None)
            has_output_tool = False

            if tool_calls:
                for tc in tool_calls:
                    tc_name = tc.get("name", "")
                    tc_args = tc.get("args", {})
                    status_text = STATUS_MAP.get(tc_name)
                    if status_text:
                        yield _emit("status", content=status_text)

                    if tc_name == "show_confirm_card":
                        has_output_tool = True
                        try:
                            foods = json.loads(tc_args.get("foods_json", "[]"))
                            totals = json.loads(tc_args.get("totals_json", "{}"))
                            yield _emit("card", card_type="confirm",
                                        foods=foods, totals=totals)
                        except (json.JSONDecodeError, KeyError):
                            logger.warning("Failed to parse confirm card args: {name}", name=tc_name)

                    elif tc_name == "refuse":
                        has_output_tool = True
                        yield _emit("refuse",
                                    content="抱歉，我只能帮你记录饮食和回答食物相关的问题哦～")

                    elif tc_name == "get_daily_summary":
                        has_output_tool = True

            # 消息包含输出型工具时跳过文本；summary emit 后抑制后续 LLM 文本
            if not has_output_tool and not _suppress_text:
                text = _extract_text(msg)
                if text:
                    yield _emit("text", content=text)

            # 仅在新的工具调用出现时重置抑制标记
            if tool_calls:
                _suppress_text = False

    yield _emit("done")
