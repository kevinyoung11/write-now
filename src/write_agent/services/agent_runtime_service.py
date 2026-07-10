from __future__ import annotations

import json
import threading
import time
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
        return {"run_id": run.id, "thread_id": thread.id, "status": "running"}

    def stream_chat_run(self, *, user_id: str, run_id: int):
        context = self._claim_chat_run_for_streaming(user_id=user_id, run_id=run_id)
        if context is None:
            return

        thread, run, content, selection, base_version_id, document_text = context
        final_chunks: list[str] = []
        settings = get_settings()
        stream_started_at = time.monotonic()
        stream_budget_seconds = max(
            float(getattr(settings, "agent_stream_max_seconds", 50.0) or 0.0),
            0.0,
        )
        budget_exhausted = False
        try:
            agent = self._build_deep_agent()
            message = self._build_user_message(
                content=content,
                selection=selection,
                document_id=int(run.document_id),
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
                        yield self.append_event(
                            user_id=user_id,
                            run_id=int(run.id),
                            event_type="message_delta",
                            payload={"delta": delta},
                        )
                        if (
                            stream_budget_seconds > 0
                            and time.monotonic() - stream_started_at
                            >= stream_budget_seconds
                        ):
                            budget_exhausted = True
                            break
                elif mode == "updates":
                    reasoning = _reasoning_delta(chunk)
                    if reasoning:
                        trace = self.save_reasoning_trace(
                            user_id=user_id,
                            run_id=int(run.id),
                            thread_id=int(thread.id),
                            seq=len(final_chunks) + 1,
                            content=reasoning,
                            summary=reasoning,
                            visibility="visible",
                        )
                        yield self.append_event(
                            user_id=user_id,
                            run_id=int(run.id),
                            event_type="reasoning_delta",
                            payload={
                                "content": trace.content,
                                "summary": trace.summary,
                                "visibility": trace.visibility,
                            },
                        )
                    yield self.append_event(
                        user_id=user_id,
                        run_id=int(run.id),
                        event_type="runtime_update",
                        payload={"update": chunk},
                    )
                    if (
                        stream_budget_seconds > 0
                        and time.monotonic() - stream_started_at
                        >= stream_budget_seconds
                    ):
                        budget_exhausted = True
                        break

            if self._is_run_terminal(run_id=int(run.id), user_id=user_id):
                return
            if budget_exhausted and not final_chunks:
                event = self._fail_run_with_event(
                    run_id=int(run.id),
                    user_id=user_id,
                    error_message="Agent stream exceeded request time budget before producing output.",
                )
                if event is not None:
                    yield event
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
            for event in self._complete_run_with_events(
                user_id=user_id,
                run_id=int(run.id),
                final_answer=final_answer,
                truncated=budget_exhausted,
            ):
                yield event
        except Exception as error:
            event = self._fail_run_with_event(
                run_id=int(run.id),
                user_id=user_id,
                error_message=str(error),
            )
            if event is not None:
                yield event

    def _claim_chat_run_for_streaming(self, *, user_id: str, run_id: int):
        self.ensure_schema()
        with Session(engine, expire_on_commit=False) as session:
            run = self._get_scoped_run(session, run_id=run_id, user_id=user_id)
            if run.status in TERMINAL_RUN_STATUSES:
                return None
            if run.type != "chat":
                raise ValueError("Run not found")
            if run.current_stage != "run_started":
                return None
            thread = session.get(AgentThread, run.thread_id)
            if thread is None or thread.user_id != user_id:
                raise ValueError("Thread not found")
            user_message = session.exec(
                select(AgentMessage)
                .where(
                    AgentMessage.run_id == int(run.id),
                    AgentMessage.role == "user",
                )
                .order_by(AgentMessage.created_at.desc())
            ).first()
            if user_message is None:
                raise ValueError("User message not found")
            run.current_stage = "streaming"
            run.updated_at = datetime.now()
            session.add(run)
            session.commit()
            session.refresh(run)

            metadata = json.loads(user_message.metadata_json or "{}")
            content = user_message.content
            selection = metadata.get("selection") or {}
            base_version_id = run.input_version_id

        _document, current_version = document_service.get_document(
            user_id=user_id,
            document_id=int(run.document_id),
        )
        document_text = current_version.content_text
        if base_version_id is not None and current_version.id != base_version_id:
            versions = document_service.list_versions(
                user_id=user_id,
                document_id=int(run.document_id),
            )
            for version in versions:
                if version.id == base_version_id:
                    document_text = version.content_text
                    break

        return thread, run, content, selection, base_version_id, document_text

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
                    reasoning = _reasoning_delta(chunk)
                    if reasoning:
                        trace = self.save_reasoning_trace(
                            user_id=user_id,
                            run_id=int(run.id),
                            thread_id=int(thread.id),
                            seq=len(final_chunks) + 1,
                            content=reasoning,
                            summary=reasoning,
                            visibility="visible",
                        )
                        self.append_event(
                            user_id=user_id,
                            run_id=int(run.id),
                            event_type="reasoning_delta",
                            payload={
                                "content": trace.content,
                                "summary": trace.summary,
                                "visibility": trace.visibility,
                            },
                        )
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
        self,
        *,
        user_id: str,
        run_id: int,
        final_answer: str,
        truncated: bool = False,
    ) -> list[AgentRunEvent]:
        self.ensure_schema()
        with _RUN_APPEND_LOCKS[run_id]:
            with Session(engine, expire_on_commit=False) as session:
                run = self._get_scoped_run(session, run_id=run_id, user_id=user_id)
                if run.status in TERMINAL_RUN_STATUSES:
                    return []
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
                message_completed = AgentRunEvent(
                    run_id=int(run.id),
                    seq=next_seq,
                    event_type="message_completed",
                    payload_json=_dump_json({"content": final_answer}),
                )
                run_completed = AgentRunEvent(
                    run_id=int(run.id),
                    seq=next_seq + 1,
                    event_type="run_completed",
                    payload_json=_dump_json(
                        {"status": "completed", "truncated": truncated}
                    ),
                )
                session.add(message_completed)
                session.add(run_completed)
                session.commit()
                session.refresh(message_completed)
                session.refresh(run_completed)
                return [message_completed, run_completed]

    def _fail_run_with_event(
        self, *, user_id: str, run_id: int, error_message: str
    ) -> AgentRunEvent | None:
        self.ensure_schema()
        with _RUN_APPEND_LOCKS[run_id]:
            with Session(engine, expire_on_commit=False) as session:
                run = self._get_scoped_run(session, run_id=run_id, user_id=user_id)
                if run.status in TERMINAL_RUN_STATUSES:
                    return None
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
                event = AgentRunEvent(
                    run_id=int(run.id),
                    seq=next_seq,
                    event_type="run_failed",
                    payload_json=_dump_json({"error": error_message}),
                )
                session.add(event)
                session.commit()
                session.refresh(event)
                return event

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
            max_completion_tokens=settings.agent_chat_max_completion_tokens,
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


def _reasoning_delta(chunk: object) -> str:
    if isinstance(chunk, dict):
        for key in ("reasoning_delta", "reasoning", "reasoning_trace"):
            value = chunk.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, dict):
                nested = value.get("content") or value.get("summary")
                if nested:
                    return str(nested)
        for value in chunk.values():
            nested = _reasoning_delta(value)
            if nested:
                return nested
    content = getattr(chunk, "reasoning", None) or getattr(
        chunk, "reasoning_delta", None
    )
    if isinstance(content, str):
        return content
    return ""
