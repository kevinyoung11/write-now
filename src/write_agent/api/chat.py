from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

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


@router.post("/documents/{document_id:int}/chat/messages")
async def create_chat_message(
    document_id: int,
    request: CreateChatMessageRequest,
    user: CurrentUserDep,
):
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="Message content is required")
    return agent_runtime_service.start_chat_run(
        user_id=user.supabase_user_id,
        document_id=document_id,
        content=request.content,
        selection=request.selection.model_dump() if request.selection else None,
        base_version_id=request.base_version_id,
    )


@router.get("/chat/runs/{run_id:int}/events")
async def stream_chat_run_events(
    run_id: int,
    user: CurrentUserDep,
    from_seq: int = 0,
):
    def generate():
        try:
            events = agent_runtime_service.list_events(
                user_id=user.supabase_user_id,
                run_id=run_id,
                from_seq=from_seq,
            )
        except ValueError as error:
            yield _sse("error", {"detail": str(error)}, from_seq)
            return

        for event in events:
            yield _sse(
                event.event_type,
                json.loads(event.payload_json or "{}"),
                int(event.seq),
            )

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
        raise HTTPException(status_code=404, detail=str(error)) from error
    agent_runtime_service.append_event(
        user_id=user.supabase_user_id,
        run_id=run_id,
        event_type="run_cancelled",
        payload={"status": "cancelled"},
    )
    return {"run_id": run.id, "status": run.status}

