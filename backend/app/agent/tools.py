# backend/app/agent/tools.py
"""LangGraph Agent 工具实现"""
from __future__ import annotations

import json
from decimal import Decimal
from datetime import date

from langchain_core.tools import tool
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database import async_session
from app.models import FoodRecord, FoodItem
from app.rag import rag_search_food


@tool
async def search_food(food_name: str) -> str:
    """搜索食物营养数据。输入食物名称，返回营养成分列表（每100g）。"""
    logger.debug("search_food: {food_name}", food_name=food_name)
    try:
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
        logger.debug("search_food: {count} results", count=len(results))
        return "\n".join(lines)
    except Exception:
        logger.exception("search_food failed: {food_name}", food_name=food_name)
        return f"搜索「{food_name}」时发生错误"


@tool
async def save_record(user_id: int, record_date: str, meal_type: str, foods: str) -> str:
    """保存饮食记录。foods 是 JSON 数组，每项包含 food_name, amount_g, kcal, protein_g, carbs_g, fat_g, source。"""
    items = json.loads(foods)
    logger.debug(
        "save_record: user={user_id} date={date} meal={meal} count={count}",
        user_id=user_id, date=record_date, meal=meal_type, count=len(items),
    )
    try:
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
    except Exception:
        logger.exception("save_record failed")
        return f"保存记录失败"


@tool
async def get_daily_summary(user_id: int, date_str: str) -> str:
    """查询某日饮食汇总。date_str 格式: YYYY-MM-DD。返回结构化 JSON 供前端渲染汇总卡片。"""
    logger.debug("get_daily_summary: user={user_id} date={date}", user_id=user_id, date=date_str)
    try:
        async with async_session() as session:
            result = await session.execute(
                select(FoodRecord).where(
                    FoodRecord.user_id == user_id,
                    FoodRecord.record_date == date_str,
                )
            )
            records = result.scalars().all()

            if not records:
                return json.dumps({
                    "_summary": True,
                    "title": f"{date_str} 还没有饮食记录",
                    "date": date_str,
                    "foods": [],
                    "totals": {},
                }, ensure_ascii=False)

            all_items: list[FoodItem] = []
            for rec in records:
                await session.refresh(rec, ["items"])
                all_items.extend(rec.items)

            total_kcal = sum(i.kcal for i in all_items)
            total_protein = sum(float(i.protein_g) for i in all_items)
            total_carbs = sum(float(i.carbs_g) for i in all_items)
            total_fat = sum(float(i.fat_g) for i in all_items)

            foods_list = [
                {"name": item.food_name, "amount": f"{item.amount_g}g", "kcal": item.kcal}
                for item in all_items
            ]
            totals = {
                "kcal": total_kcal,
                "protein": round(total_protein),
                "carbs": round(total_carbs),
                "fat": round(total_fat),
            }

            lines = [
                f"{date_str} 摄入汇总",
                f"热量: {total_kcal} kcal",
                f"蛋白质: {total_protein:.0f}g | 碳水: {total_carbs:.0f}g | 脂肪: {total_fat:.0f}g",
                "",
                "食物列表:",
            ]
            for item in all_items:
                lines.append(f"- {item.food_name} | {item.amount_g}g | {item.kcal}kcal")

            logger.debug("get_daily_summary: {kcal} kcal, {count} foods", kcal=total_kcal, count=len(all_items))
            return json.dumps({
                "_summary": True,
                "title": f"{date_str} 摄入汇总",
                "date": date_str,
                "foods": foods_list,
                "totals": totals,
                "text": "\n".join(lines),
            }, ensure_ascii=False)
    except Exception:
        logger.exception("get_daily_summary failed")
        return f"查询失败"


@tool
async def query_history(user_id: int, start_date: str, end_date: str) -> str:
    """查询日期范围内的饮食记录汇总。start_date 和 end_date 格式: YYYY-MM-DD。"""
    logger.debug(
        "query_history: user={user_id} range={start}~{end}",
        user_id=user_id, start=start_date, end=end_date,
    )
    try:
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
    except Exception:
        logger.exception("query_history failed")
        return f"查询失败"


@tool
async def show_confirm_card(foods_json: str, totals_json: str) -> str:
    """展示饮食确认卡片。foods_json 是 JSON 数组 [{"name":"米饭","amount":"200g","kcal":232},...]，totals_json 是 {"kcal":600,"protein":24,"carbs":56,"fat":38}。
    调用此工具后，前端会展示可交互的确认卡片，用户点击确认后才调用 save_record 保存。"""
    foods = json.loads(foods_json)
    logger.debug("show_confirm_card: {count} foods", count=len(foods))
    return f"已展示确认卡片"


@tool
async def delete_record(user_id: int, record_date: str, meal_type: str = "") -> str:
    """删除指定日期和餐次的饮食记录。record_date 格式 YYYY-MM-DD，meal_type 为空则删除当天全部记录。"""
    logger.debug(
        "delete_record: user={user_id} date={date} meal={meal}",
        user_id=user_id, date=record_date, meal=meal_type,
    )
    try:
        async with async_session() as session:
            stmt = select(FoodRecord).where(
                FoodRecord.user_id == user_id,
                FoodRecord.record_date == record_date,
            )
            if meal_type:
                stmt = stmt.where(FoodRecord.meal_type == meal_type)

            result = await session.execute(stmt)
            records = result.scalars().all()

            if not records:
                target = f"{record_date} {meal_type}" if meal_type else record_date
                return f"{target} 没有找到饮食记录"

            count = 0
            for rec in records:
                count += 1
                await session.delete(rec)
            await session.commit()

            target = f"{record_date} {meal_type}" if meal_type else record_date
            return f"已删除 {target} 的 {count} 条饮食记录"
    except Exception:
        logger.exception("delete_record failed")
        return f"删除失败"


def _make_food_item(record_id: int, f: dict) -> FoodItem:
    return FoodItem(
        record_id=record_id,
        food_name=f["food_name"],
        amount_g=Decimal(str(f.get("amount_g", 100))),
        unit=f.get("unit", "g"),
        kcal=int(f["kcal"]),
        protein_g=Decimal(str(f.get("protein_g", 0))),
        carbs_g=Decimal(str(f.get("carbs_g", 0))),
        fat_g=Decimal(str(f.get("fat_g", 0))),
        source=f.get("source", "llm"),
    )


async def _get_records(session: AsyncSession, user_id: int, record_date: str, meal_type: str) -> list[FoodRecord]:
    stmt = select(FoodRecord).where(
        FoodRecord.user_id == user_id,
        FoodRecord.record_date == record_date,
    )
    if meal_type:
        stmt = stmt.where(FoodRecord.meal_type == meal_type)
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _target(record_date: str, meal_type: str) -> str:
    return f"{record_date} {meal_type}" if meal_type else record_date


@tool
async def replace_record(user_id: int, record_date: str, meal_type: str, foods_json: str) -> str:
    """全量替换指定日期和餐次的所有食物。foods_json 为 JSON 数组 [{"food_name":"米饭","amount_g":200,"kcal":232},...]。"""
    items_data = json.loads(foods_json)
    logger.debug(
        "replace_record: user={user_id} date={date} meal={meal} count={count}",
        user_id=user_id, date=record_date, meal=meal_type, count=len(items_data),
    )
    try:
        async with async_session() as session:
            records = await _get_records(session, user_id, record_date, meal_type)
            if not records:
                return f"{_target(record_date, meal_type)} 没有找到饮食记录"

            for rec in records:
                await session.refresh(rec, ["items"])
                for item in rec.items:
                    await session.delete(item)
                for f in items_data:
                    session.add(_make_food_item(rec.id, f))

            await session.commit()
            return f"已替换 {_target(record_date, meal_type)} 的 {len(items_data)} 种食物"
    except Exception:
        logger.exception("replace_record failed")
        return f"替换失败"


@tool
async def add_food(user_id: int, record_date: str, meal_type: str, foods_json: str) -> str:
    """往已有餐次追加食物。foods_json 为 JSON 数组 [{"food_name":"鸡蛋","amount_g":60,"kcal":86},...]。"""
    items_data = json.loads(foods_json)
    logger.debug(
        "add_food: user={user_id} date={date} meal={meal} count={count}",
        user_id=user_id, date=record_date, meal=meal_type, count=len(items_data),
    )
    try:
        async with async_session() as session:
            records = await _get_records(session, user_id, record_date, meal_type)
            if not records:
                return f"{_target(record_date, meal_type)} 没有找到饮食记录，请先调用 save_record"

            for rec in records:
                for f in items_data:
                    session.add(_make_food_item(rec.id, f))

            await session.commit()
            return f"已追加 {len(items_data)} 种食物到 {_target(record_date, meal_type)}"
    except Exception:
        logger.exception("add_food failed")
        return f"追加失败"


@tool
async def remove_food(user_id: int, record_date: str, meal_type: str, foods_json: str) -> str:
    """从已有餐次移除指定食物。foods_json 为 JSON 数组 [{"food_name":"米饭"},{"food_name":"鸡蛋"}]，只需填 food_name。"""
    items_data = json.loads(foods_json)
    remove_names = {f["food_name"] for f in items_data}
    logger.debug(
        "remove_food: user={user_id} date={date} meal={meal} names={names}",
        user_id=user_id, date=record_date, meal=meal_type, names=remove_names,
    )
    try:
        async with async_session() as session:
            records = await _get_records(session, user_id, record_date, meal_type)
            if not records:
                return f"{_target(record_date, meal_type)} 没有找到饮食记录"

            removed = 0
            for rec in records:
                await session.refresh(rec, ["items"])
                for item in rec.items:
                    if item.food_name in remove_names:
                        await session.delete(item)
                        removed += 1

            await session.commit()
            return f"已从 {_target(record_date, meal_type)} 移除 {removed} 种食物"
    except Exception:
        logger.exception("remove_food failed")
        return f"移除失败"


@tool
async def update_food(
    user_id: int,
    record_date: str,
    meal_type: str,
    old_food_name: str,
    new_food_name: str = "",
    amount_g: int = 0,
    kcal: int = 0,
    protein_g: float = 0,
    carbs_g: float = 0,
    fat_g: float = 0,
) -> str:
    """修改已有餐次中某个食物的名称、分量或营养值。只需传入要修改的字段，未传入的字段保持不变。
    示例: "把200g米饭改成300g" → update_food(old_food_name="米饭", amount_g=300)
    "把米饭改成面条" → update_food(old_food_name="米饭", new_food_name="面条")
    """
    logger.debug(
        "update_food: user={user_id} date={date} meal={meal} old={old}",
        user_id=user_id, date=record_date, meal=meal_type, old=old_food_name,
    )
    try:
        async with async_session() as session:
            records = await _get_records(session, user_id, record_date, meal_type)
            if not records:
                return f"{_target(record_date, meal_type)} 没有找到饮食记录"

            updated = 0
            for rec in records:
                await session.refresh(rec, ["items"])
                for item in rec.items:
                    if item.food_name == old_food_name:
                        if new_food_name:
                            item.food_name = new_food_name
                        if amount_g > 0:
                            item.amount_g = Decimal(amount_g)
                        if kcal > 0:
                            item.kcal = kcal
                        if protein_g > 0:
                            item.protein_g = Decimal(str(protein_g))
                        if carbs_g > 0:
                            item.carbs_g = Decimal(str(carbs_g))
                        if fat_g > 0:
                            item.fat_g = Decimal(str(fat_g))
                        updated += 1

            if updated == 0:
                return f"未找到食物「{old_food_name}」"
            await session.commit()
            return f"已更新 {_target(record_date, meal_type)} 的「{old_food_name}」"
    except Exception:
        logger.exception("update_food failed")
        return f"修改失败"


@tool
async def refuse(reason: str = "") -> str:
    """拒绝回答与饮食无关的话题。reason 是简短拒绝原因。"""
    logger.info("refuse triggered: {reason}", reason=reason or "non-diet topic")
    return "抱歉，我只能帮你记录饮食和回答食物相关的问题哦～"


ALL_TOOLS = [search_food, save_record, get_daily_summary, query_history,
             show_confirm_card, delete_record, replace_record,
             add_food, remove_food, update_food, refuse]
