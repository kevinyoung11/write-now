from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


class AgentRunEvent(SQLModel, table=True):
    __tablename__ = "agent_runtime_run_events"
    __table_args__ = (UniqueConstraint("run_id", "seq"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="agent_runtime_runs.id", index=True)
    seq: int = Field(index=True)
    event_type: str = Field(index=True)
    payload_json: str = Field(default="{}")
    created_at: datetime = Field(default_factory=datetime.now, index=True)
