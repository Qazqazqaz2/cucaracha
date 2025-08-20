from models.base import SQLModel, Field, Column, DateTime, datetime, timezone
from typing import Optional

class GiftType(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    title: str
    price_stars: int
    remaining_global: int = 0
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    )