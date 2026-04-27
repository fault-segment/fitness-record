# Agent tools — 占位，后续接入 LangGraph + RAG
# 工具列表：
#   search_food  — RAG 检索食物营养数据
#   save_record  — 保存确认后的饮食记录
#   get_daily_summary — 查询某日摄入汇总
#   query_history — 查询日期范围的记录
#   refuse       — 拒绝无关话题


async def run_agent(user_id: int, message: str) -> str:
    return f"[Agent 占位] 收到消息: {message}"
