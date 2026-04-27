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
