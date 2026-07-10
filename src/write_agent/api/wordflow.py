from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
import requests

from write_agent.core import get_settings
from write_agent.services import wordflow_proxy_service
from write_agent.services.wordflow_proxy_service import WordflowProxyError, WordflowTextGenRequest

router = APIRouter(prefix="/wordflow", tags=["Wordflow"])
settings = get_settings()


@router.post("/text-gen")
async def text_gen(request: WordflowTextGenRequest):
    try:
        result = wordflow_proxy_service.generate_text(request)
    except WordflowProxyError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error

    prompt = request.prompt
    if request.provider == "wordflow":
        prompt = f"{request.prompt}{request.input_text}"

    return {
        "command": "finishTextGen",
        "payload": {
            "requestID": request.request_id,
            "apiKey": "",
            "result": result,
            "prompt": prompt,
            "detail": request.detail,
        },
    }


@router.api_route("/records", methods=["GET", "POST"])
async def records_proxy(request: Request):
    body = await request.body()
    headers = {}
    content_type = request.headers.get("content-type")
    if content_type:
        headers["content-type"] = content_type

    try:
        upstream = requests.request(
            request.method,
            settings.wordflow_remote_endpoint,
            params=dict(request.query_params),
            data=body if body else None,
            headers=headers,
            timeout=settings.openai_timeout_seconds,
        )
    except requests.RequestException as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    response_headers = {}
    for name in ("x-has-pagination", "set-cookie"):
        value = upstream.headers.get(name)
        if value:
            response_headers[name] = value

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
        headers=response_headers,
    )
