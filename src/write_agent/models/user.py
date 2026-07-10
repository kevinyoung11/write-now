from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    supabase_user_id: str = Field(index=True, unique=True)
    email: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.now)
