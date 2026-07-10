from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import requests
from fastapi import Depends, Header, HTTPException
from sqlmodel import SQLModel, Session, select

from write_agent.core import get_settings
from write_agent.core.database import engine
from write_agent.models import User


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

    return _ensure_local_user(
        supabase_user_id=user_id,
        email=str(payload.get("email") or ""),
    )


def _allow_dev_user_fallback(settings) -> bool:
    if not settings.auth_dev_user_enabled:
        return False
    return not settings.supabase_url and not settings.supabase_anon_key


def _ensure_local_user(*, supabase_user_id: str, email: str) -> CurrentUser:
    SQLModel.metadata.create_all(engine, tables=[User.__table__])
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
