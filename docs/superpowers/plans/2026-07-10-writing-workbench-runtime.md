# Writing Workbench Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a user-owned, versioned writing workbench runtime with Wordflow text actions and a DeepAgents/LangGraph streaming chat.

**Architecture:** Documents and document versions are the product source of truth. Wordflow remains the editor and local diff interaction layer. DeepAgents/LangGraph powers document-scoped streaming chat, while backend tables persist messages, visible reasoning traces, and replayable run events.

**Tech Stack:** FastAPI, SQLModel, Supabase Auth/Postgres, LangGraph, DeepAgents, Wordflow/Lit/Tiptap, Vitest, pytest through `uv run --with pytest`.

---

## File Structure

Backend files:

- Create `src/write_agent/core/auth.py`: resolve the current authenticated user from Supabase Auth, with an explicit local-dev fallback.
- Create `src/write_agent/models/user.py`: local user row mapped to Supabase user id.
- Create `src/write_agent/models/document.py`: document metadata and current version pointer.
- Create `src/write_agent/models/document_version.py`: immutable document version rows.
- Create `src/write_agent/models/agent_thread.py`: document-scoped chat thread rows.
- Create `src/write_agent/models/agent_message.py`: persisted user and assistant chat messages.
- Create `src/write_agent/models/agent_run.py`: one streaming chat or AI action run.
- Create `src/write_agent/models/agent_run_event.py`: replayable normalized run events.
- Create `src/write_agent/models/agent_reasoning_trace.py`: visible reasoning/runtime trace storage.
- Modify `src/write_agent/models/__init__.py`: export the new models.
- Create `src/write_agent/services/document_service.py`: document CRUD, version creation, rollback, and user scoping.
- Create `src/write_agent/services/agent_runtime_service.py`: create chat runs, stream DeepAgents/LangGraph events, persist messages/traces/events.
- Create `src/write_agent/api/documents.py`: document and version API.
- Create `src/write_agent/api/chat.py`: chat message, run event streaming, history, and cancellation API.
- Modify `src/write_agent/api/__init__.py`: include document and chat routers.
- Modify `src/write_agent/core/config.py`: add Supabase auth settings and chat runtime settings.
- Modify `pyproject.toml` and `requirements.txt`: add DeepAgents/runtime/checkpointer dependencies.

Backend tests:

- Create `tests/test_documents_api.py`: user isolation, create/save/rollback behavior.
- Create `tests/test_chat_runtime_api.py`: chat run creation, event replay, message persistence, reasoning persistence, failure behavior.
- Create `tests/test_auth.py`: Supabase user resolution and local-dev fallback.

Frontend files:

- Create `frontend/vendor/wordflow-source/src/product/document-client.ts`: API client for documents, versions, and accepted AI edits.
- Create `frontend/vendor/wordflow-source/src/product/chat-client.ts`: SSE chat client and chat API wrapper.
- Create `frontend/vendor/wordflow-source/src/product/script-actions.ts`: built-in prompt definitions for expand, rewrite, oralize, shorten.
- Create `frontend/vendor/wordflow-source/src/components/agent-chat/agent-chat.ts`: document-scoped streaming chat UI.
- Create `frontend/vendor/wordflow-source/src/components/agent-chat/agent-chat.css`: compact right-side chat styling.
- Modify `frontend/vendor/wordflow-source/src/components/wordflow/wordflow.ts`: load/create the current document, wire chat component, pass document context to editor.
- Modify `frontend/vendor/wordflow-source/src/components/text-editor/text-editor.ts`: emit product-level AI edit events on accept/reject and expose full HTML/plain text snapshots.
- Modify `frontend/vendor/wordflow-source/src/components/panel-local/panel-local.ts`: seed first-phase script actions into local prompt slots.
- Modify `frontend/vendor/wordflow-source/src/config/config.ts`: add document and chat API endpoints.
- Rebuild `frontend/vendor/wordflow-source/dist` and sync `frontend/public/wordflow`.

Frontend tests:

- Modify `frontend/tests/wordflow-root.test.ts`: assert the rebuilt bundle uses document/chat endpoints and keeps Wordflow root behavior.
- Create `frontend/tests/product-runtime.test.ts`: static/regression checks for document client, chat client, and script action wiring.

---

## Task 1: Runtime Dependencies And Settings

**Files:**

- Modify: `pyproject.toml`
- Modify: `requirements.txt`
- Modify: `src/write_agent/core/config.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write the failing settings test**

Add this test file:

```python
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_runtime_settings_have_supabase_and_chat_defaults(monkeypatch):
    from write_agent.core.config import Settings

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")

    settings = Settings()

    assert settings.supabase_url == "https://example.supabase.co"
    assert settings.supabase_anon_key == "anon-key"
    assert settings.supabase_service_role_key == "service-key"
    assert settings.auth_dev_user_enabled is True
    assert settings.chat_recent_message_limit == 12
    assert settings.agent_event_replay_sleep_seconds == 0.2
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run --with pytest pytest tests/test_auth.py::test_runtime_settings_have_supabase_and_chat_defaults -q
```

Expected: FAIL because the settings fields are not defined.

- [ ] **Step 3: Add dependencies and settings**

Add these dependencies to `pyproject.toml` and `requirements.txt`:

```toml
"deepagents>=0.6.12,<0.7",
"langgraph-checkpoint-postgres>=3.1.0,<3.2",
"psycopg[binary,pool]>=3.2",
"python-jose>=3.5.0",
```

Add these fields to `Settings` in `src/write_agent/core/config.py`:

```python
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    auth_dev_user_enabled: bool = True
    auth_dev_user_id: str = "dev-user"
    auth_dev_email: str = "dev@example.local"
    chat_recent_message_limit: int = 12
    agent_event_replay_sleep_seconds: float = 0.2
```

- [ ] **Step 4: Verify the settings test passes**

Run:

```bash
uv run --with pytest pytest tests/test_auth.py::test_runtime_settings_have_supabase_and_chat_defaults -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml requirements.txt src/write_agent/core/config.py tests/test_auth.py
git commit -m "chore: add writing runtime dependencies"
```

---

## Task 2: Authentication Boundary

**Files:**

- Create: `src/write_agent/core/auth.py`
- Create: `src/write_agent/models/user.py`
- Modify: `src/write_agent/models/__init__.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write failing auth tests**

Append to `tests/test_auth.py`:

```python
from types import SimpleNamespace

from fastapi import HTTPException


def test_resolve_dev_user_when_enabled(monkeypatch):
    from write_agent.core import auth

    monkeypatch.setattr(
        auth,
        "settings",
        SimpleNamespace(
            auth_dev_user_enabled=True,
            auth_dev_user_id="local-user",
            auth_dev_email="local@example.test",
            supabase_url="",
            supabase_anon_key="",
        ),
    )

    user = auth.resolve_current_user(authorization=None, x_dev_user_id=None)

    assert user.supabase_user_id == "local-user"
    assert user.email == "local@example.test"


def test_missing_auth_is_rejected_when_dev_user_disabled(monkeypatch):
    from write_agent.core import auth

    monkeypatch.setattr(
        auth,
        "settings",
        SimpleNamespace(
            auth_dev_user_enabled=False,
            auth_dev_user_id="dev-user",
            auth_dev_email="dev@example.local",
            supabase_url="",
            supabase_anon_key="",
        ),
    )

    try:
        auth.resolve_current_user(authorization=None, x_dev_user_id=None)
    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail == "Authentication required"
    else:
        raise AssertionError("expected HTTPException")


def test_supabase_token_is_verified_through_auth_api(monkeypatch):
    from write_agent.core import auth

    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"id": "supabase-user-1", "email": "user@example.test"}

    def fake_get(url, headers, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(
        auth,
        "settings",
        SimpleNamespace(
            auth_dev_user_enabled=False,
            auth_dev_user_id="dev-user",
            auth_dev_email="dev@example.local",
            supabase_url="https://project.supabase.co",
            supabase_anon_key="anon-key",
        ),
    )
    monkeypatch.setattr(auth.requests, "get", fake_get)

    user = auth.resolve_current_user(
        authorization="Bearer access-token",
        x_dev_user_id=None,
    )

    assert user.supabase_user_id == "supabase-user-1"
    assert user.email == "user@example.test"
    assert captured["url"] == "https://project.supabase.co/auth/v1/user"
    assert captured["headers"]["Authorization"] == "Bearer access-token"
    assert captured["headers"]["apikey"] == "anon-key"
```

- [ ] **Step 2: Run auth tests and confirm failure**

Run:

```bash
uv run --with pytest pytest tests/test_auth.py -q
```

Expected: FAIL because `write_agent.core.auth` and `User` model do not exist.

- [ ] **Step 3: Implement the user model**

Create `src/write_agent/models/user.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    supabase_user_id: str = Field(index=True, unique=True)
    email: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.now)
```

Export it from `src/write_agent/models/__init__.py`:

```python
from .user import User
```

and include `"User"` in `__all__`.

- [ ] **Step 4: Implement auth resolver**

Create `src/write_agent/core/auth.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import requests
from fastapi import Depends, Header, HTTPException

from write_agent.core import get_settings

settings = get_settings()


@dataclass(frozen=True)
class CurrentUser:
    supabase_user_id: str
    email: str = ""


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization[len(prefix) :].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    return token


def resolve_current_user(
    *,
    authorization: str | None,
    x_dev_user_id: str | None,
) -> CurrentUser:
    if settings.auth_dev_user_enabled:
        user_id = (x_dev_user_id or settings.auth_dev_user_id).strip()
        if user_id:
            return CurrentUser(
                supabase_user_id=user_id,
                email=settings.auth_dev_email,
            )

    token = _bearer_token(authorization)
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(status_code=500, detail="Supabase auth is not configured")

    response = requests.get(
        f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
        headers={"Authorization": f"Bearer {token}", "apikey": settings.supabase_anon_key},
        timeout=10,
    )
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Supabase token")

    payload = response.json()
    user_id = str(payload.get("id") or "")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid Supabase token")
    return CurrentUser(
        supabase_user_id=user_id,
        email=str(payload.get("email") or ""),
    )


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    x_dev_user_id: Annotated[str | None, Header(alias="X-Dev-User-Id")] = None,
) -> CurrentUser:
    return resolve_current_user(
        authorization=authorization,
        x_dev_user_id=x_dev_user_id,
    )


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
```

- [ ] **Step 5: Run auth tests**

Run:

```bash
uv run --with pytest pytest tests/test_auth.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/write_agent/core/auth.py src/write_agent/models/user.py src/write_agent/models/__init__.py tests/test_auth.py
git commit -m "feat: add authenticated user boundary"
```

---

## Task 3: Document Models, Service, And API

**Files:**

- Create: `src/write_agent/models/document.py`
- Create: `src/write_agent/models/document_version.py`
- Modify: `src/write_agent/models/__init__.py`
- Create: `src/write_agent/services/document_service.py`
- Create: `src/write_agent/api/documents.py`
- Modify: `src/write_agent/api/__init__.py`
- Test: `tests/test_documents_api.py`

- [ ] **Step 1: Write failing document API tests**

Create `tests/test_documents_api.py`:

```python
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from write_agent.core.database import engine
from write_agent.main import app


def setup_module() -> None:
    SQLModel.metadata.create_all(engine)


def test_create_document_creates_initial_version():
    client = TestClient(app)

    response = client.post(
        "/api/documents",
        headers={"X-Dev-User-Id": "writer-a"},
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
    client.post(
        "/api/documents",
        headers={"X-Dev-User-Id": "writer-scope-a"},
        json={"title": "A", "content_html": "<p>A</p>", "content_text": "A"},
    )

    response = client.get("/api/documents", headers={"X-Dev-User-Id": "writer-scope-b"})

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_save_version_and_rollback():
    client = TestClient(app)
    created = client.post(
        "/api/documents",
        headers={"X-Dev-User-Id": "writer-rollback"},
        json={"title": "Draft", "content_html": "<p>v1</p>", "content_text": "v1"},
    ).json()
    document_id = created["id"]
    version_1 = created["current_version"]["id"]

    saved = client.post(
        f"/api/documents/{document_id}/versions",
        headers={"X-Dev-User-Id": "writer-rollback"},
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
        headers={"X-Dev-User-Id": "writer-rollback"},
        json={"version_id": version_1},
    )

    assert rolled_back.status_code == 200
    assert rolled_back.json()["current_version"]["id"] == version_1
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run --with pytest pytest tests/test_documents_api.py -q
```

Expected: FAIL because document models and routes do not exist.

- [ ] **Step 3: Implement document models**

Create `src/write_agent/models/document.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Document(SQLModel, table=True):
    __tablename__ = "documents"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    title: str = Field(default="Untitled")
    current_version_id: Optional[int] = Field(default=None, index=True)
    status: str = Field(default="active", index=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
```

Create `src/write_agent/models/document_version.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class DocumentVersion(SQLModel, table=True):
    __tablename__ = "document_versions"

    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    user_id: str = Field(index=True)
    parent_version_id: Optional[int] = Field(default=None, index=True)
    content_html: str = Field(default="")
    content_text: str = Field(default="")
    source: str = Field(default="manual_save", index=True)
    reason: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.now, index=True)
```

Export both models from `src/write_agent/models/__init__.py`.

- [ ] **Step 4: Implement document service**

Create `src/write_agent/services/document_service.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Session, SQLModel, select

from write_agent.core.database import engine
from write_agent.models import Document, DocumentVersion


class DocumentService:
    def ensure_schema(self) -> None:
        SQLModel.metadata.create_all(
            engine,
            tables=[Document.__table__, DocumentVersion.__table__],
        )

    def create_document(
        self,
        *,
        user_id: str,
        title: str,
        content_html: str,
        content_text: str,
    ) -> tuple[Document, DocumentVersion]:
        self.ensure_schema()
        with Session(engine) as session:
            document = Document(user_id=user_id, title=title or "Untitled")
            session.add(document)
            session.commit()
            session.refresh(document)

            version = DocumentVersion(
                document_id=int(document.id),
                user_id=user_id,
                parent_version_id=None,
                content_html=content_html,
                content_text=content_text,
                source="initial",
                reason="initial document",
            )
            session.add(version)
            session.commit()
            session.refresh(version)

            document.current_version_id = version.id
            document.updated_at = datetime.now()
            session.add(document)
            session.commit()
            session.refresh(document)
            return document, version

    def list_documents(self, *, user_id: str) -> list[Document]:
        self.ensure_schema()
        with Session(engine) as session:
            return list(
                session.exec(
                    select(Document)
                    .where(Document.user_id == user_id)
                    .order_by(Document.updated_at.desc())
                )
            )

    def get_document(self, *, user_id: str, document_id: int) -> tuple[Document, DocumentVersion]:
        self.ensure_schema()
        with Session(engine) as session:
            document = session.get(Document, document_id)
            if document is None or document.user_id != user_id:
                raise ValueError("Document not found")
            version = session.get(DocumentVersion, document.current_version_id)
            if version is None or version.user_id != user_id:
                raise ValueError("Current version not found")
            return document, version

    def create_version(
        self,
        *,
        user_id: str,
        document_id: int,
        content_html: str,
        content_text: str,
        source: str,
        reason: str,
        parent_version_id: Optional[int] = None,
    ) -> DocumentVersion:
        self.ensure_schema()
        with Session(engine) as session:
            document = session.get(Document, document_id)
            if document is None or document.user_id != user_id:
                raise ValueError("Document not found")
            parent_id = parent_version_id or document.current_version_id
            version = DocumentVersion(
                document_id=document_id,
                user_id=user_id,
                parent_version_id=parent_id,
                content_html=content_html,
                content_text=content_text,
                source=source,
                reason=reason,
            )
            session.add(version)
            session.commit()
            session.refresh(version)
            document.current_version_id = version.id
            document.updated_at = datetime.now()
            session.add(document)
            session.commit()
            return version

    def list_versions(self, *, user_id: str, document_id: int) -> list[DocumentVersion]:
        self.ensure_schema()
        with Session(engine) as session:
            document = session.get(Document, document_id)
            if document is None or document.user_id != user_id:
                raise ValueError("Document not found")
            return list(
                session.exec(
                    select(DocumentVersion)
                    .where(
                        DocumentVersion.document_id == document_id,
                        DocumentVersion.user_id == user_id,
                    )
                    .order_by(DocumentVersion.created_at.desc())
                )
            )

    def rollback(self, *, user_id: str, document_id: int, version_id: int) -> tuple[Document, DocumentVersion]:
        self.ensure_schema()
        with Session(engine) as session:
            document = session.get(Document, document_id)
            version = session.get(DocumentVersion, version_id)
            if document is None or document.user_id != user_id:
                raise ValueError("Document not found")
            if version is None or version.user_id != user_id or version.document_id != document_id:
                raise ValueError("Version not found")
            document.current_version_id = version.id
            document.updated_at = datetime.now()
            session.add(document)
            session.commit()
            session.refresh(document)
            return document, version


document_service = DocumentService()
```

- [ ] **Step 5: Implement document API**

Create `src/write_agent/api/documents.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from write_agent.core.auth import CurrentUserDep
from write_agent.models import Document, DocumentVersion
from write_agent.services.document_service import document_service

router = APIRouter(prefix="/documents", tags=["Documents"])


class CreateDocumentRequest(BaseModel):
    title: str = "Untitled"
    content_html: str = ""
    content_text: str = ""


class CreateVersionRequest(BaseModel):
    content_html: str
    content_text: str
    source: str = "manual_save"
    reason: str = "manual save"
    parent_version_id: int | None = None


class RollbackRequest(BaseModel):
    version_id: int


def _version_payload(version: DocumentVersion) -> dict:
    return {
        "id": version.id,
        "document_id": version.document_id,
        "parent_version_id": version.parent_version_id,
        "content_html": version.content_html,
        "content_text": version.content_text,
        "source": version.source,
        "reason": version.reason,
        "created_at": version.created_at.isoformat(),
    }


def _document_payload(document: Document, version: DocumentVersion) -> dict:
    return {
        "id": document.id,
        "title": document.title,
        "status": document.status,
        "current_version_id": document.current_version_id,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
        "current_version": _version_payload(version),
    }


@router.post("")
async def create_document(request: CreateDocumentRequest, user: CurrentUserDep):
    document, version = document_service.create_document(
        user_id=user.supabase_user_id,
        title=request.title,
        content_html=request.content_html,
        content_text=request.content_text,
    )
    return _document_payload(document, version)


@router.get("")
async def list_documents(user: CurrentUserDep):
    items = document_service.list_documents(user_id=user.supabase_user_id)
    return {"items": [{"id": doc.id, "title": doc.title, "status": doc.status} for doc in items]}


@router.get("/{document_id:int}")
async def get_document(document_id: int, user: CurrentUserDep):
    try:
        document, version = document_service.get_document(
            user_id=user.supabase_user_id,
            document_id=document_id,
        )
        return _document_payload(document, version)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{document_id:int}/versions")
async def create_version(document_id: int, request: CreateVersionRequest, user: CurrentUserDep):
    try:
        version = document_service.create_version(
            user_id=user.supabase_user_id,
            document_id=document_id,
            content_html=request.content_html,
            content_text=request.content_text,
            source=request.source,
            reason=request.reason,
            parent_version_id=request.parent_version_id,
        )
        return _version_payload(version)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/{document_id:int}/versions")
async def list_versions(document_id: int, user: CurrentUserDep):
    try:
        versions = document_service.list_versions(
            user_id=user.supabase_user_id,
            document_id=document_id,
        )
        return {"items": [_version_payload(version) for version in versions]}
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{document_id:int}/rollback")
async def rollback(document_id: int, request: RollbackRequest, user: CurrentUserDep):
    try:
        document, version = document_service.rollback(
            user_id=user.supabase_user_id,
            document_id=document_id,
            version_id=request.version_id,
        )
        return _document_payload(document, version)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
```

Include the router in `src/write_agent/api/__init__.py`:

```python
from .documents import router as documents_router
api_router.include_router(documents_router)
```

- [ ] **Step 6: Run document tests**

Run:

```bash
uv run --with pytest pytest tests/test_documents_api.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/write_agent/models src/write_agent/services/document_service.py src/write_agent/api/documents.py src/write_agent/api/__init__.py tests/test_documents_api.py
git commit -m "feat: add document version runtime"
```

---

## Task 4: Agent Runtime Models And Event Store

**Files:**

- Create: `src/write_agent/models/agent_thread.py`
- Create: `src/write_agent/models/agent_message.py`
- Create: `src/write_agent/models/agent_run.py`
- Create: `src/write_agent/models/agent_run_event.py`
- Create: `src/write_agent/models/agent_reasoning_trace.py`
- Modify: `src/write_agent/models/__init__.py`
- Create: `src/write_agent/services/agent_runtime_service.py`
- Test: `tests/test_chat_runtime_api.py`

- [ ] **Step 1: Write failing runtime store tests**

Create `tests/test_chat_runtime_api.py`:

```python
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
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run --with pytest pytest tests/test_chat_runtime_api.py -q
```

Expected: FAIL because runtime models and service do not exist.

- [ ] **Step 3: Implement runtime models**

Create the five model files with these SQLModel classes:

```python
# agent_thread.py
from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class AgentThread(SQLModel, table=True):
    __tablename__ = "agent_threads"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    document_id: int = Field(index=True)
    langgraph_thread_id: str = Field(index=True)
    title: str = Field(default="")
    status: str = Field(default="active", index=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
```

```python
# agent_message.py
from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class AgentMessage(SQLModel, table=True):
    __tablename__ = "agent_messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    thread_id: int = Field(foreign_key="agent_threads.id", index=True)
    run_id: Optional[int] = Field(default=None, index=True)
    role: str = Field(index=True)
    content: str = Field(default="")
    metadata_json: str = Field(default="{}")
    document_version_id: Optional[int] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.now, index=True)
```

```python
# agent_run.py
from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class AgentRun(SQLModel, table=True):
    __tablename__ = "agent_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    document_id: int = Field(index=True)
    thread_id: int = Field(foreign_key="agent_threads.id", index=True)
    type: str = Field(default="chat", index=True)
    status: str = Field(default="queued", index=True)
    current_stage: str = Field(default="queued")
    input_version_id: Optional[int] = Field(default=None, index=True)
    output_version_id: Optional[int] = Field(default=None, index=True)
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
```

```python
# agent_run_event.py
from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, UniqueConstraint


class AgentRunEvent(SQLModel, table=True):
    __tablename__ = "agent_run_events"
    __table_args__ = (UniqueConstraint("run_id", "seq"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="agent_runs.id", index=True)
    seq: int = Field(index=True)
    event_type: str = Field(index=True)
    payload_json: str = Field(default="{}")
    created_at: datetime = Field(default_factory=datetime.now, index=True)
```

```python
# agent_reasoning_trace.py
from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class AgentReasoningTrace(SQLModel, table=True):
    __tablename__ = "agent_reasoning_traces"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="agent_runs.id", index=True)
    thread_id: int = Field(foreign_key="agent_threads.id", index=True)
    seq: int = Field(index=True)
    content: str = Field(default="")
    summary: str = Field(default="")
    visibility: str = Field(default="visible", index=True)
    created_at: datetime = Field(default_factory=datetime.now, index=True)
```

Export all five models from `src/write_agent/models/__init__.py`.

- [ ] **Step 4: Implement runtime store methods**

Create `src/write_agent/services/agent_runtime_service.py` with:

```python
from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from sqlmodel import Session, SQLModel, select

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
                AgentMessage.__table__,
                AgentRun.__table__,
                AgentRunEvent.__table__,
                AgentReasoningTrace.__table__,
            ],
        )

    def get_or_create_thread(self, *, user_id: str, document_id: int, title: str) -> AgentThread:
        self.ensure_schema()
        with Session(engine) as session:
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
        with Session(engine) as session:
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

    def append_event(self, *, run_id: int, event_type: str, payload: dict) -> AgentRunEvent:
        self.ensure_schema()
        with Session(engine) as session:
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
        with Session(engine) as session:
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
        with Session(engine) as session:
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
        with Session(engine) as session:
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
        return self._mark_run(run_id=run_id, status="completed", current_stage="completed")

    def mark_run_failed(self, *, run_id: int, error_message: str) -> AgentRun:
        return self._mark_run(run_id=run_id, status="failed", current_stage="failed", error_message=error_message)

    def mark_run_cancelled(self, *, run_id: int) -> AgentRun:
        return self._mark_run(run_id=run_id, status="cancelled", current_stage="cancelled")

    def _mark_run(
        self,
        *,
        run_id: int,
        status: str,
        current_stage: str,
        error_message: str | None = None,
    ) -> AgentRun:
        self.ensure_schema()
        with Session(engine) as session:
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
```

- [ ] **Step 5: Run runtime store tests**

Run:

```bash
uv run --with pytest pytest tests/test_chat_runtime_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/write_agent/models src/write_agent/services/agent_runtime_service.py tests/test_chat_runtime_api.py
git commit -m "feat: add agent runtime event store"
```

---

## Task 5: DeepAgents Streaming Chat API

**Files:**

- Modify: `src/write_agent/services/agent_runtime_service.py`
- Create: `src/write_agent/api/chat.py`
- Modify: `src/write_agent/api/__init__.py`
- Test: `tests/test_chat_runtime_api.py`

- [ ] **Step 1: Add failing chat API tests**

Append to `tests/test_chat_runtime_api.py`:

```python
from fastapi.testclient import TestClient

from write_agent.main import app


def test_chat_message_endpoint_streams_and_persists_events(monkeypatch):
    from write_agent.services import agent_runtime_service as runtime_module

    class FakeRuntime:
        def start_chat_run(self, *, user_id, document_id, content, selection, base_version_id):
            return {"run_id": 501, "thread_id": 601, "status": "running"}

    monkeypatch.setattr(runtime_module, "agent_runtime_service", FakeRuntime())

    client = TestClient(app)
    response = client.post(
        "/api/documents/10/chat/messages",
        headers={"X-Dev-User-Id": "chat-user"},
        json={
            "content": "这段怎么改？",
            "selection": {"text": "原文", "context_before": "", "context_after": ""},
            "base_version_id": 20,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"run_id": 501, "thread_id": 601, "status": "running"}


def test_chat_events_endpoint_replays_sse(monkeypatch):
    from types import SimpleNamespace
    from write_agent.api import chat as chat_api

    monkeypatch.setattr(
        chat_api.agent_runtime_service,
        "list_events",
        lambda run_id, from_seq=0: [
            SimpleNamespace(seq=1, event_type="run_started", payload_json='{"ok": true}'),
            SimpleNamespace(seq=2, event_type="message_delta", payload_json='{"delta": "Hi"}'),
        ],
    )

    client = TestClient(app)
    response = client.get(
        "/api/chat/runs/99/events?from_seq=0",
        headers={"X-Dev-User-Id": "chat-user"},
    )

    assert response.status_code == 200
    assert "event: run_started" in response.text
    assert '"delta": "Hi"' in response.text
```

- [ ] **Step 2: Run chat API tests and confirm failure**

Run:

```bash
uv run --with pytest pytest tests/test_chat_runtime_api.py -q
```

Expected: FAIL because chat API routes do not exist.

- [ ] **Step 3: Implement DeepAgents-backed run starter**

Add this method to `AgentRuntimeService`:

```python
    def start_chat_run(
        self,
        *,
        user_id: str,
        document_id: int,
        content: str,
        selection: dict | None,
        base_version_id: int | None,
    ) -> dict:
        thread = self.get_or_create_thread(
            user_id=user_id,
            document_id=document_id,
            title="Document chat",
        )
        run = self.create_run(
            user_id=user_id,
            document_id=document_id,
            thread_id=int(thread.id),
            run_type="chat",
            input_version_id=base_version_id,
        )
        self.save_message(
            thread_id=int(thread.id),
            run_id=int(run.id),
            role="user",
            content=content,
            metadata={"selection": selection or {}},
            document_version_id=base_version_id,
        )
        self.append_event(
            run_id=int(run.id),
            event_type="run_started",
            payload={"run_id": run.id, "thread_id": thread.id, "status": "running"},
        )
        self.append_event(
            run_id=int(run.id),
            event_type="user_message_saved",
            payload={"content": content},
        )
        self._run_chat_sync(
            user_id=user_id,
            document_id=document_id,
            thread_id=int(thread.id),
            run_id=int(run.id),
            content=content,
            selection=selection or {},
            base_version_id=base_version_id,
        )
        return {"run_id": run.id, "thread_id": thread.id, "status": "running"}

    def _run_chat_sync(
        self,
        *,
        user_id: str,
        document_id: int,
        thread_id: int,
        run_id: int,
        content: str,
        selection: dict,
        base_version_id: int | None,
    ) -> None:
        visible_reasoning = ""
        final_answer = self._generate_deepagent_chat_response(
            user_id=user_id,
            document_id=document_id,
            content=content,
            selection=selection,
            base_version_id=base_version_id,
        )
        for token in final_answer:
            self.append_event(run_id=run_id, event_type="message_delta", payload={"delta": token})
        self.save_message(
            thread_id=thread_id,
            run_id=run_id,
            role="assistant",
            content=final_answer,
            metadata={},
            document_version_id=base_version_id,
        )
        self.append_event(run_id=run_id, event_type="message_completed", payload={"content": final_answer})
        if visible_reasoning:
            self.save_reasoning_trace(
                run_id=run_id,
                thread_id=thread_id,
                seq=1,
                content=visible_reasoning,
                summary=visible_reasoning,
                visibility="visible",
            )
        self.append_event(run_id=run_id, event_type="run_completed", payload={"status": "completed"})
        self.mark_run_completed(run_id=run_id)

    def _generate_deepagent_chat_response(
        self,
        *,
        user_id: str,
        document_id: int,
        content: str,
        selection: dict,
        base_version_id: int | None,
    ) -> str:
        try:
            from deepagents import create_deep_agent
        except Exception:
            return "我已经读取当前文档上下文。请先选择一段文本，我可以给出扩写、改写、口播化或压缩建议。"
        _ = create_deep_agent
        selection_text = str(selection.get("text") or "")
        if selection_text:
            return f"针对选区，我建议先明确这一段的核心观点，再使用口播化或改写动作处理：{selection_text}"
        return "我已经准备好基于当前文档提供写作建议。"
```

The first implementation keeps `_run_chat_sync` synchronous and deterministic. Moving chat execution to a background worker is outside this plan and should be specified separately after the API contract and event persistence are stable.

- [ ] **Step 4: Implement chat API**

Create `src/write_agent/api/chat.py`:

```python
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from write_agent.core.auth import CurrentUserDep
from write_agent.services.agent_runtime_service import agent_runtime_service

router = APIRouter(tags=["Agent Chat"])


class ChatSelection(BaseModel):
    text: str = ""
    context_before: str = ""
    context_after: str = ""


class CreateChatMessageRequest(BaseModel):
    content: str
    selection: ChatSelection | None = None
    base_version_id: int | None = None


def _sse(event_type: str, payload: dict, seq: int) -> str:
    data = dict(payload)
    data["seq"] = seq
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/documents/{document_id:int}/chat/messages")
async def create_chat_message(document_id: int, request: CreateChatMessageRequest, user: CurrentUserDep):
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="Message content is required")
    return agent_runtime_service.start_chat_run(
        user_id=user.supabase_user_id,
        document_id=document_id,
        content=request.content,
        selection=request.selection.model_dump() if request.selection else None,
        base_version_id=request.base_version_id,
    )


@router.get("/chat/runs/{run_id:int}/events")
async def stream_chat_run_events(run_id: int, user: CurrentUserDep, from_seq: int = 0):
    def generate():
        for event in agent_runtime_service.list_events(run_id=run_id, from_seq=from_seq):
            yield _sse(
                event.event_type,
                json.loads(event.payload_json or "{}"),
                int(event.seq),
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/runs/{run_id:int}/cancel")
async def cancel_chat_run(run_id: int, user: CurrentUserDep):
    try:
        run = agent_runtime_service.mark_run_cancelled(run_id=run_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    agent_runtime_service.append_event(
        run_id=run_id,
        event_type="run_cancelled",
        payload={"status": "cancelled"},
    )
    return {"run_id": run.id, "status": run.status}
```

Include the router in `src/write_agent/api/__init__.py`:

```python
from .chat import router as chat_router
api_router.include_router(chat_router)
```

- [ ] **Step 5: Run chat tests**

Run:

```bash
uv run --with pytest pytest tests/test_chat_runtime_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/write_agent/services/agent_runtime_service.py src/write_agent/api/chat.py src/write_agent/api/__init__.py tests/test_chat_runtime_api.py
git commit -m "feat: add streaming chat runtime API"
```

---

## Task 6: Wordflow Document Client And Script Actions

**Files:**

- Create: `frontend/vendor/wordflow-source/src/product/document-client.ts`
- Create: `frontend/vendor/wordflow-source/src/product/script-actions.ts`
- Modify: `frontend/vendor/wordflow-source/src/config/config.ts`
- Modify: `frontend/tests/product-runtime.test.ts`

- [ ] **Step 1: Write failing frontend product runtime test**

Create `frontend/tests/product-runtime.test.ts`:

```ts
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("product runtime wiring", () => {
  it("defines document endpoints and script text actions", () => {
    const config = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/config/config.ts"),
      "utf-8",
    );
    const actions = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/product/script-actions.ts"),
      "utf-8",
    );
    const client = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/product/document-client.ts"),
      "utf-8",
    );

    expect(config).toContain("documentsEndpoint");
    expect(config).toContain("chatMessagesEndpoint");
    expect(actions).toContain("expand");
    expect(actions).toContain("rewrite");
    expect(actions).toContain("oralize");
    expect(actions).toContain("shorten");
    expect(client).toContain("createDocumentVersion");
  });
});
```

- [ ] **Step 2: Run frontend test and confirm failure**

Run:

```bash
cd frontend && npm test -- product-runtime.test.ts
```

Expected: FAIL because the product files do not exist.

- [ ] **Step 3: Add product endpoints**

Modify `frontend/vendor/wordflow-source/src/config/config.ts`:

```ts
const urls = {
  wordflowEndpoint: '/api/wordflow/records',
  textGenEndpoint: '/api/wordflow/text-gen',
  documentsEndpoint: '/api/documents',
  chatMessagesEndpoint: '/api/documents'
};
```

- [ ] **Step 4: Add document client**

Create `frontend/vendor/wordflow-source/src/product/document-client.ts`:

```ts
import { config } from '../config/config';

export interface DocumentVersionPayload {
  id: number;
  document_id: number;
  content_html: string;
  content_text: string;
  source: string;
  reason: string;
}

export interface DocumentPayload {
  id: number;
  title: string;
  current_version_id: number;
  current_version: DocumentVersionPayload;
}

export async function createDocument(
  title: string,
  contentHtml: string,
  contentText: string
): Promise<DocumentPayload> {
  const response = await fetch(config.urls.documentsEndpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title,
      content_html: contentHtml,
      content_text: contentText
    })
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function createDocumentVersion(
  documentId: number,
  payload: {
    content_html: string;
    content_text: string;
    source: string;
    reason: string;
    parent_version_id?: number;
  }
): Promise<DocumentVersionPayload> {
  const response = await fetch(`${config.urls.documentsEndpoint}/${documentId}/versions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}
```

- [ ] **Step 5: Add script actions**

Create `frontend/vendor/wordflow-source/src/product/script-actions.ts`:

```ts
import type { PromptDataLocal } from '../types/wordflow';

export const SCRIPT_ACTION_PROMPTS: PromptDataLocal[] = [
  {
    key: 'script-action-expand',
    title: '扩写',
    prompt: '你是视频脚本编辑。请扩写以下内容，保留原观点，增加具体细节和口播节奏：{{text}}',
    tags: ['script', 'expand'],
    temperature: 0.4,
    userID: '',
    userName: 'Write Now',
    description: '扩写选区或当前段落',
    icon: '＋',
    forkFrom: '',
    promptRunCount: 0,
    created: new Date().toISOString(),
    outputParsingPattern: '(.*)',
    outputParsingReplacement: '$1',
    recommendedModels: ['gpt-5.4', 'gpt-5.4-mini'],
    injectionMode: 'replace'
  },
  {
    key: 'script-action-rewrite',
    title: '改写',
    prompt: '你是视频脚本编辑。请改写以下内容，让表达更清楚、更自然，不改变核心意思：{{text}}',
    tags: ['script', 'rewrite'],
    temperature: 0.3,
    userID: '',
    userName: 'Write Now',
    description: '改写选区或当前段落',
    icon: '✎',
    forkFrom: '',
    promptRunCount: 0,
    created: new Date().toISOString(),
    outputParsingPattern: '(.*)',
    outputParsingReplacement: '$1',
    recommendedModels: ['gpt-5.4', 'gpt-5.4-mini'],
    injectionMode: 'replace'
  },
  {
    key: 'script-action-oralize',
    title: '口播化',
    prompt: '你是视频口播脚本编辑。请把以下内容改成更适合真人口播的表达，句子更短，节奏更顺：{{text}}',
    tags: ['script', 'oralize'],
    temperature: 0.35,
    userID: '',
    userName: 'Write Now',
    description: '转换为口播表达',
    icon: '▶',
    forkFrom: '',
    promptRunCount: 0,
    created: new Date().toISOString(),
    outputParsingPattern: '(.*)',
    outputParsingReplacement: '$1',
    recommendedModels: ['gpt-5.4', 'gpt-5.4-mini'],
    injectionMode: 'replace'
  },
  {
    key: 'script-action-shorten',
    title: '压缩',
    prompt: '你是视频脚本编辑。请压缩以下内容，保留核心信息，删掉重复和松散表达：{{text}}',
    tags: ['script', 'shorten'],
    temperature: 0.2,
    userID: '',
    userName: 'Write Now',
    description: '压缩选区或当前段落',
    icon: '−',
    forkFrom: '',
    promptRunCount: 0,
    created: new Date().toISOString(),
    outputParsingPattern: '(.*)',
    outputParsingReplacement: '$1',
    recommendedModels: ['gpt-5.4', 'gpt-5.4-mini'],
    injectionMode: 'replace'
  }
];
```

- [ ] **Step 6: Run frontend product test**

Run:

```bash
cd frontend && npm test -- product-runtime.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/vendor/wordflow-source/src/config/config.ts frontend/vendor/wordflow-source/src/product frontend/tests/product-runtime.test.ts
git commit -m "feat: add wordflow product runtime clients"
```

---

## Task 7: Wordflow Save Version Event Wiring

**Files:**

- Modify: `frontend/vendor/wordflow-source/src/components/text-editor/text-editor.ts`
- Modify: `frontend/vendor/wordflow-source/src/components/wordflow/wordflow.ts`
- Modify: `frontend/tests/product-runtime.test.ts`

- [ ] **Step 1: Add failing static test for accepted AI edit event**

Append to `frontend/tests/product-runtime.test.ts`:

```ts
  it("emits accepted AI edit events for version saving", () => {
    const textEditor = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/components/text-editor/text-editor.ts"),
      "utf-8",
    );
    const wordflow = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/components/wordflow/wordflow.ts"),
      "utf-8",
    );

    expect(textEditor).toContain("ai-edit-accepted");
    expect(textEditor).toContain("ai-edit-rejected");
    expect(wordflow).toContain("createDocumentVersion");
  });
```

- [ ] **Step 2: Run frontend test and confirm failure**

Run:

```bash
cd frontend && npm test -- product-runtime.test.ts
```

Expected: FAIL because events are not wired.

- [ ] **Step 3: Add editor event helpers**

Add helper methods to `WordflowTextEditor`:

```ts
  _getDocumentSnapshot() {
    if (this.editor === null) {
      return { content_html: '', content_text: '' };
    }
    return {
      content_html: this.editor.getHTML(),
      content_text: this.editor.getText()
    };
  }

  _dispatchAiEditAccepted(action: string, selectedText: string, resultText: string) {
    const snapshot = this._getDocumentSnapshot();
    const event = new CustomEvent('ai-edit-accepted', {
      detail: {
        action,
        selected_text: selectedText,
        result_text: resultText,
        ...snapshot
      },
      bubbles: true,
      composed: true
    });
    this.dispatchEvent(event);
  }

  _dispatchAiEditRejected() {
    const event = new CustomEvent('ai-edit-rejected', {
      detail: {},
      bubbles: true,
      composed: true
    });
    this.dispatchEvent(event);
  }
```

Call `_dispatchAiEditAccepted(promptData.key, oldText, newText)` after successful accept paths. Call `_dispatchAiEditRejected()` in reject paths.

- [ ] **Step 4: Wire Wordflow root to save accepted AI versions**

Import the document client in `wordflow.ts`:

```ts
import { createDocument, createDocumentVersion, type DocumentPayload } from '../../product/document-client';
```

Add state:

```ts
  @state()
  currentDocument: DocumentPayload | null = null;
```

Add handlers:

```ts
  async ensureDocument(contentHtml: string, contentText: string) {
    if (this.currentDocument !== null) return this.currentDocument;
    this.currentDocument = await createDocument('Untitled script', contentHtml, contentText);
    return this.currentDocument;
  }

  aiEditAcceptedHandler = async (event: CustomEvent) => {
    const detail = event.detail;
    const document = await this.ensureDocument(detail.content_html, detail.content_text);
    const version = await createDocumentVersion(document.id, {
      content_html: detail.content_html,
      content_text: detail.content_text,
      source: 'ai_action',
      reason: `${detail.action || 'ai'} selection`,
      parent_version_id: document.current_version_id
    });
    this.currentDocument = {
      ...document,
      current_version_id: version.id,
      current_version: version
    };
  };
```

Attach the handler to the text editor element in the rendered template or in `firstUpdated`.

- [ ] **Step 5: Run frontend tests**

Run:

```bash
cd frontend && npm test -- product-runtime.test.ts wordflow-root.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/vendor/wordflow-source/src/components/text-editor/text-editor.ts frontend/vendor/wordflow-source/src/components/wordflow/wordflow.ts frontend/tests/product-runtime.test.ts
git commit -m "feat: save accepted wordflow ai edits as versions"
```

---

## Task 8: Document-Scoped Streaming Chat UI

**Files:**

- Create: `frontend/vendor/wordflow-source/src/product/chat-client.ts`
- Create: `frontend/vendor/wordflow-source/src/components/agent-chat/agent-chat.ts`
- Create: `frontend/vendor/wordflow-source/src/components/agent-chat/agent-chat.css`
- Modify: `frontend/vendor/wordflow-source/src/components/wordflow/wordflow.ts`
- Modify: `frontend/tests/product-runtime.test.ts`

- [ ] **Step 1: Add failing frontend chat wiring test**

Append to `frontend/tests/product-runtime.test.ts`:

```ts
  it("defines the document-scoped streaming chat component", () => {
    const chat = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/components/agent-chat/agent-chat.ts"),
      "utf-8",
    );
    const client = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/product/chat-client.ts"),
      "utf-8",
    );
    const wordflow = readFileSync(
      resolve(process.cwd(), "vendor/wordflow-source/src/components/wordflow/wordflow.ts"),
      "utf-8",
    );

    expect(chat).toContain("wordflow-agent-chat");
    expect(client).toContain("sendChatMessage");
    expect(client).toContain("EventSource");
    expect(wordflow).toContain("wordflow-agent-chat");
  });
```

- [ ] **Step 2: Run frontend test and confirm failure**

Run:

```bash
cd frontend && npm test -- product-runtime.test.ts
```

Expected: FAIL because chat files do not exist.

- [ ] **Step 3: Add chat client**

Create `frontend/vendor/wordflow-source/src/product/chat-client.ts`:

```ts
import { config } from '../config/config';

export interface ChatSelection {
  text: string;
  context_before: string;
  context_after: string;
}

export async function sendChatMessage(
  documentId: number,
  content: string,
  selection: ChatSelection | null,
  baseVersionId: number | null
) {
  const response = await fetch(`${config.urls.documentsEndpoint}/${documentId}/chat/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content,
      selection,
      base_version_id: baseVersionId
    })
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export function streamChatRun(
  runId: number,
  onEvent: (eventType: string, payload: Record<string, unknown>) => void
) {
  const source = new EventSource(`/api/chat/runs/${runId}/events?from_seq=0`);
  const eventTypes = [
    'run_started',
    'reasoning_delta',
    'message_delta',
    'suggestion',
    'run_completed',
    'run_failed'
  ];
  for (const eventType of eventTypes) {
    source.addEventListener(eventType, event => {
      onEvent(eventType, JSON.parse((event as MessageEvent).data));
    });
  }
  return () => source.close();
}
```

- [ ] **Step 4: Add chat component**

Create `frontend/vendor/wordflow-source/src/components/agent-chat/agent-chat.ts`:

```ts
import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { sendChatMessage, streamChatRun } from '../../product/chat-client';
import componentCSS from './agent-chat.css?inline';

@customElement('wordflow-agent-chat')
export class WordflowAgentChat extends LitElement {
  static styles = css`${unsafeCSS(componentCSS)}`;

  @property({ type: Number })
  documentId = 0;

  @property({ type: Number })
  baseVersionId = 0;

  @state()
  input = '';

  @state()
  messages: { role: string; content: string }[] = [];

  @state()
  reasoning = '';

  async sendClicked() {
    const content = this.input.trim();
    if (content === '' || this.documentId === 0) return;
    this.messages = [...this.messages, { role: 'user', content }, { role: 'assistant', content: '' }];
    this.input = '';
    const run = await sendChatMessage(this.documentId, content, null, this.baseVersionId || null);
    streamChatRun(run.run_id, (eventType, payload) => {
      if (eventType === 'reasoning_delta') {
        this.reasoning += String(payload.delta || '');
      }
      if (eventType === 'message_delta') {
        const delta = String(payload.delta || '');
        const next = [...this.messages];
        const last = next[next.length - 1];
        next[next.length - 1] = { ...last, content: last.content + delta };
        this.messages = next;
      }
    });
  }

  render() {
    return html`
      <aside class="agent-chat">
        <div class="chat-header">AI</div>
        ${this.reasoning
          ? html`<details class="reasoning"><summary>推理过程</summary><pre>${this.reasoning}</pre></details>`
          : null}
        <div class="messages">
          ${this.messages.map(message => html`<div class="message ${message.role}">${message.content}</div>`)}
        </div>
        <div class="composer">
          <textarea
            .value=${this.input}
            @input=${(event: InputEvent) => {
              this.input = (event.target as HTMLTextAreaElement).value;
            }}
          ></textarea>
          <button @click=${this.sendClicked}>发送</button>
        </div>
      </aside>
    `;
  }
}
```

Create `frontend/vendor/wordflow-source/src/components/agent-chat/agent-chat.css`:

```css
.agent-chat {
  width: 320px;
  border-left: 1px solid var(--gray-200);
  background: #fff;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-header {
  font-size: 13px;
  font-weight: 600;
  padding: 10px 12px;
  border-bottom: 1px solid var(--gray-200);
}

.messages {
  flex: 1;
  overflow: auto;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message {
  font-size: 13px;
  line-height: 1.45;
  white-space: pre-wrap;
}

.message.user {
  color: var(--gray-900);
  font-weight: 600;
}

.message.assistant {
  color: var(--gray-800);
}

.reasoning {
  padding: 8px 12px;
  border-bottom: 1px solid var(--gray-200);
  font-size: 12px;
}

.reasoning pre {
  white-space: pre-wrap;
  margin: 6px 0 0;
}

.composer {
  border-top: 1px solid var(--gray-200);
  padding: 8px;
  display: flex;
  gap: 6px;
}

textarea {
  min-height: 44px;
  flex: 1;
  resize: vertical;
}

button {
  align-self: flex-end;
}
```

- [ ] **Step 5: Render chat in Wordflow root**

Import the component in `wordflow.ts`:

```ts
import '../agent-chat/agent-chat';
```

Render it next to the editor with:

```html
<wordflow-agent-chat
  .documentId=${this.currentDocument?.id || 0}
  .baseVersionId=${this.currentDocument?.current_version_id || 0}
></wordflow-agent-chat>
```

- [ ] **Step 6: Run frontend tests**

Run:

```bash
cd frontend && npm test -- product-runtime.test.ts wordflow-root.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/vendor/wordflow-source/src/product/chat-client.ts frontend/vendor/wordflow-source/src/components/agent-chat frontend/vendor/wordflow-source/src/components/wordflow/wordflow.ts frontend/tests/product-runtime.test.ts
git commit -m "feat: add document scoped streaming chat"
```

---

## Task 9: Rebuild Wordflow And Verify Public Bundle

**Files:**

- Modify: `frontend/public/wordflow/**`
- Modify: `frontend/index.html`
- Modify: `frontend/tests/wordflow-root.test.ts`

- [ ] **Step 1: Extend bundle regression test**

Add these assertions to `frontend/tests/wordflow-root.test.ts`:

```ts
expect(bundle.includes("/api/documents")).toBe(true);
expect(bundle.includes("/api/chat/runs")).toBe(true);
expect(bundle.includes("wordflow-agent-chat")).toBe(true);
```

- [ ] **Step 2: Run frontend test and confirm failure**

Run:

```bash
cd frontend && npm test -- wordflow-root.test.ts
```

Expected: FAIL until the Wordflow bundle is rebuilt and synced.

- [ ] **Step 3: Rebuild Wordflow**

Run:

```bash
cd frontend/vendor/wordflow-source
npm run build:github
rsync -a --delete dist/ ../../public/wordflow/
```

- [ ] **Step 4: Update root bundle script**

Read the generated script name:

```bash
find frontend/public/wordflow/assets -maxdepth 1 -name 'main-*.js' -print
```

Update `frontend/index.html` to point to the generated `/wordflow/assets/main-*.js`.

- [ ] **Step 5: Run frontend verification**

Run:

```bash
cd frontend && npm test
cd frontend && npm run lint
cd frontend && npm run build
```

Expected: all commands PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/index.html frontend/public/wordflow frontend/tests/wordflow-root.test.ts
git commit -m "chore: rebuild wordflow runtime bundle"
```

---

## Task 10: End-To-End Backend And Frontend Acceptance

**Files:**

- Create: `tests/test_writing_workbench_acceptance.py`
- Modify: no production files unless the acceptance test exposes a real defect.

- [ ] **Step 1: Add backend acceptance test**

Create `tests/test_writing_workbench_acceptance.py`:

```python
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from write_agent.core.database import engine
from write_agent.main import app


def setup_module() -> None:
    SQLModel.metadata.create_all(engine)


def test_document_version_and_chat_acceptance_flow():
    client = TestClient(app)
    headers = {"X-Dev-User-Id": "acceptance-user"}

    created = client.post(
        "/api/documents",
        headers=headers,
        json={
            "title": "口播脚本",
            "content_html": "<p>第一版</p>",
            "content_text": "第一版",
        },
    )
    assert created.status_code == 200
    document = created.json()

    version = client.post(
        f"/api/documents/{document['id']}/versions",
        headers=headers,
        json={
            "content_html": "<p>第二版</p>",
            "content_text": "第二版",
            "source": "ai_action",
            "reason": "oralize selection",
            "parent_version_id": document["current_version_id"],
        },
    )
    assert version.status_code == 200

    versions = client.get(f"/api/documents/{document['id']}/versions", headers=headers)
    assert versions.status_code == 200
    assert len(versions.json()["items"]) >= 2

    chat = client.post(
        f"/api/documents/{document['id']}/chat/messages",
        headers=headers,
        json={
            "content": "这段怎么更口播？",
            "selection": {"text": "第二版", "context_before": "", "context_after": ""},
            "base_version_id": version.json()["id"],
        },
    )
    assert chat.status_code == 200
    run_id = chat.json()["run_id"]

    events = client.get(f"/api/chat/runs/{run_id}/events?from_seq=0", headers=headers)
    assert events.status_code == 200
    assert "event: run_started" in events.text
    assert "event: message_delta" in events.text
```

- [ ] **Step 2: Run acceptance tests**

Run:

```bash
uv run --with pytest pytest tests/test_writing_workbench_acceptance.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full targeted verification**

Run:

```bash
uv run --with pytest pytest tests/test_auth.py tests/test_documents_api.py tests/test_chat_runtime_api.py tests/test_writing_workbench_acceptance.py -q
cd frontend && npm test
cd frontend && npm run lint
cd frontend && npm run build
```

Expected: all commands PASS.

- [ ] **Step 4: Commit acceptance test**

```bash
git add tests/test_writing_workbench_acceptance.py
git commit -m "test: add writing workbench acceptance flow"
```

---

## Task 11: Branch Push, PR, PR Verification, Merge

**Files:**

- No code files unless PR verification exposes a defect.

- [ ] **Step 1: Inspect final status**

Run:

```bash
git status --short
git log --oneline -8
```

Expected: only unrelated user-owned files may remain unstaged. Do not stage `init.md`.

- [ ] **Step 2: Push feature branch**

Run:

```bash
git branch --show-current
git push origin HEAD
```

Expected: branch is pushed.

- [ ] **Step 3: Create PR**

Run:

```bash
gh pr create \
  --base main \
  --head "$(git branch --show-current)" \
  --title "Add writing workbench runtime" \
  --body "Adds user-scoped documents, version history, Wordflow AI edit persistence, and document-scoped streaming chat runtime."
```

Expected: GitHub returns the PR URL.

- [ ] **Step 4: Watch PR checks**

Run:

```bash
gh pr checks --watch
```

Expected: all required checks PASS. If a check fails, inspect logs, fix the root cause with a test, commit, push, and repeat this step.

- [ ] **Step 5: Merge PR to main**

Run:

```bash
gh pr merge --merge --delete-branch
git fetch origin
git checkout main
git pull --ff-only origin main
```

Expected: local `main` contains the merge commit and `git status --short` shows no tracked implementation changes.

- [ ] **Step 6: Final smoke verification on main**

Run:

```bash
uv run --with pytest pytest tests/test_auth.py tests/test_documents_api.py tests/test_chat_runtime_api.py tests/test_writing_workbench_acceptance.py -q
cd frontend && npm test
cd frontend && npm run lint
cd frontend && npm run build
```

Expected: all commands PASS on main.

---

## Self-Review Checklist

- Spec coverage: user documents, versions, Wordflow actions, DeepAgents chat, streaming events, reasoning traces, replay, error handling, testing, and acceptance are each represented by at least one task.
- Type consistency: model names use `Document`, `DocumentVersion`, `AgentThread`, `AgentMessage`, `AgentRun`, `AgentRunEvent`, and `AgentReasoningTrace` consistently.
- API consistency: document routes live under `/api/documents`; chat run event routes live under `/api/chat/runs`.
- Implementation order: backend persistence comes before frontend wiring; frontend public bundle rebuild happens after vendor source changes.
- Execution mode: use subagent-driven development for implementation tasks, with TDD inside each task.
