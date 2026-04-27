# backend/app/rag/store.py
from __future__ import annotations

import os
import chromadb
from sentence_transformers import SentenceTransformer

from app.config import settings

COLLECTION_NAME = "food_nutrition"

_embedder: SentenceTransformer | None = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        model_path = settings.bge_model_path or "BAAI/bge-small-zh-v1.5"
        _embedder = SentenceTransformer(model_path, local_files_only=bool(settings.bge_model_path))
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
