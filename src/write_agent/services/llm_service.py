"""
LLM 服务封装 - 统一调用大模型
"""
from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from typing import Optional

from write_agent.core import get_settings, get_logger
from write_agent.observability import emit_obs_event, obs_scope

logger = get_logger(__name__)
settings = get_settings()


class LLMService:
    """
    LLM 服务封装

    统一管理大模型调用，支持流式输出
    """

    def __init__(self):
        """初始化 LLM 客户端"""
        base_url = settings.openai_base_url.rstrip("/")
        self.wire_api = (settings.openai_wire_api or "chat_completions").strip().lower()

        if self.wire_api == "responses":
            self.base_url = base_url
            self.client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=self.base_url,
                timeout=settings.openai_timeout_seconds,
            )
            self.llm = None
        else:
            # 兼容仅提供网关根路径（如 http://localhost:8317）的场景
            if not base_url.endswith("/v1"):
                base_url = f"{base_url}/v1"
            self.base_url = base_url
            self.client = None
            self.llm = ChatOpenAI(
                model=settings.openai_model,
                openai_api_key=settings.openai_api_key,
                base_url=self.base_url,
                timeout=settings.openai_timeout_seconds,
            )
        logger.info(
            "LLM 服务初始化完成，使用模型: %s, base_url: %s, wire_api=%s, timeout=%ss",
            settings.openai_model,
            self.base_url,
            self.wire_api,
            settings.openai_timeout_seconds,
        )

    def _to_responses_input(self, messages: list[dict]) -> list[dict]:
        responses_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            if role not in {"user", "assistant", "system", "developer"}:
                role = "user"
            responses_messages.append(
                {
                    "role": role,
                    "content": [{"type": "input_text", "text": msg.get("content", "")}],
                }
            )
        return responses_messages

    def _responses_kwargs(self, messages: list[dict], system_prompt: Optional[str] = None) -> dict:
        kwargs = {
            "model": settings.openai_model,
            "input": self._to_responses_input(messages),
        }
        if system_prompt:
            kwargs["instructions"] = system_prompt
        if settings.openai_reasoning_effort:
            kwargs["reasoning"] = {"effort": settings.openai_reasoning_effort}
        if settings.openai_disable_response_storage:
            kwargs["store"] = False
        return kwargs

    def chat(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """
        简单的聊天调用

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            system_prompt: 系统提示
            temperature: 温度参数

        Returns:
            LLM 回复内容
        """
        with obs_scope("SVC.LLM.CHAT", "LLM_STREAM_CALL"):
            emit_obs_event(
                level="INFO",
                message="svc.llm.chat.start",
                payload={"messages_count": len(messages), "temperature": temperature},
            )
            if self.wire_api == "responses":
                response = self.client.responses.create(
                    **self._responses_kwargs(messages, system_prompt=system_prompt)
                )
                content = getattr(response, "output_text", "") or ""
                emit_obs_event(
                    level="INFO",
                    message="svc.llm.chat.done",
                    payload={"response_len": len(content)},
                )
                return content

            langchain_messages = []
            if system_prompt:
                langchain_messages.append(SystemMessage(content=system_prompt))

            for msg in messages:
                if msg["role"] == "user":
                    langchain_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    langchain_messages.append({"type": "ai", "content": msg["content"]})

            response = self.llm.invoke(langchain_messages)
            emit_obs_event(
                level="INFO",
                message="svc.llm.chat.done",
                payload={"response_len": len(str(response.content or ""))},
            )
            return response.content

    def stream(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
    ):
        """
        流式调用

        Args:
            messages: 消息列表
            system_prompt: 系统提示

        Yields:
            逐块返回的内容
        """
        with obs_scope("SVC.LLM.STREAM", "LLM_STREAM_CALL"):
            emit_obs_event(
                level="INFO",
                message="svc.llm.stream.start",
                payload={"messages_count": len(messages)},
            )
            if self.wire_api == "responses":
                chunk_count = 0
                with self.client.responses.stream(
                    **self._responses_kwargs(messages, system_prompt=system_prompt)
                ) as stream:
                    for event in stream:
                        if getattr(event, "type", "") == "response.output_text.delta":
                            delta = getattr(event, "delta", "")
                            if delta:
                                chunk_count += 1
                                yield delta
                emit_obs_event(
                    level="INFO",
                    message="svc.llm.stream.done",
                    payload={"chunk_count": chunk_count},
                )
                return

            langchain_messages = []
            if system_prompt:
                langchain_messages.append(SystemMessage(content=system_prompt))

            for msg in messages:
                if msg["role"] == "user":
                    langchain_messages.append(HumanMessage(content=msg["content"]))

            chunk_count = 0
            for chunk in self.llm.stream(langchain_messages):
                if chunk.content:
                    chunk_count += 1
                    yield chunk.content
            emit_obs_event(
                level="INFO",
                message="svc.llm.stream.done",
                payload={"chunk_count": chunk_count},
            )


# 全局单例
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """获取 LLM 服务单例"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
