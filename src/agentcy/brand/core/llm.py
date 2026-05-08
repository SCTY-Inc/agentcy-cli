from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from agentcy.protocols.llm import LLMError as ProviderError
from agentcy.protocols.llm import LLMProvider  # noqa: F401 — re-exported for local callers
from agentcy.protocols.utils import parse_llm_json as _parse_json


@dataclass
class LLMConfig:
    provider: str = "mock"
    model: str | None = None


class MockProvider:
    def complete(self, prompt: str, system: str | None = None, model: str | None = None) -> str:
        return ""

    def complete_json(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        default: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return default or {}


class GeminiProvider:
    """Google Gemini provider - best free tier for autonomous loops."""

    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ProviderError("GOOGLE_API_KEY not set")

    def complete(self, prompt: str, system: str | None = None, model: str | None = None) -> str:
        import httpx

        model = model or "gemini-2.0-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        messages = []
        if system:
            messages.append({"role": "user", "parts": [{"text": f"System: {system}"}]})
            messages.append({"role": "model", "parts": [{"text": "Understood."}]})
        messages.append({"role": "user", "parts": [{"text": prompt}]})

        response = httpx.post(
            url,
            params={"key": self.api_key},
            json={"contents": messages},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        return data["candidates"][0]["content"]["parts"][0]["text"]

    def complete_json(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        default: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        full_prompt = f"{prompt}\n\nRespond with valid JSON only, no markdown."
        text = self.complete(full_prompt, system, model)
        return _parse_json(text, default)


class AnthropicProvider:
    """Anthropic Claude provider - Haiku is cheap for high-volume."""

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ProviderError("ANTHROPIC_API_KEY not set")

    def complete(self, prompt: str, system: str | None = None, model: str | None = None) -> str:
        import httpx

        model = model or "claude-3-5-haiku-20241022"

        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 4096,
                "system": system or "You are a helpful assistant.",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        return data["content"][0]["text"]

    def complete_json(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        default: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        full_prompt = f"{prompt}\n\nRespond with valid JSON only, no markdown."
        text = self.complete(full_prompt, system, model)
        return _parse_json(text, default)


class ClaudeCLIProvider:
    """Claude Code CLI provider for local operator runs."""

    def __init__(self):
        self.cli_path = shutil.which("claude")
        if not self.cli_path:
            raise ProviderError("claude CLI not found")

    def _model(self, model: str | None = None) -> str | None:
        return model or os.getenv("BRANDOPS_LLM_MODEL") or os.getenv("CLAUDE_MODEL") or None

    def complete(self, prompt: str, system: str | None = None, model: str | None = None) -> str:
        prompt_parts = []
        if system:
            prompt_parts.append(f"SYSTEM INSTRUCTIONS:\n{system}\n")
        prompt_parts.append(prompt)
        final_prompt = "\n\n".join(part for part in prompt_parts if part)

        command = [self.cli_path, "-p"]
        resolved_model = self._model(model)
        if resolved_model:
            command.extend(["--model", resolved_model])
        command.extend(["--output-format", "json", final_prompt])

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300,
                cwd="/tmp",
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderError("claude CLI timed out after 300s") from exc

        if result.returncode != 0:
            message = (result.stderr or result.stdout or "claude CLI failed").strip()
            raise ProviderError(message)

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return result.stdout.strip()

        return str(payload.get("result") or result.stdout).strip()

    def complete_json(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        default: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        full_prompt = f"{prompt}\n\nRespond with valid JSON only, no markdown."
        text = self.complete(full_prompt, system, model)
        return _parse_json(text, default)



def get_provider(name: str | None = None) -> LLMProvider:
    provider = name or os.getenv("BRANDOPS_LLM_PROVIDER")
    if not provider:
        llm_provider = os.getenv("LLM_PROVIDER", "").strip().lower()
        if llm_provider in {"mock", "gemini", "anthropic", "claude-cli"}:
            provider = llm_provider
        else:
            provider = "gemini"

    if provider == "mock":
        return MockProvider()
    elif provider == "gemini":
        return GeminiProvider()
    elif provider == "anthropic":
        return AnthropicProvider()
    elif provider == "claude-cli":
        return ClaudeCLIProvider()

    raise ProviderError(f"Unknown LLM provider: {provider}")


def complete(prompt: str, system: str | None = None, model: str | None = None) -> str:
    provider = get_provider()
    return provider.complete(prompt=prompt, system=system, model=model)


def complete_json(
    prompt: str,
    system: str | None = None,
    model: str | None = None,
    default: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider = get_provider()
    return provider.complete_json(prompt=prompt, system=system, model=model, default=default)


async def acomplete(prompt: str, system: str | None = None, model: str | None = None) -> str:
    """Async version of complete - runs sync provider in thread pool."""
    return await asyncio.to_thread(complete, prompt, system, model)


async def acomplete_json(
    prompt: str,
    system: str | None = None,
    model: str | None = None,
    default: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Async version of complete_json - runs sync provider in thread pool."""
    return await asyncio.to_thread(complete_json, prompt, system, model, default)
