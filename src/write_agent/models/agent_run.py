from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class AgentRun(SQLModel, table=True):
    __tablename__ = "agent_runtime_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    document_id: int = Field(index=True)
    thread_id: int = Field(foreign_key="agent_runtime_threads.id", index=True)
    type: str = Field(default="chat", index=True)
    status: str = Field(default="queued", index=True)
    current_stage: str = Field(default="queued")
    input_version_id: Optional[int] = Field(default=None, index=True)
    output_version_id: Optional[int] = Field(default=None, index=True)
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
