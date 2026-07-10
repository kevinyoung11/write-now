from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class AgentMessage(SQLModel, table=True):
    __tablename__ = "agent_messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    thread_id: int = Field(foreign_key="agent_threads.id", index=True)
    run_id: Optional[int] = Field(default=None, index=True)
    role: str = Field(index=True)
    content: str = Field(default="")
    metadata_json: str = Field(default="{}")
    document_version_id: Optional[int] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.now, index=True)

