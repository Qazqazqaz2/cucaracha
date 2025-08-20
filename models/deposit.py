from models.base import SQLModel, Field, Column, DateTime, datetime, timezone
from typing import Optional

class Deposit(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    amount_stars_gross: int
    commission_rate: float
    commission_provisional: int
    realized_spend: int = 0
    commission_final: int = 0
    refunded_commission: int = 0
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    )