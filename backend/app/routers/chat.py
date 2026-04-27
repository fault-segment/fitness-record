from fastapi import APIRouter

from app.agent.tools import run_agent
from app.middleware import get_user_id

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def chat(body: dict[str, str], user_id: int = Depends(get_user_id)):
    """对话接口 — 占位，后续接入 LangGraph Agent"""
    message = body.get("message", "")
    # 占位：直接返回 echo
    return {
        "reply": f"[Agent 占位] 收到你的消息: {message}。LangGraph Agent 待接入。",
        "message": message,
    }
