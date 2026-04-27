from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.agent import run_agent_stream
from app.middleware import get_user_id

router = APIRouter(prefix="/api", tags=["chat"])


async def event_stream(user_id: int, message: str):
    """SSE 事件流生成器"""
    async for token in run_agent_stream(user_id, message):
        yield {"data": token}


@router.post("/chat")
async def chat(body: dict[str, str], user_id: int = Depends(get_user_id)):
    """对话接口 — SSE 流式返回 Agent 响应"""
    message = body.get("message", "")
    if not message.strip():
        return {"reply": "请说点什么吧～"}
    return EventSourceResponse(event_stream(user_id, message))
