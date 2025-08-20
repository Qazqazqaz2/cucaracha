from models.base import SQLModel, Field, Column, DateTime, datetime, timezone
from typing import Optional

class Account(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_name: str = Field(index=True, unique=True)
    proxy: Optional[str] = None
    last_error: Optional[str] = None
    blacklisted: bool = False
    stars_wallet: int = 0
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    )