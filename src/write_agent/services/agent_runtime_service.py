from __future__ import annotations

import json
import threading
from datetime import datetime
from collections import defaultdict
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlmodel import SQLModel, Session, select

from write_agent.core.database import engine
from write_agent.models import (
    AgentMessage,
    AgentReasoningTrace,
    AgentRun,
    AgentRunEvent,
    AgentThread,
)

_RUN_APPEND_LOCKS: defaultdict[int, threading.Lock] = defaultdict(threading.Lock)


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
            thread = session.get(AgentThread, thread_id)
            if thread is None or thread.user_id != user_id or thread.document_id != document_id:
                raise ValueError("Thread not found")
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
        self,
        *,
        run_id: int,
        event_type: str,
        payload: dict,
        user_id: str | None = None,
        _internal: bool = False,
    ) -> AgentRunEvent:
        self.ensure_schema()
        if user_id is None and not _internal:
            raise ValueError("User scope is required")
        with _RUN_APPEND_LOCKS[run_id]:
            with Session(engine, expire_on_commit=False) as session:
                run = self._get_scoped_run(session, run_id=run_id, user_id=user_id)
                last = session.exec(
                    select(AgentRunEvent)
                    .where(AgentRunEvent.run_id == int(run.id))
                    .order_by(AgentRunEvent.seq.desc())
                ).first()
                seq = int(last.seq if last else 0) + 1
                event = AgentRunEvent(
                    run_id=int(run.id),
                    seq=seq,
                    event_type=event_type,
                    payload_json=_dump_json(payload),
                )
                session.add(event)
                session.commit()
                session.refresh(event)
                return event

    def list_events(
        self, *, run_id: int, from_seq: int = 0, user_id: str | None = None
    ) -> list[AgentRunEvent]:
        self.ensure_schema()
        if user_id is None:
            raise ValueError("User scope is required")
        with Session(engine, expire_on_commit=False) as session:
            run = self._get_scoped_run(session, run_id=run_id, user_id=user_id)
            return list(
                session.exec(
                    select(AgentRunEvent)
                    .where(
                        AgentRunEvent.run_id == int(run.id),
                        AgentRunEvent.seq > from_seq,
                    )
                    .order_by(AgentRunEvent.seq.asc())
                )
            )

    def save_message(
        self,
        *,
        user_id: str | None = None,
        thread_id: int,
        run_id: int | None,
        role: str,
        content: str,
        metadata: dict,
        document_version_id: int | None,
    ) -> AgentMessage:
        self.ensure_schema()
        if user_id is None:
            raise ValueError("User scope is required")
        with Session(engine, expire_on_commit=False) as session:
            thread = session.get(AgentThread, thread_id)
            if thread is None or thread.user_id != user_id:
                raise ValueError("Thread not found")
            if run_id is not None:
                run = self._get_scoped_run(session, run_id=run_id, user_id=user_id)
                if run.thread_id != thread_id:
                    raise ValueError("Run not found")
            message = AgentMessage(
                thread_id=thread_id,
                run_id=run_id,
                role=role,
                content=content,
                metadata_json=_dump_json(metadata),
                document_version_id=document_version_id,
            )
            session.add(message)
            session.commit()
            session.refresh(message)
            return message

    def save_reasoning_trace(
        self,
        *,
        user_id: str | None = None,
        run_id: int,
        thread_id: int,
        seq: int,
        content: str,
        summary: str,
        visibility: str,
    ) -> AgentReasoningTrace:
        self.ensure_schema()
        if user_id is None:
            raise ValueError("User scope is required")
        with Session(engine, expire_on_commit=False) as session:
            run = self._get_scoped_run(session, run_id=run_id, user_id=user_id)
            if run.thread_id != thread_id:
                raise ValueError("Run not found")
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

    def mark_run_completed(
        self, *, run_id: int, user_id: str | None = None, _internal: bool = False
    ) -> AgentRun:
        return self._mark_run(
            run_id=run_id,
            user_id=user_id,
            _internal=_internal,
            status="completed",
            current_stage="completed",
        )

    def mark_run_failed(
        self,
        *,
        run_id: int,
        error_message: str,
        user_id: str | None = None,
        _internal: bool = False,
    ) -> AgentRun:
        return self._mark_run(
            run_id=run_id,
            user_id=user_id,
            _internal=_internal,
            status="failed",
            current_stage="failed",
            error_message=error_message,
        )

    def mark_run_cancelled(self, *, run_id: int, user_id: str) -> AgentRun:
        return self._mark_run(
            run_id=run_id,
            user_id=user_id,
            status="cancelled",
            current_stage="cancelled",
        )

    def _mark_run(
        self,
        *,
        run_id: int,
        user_id: str | None = None,
        _internal: bool = False,
        status: str,
        current_stage: str,
        error_message: str | None = None,
    ) -> AgentRun:
        self.ensure_schema()
        if user_id is None and not _internal:
            raise ValueError("User scope is required")
        with Session(engine, expire_on_commit=False) as session:
            run = self._get_scoped_run(session, run_id=run_id, user_id=user_id)
            run.status = status
            run.current_stage = current_stage
            run.error_message = error_message
            run.updated_at = datetime.now()
            session.add(run)
            session.commit()
            session.refresh(run)
            return run

    def _get_scoped_run(
        self, session: Session, *, run_id: int, user_id: str | None
    ) -> AgentRun:
        run = session.get(AgentRun, run_id)
        if run is None or (user_id is not None and run.user_id != user_id):
            raise ValueError("Run not found")
        return run


agent_runtime_service = AgentRuntimeService()


def _dump_json(value: object) -> str:
    return json.dumps(jsonable_encoder(value), ensure_ascii=False)
