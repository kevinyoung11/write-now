from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass
from typing import Annotated

import requests
from fastapi import Depends, Header, HTTPException
from sqlmodel import Session, select

from write_agent.core import get_settings
from write_agent.core.database import engine
from write_agent.core.schema import ensure_database_schema
from write_agent.models import User

# Verifying a Supabase access token means an extra network round trip to
# Supabase's Auth API. That round trip repeats on every single API call
# (loading the current document, sending a chat message, saving a version,
# ...), which noticeably slows the app down since a token is valid for
# a while after Supabase issues it. Cache the verified identity for a short
# window so a burst of requests from one browser session only pays for that
# round trip once.
_TOKEN_CACHE_TTL_SECONDS = 60
_token_cache: dict[str, tuple[float, "CurrentUser"]] = {}
_token_cache_lock = threading.Lock()


@dataclass(frozen=True)
class CurrentUser:
    supabase_user_id: str
    email: str = ""
    local_user_id: int | None = None


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
    settings = get_settings()
    if _allow_dev_user_fallback(settings):
        user_id = (x_dev_user_id or settings.auth_dev_user_id).strip()
        if user_id:
            return _ensure_local_user(
                supabase_user_id=user_id,
                email=settings.auth_dev_email,
            )

    token = _bearer_token(authorization)
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(status_code=500, detail="Supabase auth is not configured")

    cache_key = hashlib.sha256(token.encode("utf-8")).hexdigest()
    cached = _get_cached_user(cache_key)
    if cached is not None:
        return cached

    try:
        response = requests.get(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": settings.supabase_anon_key,
            },
            timeout=10,
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Supabase auth is unavailable")

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Supabase token")

    try:
        payload = response.json()
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Supabase token")

    user_id = str(payload.get("id") or "")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid Supabase token")

    current_user = _ensure_local_user(
        supabase_user_id=user_id,
        email=str(payload.get("email") or ""),
    )
    _set_cached_user(cache_key, current_user)
    return current_user


def _get_cached_user(cache_key: str) -> "CurrentUser | None":
    with _token_cache_lock:
        entry = _token_cache.get(cache_key)
        if entry is None:
            return None
        expires_at, current_user = entry
        if expires_at < time.monotonic():
            del _token_cache[cache_key]
            return None
        return current_user


def _set_cached_user(cache_key: str, current_user: "CurrentUser") -> None:
    with _token_cache_lock:
        _token_cache[cache_key] = (
            time.monotonic() + _TOKEN_CACHE_TTL_SECONDS,
            current_user,
        )


def _allow_dev_user_fallback(settings) -> bool:
    if not settings.auth_dev_user_enabled:
        return False
    return not settings.supabase_url and not settings.supabase_anon_key


def _ensure_local_user(*, supabase_user_id: str, email: str) -> CurrentUser:
    ensure_database_schema(engine)
    with Session(engine) as session:
        user = session.exec(
            select(User).where(User.supabase_user_id == supabase_user_id)
        ).first()
        if user is None:
            user = User(supabase_user_id=supabase_user_id, email=email)
            session.add(user)
            session.commit()
            session.refresh(user)
        elif email and user.email != email:
            user.email = email
            session.add(user)
            session.commit()
            session.refresh(user)

        return CurrentUser(
            supabase_user_id=user.supabase_user_id,
            email=user.email,
            local_user_id=user.id,
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
