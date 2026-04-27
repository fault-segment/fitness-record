# backend/app/agent/tools.py
"""LangGraph Agent 工具实现"""
from __future__ import annotations

import json
from decimal import Decimal
from datetime import date

from langchain_core.tools import tool
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models import FoodRecord, FoodItem
from app.rag import rag_search_food


@tool
async def search_food(food_name: str) -> str:
    """搜索食物营养数据。输入食物名称，返回营养成分列表（每100g）。"""
    results = rag_search_food(food_name, top_k=5)
    if not results:
        return f"未找到「{food_name}」的营养数据，请用 LLM 知识估算"
    lines = [f"「{food_name}」检索结果："]
    for r in results:
        confidence = "高" if r["score"] > 0.7 else "中" if r["score"] > 0.4 else "低"
        lines.append(
            f"- {r['food_name']} | 热量:{r['kcal_per_100g']}kcal | "
            f"蛋白:{r['protein_per_100g']}g | 碳水:{r['carbs_per_100g']}g | "
            f"脂肪:{r['fat_per_100g']}g | 置信度:{confidence}"
        )
    return "\n".join(lines)


@tool
async def save_record(user_id: int, record_date: str, meal_type: str, foods: str) -> str:
    """保存饮食记录。foods 是 JSON 数组，每项包含 food_name, amount_g, kcal, protein_g, carbs_g, fat_g, source。"""
    items = json.loads(foods)
    async with async_session() as session:
        record = FoodRecord(user_id=user_id, record_date=record_date, meal_type=meal_type)
        session.add(record)
        await session.flush()

        for f in items:
            item = FoodItem(
                record_id=record.id,
                food_name=f["food_name"],
                amount_g=Decimal(str(f.get("amount_g", 100))),
                unit=f.get("unit", "g"),
                kcal=int(f["kcal"]),
                protein_g=Decimal(str(f.get("protein_g", 0))),
                carbs_g=Decimal(str(f.get("carbs_g", 0))),
                fat_g=Decimal(str(f.get("fat_g", 0))),
                source=f.get("source", "llm"),
            )
            session.add(item)

        await session.commit()
        return f"已保存 {record_date} {meal_type} 的 {len(items)} 种食物记录"


@tool
async def get_daily_summary(user_id: int, date_str: str) -> str:
    """查询某日饮食汇总。date_str 格式: YYYY-MM-DD。"""
    async with async_session() as session:
        result = await session.execute(
            select(FoodRecord).where(
                FoodRecord.user_id == user_id,
                FoodRecord.record_date == date_str,
            )
        )
        records = result.scalars().all()

        if not records:
            return f"{date_str} 还没有饮食记录"

        all_items: list[FoodItem] = []
        for rec in records:
            await session.refresh(rec, ["items"])
            all_items.extend(rec.items)

        total_kcal = sum(i.kcal for i in all_items)
        total_protein = sum(float(i.protein_g) for i in all_items)
        total_carbs = sum(float(i.carbs_g) for i in all_items)
        total_fat = sum(float(i.fat_g) for i in all_items)

        lines = [
            f"📅 {date_str} 摄入汇总",
            f"热量: {total_kcal} kcal",
            f"蛋白质: {total_protein:.0f}g | 碳水: {total_carbs:.0f}g | 脂肪: {total_fat:.0f}g",
            "",
            "食物列表:",
        ]
        for item in all_items:
            lines.append(f"- {item.food_name} | {item.amount_g}g | {item.kcal}kcal")
        return "\n".join(lines)


@tool
async def query_history(user_id: int, start_date: str, end_date: str) -> str:
    """查询日期范围内的饮食记录汇总。start_date 和 end_date 格式: YYYY-MM-DD。"""
    async with async_session() as session:
        result = await session.execute(
            select(FoodRecord).where(
                FoodRecord.user_id == user_id,
                FoodRecord.record_date >= start_date,
                FoodRecord.record_date <= end_date,
            ).order_by(FoodRecord.record_date)
        )
        records = result.scalars().all()

        if not records:
            return f"{start_date} 到 {end_date} 还没有饮食记录"

        date_map: dict[str, list[FoodItem]] = {}
        for rec in records:
            await session.refresh(rec, ["items"])
            if rec.record_date not in date_map:
                date_map[rec.record_date] = []
            date_map[rec.record_date].extend(rec.items)

        lines = [f"📅 {start_date} ~ {end_date} 饮食记录"]
        for d, items in date_map.items():
            kcal = sum(i.kcal for i in items)
            lines.append(f"{d}: {kcal} kcal ({len(items)} 种食物)")
        return "\n".join(lines)


@tool
async def refuse() -> str:
    """拒绝回答与饮食无关的话题。"""
    return "抱歉，我只能帮你记录饮食和回答食物相关的问题哦～"


ALL_TOOLS = [search_food, save_record, get_daily_summary, query_history, refuse]
