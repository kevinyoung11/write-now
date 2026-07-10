from __future__ import annotations

import json
import threading
from datetime import datetime
from collections import defaultdict
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from langchain_openai import ChatOpenAI
from sqlmodel import SQLModel, Session, select

from write_agent.core import get_settings
from write_agent.core.database import engine
from write_agent.models import (
    AgentMessage,
    AgentReasoningTrace,
    AgentRun,
    AgentRunEvent,
    AgentThread,
)
from write_agent.services.document_service import document_service

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

    def get_thread(self, *, user_id: str, thread_id: int) -> AgentThread:
        self.ensure_schema()
        with Session(engine, expire_on_commit=False) as session:
            thread = session.get(AgentThread, thread_id)
            if thread is None or thread.user_id != user_id:
                raise ValueError("Thread not found")
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
            allow_terminal=False,
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
            allow_terminal=False,
            status="failed",
            current_stage="failed",
            error_message=error_message,
        )

    def mark_run_cancelled(self, *, run_id: int, user_id: str) -> AgentRun:
        return self._cancel_run_with_event(user_id=user_id, run_id=run_id)

    def _mark_run(
        self,
        *,
        run_id: int,
        user_id: str | None = None,
        _internal: bool = False,
        allow_terminal: bool = True,
        status: str,
        current_stage: str,
        error_message: str | None = None,
    ) -> AgentRun:
        self.ensure_schema()
        if user_id is None and not _internal:
            raise ValueError("User scope is required")
        with Session(engine, expire_on_commit=False) as session:
            run = self._get_scoped_run(session, run_id=run_id, user_id=user_id)
            if not allow_terminal and run.status in TERMINAL_RUN_STATUSES:
                raise ValueError("Run is already terminal")
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

    def start_chat_run(
        self,
        *,
        user_id: str,
        document_id: int,
        content: str,
        selection: dict | None,
        base_version_id: int | None,
    ) -> dict:
        document, current_version = document_service.get_document(
            user_id=user_id,
            document_id=document_id,
        )
        if base_version_id is not None:
            versions = document_service.list_versions(
                user_id=user_id,
                document_id=document_id,
            )
            if all(version.id != base_version_id for version in versions):
                raise ValueError("Version not found")
        base_version_id = base_version_id or current_version.id
        thread = self.get_or_create_thread(
            user_id=user_id,
            document_id=document_id,
            title=document.title or "Document chat",
        )
        run = self.create_run(
            user_id=user_id,
            document_id=document_id,
            thread_id=int(thread.id),
            run_type="chat",
            input_version_id=base_version_id,
        )
        self.save_message(
            user_id=user_id,
            thread_id=int(thread.id),
            run_id=int(run.id),
            role="user",
            content=content,
            metadata={"selection": selection or {}},
            document_version_id=base_version_id,
        )
        self.append_event(
            user_id=user_id,
            run_id=int(run.id),
            event_type="run_started",
            payload={"run_id": run.id, "thread_id": thread.id, "status": "running"},
        )
        self.append_event(
            user_id=user_id,
            run_id=int(run.id),
            event_type="user_message_saved",
            payload={"content": content},
        )
        worker = threading.Thread(
            target=self._run_chat_stream,
            kwargs={
                "user_id": user_id,
                "document_id": document_id,
                "thread": thread,
                "run": run,
                "content": content,
                "selection": selection or {},
                "base_version_id": base_version_id,
                "document_text": current_version.content_text,
            },
            daemon=True,
        )
        worker.start()
        return {"run_id": run.id, "thread_id": thread.id, "status": "running"}

    def _run_chat_stream(
        self,
        *,
        user_id: str,
        document_id: int,
        thread: AgentThread,
        run: AgentRun,
        content: str,
        selection: dict,
        base_version_id: int | None,
        document_text: str,
    ) -> None:
        final_chunks: list[str] = []
        try:
            agent = self._build_deep_agent()
            message = self._build_user_message(
                content=content,
                selection=selection,
                document_id=document_id,
                base_version_id=base_version_id,
                document_text=document_text,
            )
            config = {
                "configurable": {
                    "thread_id": thread.langgraph_thread_id,
                }
            }
            for mode, chunk in agent.stream(
                {"messages": [{"role": "user", "content": message}]},
                config=config,
                stream_mode=["messages", "updates"],
            ):
                if self._is_run_terminal(run_id=int(run.id), user_id=user_id):
                    return
                if mode == "messages":
                    delta = _message_delta(chunk)
                    if delta:
                        final_chunks.append(delta)
                        self.append_event(
                            user_id=user_id,
                            run_id=int(run.id),
                            event_type="message_delta",
                            payload={"delta": delta},
                        )
                elif mode == "updates":
                    self.append_event(
                        user_id=user_id,
                        run_id=int(run.id),
                        event_type="runtime_update",
                        payload={"update": chunk},
                    )

            if self._is_run_terminal(run_id=int(run.id), user_id=user_id):
                return
            final_answer = "".join(final_chunks)
            self.save_message(
                user_id=user_id,
                thread_id=int(thread.id),
                run_id=int(run.id),
                role="assistant",
                content=final_answer,
                metadata={},
                document_version_id=base_version_id,
            )
            self._complete_run_with_events(
                user_id=user_id,
                run_id=int(run.id),
                final_answer=final_answer,
            )
        except Exception as error:
            self._fail_run_with_event(
                run_id=int(run.id),
                user_id=user_id,
                error_message=str(error),
            )

    def _complete_run_with_events(
        self, *, user_id: str, run_id: int, final_answer: str
    ) -> bool:
        self.ensure_schema()
        with _RUN_APPEND_LOCKS[run_id]:
            with Session(engine, expire_on_commit=False) as session:
                run = self._get_scoped_run(session, run_id=run_id, user_id=user_id)
                if run.status in TERMINAL_RUN_STATUSES:
                    return False
                last = session.exec(
                    select(AgentRunEvent)
                    .where(AgentRunEvent.run_id == int(run.id))
                    .order_by(AgentRunEvent.seq.desc())
                ).first()
                next_seq = int(last.seq if last else 0) + 1
                run.status = "completed"
                run.current_stage = "completed"
                run.error_message = None
                run.updated_at = datetime.now()
                session.add(run)
                session.add(
                    AgentRunEvent(
                        run_id=int(run.id),
                        seq=next_seq,
                        event_type="message_completed",
                        payload_json=_dump_json({"content": final_answer}),
                    )
                )
                session.add(
                    AgentRunEvent(
                        run_id=int(run.id),
                        seq=next_seq + 1,
                        event_type="run_completed",
                        payload_json=_dump_json({"status": "completed"}),
                    )
                )
                session.commit()
                return True

    def _fail_run_with_event(
        self, *, user_id: str, run_id: int, error_message: str
    ) -> bool:
        self.ensure_schema()
        with _RUN_APPEND_LOCKS[run_id]:
            with Session(engine, expire_on_commit=False) as session:
                run = self._get_scoped_run(session, run_id=run_id, user_id=user_id)
                if run.status in TERMINAL_RUN_STATUSES:
                    return False
                last = session.exec(
                    select(AgentRunEvent)
                    .where(AgentRunEvent.run_id == int(run.id))
                    .order_by(AgentRunEvent.seq.desc())
                ).first()
                next_seq = int(last.seq if last else 0) + 1
                run.status = "failed"
                run.current_stage = "failed"
                run.error_message = error_message
                run.updated_at = datetime.now()
                session.add(run)
                session.add(
                    AgentRunEvent(
                        run_id=int(run.id),
                        seq=next_seq,
                        event_type="run_failed",
                        payload_json=_dump_json({"error": error_message}),
                    )
                )
                session.commit()
                return True

    def _cancel_run_with_event(self, *, user_id: str, run_id: int) -> AgentRun:
        self.ensure_schema()
        with _RUN_APPEND_LOCKS[run_id]:
            with Session(engine, expire_on_commit=False) as session:
                run = self._get_scoped_run(session, run_id=run_id, user_id=user_id)
                if run.status in TERMINAL_RUN_STATUSES:
                    raise ValueError("Run is already terminal")
                last = session.exec(
                    select(AgentRunEvent)
                    .where(AgentRunEvent.run_id == int(run.id))
                    .order_by(AgentRunEvent.seq.desc())
                ).first()
                next_seq = int(last.seq if last else 0) + 1
                run.status = "cancelled"
                run.current_stage = "cancelled"
                run.error_message = None
                run.updated_at = datetime.now()
                session.add(run)
                session.add(
                    AgentRunEvent(
                        run_id=int(run.id),
                        seq=next_seq,
                        event_type="run_cancelled",
                        payload_json=_dump_json({"status": "cancelled"}),
                    )
                )
                session.commit()
                session.refresh(run)
                return run

    def _build_deep_agent(self):
        from deepagents import create_deep_agent

        settings = get_settings()
        base_url = settings.openai_base_url.strip().rstrip("/")
        if base_url and not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        model = ChatOpenAI(
            model=settings.openai_model,
            openai_api_key=settings.openai_api_key,
            base_url=base_url or None,
            timeout=settings.openai_timeout_seconds,
            reasoning_effort=settings.openai_reasoning_effort or None,
            store=False if settings.openai_disable_response_storage else None,
            use_responses_api=(settings.openai_wire_api or "").strip().lower()
            == "responses",
        )
        return create_deep_agent(
            model=model,
            tools=[],
            system_prompt=(
                "你是一个视频脚本写作工作台里的编辑型 AI。"
                "优先帮助用户把文本写深、写清楚，围绕选区和全文上下文给出可执行修改。"
                "不要编造资料；如果缺少资料，直接说明需要补充什么。"
            ),
        )

    def _build_user_message(
        self,
        *,
        content: str,
        selection: dict,
        document_id: int,
        base_version_id: int | None,
        document_text: str,
    ) -> str:
        selection_text = str(selection.get("text") or "")
        context_before = str(selection.get("context_before") or "")
        context_after = str(selection.get("context_after") or "")
        return (
            f"document_id: {document_id}\n"
            f"base_version_id: {base_version_id or ''}\n"
            f"selection_text:\n{selection_text}\n\n"
            f"context_before:\n{context_before}\n\n"
            f"context_after:\n{context_after}\n\n"
            f"document_text:\n{document_text}\n\n"
            f"user_request:\n{content}"
        )

    def _is_run_terminal(self, *, run_id: int, user_id: str) -> bool:
        self.ensure_schema()
        with Session(engine, expire_on_commit=False) as session:
            run = self._get_scoped_run(session, run_id=run_id, user_id=user_id)
            return run.status in TERMINAL_RUN_STATUSES


agent_runtime_service = AgentRuntimeService()

TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled"}


def _dump_json(value: object) -> str:
    return json.dumps(jsonable_encoder(value), ensure_ascii=False)


def _message_delta(chunk: object) -> str:
    message = chunk[0] if isinstance(chunk, tuple) and chunk else chunk
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return ""
