"""
数据库连接管理 - 统一管理数据库连接
"""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool
from sqlmodel import create_engine

from write_agent.core.config import get_settings


def normalize_database_url(database_url: str) -> str:
    """Normalize deployment database URLs without exposing credentials."""
    if not database_url:
        return database_url

    parsed = urlsplit(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        return database_url

    scheme = "postgresql"
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    query_keys = {key.lower() for key, _ in query_items}
    if "sslmode" not in query_keys:
        query_items.append(("sslmode", "require"))

    return urlunsplit(
        (
            scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query_items),
            parsed.fragment,
        )
    )


def create_app_engine(database_url: str | None = None, *, echo: bool = False) -> Engine:
    settings = get_settings()
    normalized_url = normalize_database_url(database_url or settings.database_url)
    kwargs = {"echo": echo, "pool_pre_ping": True}
    if normalized_url.startswith(("postgres://", "postgresql://")):
        kwargs["poolclass"] = NullPool
    if normalized_url.startswith("sqlite://"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(normalized_url, **kwargs)


# 创建全局数据库引擎
engine = create_app_engine()

__all__ = ["create_app_engine", "engine", "normalize_database_url"]
