from __future__ import annotations

import os
import sys
import json
from datetime import datetime
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlmodel import SQLModel

from write_agent.core.database import engine
from fastapi.testclient import TestClient
from write_agent.main import app


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


def test_chat_message_endpoint_starts_scoped_run(monkeypatch):
    from write_agent.api import chat as chat_api

    class FakeRuntime:
        def start_chat_run(self, *, user_id, document_id, content, selection, base_version_id):
            assert user_id.startswith("chat-user-")
            assert document_id == 10
            assert content == "这段怎么改？"
            assert selection == {
                "text": "原文",
                "context_before": "",
                "context_after": "",
            }
            assert base_version_id == 20
            return {"run_id": 501, "thread_id": 601, "status": "running"}

    monkeypatch.setattr(chat_api, "agent_runtime_service", FakeRuntime())

    client = TestClient(app)
    response = client.post(
        "/api/documents/10/chat/messages",
        headers={"X-Dev-User-Id": f"chat-user-{uuid4().hex}"},
        json={
            "content": "这段怎么改？",
            "selection": {"text": "原文", "context_before": "", "context_after": ""},
            "base_version_id": 20,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"run_id": 501, "thread_id": 601, "status": "running"}


def test_chat_events_endpoint_replays_scoped_sse(monkeypatch):
    from types import SimpleNamespace
    from write_agent.api import chat as chat_api

    captured = {}

    def fake_list_events(*, user_id, run_id, from_seq=0):
        captured["user_id"] = user_id
        captured["run_id"] = run_id
        captured["from_seq"] = from_seq
        return [
            SimpleNamespace(seq=1, event_type="run_started", payload_json='{"ok": true}'),
            SimpleNamespace(seq=2, event_type="message_delta", payload_json='{"delta": "Hi"}'),
        ]

    monkeypatch.setattr(chat_api.agent_runtime_service, "list_events", fake_list_events)

    client = TestClient(app)
    user_id = f"chat-user-{uuid4().hex}"
    response = client.get(
        "/api/chat/runs/99/events?from_seq=0",
        headers={"X-Dev-User-Id": user_id},
    )

    assert response.status_code == 200
    assert captured == {"user_id": user_id, "run_id": 99, "from_seq": 0}
    assert "event: run_started" in response.text
    assert '"delta": "Hi"' in response.text


def test_runtime_chat_run_uses_deepagents_stream(monkeypatch):
    from write_agent.services.agent_runtime_service import AgentRuntimeService

    class FakeAgent:
        def stream(self, input_payload, config=None, stream_mode=None):
            assert input_payload["messages"][0]["role"] == "user"
            assert config["configurable"]["thread_id"].startswith("doc-")
            assert stream_mode == ["messages", "updates"]
            yield (
                "messages",
                (SimpleContent("Hello"), {"langgraph_node": "agent"}),
            )
            yield ("updates", {"agent": {"stage": "done"}})

    class SimpleContent:
        def __init__(self, content):
            self.content = content

    service = AgentRuntimeService()
    user_id = f"deepagent-user-{uuid4().hex}"
    monkeypatch.setattr(service, "_build_deep_agent", lambda: FakeAgent())

    result = service.start_chat_run(
        user_id=user_id,
        document_id=3001,
        content="帮我润色",
        selection={"text": "原文"},
        base_version_id=None,
    )

    events = service.list_events(
        user_id=user_id,
        run_id=int(result["run_id"]),
        from_seq=0,
    )
    event_types = [event.event_type for event in events]
    assert "message_delta" in event_types
    assert "runtime_update" in event_types
    assert event_types[-1] == "run_completed"
