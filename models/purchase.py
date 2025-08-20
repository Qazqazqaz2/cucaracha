from models.base import SQLModel, Field, Column, DateTime, datetime, timezone
from typing import Optional

class Purchase(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    gift_type_id: int = Field(index=True, foreign_key="gifttype.id")
    account_id: int = Field(index=True, foreign_key="account.id")
    price_stars: int
    status: str = "purchased"
    owner_user_id: Optional[int] = Field(default=None, index=True)
    ext_payload: Optional[str] = None
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    )