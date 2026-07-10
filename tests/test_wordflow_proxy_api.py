from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi.testclient import TestClient

from write_agent.main import app


def test_wordflow_text_gen_uses_backend_openai_proxy(monkeypatch):
    from write_agent.services import wordflow_proxy_service

    captured: dict = {}

    def fake_generate(request):
        captured.update(request.model_dump())
        return "proxied result"

    monkeypatch.setattr(wordflow_proxy_service, "generate_text", fake_generate)

    client = TestClient(app)
    response = client.post(
        "/api/wordflow/text-gen",
        json={
            "provider": "openai",
            "request_id": "text-gen",
            "prompt": "Improve this sentence.",
            "temperature": 0.2,
            "model": "gpt-5.4",
            "stop_sequences": ["</output>"],
            "detail": "replace",
            "api_key": "client-key-should-not-return",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "command": "finishTextGen",
        "payload": {
            "requestID": "text-gen",
            "apiKey": "",
            "result": "proxied result",
            "prompt": "Improve this sentence.",
            "detail": "replace",
        },
    }
    assert captured["provider"] == "openai"
    assert captured["model"] == "gpt-5.4"
    assert captured["api_key"] == "client-key-should-not-return"


def test_wordflow_text_gen_reports_provider_errors(monkeypatch):
    from write_agent.services import wordflow_proxy_service

    def fake_generate(_request):
        raise wordflow_proxy_service.WordflowProxyError("upstream unavailable", status_code=502)

    monkeypatch.setattr(wordflow_proxy_service, "generate_text", fake_generate)

    client = TestClient(app)
    response = client.post(
        "/api/wordflow/text-gen",
        json={
            "provider": "openai",
            "request_id": "text-gen",
            "prompt": "Hello",
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "upstream unavailable"


def test_wordflow_records_proxy_preserves_status_headers_and_payload(monkeypatch):
    from write_agent.api import wordflow as wordflow_api

    captured: dict = {}

    class FakeResponse:
        status_code = 200
        content = b'[{"title":"Prompt"}]'
        headers = {"content-type": "application/json", "x-has-pagination": "true"}

    def fake_request(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse()

    monkeypatch.setattr(wordflow_api.requests, "request", fake_request)
    monkeypatch.setattr(
        wordflow_api,
        "settings",
        SimpleNamespace(
            wordflow_remote_endpoint="https://wordflow.example/records",
            openai_timeout_seconds=30,
        ),
    )

    client = TestClient(app)
    response = client.get("/api/wordflow/records", params={"tag": "writing", "mostPopular": "true"})

    assert response.status_code == 200
    assert response.json() == [{"title": "Prompt"}]
    assert response.headers["x-has-pagination"] == "true"
    assert captured["method"] == "GET"
    assert captured["url"] == "https://wordflow.example/records"
    assert captured["kwargs"]["params"] == {"tag": "writing", "mostPopular": "true"}
