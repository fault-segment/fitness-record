# backend/app/rag/seed.py
"""Run once to seed Chroma with food data."""
from app.rag.store import init_food_db
from app.rag.data import FOOD_DATA

if __name__ == "__main__":
    init_food_db(FOOD_DATA)
