from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from sqlmodel import SQLModel, Session, select

from write_agent.core.database import engine
from write_agent.models import (
    AgentMessage,
    AgentReasoningTrace,
    AgentRun,
    AgentRunEvent,
    AgentThread,
)


class AgentRuntimeService:
    def ensure_schema(self) -> None:
        SQLModel.metadata.create_all(
            engine,
            tables=[
                AgentThread.__table__,
                AgentRun.__table__,
                AgentRunEvent.__table__,
                AgentMessage.__table__,
                AgentReasoningTrace.__table__,
            ],
        )

    def get_or_create_thread(
        self, *, user_id: str, document_id: int, title: str
    ) -> AgentThread:
        self.ensure_schema()
        with Session(engine, expire_on_commit=False) as session:
            existing = session.exec(
                select(AgentThread).where(
                    AgentThread.user_id == user_id,
                    AgentThread.document_id == document_id,
                    AgentThread.status == "active",
                )
            ).first()
            if existing:
                return existing
            thread = AgentThread(
                user_id=user_id,
                document_id=document_id,
                langgraph_thread_id=f"doc-{document_id}-{uuid4().hex}",
                title=title,
            )
            session.add(thread)
            session.commit()
            session.refresh(thread)
            return thread

    def create_run(
        self,
        *,
        user_id: str,
        document_id: int,
        thread_id: int,
        run_type: str,
        input_version_id: int | None,
    ) -> AgentRun:
        self.ensure_schema()
        with Session(engine, expire_on_commit=False) as session:
            run = AgentRun(
                user_id=user_id,
                document_id=document_id,
                thread_id=thread_id,
                type=run_type,
                status="running",
                current_stage="run_started",
                input_version_id=input_version_id,
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return run

    def append_event(
        self, *, run_id: int, event_type: str, payload: dict
    ) -> AgentRunEvent:
        self.ensure_schema()
        with Session(engine, expire_on_commit=False) as session:
            last = session.exec(
                select(AgentRunEvent)
                .where(AgentRunEvent.run_id == run_id)
                .order_by(AgentRunEvent.seq.desc())
            ).first()
            seq = int(last.seq if last else 0) + 1
            event = AgentRunEvent(
                run_id=run_id,
                seq=seq,
                event_type=event_type,
                payload_json=json.dumps(payload, ensure_ascii=False),
            )
            session.add(event)
            session.commit()
            session.refresh(event)
            return event

    def list_events(self, *, run_id: int, from_seq: int = 0) -> list[AgentRunEvent]:
        self.ensure_schema()
        with Session(engine, expire_on_commit=False) as session:
            return list(
                session.exec(
                    select(AgentRunEvent)
                    .where(AgentRunEvent.run_id == run_id, AgentRunEvent.seq > from_seq)
                    .order_by(AgentRunEvent.seq.asc())
                )
            )

    def save_message(
        self,
        *,
        thread_id: int,
        run_id: int | None,
        role: str,
        content: str,
        metadata: dict,
        document_version_id: int | None,
    ) -> AgentMessage:
        self.ensure_schema()
        with Session(engine, expire_on_commit=False) as session:
            message = AgentMessage(
                thread_id=thread_id,
                run_id=run_id,
                role=role,
                content=content,
                metadata_json=json.dumps(metadata, ensure_ascii=False),
                document_version_id=document_version_id,
            )
            session.add(message)
            session.commit()
            session.refresh(message)
            return message

    def save_reasoning_trace(
        self,
        *,
        run_id: int,
        thread_id: int,
        seq: int,
        content: str,
        summary: str,
        visibility: str,
    ) -> AgentReasoningTrace:
        self.ensure_schema()
        with Session(engine, expire_on_commit=False) as session:
            trace = AgentReasoningTrace(
                run_id=run_id,
                thread_id=thread_id,
                seq=seq,
                content=content,
                summary=summary,
                visibility=visibility,
            )
            session.add(trace)
            session.commit()
            session.refresh(trace)
            return trace

    def mark_run_completed(self, *, run_id: int) -> AgentRun:
        return self._mark_run(
            run_id=run_id,
            status="completed",
            current_stage="completed",
        )

    def mark_run_failed(self, *, run_id: int, error_message: str) -> AgentRun:
        return self._mark_run(
            run_id=run_id,
            status="failed",
            current_stage="failed",
            error_message=error_message,
        )

    def mark_run_cancelled(self, *, run_id: int) -> AgentRun:
        return self._mark_run(
            run_id=run_id,
            status="cancelled",
            current_stage="cancelled",
        )

    def _mark_run(
        self,
        *,
        run_id: int,
        status: str,
        current_stage: str,
        error_message: str | None = None,
    ) -> AgentRun:
        self.ensure_schema()
        with Session(engine, expire_on_commit=False) as session:
            run = session.get(AgentRun, run_id)
            if run is None:
                raise ValueError("Run not found")
            run.status = status
            run.current_stage = current_stage
            run.error_message = error_message
            run.updated_at = datetime.now()
            session.add(run)
            session.commit()
            session.refresh(run)
            return run


agent_runtime_service = AgentRuntimeService()

