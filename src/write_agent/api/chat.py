from __future__ import annotations

import json
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from write_agent.core import get_settings
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


TERMINAL_EVENTS = {"run_completed", "run_failed", "run_cancelled"}


@router.post("/documents/{document_id:int}/chat/messages")
async def create_chat_message(
    document_id: int,
    request: CreateChatMessageRequest,
    user: CurrentUserDep,
):
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="Message content is required")
    try:
        return agent_runtime_service.start_chat_run(
            user_id=user.supabase_user_id,
            document_id=document_id,
            content=request.content,
            selection=request.selection.model_dump() if request.selection else None,
            base_version_id=request.base_version_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/chat/runs/{run_id:int}/events")
async def stream_chat_run_events(
    run_id: int,
    user: CurrentUserDep,
    from_seq: int = 0,
):
    def generate():
        next_seq = from_seq
        settings = get_settings()
        sleep_seconds = max(settings.agent_event_replay_sleep_seconds, 0.05)
        try:
            agent_runtime_service.list_events(
                user_id=user.supabase_user_id, run_id=run_id, from_seq=next_seq
            )
        except ValueError as error:
            yield _sse("error", {"detail": str(error)}, from_seq)
            return

        while True:
            events = agent_runtime_service.list_events(
                user_id=user.supabase_user_id,
                run_id=run_id,
                from_seq=next_seq,
            )
            if not events:
                time.sleep(sleep_seconds)
                continue

            for event in events:
                next_seq = int(event.seq)
                yield _sse(
                    event.event_type,
                    json.loads(event.payload_json or "{}"),
                    next_seq,
                )
                if event.event_type in TERMINAL_EVENTS:
                    return

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/runs/{run_id:int}/cancel")
async def cancel_chat_run(run_id: int, user: CurrentUserDep):
    try:
        run = agent_runtime_service.mark_run_cancelled(
            user_id=user.supabase_user_id,
            run_id=run_id,
        )
    except ValueError as error:
        if str(error) == "Run is already terminal":
            raise HTTPException(status_code=409, detail=str(error)) from error
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"run_id": run.id, "status": run.status}
