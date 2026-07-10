from __future__ import annotations

import os
import sys
import json
import time
from datetime import datetime
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy import create_engine, inspect, text
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


def test_runtime_store_uses_dedicated_tables_when_legacy_agent_tables_exist(
    monkeypatch, tmp_path
):
    from write_agent.services import agent_runtime_service as runtime_module
    from write_agent.services.agent_runtime_service import AgentRuntimeService

    legacy_engine = create_engine(f"sqlite:///{tmp_path}/legacy-agent.db")
    with legacy_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE agent_threads ("
                "id TEXT PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE agent_runs ("
                "id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, status TEXT NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE agent_messages ("
                "id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, content TEXT NOT NULL)"
            )
        )

    monkeypatch.setattr(runtime_module, "engine", legacy_engine)

    service = AgentRuntimeService()
    user_id = f"legacy-runtime-user-{uuid4().hex}"
    thread = service.get_or_create_thread(
        user_id=user_id,
        document_id=9001,
        title="Legacy Conflict Test",
    )
    run = service.create_run(
        user_id=user_id,
        document_id=9001,
        thread_id=int(thread.id),
        run_type="chat",
        input_version_id=None,
    )
    event = service.append_event(
        user_id=user_id,
        run_id=int(run.id),
        event_type="run_started",
        payload={"status": "running"},
    )

    tables = set(inspect(legacy_engine).get_table_names())
    assert "agent_runtime_threads" in tables
    assert "agent_runtime_runs" in tables
    assert "agent_runtime_run_events" in tables
    assert event.seq == 1


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
            SimpleNamespace(seq=3, event_type="run_completed", payload_json='{"status": "completed"}'),
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


def test_chat_events_endpoint_drives_stream_execution(monkeypatch):
    from types import SimpleNamespace
    from write_agent.api import chat as chat_api

    calls = {"stream": 0}

    class FakeRuntime:
        def list_events(self, *, user_id, run_id, from_seq=0):
            return []

        def stream_chat_run(self, *, user_id, run_id):
            calls["stream"] += 1
            yield SimpleNamespace(
                seq=1,
                event_type="message_delta",
                payload_json='{"delta": "Hi"}',
            )
            yield SimpleNamespace(
                seq=2,
                event_type="run_completed",
                payload_json='{"status": "completed"}',
            )

    monkeypatch.setattr(chat_api, "agent_runtime_service", FakeRuntime())

    client = TestClient(app)
    response = client.get(
        "/api/chat/runs/99/events?from_seq=0",
        headers={"X-Dev-User-Id": f"chat-user-{uuid4().hex}"},
    )

    assert response.status_code == 200
    assert calls["stream"] == 1
    assert "event: message_delta" in response.text
    assert "event: run_completed" in response.text


def test_chat_message_endpoint_rejects_unowned_document():
    owner_id = f"chat-owner-{uuid4().hex}"
    attacker_id = f"chat-attacker-{uuid4().hex}"
    document = _create_document(user_id=owner_id)

    client = TestClient(app)
    response = client.post(
        f"/api/documents/{document['id']}/chat/messages",
        headers={"X-Dev-User-Id": attacker_id},
        json={
            "content": "这段怎么改？",
            "base_version_id": document["current_version"]["id"],
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


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
    document = _create_document(user_id=user_id)
    monkeypatch.setattr(service, "_build_deep_agent", lambda: FakeAgent())

    result = service.start_chat_run(
        user_id=user_id,
        document_id=int(document["id"]),
        content="帮我润色",
        selection={"text": "原文"},
        base_version_id=document["current_version"]["id"],
    )
    list(
        service.stream_chat_run(
            user_id=user_id,
            run_id=int(result["run_id"]),
        )
    )

    events = _wait_for_run_completed(
        service=service,
        user_id=user_id,
        run_id=int(result["run_id"]),
    )
    event_types = [event.event_type for event in events]
    assert "message_delta" in event_types
    assert "runtime_update" in event_types
    assert event_types[-1] == "run_completed"


def test_runtime_chat_run_persists_visible_reasoning(monkeypatch):
    from write_agent.services.agent_runtime_service import AgentRuntimeService
    from write_agent.models import AgentReasoningTrace
    from sqlmodel import Session, select

    class FakeAgent:
        def stream(self, input_payload, config=None, stream_mode=None):
            yield ("updates", {"reasoning_delta": "先判断问题"})
            yield ("messages", (SimpleContent("结论"), {}))

    class SimpleContent:
        def __init__(self, content):
            self.content = content

    service = AgentRuntimeService()
    user_id = f"reasoning-stream-user-{uuid4().hex}"
    document = _create_document(user_id=user_id)
    monkeypatch.setattr(service, "_build_deep_agent", lambda: FakeAgent())

    result = service.start_chat_run(
        user_id=user_id,
        document_id=int(document["id"]),
        content="怎么改",
        selection=None,
        base_version_id=document["current_version"]["id"],
    )
    list(
        service.stream_chat_run(
            user_id=user_id,
            run_id=int(result["run_id"]),
        )
    )

    events = _wait_for_run_completed(
        service=service,
        user_id=user_id,
        run_id=int(result["run_id"]),
    )
    assert any(event.event_type == "reasoning_delta" for event in events)

    with Session(engine) as session:
        trace = session.exec(
            select(AgentReasoningTrace).where(
                AgentReasoningTrace.run_id == int(result["run_id"])
            )
        ).one()
    assert trace.content == "先判断问题"
    assert trace.visibility == "visible"


def test_chat_run_start_returns_before_stream_execution(monkeypatch):
    from write_agent.services.agent_runtime_service import AgentRuntimeService

    class SlowAgent:
        def stream(self, input_payload, config=None, stream_mode=None):
            time.sleep(0.25)
            yield ("messages", (SimpleContent("late"), {}))

    class SimpleContent:
        def __init__(self, content):
            self.content = content

    service = AgentRuntimeService()
    user_id = f"live-stream-user-{uuid4().hex}"
    document = _create_document(user_id=user_id)
    calls = {"build": 0}

    def build_agent():
        calls["build"] += 1
        return SlowAgent()

    monkeypatch.setattr(service, "_build_deep_agent", lambda: SlowAgent())
    monkeypatch.setattr(service, "_build_deep_agent", build_agent)

    started = time.monotonic()
    result = service.start_chat_run(
        user_id=user_id,
        document_id=int(document["id"]),
        content="开始",
        selection=None,
        base_version_id=document["current_version"]["id"],
    )
    elapsed = time.monotonic() - started

    assert result["status"] == "running"
    assert elapsed < 0.2
    assert calls["build"] == 0

    streamed = list(
        service.stream_chat_run(
            user_id=user_id,
            run_id=int(result["run_id"]),
        )
    )
    assert calls["build"] == 1
    assert any(event.event_type == "run_completed" for event in streamed)


def test_chat_run_rejects_unowned_document_and_version(monkeypatch):
    from write_agent.services.agent_runtime_service import AgentRuntimeService

    owner_id = f"doc-owner-{uuid4().hex}"
    attacker_id = f"doc-attacker-{uuid4().hex}"
    document = _create_document(user_id=owner_id)
    service = AgentRuntimeService()

    try:
        service.start_chat_run(
            user_id=attacker_id,
            document_id=int(document["id"]),
            content="偷看",
            selection=None,
            base_version_id=document["current_version"]["id"],
        )
    except ValueError as error:
        assert str(error) == "Document not found"
    else:
        raise AssertionError("expected ValueError")

    other = _create_document(user_id=owner_id)
    try:
        service.start_chat_run(
            user_id=owner_id,
            document_id=int(document["id"]),
            content="错版本",
            selection=None,
            base_version_id=other["current_version"]["id"],
        )
    except ValueError as error:
        assert str(error) == "Version not found"
    else:
        raise AssertionError("expected ValueError")


def test_cancel_does_not_overwrite_completed_run():
    from write_agent.services.agent_runtime_service import AgentRuntimeService

    service = AgentRuntimeService()
    user_id = f"cancel-user-{uuid4().hex}"
    thread = service.get_or_create_thread(
        user_id=user_id,
        document_id=4001,
        title="Cancel Test",
    )
    run = service.create_run(
        user_id=user_id,
        document_id=4001,
        thread_id=int(thread.id),
        run_type="chat",
        input_version_id=None,
    )
    service.mark_run_completed(user_id=user_id, run_id=int(run.id))

    try:
        service.mark_run_cancelled(user_id=user_id, run_id=int(run.id))
    except ValueError as error:
        assert str(error) == "Run is already terminal"
    else:
        raise AssertionError("expected ValueError")


def test_cancelled_live_run_does_not_complete(monkeypatch):
    from write_agent.services.agent_runtime_service import AgentRuntimeService

    class SlowAgent:
        def stream(self, input_payload, config=None, stream_mode=None):
            time.sleep(0.15)
            yield ("messages", (SimpleContent("late"), {}))

    class SimpleContent:
        def __init__(self, content):
            self.content = content

    service = AgentRuntimeService()
    user_id = f"cancel-live-{uuid4().hex}"
    document = _create_document(user_id=user_id)
    monkeypatch.setattr(service, "_build_deep_agent", lambda: SlowAgent())
    result = service.start_chat_run(
        user_id=user_id,
        document_id=int(document["id"]),
        content="开始",
        selection=None,
        base_version_id=document["current_version"]["id"],
    )
    stream = service.stream_chat_run(user_id=user_id, run_id=int(result["run_id"]))
    first_event = next(stream)
    assert first_event.event_type in {"message_delta", "runtime_update"}

    service.mark_run_cancelled(user_id=user_id, run_id=int(result["run_id"]))
    list(stream)

    events = service.list_events(
        user_id=user_id,
        run_id=int(result["run_id"]),
        from_seq=0,
    )
    event_types = [event.event_type for event in events]
    assert "run_cancelled" in event_types
    assert "run_completed" not in event_types


def test_cancelled_live_run_does_not_fail_on_late_stream_error(monkeypatch):
    from write_agent.services.agent_runtime_service import AgentRuntimeService

    class FailingAgent:
        def stream(self, input_payload, config=None, stream_mode=None):
            time.sleep(0.15)
            raise RuntimeError("late failure")

    service = AgentRuntimeService()
    user_id = f"cancel-error-{uuid4().hex}"
    document = _create_document(user_id=user_id)
    monkeypatch.setattr(service, "_build_deep_agent", lambda: FailingAgent())
    result = service.start_chat_run(
        user_id=user_id,
        document_id=int(document["id"]),
        content="开始",
        selection=None,
        base_version_id=document["current_version"]["id"],
    )

    service.mark_run_cancelled(user_id=user_id, run_id=int(result["run_id"]))
    list(service.stream_chat_run(user_id=user_id, run_id=int(result["run_id"])))

    events = service.list_events(
        user_id=user_id,
        run_id=int(result["run_id"]),
        from_seq=0,
    )
    event_types = [event.event_type for event in events]
    assert "run_cancelled" in event_types
    assert "run_failed" not in event_types


def _create_document(*, user_id: str) -> dict:
    client = TestClient(app)
    response = client.post(
        "/api/documents",
        headers={"X-Dev-User-Id": user_id},
        json={
            "title": "Chat document",
            "content_html": "<p>正文</p>",
            "content_text": "正文",
        },
    )
    assert response.status_code == 200
    return response.json()


def _wait_for_run_completed(service, *, user_id: str, run_id: int):
    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline:
        events = service.list_events(user_id=user_id, run_id=run_id, from_seq=0)
        if events and events[-1].event_type == "run_completed":
            return events
        time.sleep(0.05)
    raise AssertionError("expected run_completed event")
