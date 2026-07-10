from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlmodel import SQLModel

from write_agent.core.database import engine


def setup_module() -> None:
    SQLModel.metadata.create_all(engine)


def test_runtime_store_creates_thread_run_and_replayable_events():
    from write_agent.services.agent_runtime_service import AgentRuntimeService

    service = AgentRuntimeService()
    thread = service.get_or_create_thread(
        user_id="runtime-user",
        document_id=1001,
        title="Runtime Test",
    )
    run = service.create_run(
        user_id="runtime-user",
        document_id=1001,
        thread_id=int(thread.id),
        run_type="chat",
        input_version_id=2001,
    )

    first = service.append_event(
        run_id=int(run.id),
        event_type="run_started",
        payload={"status": "running"},
    )
    second = service.append_event(
        run_id=int(run.id),
        event_type="message_delta",
        payload={"delta": "hello"},
    )

    assert first.seq == 1
    assert second.seq == 2
    replay = service.list_events(run_id=int(run.id), from_seq=1)
    assert [event.event_type for event in replay] == ["message_delta"]


def test_runtime_store_persists_messages_and_reasoning():
    from write_agent.services.agent_runtime_service import AgentRuntimeService

    service = AgentRuntimeService()
    thread = service.get_or_create_thread(
        user_id="reasoning-user",
        document_id=1002,
        title="Reasoning Test",
    )
    run = service.create_run(
        user_id="reasoning-user",
        document_id=1002,
        thread_id=int(thread.id),
        run_type="chat",
        input_version_id=None,
    )

    message = service.save_message(
        thread_id=int(thread.id),
        run_id=int(run.id),
        role="assistant",
        content="final answer",
        metadata={},
        document_version_id=None,
    )
    trace = service.save_reasoning_trace(
        run_id=int(run.id),
        thread_id=int(thread.id),
        seq=1,
        content="visible reasoning",
        summary="visible reasoning",
        visibility="visible",
    )

    assert message.content == "final answer"
    assert trace.visibility == "visible"

