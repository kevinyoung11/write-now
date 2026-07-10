from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class AgentReasoningTrace(SQLModel, table=True):
    __tablename__ = "agent_reasoning_traces"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="agent_runs.id", index=True)
    thread_id: int = Field(foreign_key="agent_threads.id", index=True)
    seq: int = Field(index=True)
    content: str = Field(default="")
    summary: str = Field(default="")
    visibility: str = Field(default="visible", index=True)
    created_at: datetime = Field(default_factory=datetime.now, index=True)

