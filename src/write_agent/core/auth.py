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
        headers={
            "Authorization": f"Bearer {token}",
            "apikey": settings.supabase_anon_key,
        },
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
