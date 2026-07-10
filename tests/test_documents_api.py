from __future__ import annotations

import os
import sys
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from write_agent.core.database import engine
from write_agent.main import app


def setup_module() -> None:
    SQLModel.metadata.create_all(engine)


def test_create_document_creates_initial_version():
    client = TestClient(app)
    user_id = f"writer-a-{uuid4().hex}"

    response = client.post(
        "/api/documents",
        headers={"X-Dev-User-Id": user_id},
        json={
            "title": "视频脚本",
            "content_html": "<p>开头</p>",
            "content_text": "开头",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "视频脚本"
    assert payload["current_version"]["content_text"] == "开头"
    assert payload["current_version"]["source"] == "initial"


def test_document_list_is_user_scoped():
    client = TestClient(app)
    writer_a = f"writer-scope-a-{uuid4().hex}"
    writer_b = f"writer-scope-b-{uuid4().hex}"
    client.post(
        "/api/documents",
        headers={"X-Dev-User-Id": writer_a},
        json={"title": "A", "content_html": "<p>A</p>", "content_text": "A"},
    )

    response = client.get("/api/documents", headers={"X-Dev-User-Id": writer_b})

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_save_version_and_rollback():
    client = TestClient(app)
    user_id = f"writer-rollback-{uuid4().hex}"
    created = client.post(
        "/api/documents",
        headers={"X-Dev-User-Id": user_id},
        json={"title": "Draft", "content_html": "<p>v1</p>", "content_text": "v1"},
    ).json()
    document_id = created["id"]
    version_1 = created["current_version"]["id"]

    saved = client.post(
        f"/api/documents/{document_id}/versions",
        headers={"X-Dev-User-Id": user_id},
        json={
            "content_html": "<p>v2</p>",
            "content_text": "v2",
            "source": "manual_save",
            "reason": "manual save",
        },
    )
    assert saved.status_code == 200
    version_2 = saved.json()["id"]
    assert version_2 != version_1

    rolled_back = client.post(
        f"/api/documents/{document_id}/rollback",
        headers={"X-Dev-User-Id": user_id},
        json={"version_id": version_1},
    )

    assert rolled_back.status_code == 200
    assert rolled_back.json()["current_version"]["id"] == version_1


def test_create_version_rejects_parent_version_from_another_document():
    client = TestClient(app)
    user_id = f"writer-parent-{uuid4().hex}"
    first = client.post(
        "/api/documents",
        headers={"X-Dev-User-Id": user_id},
        json={"title": "First", "content_html": "<p>first</p>", "content_text": "first"},
    ).json()
    second = client.post(
        "/api/documents",
        headers={"X-Dev-User-Id": user_id},
        json={"title": "Second", "content_html": "<p>second</p>", "content_text": "second"},
    ).json()

    response = client.post(
        f"/api/documents/{first['id']}/versions",
        headers={"X-Dev-User-Id": user_id},
        json={
            "content_html": "<p>bad</p>",
            "content_text": "bad",
            "parent_version_id": second["current_version"]["id"],
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Parent version not found"
