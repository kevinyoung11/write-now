from __future__ import annotations

import threading
from typing import Any

from sqlmodel import SQLModel

from write_agent.core.database import engine
import write_agent.models  # noqa: F401 - registers SQLModel metadata

_schema_lock = threading.Lock()
_ready_engine_ids: set[int] = set()


def ensure_database_schema(target_engine: Any | None = None) -> None:
    schema_engine = target_engine or engine
    engine_id = id(schema_engine)
    if engine_id in _ready_engine_ids:
        return

    with _schema_lock:
        if engine_id in _ready_engine_ids:
            return
        if schema_engine is engine:
            SQLModel.metadata.create_all(engine)
        else:
            SQLModel.metadata.create_all(schema_engine)
        _ready_engine_ids.add(engine_id)
