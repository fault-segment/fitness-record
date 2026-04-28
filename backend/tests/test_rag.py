"""RAG 食品知识库回归测试"""
import pytest

pytest.importorskip("chromadb")
pytest.importorskip("sentence_transformers")


class TestFoodSearch:
    """向量检索功能"""

    def test_finds_rice(self):
        from app.rag.store import search_food
        results = search_food("米饭")
        assert len(results) > 0
        assert results[0]["food_name"] == "白米饭"
        assert results[0]["kcal_per_100g"] == 116

    def test_finds_partial_match(self):
        from app.rag.store import search_food
        results = search_food("鸡")
        assert len(results) > 0
        names = [r["food_name"] for r in results]
        assert any("鸡" in n for n in names)

    def test_no_match_low_score(self):
        from app.rag.store import search_food
        results = search_food("毒蘑菇xyz")
        assert len(results) == 0 or results[0]["score"] < 0.7

    def test_returns_nutrition_fields(self):
        from app.rag.store import search_food
        results = search_food("鸡蛋")
        assert len(results) > 0
        r = results[0]
        for field in ["food_name", "kcal_per_100g", "protein_per_100g", "carbs_per_100g", "fat_per_100g", "score"]:
            assert field in r, f"missing field: {field}"

    def test_top_5_results(self):
        from app.rag.store import search_food
        results = search_food("肉", top_k=3)
        assert len(results) <= 3


class TestFoodData:
    """营养数据完整性"""

    def test_min_count(self):
        from app.rag.data import FOOD_DATA
        assert len(FOOD_DATA) >= 40

    def test_all_have_required_fields(self):
        from app.rag.data import FOOD_DATA
        for food in FOOD_DATA:
            for field in ["name", "kcal", "protein", "carbs", "fat"]:
                assert field in food, f"{food.get('name', '?')} missing {field}"

    def test_kcal_positive(self):
        from app.rag.data import FOOD_DATA
        for food in FOOD_DATA:
            assert food["kcal"] > 0, f"{food['name']} kcal should be > 0"

    def test_no_duplicate_names(self):
        from app.rag.data import FOOD_DATA
        names = [f["name"] for f in FOOD_DATA]
        assert len(names) == len(set(names))
