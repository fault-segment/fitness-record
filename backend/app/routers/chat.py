from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse
from loguru import logger
from datetime import date
from sqlalchemy import select

from app.agent import run_agent_stream
from app.middleware import get_user_id
from app.database import async_session
from app.models import FoodRecord, FoodItem

router = APIRouter(prefix="/api", tags=["chat"])


async def event_stream(user_id: int, message: str):
    """SSE 事件流生成器"""
    try:
        async for token in run_agent_stream(user_id, message):
            yield {"data": token}
    except Exception:
        logger.exception("Agent stream failed for user {id}", id=user_id)
        raise


@router.post("/chat")
async def chat(body: dict[str, str], user_id: int = Depends(get_user_id)):
    """对话接口 — SSE 流式返回 Agent 响应"""
    message = body.get("message", "")
    if not message.strip():
        logger.debug("Empty chat message received")
        return {"reply": "请说点什么吧～"}
    return EventSourceResponse(event_stream(user_id, message))


@router.get("/today-summary")
async def today_summary(user_id: int = Depends(get_user_id)):
    """返回今日摄入汇总，供页面顶部栏使用"""
    today = date.today().isoformat()
    async with async_session() as session:
        result = await session.execute(
            select(FoodRecord).where(
                FoodRecord.user_id == user_id,
                FoodRecord.record_date == today,
            )
        )
        records = result.scalars().all()

        if not records:
            return {"date": today, "kcal": 0, "protein": 0, "carbs": 0, "fat": 0, "food_count": 0}

        total_kcal = 0
        total_protein = 0.0
        total_carbs = 0.0
        total_fat = 0.0
        food_count = 0
        meals: list[dict] = []

        for rec in records:
            await session.refresh(rec, ["items"])
            meal_foods = []
            meal_kcal = 0
            for item in rec.items:
                food_count += 1
                total_kcal += item.kcal
                total_protein += float(item.protein_g)
                total_carbs += float(item.carbs_g)
                total_fat += float(item.fat_g)
                meal_kcal += item.kcal
                meal_foods.append({
                    "name": item.food_name,
                    "amount": f"{item.amount_g}g",
                    "kcal": item.kcal,
                })
            meals.append({
                "meal_type": rec.meal_type,
                "kcal": meal_kcal,
                "foods": meal_foods,
            })

        return {
            "date": today,
            "kcal": total_kcal,
            "protein": round(total_protein),
            "carbs": round(total_carbs),
            "fat": round(total_fat),
            "food_count": food_count,
            "meals": meals,
        }
