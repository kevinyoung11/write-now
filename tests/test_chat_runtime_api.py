from __future__ import annotations

import os
import sys
import json
from datetime import datetime
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlmodel import SQLModel

from write_agent.core.database import engine


def setup_module() -> None:
    SQLModel.metadata.create_all(engine)


def test_runtime_store_creates_thread_run_and_replayable_events():
    from write_agent.services.agent_runtime_service import AgentRuntimeService

    service = AgentRuntimeService()
    user_id = f"runtime-user-{uuid4().hex}"
    document_id = 1001
    thread = service.get_or_create_thread(
        user_id=user_id,
        document_id=document_id,
        title="Runtime Test",
    )
    run = service.create_run(
        user_id=user_id,
        document_id=document_id,
        thread_id=int(thread.id),
        run_type="chat",
        input_version_id=2001,
    )

    first = service.append_event(
        user_id=user_id,
        run_id=int(run.id),
        event_type="run_started",
        payload={"status": "running", "created_at": datetime(2026, 7, 10, 12, 0, 0)},
    )
    second = service.append_event(
        user_id=user_id,
        run_id=int(run.id),
        event_type="message_delta",
        payload={"delta": "hello"},
    )

    assert first.seq == 1
    assert second.seq == 2
    assert json.loads(first.payload_json)["created_at"] == "2026-07-10T12:00:00"
    replay = service.list_events(user_id=user_id, run_id=int(run.id), from_seq=1)
    assert [event.event_type for event in replay] == ["message_delta"]

    try:
        service.list_events(user_id="another-user", run_id=int(run.id), from_seq=0)
    except ValueError as error:
        assert str(error) == "Run not found"
    else:
        raise AssertionError("expected ValueError")


def test_runtime_store_persists_messages_and_reasoning():
    from write_agent.services.agent_runtime_service import AgentRuntimeService

    service = AgentRuntimeService()
    user_id = f"reasoning-user-{uuid4().hex}"
    document_id = 1002
    thread = service.get_or_create_thread(
        user_id=user_id,
        document_id=document_id,
        title="Reasoning Test",
    )
    run = service.create_run(
        user_id=user_id,
        document_id=document_id,
        thread_id=int(thread.id),
        run_type="chat",
        input_version_id=None,
    )

    message = service.save_message(
        user_id=user_id,
        thread_id=int(thread.id),
        run_id=int(run.id),
        role="assistant",
        content="final answer",
        metadata={"seen_at": datetime(2026, 7, 10, 12, 5, 0), "thread": uuid4()},
        document_version_id=None,
    )
    trace = service.save_reasoning_trace(
        user_id=user_id,
        run_id=int(run.id),
        thread_id=int(thread.id),
        seq=1,
        content="visible reasoning",
        summary="visible reasoning",
        visibility="visible",
    )

    assert message.content == "final answer"
    metadata = json.loads(message.metadata_json)
    assert metadata["seen_at"] == "2026-07-10T12:05:00"
    assert isinstance(metadata["thread"], str)
    assert trace.visibility == "visible"

    try:
        service.mark_run_cancelled(user_id="another-user", run_id=int(run.id))
    except ValueError as error:
        assert str(error) == "Run not found"
    else:
        raise AssertionError("expected ValueError")
