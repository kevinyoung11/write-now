from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_request_scoped_services_do_not_create_schema_per_call():
    for relative_path in (
        "src/write_agent/services/document_service.py",
        "src/write_agent/services/agent_runtime_service.py",
        "src/write_agent/core/auth.py",
    ):
        source = (ROOT / relative_path).read_text()
        assert "metadata.create_all" not in source


def test_database_schema_has_central_bootstrap():
    source = (ROOT / "src/write_agent/core/schema.py").read_text()

    assert "def ensure_database_schema" in source
    assert "SQLModel.metadata.create_all(engine)" in source
