"""LLM provider adapter."""

from typing import Any

from ...utils.llm_client import LLMClient


class LLMProvider:
    """Thin adapter around the configured LLM client."""

    def __init__(self, client: LLMClient | None = None):
        self.client = client or LLMClient()

    @property
    def provider_name(self) -> str:
        return self.client.provider

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        return self.client.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
