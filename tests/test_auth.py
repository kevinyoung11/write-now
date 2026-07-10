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
    assert settings.auth_dev_user_id == "dev-user"
    assert settings.auth_dev_email == "dev@example.local"
    assert settings.chat_recent_message_limit == 12
    assert settings.agent_event_replay_sleep_seconds == 0.2


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
