# 饮食助手 Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working diet recording Agent: food recording with confirmation flow, daily history lookup, RAG food search, all through LangGraph ReAct Agent + SSE streaming.

**Architecture:** LangGraph ReAct Agent with 5 tools (search_food, save_record, get_daily_summary, query_history, refuse). Chroma for vector food search (free, embedded). SSE streaming for chat. Backend already has FastAPI scaffold, auth, and placeholder routes. Miniapp has chat UI with voice. This plan fills in the remaining agent, data, and integration pieces.

**Tech Stack:** Python FastAPI, LangGraph, LanceDB, SQLAlchemy async (TiDB Cloud MySQL), OpenAI-compatible LLM, SSE (sse-starlette)

---

## File Structure

```
backend/
├── app/
│   ├── main.py              [modify] — register new routers
│   ├── config.py            [modify] — add embedding config
│   ├── database.py          [modify] — add new models to init
│   ├── models/
│   │   ├── user.py          [keep]
│   │   ├── record.py        [create] — FoodRecord + FoodItem models
│   ├── routers/
│   │   ├── auth.py          [keep]
│   │   ├── chat.py          [modify] — replace placeholder with SSE Agent
│   │   ├── speech.py        [keep]
│   ├── agent/
│   │   ├── graph.py         [create] — LangGraph ReAct graph
│   │   ├── tools.py         [modify] — real tool implementations
│   │   ├── prompt.py        [create] — system prompt
│   ├── rag/
│   │   ├── store.py         [create] — LanceDB wrapper
│   │   ├── seed.py          [create] — food data seeding script
│   │   ├── data.py          [create] — seed food dataset
├── requirements.txt         [modify] — add langgraph, lancedb, etc.
```

---

### Task 1: Food Record Data Models

**Files:**
- Create: `backend/app/models/record.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/database.py`

- [ ] **Step 1: Create record models**

```python
# backend/app/models/record.py
import time
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FoodRecord(Base):
    __tablename__ = "food_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    record_date: Mapped[str] = mapped_column(String(16), nullable=False)  # YYYY-MM-DD
    meal_type: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[int] = mapped_column(BigInteger, default=lambda: int(time.time()))

    items: Mapped[list["FoodItem"]] = relationship(back_populates="record", cascade="all, delete-orphan")


class FoodItem(Base):
    __tablename__ = "food_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    record_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("food_records.id"), nullable=False)
    food_name: Mapped[str] = mapped_column(String(256), nullable=False)
    amount_g: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    unit: Mapped[str | None] = mapped_column(String(32))
    kcal: Mapped[int] = mapped_column(Integer, nullable=False)
    protein_g: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    carbs_g: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    fat_g: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    source: Mapped[str] = mapped_column(String(16), default="db")  # "db" or "llm"

    record: Mapped["FoodRecord"] = relationship(back_populates="items")
```

- [ ] **Step 2: Update models init**

```python
# backend/app/models/__init__.py
from app.models.user import User
from app.models.record import FoodRecord, FoodItem

__all__ = ["User", "FoodRecord", "FoodItem"]
```

- [ ] **Step 3: Update database.py to import models before create_all**

```python
# backend/app/database.py — add after engine definition, before get_session:
from app.models import User, FoodRecord, FoodItem  # noqa: F401  # ensure models loaded
```

Run the existing `init_db` on startup — it already calls `Base.metadata.create_all`, which will now include the new tables.

- [ ] **Step 4: Verify table creation**

Run: `python -c "from app.main import app; print('Tables ready')"`
Expected: No errors, tables created in TiDB Cloud.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/record.py backend/app/models/__init__.py backend/app/database.py
git commit -m "feat: add FoodRecord and FoodItem data models"
```

---

### Task 2: RAG Food Knowledge Base (LanceDB)

**Files:**
- Create: `backend/app/rag/__init__.py`
- Create: `backend/app/rag/store.py`
- Create: `backend/app/rag/data.py`
- Create: `backend/app/rag/seed.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add dependencies to requirements.txt**

```
# backend/requirements.txt — append:
langgraph>=0.4.0
chromadb>=0.5.0
langchain-openai>=0.3.0
sentence-transformers>=3.0.0
```

首次运行时 `SentenceTransformer("BAAI/bge-small-zh-v1.5")` 会自动下载模型（约 100MB，内存占用 ~300MB），之后缓存本地。

- [ ] **Step 2: Create rag init**

```python
# backend/app/rag/__init__.py
from app.rag.store import search_food as rag_search_food, init_food_db

__all__ = ["rag_search_food", "init_food_db"]
```

- [ ] **Step 3: Create Chroma store wrapper**

```python
# backend/app/rag/store.py
from __future__ import annotations

import chromadb
from sentence_transformers import SentenceTransformer

COLLECTION_NAME = "food_nutrition"

_embedder: SentenceTransformer | None = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer("BAAI/bge-small-zh-v1.5")
    return _embedder


def _get_embedding(text: str) -> list[float]:
    model = _get_embedder()
    return model.encode(text, normalize_embeddings=True).tolist()


def init_food_db(food_data: list[dict]):
    """Seed Chroma with food nutrition data."""
    client = chromadb.PersistentClient(path="data/food_chromadb")
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    ids = []
    documents = []
    metadatas = []
    embeddings = []

    for i, f in enumerate(food_data):
        text = f"食物：{f['name']}。每100g含热量{f['kcal']}kcal，" \
               f"蛋白质{f['protein']}g，碳水化合物{f['carbs']}g，脂肪{f['fat']}g。{f.get('desc', '')}"
        ids.append(str(i))
        documents.append(text)
        metadatas.append({
            "food_name": f["name"],
            "kcal_per_100g": f["kcal"],
            "protein_per_100g": f["protein"],
            "carbs_per_100g": f["carbs"],
            "fat_per_100g": f["fat"],
        })
        embeddings.append(_get_embedding(text))

    collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
    print(f"Seeded {len(food_data)} foods into Chroma")


def search_food(query: str, top_k: int = 5) -> list[dict]:
    """Search food by name, return top-k matches with nutrition data."""
    client = chromadb.PersistentClient(path="data/food_chromadb")
    try:
        collection = client.get_collection(COLLECTION_NAME)
    except Exception:
        return []

    query_emb = _get_embedding(query)
    results = collection.query(query_embeddings=[query_emb], n_results=top_k)

    if not results["metadatas"] or not results["metadatas"][0]:
        return []

    out = []
    for i, meta in enumerate(results["metadatas"][0]):
        distance = results["distances"][0][i] if results["distances"] else 0
        out.append({
            "food_name": meta["food_name"],
            "kcal_per_100g": meta["kcal_per_100g"],
            "protein_per_100g": meta["protein_per_100g"],
            "carbs_per_100g": meta["carbs_per_100g"],
            "fat_per_100g": meta["fat_per_100g"],
            "score": float(1.0 - distance),
        })
    return out
```

- [ ] **Step 4: Create seed food data (common Chinese foods)**

```python
# backend/app/rag/data.py
# 常见食物营养数据（每100g），来源：中国食物成分表 + USDA
FOOD_DATA = [
    # 主食类
    {"name": "白米饭", "kcal": 116, "protein": 2.6, "carbs": 25.9, "fat": 0.3, "desc": "蒸熟的粳米饭"},
    {"name": "馒头", "kcal": 223, "protein": 7.0, "carbs": 44.2, "fat": 1.1, "desc": "小麦粉蒸制"},
    {"name": "面条", "kcal": 110, "protein": 3.5, "carbs": 22.0, "fat": 0.5, "desc": "煮熟的白面条"},
    {"name": "小米粥", "kcal": 46, "protein": 1.4, "carbs": 8.4, "fat": 0.7, "desc": "小米加水煮制的粥"},
    {"name": "全麦面包", "kcal": 247, "protein": 13.0, "carbs": 41.3, "fat": 3.4, "desc": "全麦粉烘焙面包"},
    {"name": "燕麦片", "kcal": 367, "protein": 13.5, "carbs": 66.3, "fat": 6.7, "desc": "即食燕麦片"},
    {"name": "红薯", "kcal": 86, "protein": 1.1, "carbs": 20.1, "fat": 0.1, "desc": "蒸熟的红薯"},
    {"name": "玉米", "kcal": 112, "protein": 4.0, "carbs": 22.8, "fat": 1.2, "desc": "煮熟的甜玉米"},

    # 肉类
    {"name": "猪瘦肉", "kcal": 143, "protein": 20.3, "carbs": 1.5, "fat": 6.2, "desc": "猪里脊肉"},
    {"name": "红烧肉", "kcal": 245, "protein": 15.3, "carbs": 5.2, "fat": 19.8, "desc": "五花肉红烧，含糖和酱油"},
    {"name": "鸡胸肉", "kcal": 133, "protein": 31.0, "carbs": 0.0, "fat": 1.2, "desc": "去皮鸡胸肉，水煮"},
    {"name": "鸡腿肉", "kcal": 181, "protein": 20.0, "carbs": 0.0, "fat": 11.0, "desc": "带皮鸡腿肉"},
    {"name": "牛肉", "kcal": 125, "protein": 22.0, "carbs": 2.0, "fat": 4.2, "desc": "牛瘦肉，煮熟的"},
    {"name": "羊肉", "kcal": 203, "protein": 19.0, "carbs": 0.0, "fat": 14.1, "desc": "羊瘦肉"},
    {"name": "猪排骨", "kcal": 264, "protein": 18.3, "carbs": 0.0, "fat": 20.4, "desc": "猪小排"},
    {"name": "培根", "kcal": 541, "protein": 12.0, "carbs": 1.0, "fat": 55.0, "desc": "烟熏培根肉"},

    # 蛋奶类
    {"name": "鸡蛋", "kcal": 155, "protein": 12.6, "carbs": 1.1, "fat": 11.0, "desc": "煮熟的鸡蛋"},
    {"name": "牛奶", "kcal": 65, "protein": 3.0, "carbs": 4.9, "fat": 3.6, "desc": "全脂牛奶"},
    {"name": "酸奶", "kcal": 72, "protein": 2.5, "carbs": 9.3, "fat": 2.7, "desc": "原味酸奶"},
    {"name": "奶酪", "kcal": 350, "protein": 25.0, "carbs": 1.3, "fat": 27.0, "desc": "切达奶酪"},

    # 蔬菜类
    {"name": "西红柿", "kcal": 18, "protein": 0.9, "carbs": 3.9, "fat": 0.2, "desc": "新鲜西红柿"},
    {"name": "黄瓜", "kcal": 16, "protein": 0.7, "carbs": 2.9, "fat": 0.1, "desc": "新鲜黄瓜"},
    {"name": "菠菜", "kcal": 23, "protein": 2.9, "carbs": 3.6, "fat": 0.4, "desc": "焯水菠菜"},
    {"name": "白菜", "kcal": 13, "protein": 1.5, "carbs": 2.2, "fat": 0.2, "desc": "大白菜"},
    {"name": "西兰花", "kcal": 35, "protein": 3.7, "carbs": 7.2, "fat": 0.4, "desc": "煮熟的西兰花"},
    {"name": "土豆", "kcal": 76, "protein": 2.0, "carbs": 17.5, "fat": 0.1, "desc": "煮熟的土豆"},
    {"name": "胡萝卜", "kcal": 41, "protein": 0.9, "carbs": 10.0, "fat": 0.2, "desc": "新鲜胡萝卜"},
    {"name": "豆腐", "kcal": 76, "protein": 8.1, "carbs": 1.9, "fat": 3.7, "desc": "嫩豆腐"},
    {"name": "豆芽", "kcal": 18, "protein": 2.1, "carbs": 2.6, "fat": 0.2, "desc": "绿豆芽"},

    # 水果类
    {"name": "苹果", "kcal": 52, "protein": 0.3, "carbs": 13.8, "fat": 0.2, "desc": "新鲜苹果"},
    {"name": "香蕉", "kcal": 89, "protein": 1.1, "carbs": 22.8, "fat": 0.3, "desc": "新鲜香蕉"},
    {"name": "橙子", "kcal": 47, "protein": 0.9, "carbs": 11.8, "fat": 0.1, "desc": "新鲜橙子"},
    {"name": "葡萄", "kcal": 69, "protein": 0.7, "carbs": 18.1, "fat": 0.2, "desc": "新鲜葡萄"},
    {"name": "西瓜", "kcal": 30, "protein": 0.6, "carbs": 7.6, "fat": 0.2, "desc": "新鲜西瓜"},
    {"name": "草莓", "kcal": 32, "protein": 0.7, "carbs": 7.7, "fat": 0.3, "desc": "新鲜草莓"},
    {"name": "牛油果", "kcal": 160, "protein": 2.0, "carbs": 8.5, "fat": 14.7, "desc": "新鲜牛油果"},

    # 水产类
    {"name": "三文鱼", "kcal": 208, "protein": 20.4, "carbs": 0.0, "fat": 13.4, "desc": "养殖三文鱼"},
    {"name": "虾仁", "kcal": 99, "protein": 24.0, "carbs": 0.2, "fat": 0.5, "desc": "去壳虾仁，煮熟"},
    {"name": "带鱼", "kcal": 205, "protein": 18.5, "carbs": 0.0, "fat": 14.0, "desc": "煎带鱼"},
    {"name": "鲫鱼", "kcal": 135, "protein": 18.0, "carbs": 0.0, "fat": 7.0, "desc": "清蒸鲫鱼"},

    # 饮品/汤类
    {"name": "豆浆", "kcal": 31, "protein": 3.0, "carbs": 1.2, "fat": 1.6, "desc": "无糖豆浆"},
    {"name": "可乐", "kcal": 42, "protein": 0.0, "carbs": 10.6, "fat": 0.0, "desc": "可口可乐"},
    {"name": "橙汁", "kcal": 45, "protein": 0.7, "carbs": 10.4, "fat": 0.2, "desc": "鲜榨橙汁"},
    {"name": "啤酒", "kcal": 43, "protein": 0.5, "carbs": 3.6, "fat": 0.0, "desc": "普通啤酒"},
    {"name": "紫菜蛋花汤", "kcal": 32, "protein": 3.0, "carbs": 2.0, "fat": 1.5, "desc": "紫菜+鸡蛋花汤"},
    {"name": "西红柿蛋汤", "kcal": 38, "protein": 2.5, "carbs": 3.0, "fat": 2.0, "desc": "西红柿+鸡蛋汤"},

    # 零食/调料
    {"name": "巧克力", "kcal": 546, "protein": 4.9, "carbs": 59.4, "fat": 31.3, "desc": "牛奶巧克力"},
    {"name": "薯片", "kcal": 536, "protein": 6.0, "carbs": 53.0, "fat": 34.0, "desc": "油炸薯片"},
    {"name": "花生", "kcal": 567, "protein": 25.8, "carbs": 16.1, "fat": 49.2, "desc": "炒花生仁"},
    {"name": "核桃", "kcal": 654, "protein": 15.2, "carbs": 13.7, "fat": 65.2, "desc": "干核桃仁"},
    {"name": "食用油", "kcal": 899, "protein": 0.0, "carbs": 0.0, "fat": 99.9, "desc": "常用烹调油"},
    {"name": "白糖", "kcal": 400, "protein": 0.0, "carbs": 100.0, "fat": 0.0, "desc": "白砂糖"},
    {"name": "蜂蜜", "kcal": 304, "protein": 0.3, "carbs": 82.4, "fat": 0.0, "desc": "天然蜂蜜"},
]
```

- [ ] **Step 5: Create seeding script**

```python
# backend/app/rag/seed.py
"""Run once to seed LanceDB with food data."""
from app.rag.store import init_food_db
from app.rag.data import FOOD_DATA

if __name__ == "__main__":
    init_food_db(FOOD_DATA)
```

- [ ] **Step 6: Run seed and verify**

Run: `cd backend && python -m app.rag.seed`
Expected: `Seeded 49 foods into LanceDB`

- [ ] **Step 7: Commit**

```bash
git add backend/app/rag/ backend/requirements.txt
git commit -m "feat: add RAG food knowledge base with LanceDB + 49 common foods"
```

---

### Task 3: LangGraph Agent Tools

**Files:**
- Modify: `backend/app/agent/tools.py` — replace placeholder with real implementations
- Create: `backend/app/agent/prompt.py`

- [ ] **Step 1: Create system prompt**

```python
# backend/app/agent/prompt.py
SYSTEM_PROMPT = """你是饮食记录助手。你只能做三件事：
1. 帮用户记录饮食（需要解析食物→展示确认卡片→用户确认后保存）
2. 回答与食物/营养相关的问题
3. 拒绝与饮食无关的请求

## 记录饮食流程
当用户告诉你吃了什么，你必须：
1. 用 search_food 查询每种食物的营养数据
2. 如果数据库没找到，用你的知识估算（标注"约"）
3. 展示确认卡片格式：
```
帮你整理好了，确认一下：
🍚 米饭 ~200g   232 kcal
🥩 红烧肉 ~150g 368 kcal
合计 600 kcal
蛋白质 24g | 碳水 56g | 脂肪 38g
```
4. 等待用户确认后才调用 save_record 保存
5. 如果用户说"确认"或"好的"或"OK"，调用 save_record

## 查看历史
- 用户说"今天吃了什么"→ 调用 get_daily_summary，日期为今天
- 用户说"昨天"或具体日期 → 传入对应日期
- 展示格式：总热量 + 三大营养素 + 食物列表

## 营养咨询
- 用户问食物营养问题 → 用 search_food 查询后回答
- 食物建议、热量对比等 → 用你的知识直接回答

## 无关话题
- 如果用户说的事情和饮食、食物、营养完全无关
- 礼貌拒绝："抱歉，我只能帮你记录饮食和回答食物相关的问题哦～"

## 重要
- 记录饮食前必须先展示确认卡片
- 热量估算时标注"约"
- 回复简洁友好，使用中文
"""
```

- [ ] **Step 2: Rewrite agent tools with real implementations**

```python
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
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/agent/
git commit -m "feat: implement real LangGraph agent tools"
```

---

### Task 4: LangGraph ReAct Graph + SSE Chat Endpoint

**Files:**
- Create: `backend/app/agent/graph.py`
- Modify: `backend/app/agent/__init__.py`
- Modify: `backend/app/routers/chat.py`

- [ ] **Step 1: Create LangGraph ReAct graph**

```python
# backend/app/agent/graph.py
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
```

- [ ] **Step 2: Update agent init**

```python
# backend/app/agent/__init__.py
from app.agent.graph import run_agent_stream

__all__ = ["run_agent_stream"]
```

- [ ] **Step 3: Rewrite chat router to use SSE streaming**

```python
# backend/app/routers/chat.py
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
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/agent/graph.py backend/app/agent/__init__.py backend/app/routers/chat.py
git commit -m "feat: LangGraph ReAct agent with SSE streaming chat endpoint"
```

---

### Task 5: Miniapp SSE Support

**Files:**
- Modify: `miniapp/miniprogram/utils/api.ts`
- Modify: `miniapp/miniprogram/pages/index/index.ts`

- [ ] **Step 1: Add SSE-capable chat function to api.ts**

Replace the `chat` function in `miniapp/miniprogram/utils/api.ts`:

```typescript
// utils/api.ts — replace the existing chat() function with:

export function chatStream(
  message: string,
  onToken: (token: string) => void,
  onDone: () => void,
  onError: (err: any) => void,
): void {
  const token = getToken()
  const header: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) header['Authorization'] = `Bearer ${token}`

  const task = wx.request({
    url: `${BASE_URL}/api/chat`,
    method: 'POST',
    header,
    data: { message },
    enableChunked: true,
    success: () => onDone(),
    fail: onError,
  })

  // WeChat Mini Program chunked response
  task.onChunkReceived((res: any) => {
    const text = new TextDecoder().decode(res.data)
    // Parse SSE data lines
    const lines = text.split('\n')
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6)
        if (data && data !== '[DONE]') {
          onToken(data)
        }
      }
    }
  })
}
```

- [ ] **Step 2: Update index.ts sendText to use streaming**

Replace the `sendText` method in `miniapp/miniprogram/pages/index/index.ts`:

```typescript
  sendText() {
    const text = this.data.inputValue.trim()
    if (!text) return
    this.setData({ inputValue: '' })
    this.addMsg('user', 'text', text)

    // Stream agent response
    let fullReply = ''
    const msgIdx = this.data.messages.length  // index of agent msg to update
    this.addMsg('agent', 'text', '思考中...')

    chatStream(
      text,
      (token: string) => {
        fullReply += token
        // Update last message in-place
        const msgs = [...this.data.messages]
        msgs[msgIdx] = { role: 'agent', type: 'text', content: fullReply }
        this.setData({ messages: msgs }, () => {
          this.setData({ scrollTop: 99999 })
        })
      },
      () => {
        // Done — finalize
        const msgs = [...this.data.messages]
        msgs[msgIdx] = { role: 'agent', type: 'text', content: fullReply }
        this.setData({ messages: msgs })
      },
      () => {
        const msgs = [...this.data.messages]
        msgs[msgIdx] = { role: 'agent', type: 'text', content: '网络出了点问题，请稍后再试～' }
        this.setData({ messages: msgs })
      },
    )
  },
```

- [ ] **Step 3: Commit**

```bash
git add miniapp/miniprogram/utils/api.ts miniapp/miniprogram/pages/index/index.ts
git commit -m "feat: add SSE streaming support to miniapp chat"
```

---

### Task 6: Integration — Wire Everything Together

**Files:**
- Modify: `backend/app/main.py` — ensure all routers and startup tasks registered
- Modify: `backend/app/database.py` — init RAG on startup

- [ ] **Step 1: Add RAG init to startup**

```python
# backend/app/main.py — modify lifespan to also init RAG:
from app.rag.seed import init_food_db as seed_food_db
from app.rag.data import FOOD_DATA

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Seed food DB if empty
    import os
    if not os.path.exists("data/food_chromadb"):
        seed_food_db(FOOD_DATA)
    yield
```

- [ ] **Step 2: Verify all imports and startup**

Run: `cd backend && uvicorn app.main:app --reload`
Expected: Server starts, tables created, LanceDB seeded, health check passes.

Run: `curl http://localhost:8000/api/health`
Expected: `{"status":"ok"}`

- [ ] **Step 3: Test auth flow manually**

Run (get a test code or skip — this needs real WeChat):
```
curl -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d '{"code":"test"}'
```
Expected: Error about invalid code from WeChat (expected — needs real wx.login code).

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: wire RAG seed into startup, verify integration"
```

---

### Task 7: Quick Smoke Test

**Files:**
- Create: `backend/tests/test_agent.py`

- [ ] **Step 1: Write basic agent smoke test**

```python
# backend/tests/test_agent.py
import pytest
from app.rag.store import search_food


@pytest.mark.asyncio
async def test_search_food_finds_rice():
    results = search_food("米饭")
    assert len(results) > 0
    assert results[0]["food_name"] == "白米饭"
    assert results[0]["kcal_per_100g"] == 116


@pytest.mark.asyncio
async def test_search_food_no_match():
    results = search_food("毒蘑菇xyz")
    assert len(results) == 0 or all(r["score"] < 0.3 for r in results)


def test_food_data_count():
    from app.rag.data import FOOD_DATA
    assert len(FOOD_DATA) >= 40
```

- [ ] **Step 2: Run tests**

Run: `cd backend && pip install pytest pytest-asyncio && python -m pytest tests/test_agent.py -v`
Expected: 3 PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/
git commit -m "test: add agent smoke tests for food search"
```

---

## Summary

After all tasks complete, the system should:

1. **Backend starts clean** — FastAPI + TiDB Cloud + LanceDB ready
2. **Agent works** — LangGraph ReAct agent routes to correct tools
3. **Food search works** — search_food returns nutrition data from LanceDB
4. **Records save** — save_record writes to TiDB Cloud
5. **History works** — get_daily_summary and query_history return data
6. **SSE streaming** — chat endpoint streams agent tokens to miniapp
7. **Miniapp shows responses** — chat UI renders streamed tokens

Prerequisites before running:
- TiDB Cloud connection string in `backend/.env` (`DATABASE_URL`)
- LLM API key in `backend/.env` (`LLM_API_KEY` and `LLM_BASE_URL`)
- WeChat app secret in `backend/.env` (`WECHAT_SECRET`)
- `pip install -r backend/requirements.txt`
