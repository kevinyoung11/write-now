from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class AgentThread(SQLModel, table=True):
    __tablename__ = "agent_runtime_threads"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    document_id: int = Field(index=True)
    langgraph_thread_id: str = Field(index=True)
    title: str = Field(default="")
    status: str = Field(default="active", index=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
