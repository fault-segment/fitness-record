# backend/tests/test_agent.py
import pytest


@pytest.mark.asyncio
async def test_search_food_finds_rice():
    pytest.importorskip("chromadb")
    pytest.importorskip("sentence_transformers")
    from app.rag.store import search_food
    results = search_food("米饭")
    assert len(results) > 0
    assert results[0]["food_name"] == "白米饭"
    assert results[0]["kcal_per_100g"] == 116


@pytest.mark.asyncio
async def test_search_food_no_match():
    pytest.importorskip("chromadb")
    pytest.importorskip("sentence_transformers")
    from app.rag.store import search_food
    results = search_food("毒蘑菇xyz")
    assert len(results) == 0 or all(r["score"] < 0.3 for r in results)


def test_food_data_count():
    from app.rag.data import FOOD_DATA
    assert len(FOOD_DATA) >= 40
