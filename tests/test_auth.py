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
