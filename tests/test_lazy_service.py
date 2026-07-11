from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_lazy_service_defers_construction_until_first_use():
    from write_agent.core.lazy_service import LazyService

    calls = []

    class Real:
        def greet(self):
            return "hi"

    def getter():
        calls.append("constructed")
        return Real()

    proxy = LazyService(getter)
    assert calls == []

    assert proxy.greet() == "hi"
    assert calls == ["constructed"]

    # Repeated use reuses the same instance instead of re-constructing it.
    assert proxy.greet() == "hi"
    assert calls == ["constructed"]


def test_lazy_service_setattr_forwards_to_the_resolved_instance():
    from write_agent.core.lazy_service import LazyService

    class Real:
        def greet(self):
            return "hi"

    proxy = LazyService(Real)
    proxy.greet = lambda: "patched"

    assert proxy.greet() == "patched"


def test_heavy_rag_dependencies_are_not_imported_by_the_api_module():
    """
    Every router used to build its service singleton at import time
    (`service = get_xxx_service()`), so importing write_agent.api pulled in
    every feature's heaviest dependencies (chromadb/onnxruntime for RAG, in
    particular) up front. That directly slows down cold starts for routes
    that never touch those features, like the document/chat endpoints the
    editor actually uses. This asserts the RAG stack stays lazy, checked in
    a fresh subprocess so it reflects an actual cold import.
    """
    import subprocess

    repo_root = os.path.join(os.path.dirname(__file__), "..")
    src_dir = os.path.join(repo_root, "src")
    script = (
        "import sys; import write_agent.api; "
        "assert 'chromadb' not in sys.modules, 'chromadb was imported eagerly'; "
        "assert 'langchain_chroma' not in sys.modules, "
        "'langchain_chroma was imported eagerly'; "
        "print('ok')"
    )
    env = {**os.environ, "PYTHONPATH": src_dir}
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ok" in result.stdout
