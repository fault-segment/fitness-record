# 工具执行后条件路由优化

## 问题

当前 `tools → agent` 是无条件边，所有工具执行完都回 `agent_node` 再跑一轮 LLM。对于 `show_confirm_card`、`refuse`、`save_record` 等"最终输出型"工具，这一轮 LLM 调用纯属浪费——增加 1-3 秒延迟 + 产生需要事后抑制的冗余文本。

### 当前补丁

`run_agent_stream()` 里用三个变量兜底：
- `has_output_tool` — 同一轮 AIMessage 检测到输出型工具时跳过文本
- `_suppress_text` — 跨轮抑制（仅对 `get_daily_summary` 生效）
- `OUTPUT_TOOLS` — 标记哪些工具产生结构化输出

这些补丁覆盖不全（card/refuse 跨轮漏了），且治标不治本。

### 根本原因

LangGraph 图结构：

```
agent → should_continue → tools 或 END
tools → agent               ← 无条件！
```

`tool_node` 执行完后必定回到 `agent_node`，LLM 看到 ToolMessage 总会输出点什么，哪怕工具结果已经是最终答案。

## 方案

把 `tools → agent` 的无条件边改成条件边，terminal 工具执行完直接 END。

### 图结构

```
agent → should_continue → tools 或 END
tools → should_continue_after_tools → agent 或 END
```

### 工具分类

| 类型 | 工具 | 理由 |
|------|------|------|
| Terminal（→ END） | `show_confirm_card`、`refuse`、`save_record`、`delete_record`、`replace_record`、`add_food`、`remove_food`、`update_food`、`get_daily_summary`、`query_history` | 结果即最终输出，LLM 无需再加工 |
| Non-terminal（→ agent） | `search_food` | 结果需 LLM 处理：判断置信度、估算未命中食物、决定后续工具 |

### 关键判断逻辑

`should_continue_after_tools(state)` 查看上一轮的 AIMessage 中的 tool_calls。只有当**所有** tool_calls 都是 terminal 时才返回 END，否则回 agent_node。这保证了混合调用（如 `search_food` + `show_confirm_card` 在同一轮）的正确性——只要有一个非 terminal 就继续。

### 改动

**文件：** `backend/app/agent/graph.py`

1. 新增 `TERMINAL_TOOLS` 集合
2. 新增 `should_continue_after_tools(state)` 函数
3. `workflow.add_edge("tools", "agent")` → `workflow.add_conditional_edges("tools", should_continue_after_tools, {"agent": "agent", END: END})`
4. 移除 `run_agent_stream()` 中的补丁：`has_output_tool`、`_suppress_text`、`OUTPUT_TOOLS`

### 收益

- 少一轮 LLM 调用（terminal 工具后不回 agent_node）
- 彻底消除冗余文本
- 代码简化

## 状态

待实施（低优先级）。
