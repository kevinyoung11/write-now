from __future__ import annotations

from typing import Literal

import requests
from openai import OpenAI
from pydantic import BaseModel, Field

from write_agent.core import get_logger, get_settings

logger = get_logger(__name__)
settings = get_settings()


Provider = Literal["openai", "gemini", "palm", "wordflow"]


class WordflowProxyError(Exception):
    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class WordflowTextGenRequest(BaseModel):
    provider: Provider = "openai"
    request_id: str = Field(default="")
    prompt: str
    input_text: str = ""
    temperature: float = 0.7
    model: str = ""
    stop_sequences: list[str] = Field(default_factory=list)
    detail: str = ""
    api_key: str = ""
    user_id: str = ""


def _extract_openai_text(response) -> str:
    output_text = getattr(response, "output_text", "")
    if output_text:
        return str(output_text)

    output = getattr(response, "output", None)
    if output:
        chunks: list[str] = []
        for item in output:
            for content in getattr(item, "content", []) or []:
                text = getattr(content, "text", None)
                if text:
                    chunks.append(str(text))
        if chunks:
            return "".join(chunks)

    choices = getattr(response, "choices", None)
    if choices:
        content = getattr(choices[0].message, "content", "")
        if content:
            return str(content)

    raise WordflowProxyError("OpenAI response did not include final text")


def _openai_client(api_key: str, *, wire_api: str) -> OpenAI:
    base_url = settings.openai_base_url.strip().rstrip("/")
    if wire_api != "responses" and not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=settings.openai_timeout_seconds,
    )


def _generate_openai(request: WordflowTextGenRequest) -> str:
    api_key = request.api_key.strip() or settings.openai_api_key.strip()
    if not api_key:
        raise WordflowProxyError("OpenAI API key is not configured", status_code=400)

    wire_api = (settings.openai_wire_api or "chat_completions").strip().lower()
    model = request.model.strip() or settings.openai_model
    client = _openai_client(api_key, wire_api=wire_api)

    try:
        if wire_api == "responses":
            kwargs = {
                "model": model,
                "input": request.prompt,
            }
            if settings.openai_reasoning_effort:
                kwargs["reasoning"] = {"effort": settings.openai_reasoning_effort}
            if settings.openai_disable_response_storage:
                kwargs["store"] = False
            return _extract_openai_text(client.responses.create(**kwargs))

        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": request.prompt}],
            temperature=request.temperature,
            stop=request.stop_sequences or None,
        )
        return _extract_openai_text(completion)
    except WordflowProxyError:
        raise
    except Exception as error:
        logger.warning("Wordflow OpenAI proxy failed: %s", error)
        raise WordflowProxyError(str(error)) from error


def _google_api_key(request: WordflowTextGenRequest) -> str:
    api_key = request.api_key.strip() or settings.google_api_key.strip()
    if not api_key:
        raise WordflowProxyError("Google API key is not configured", status_code=400)
    return api_key


def _generate_gemini(request: WordflowTextGenRequest) -> str:
    api_key = _google_api_key(request)
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    payload = {
        "contents": [{"parts": [{"text": request.prompt}]}],
        "generationConfig": {
            "temperature": request.temperature,
            "stopSequences": request.stop_sequences,
        },
    }
    response = requests.post(
        url,
        params={"key": api_key},
        json=payload,
        timeout=settings.openai_timeout_seconds,
    )
    if response.status_code != 200:
        raise WordflowProxyError(response.text, status_code=response.status_code)
    data = response.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as error:
        raise WordflowProxyError("Gemini response did not include final text") from error


def _generate_palm(request: WordflowTextGenRequest) -> str:
    api_key = _google_api_key(request)
    url = "https://generativelanguage.googleapis.com/v1beta2/models/text-bison-001:generateText"
    payload = {
        "prompt": {"text": request.prompt},
        "temperature": request.temperature,
        "stopSequences": request.stop_sequences,
    }
    response = requests.post(
        url,
        params={"key": api_key},
        json=payload,
        timeout=settings.openai_timeout_seconds,
    )
    if response.status_code != 200:
        raise WordflowProxyError(response.text, status_code=response.status_code)
    data = response.json()
    try:
        return data["candidates"][0]["output"]
    except (KeyError, IndexError, TypeError) as error:
        raise WordflowProxyError("PaLM response did not include final text") from error


def _generate_wordflow(request: WordflowTextGenRequest) -> str:
    endpoint = settings.wordflow_remote_endpoint
    body = {
        "prompt": request.prompt,
        "text": request.input_text,
        "temperature": request.temperature,
        "userID": request.user_id,
        "model": request.model,
    }
    response = requests.post(
        endpoint,
        params={"type": "run"},
        json=body,
        timeout=settings.openai_timeout_seconds,
    )
    if response.status_code != 200:
        raise WordflowProxyError(response.text, status_code=response.status_code)
    data = response.json()
    try:
        return data["payload"]["result"]
    except (KeyError, TypeError) as error:
        raise WordflowProxyError("Wordflow response did not include final text") from error


def generate_text(request: WordflowTextGenRequest) -> str:
    if request.provider == "openai":
        return _generate_openai(request)
    if request.provider == "gemini":
        return _generate_gemini(request)
    if request.provider == "palm":
        return _generate_palm(request)
    if request.provider == "wordflow":
        return _generate_wordflow(request)
    raise WordflowProxyError("Unsupported provider", status_code=400)
