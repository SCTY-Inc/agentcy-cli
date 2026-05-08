"""Helpers for using CLI-backed LLMs inside OASIS/CAMEL simulations."""

import asyncio
import json
import math
import os
import sys
import time
import uuid
from typing import Any, Dict, List

try:
    from camel.models.openai_model import OpenAIModel
    _CAMEL_IMPORT_ERROR: ImportError | None = None
except ImportError as exc:  # pragma: no cover - exercised via external install smoke
    _CAMEL_IMPORT_ERROR = exc

    class OpenAIModel:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs) -> None:
            pass

from openai.types.chat.chat_completion import ChatCompletion

from ..config import Config
from .llm_client import LLMClient
from .logger import get_logger

logger = get_logger('mirofish.oasis_llm')

DEFAULT_CLI_SEMAPHORE = 3
SUPPORTED_SIMULATION_PYTHON = (3, 11)
_MISSING = object()


def get_simulation_runtime_preflight(
    version_info: Any | None = None,
    camel_import_error: ImportError | None | object = _MISSING,
) -> Dict[str, Any]:
    """Return machine-readable simulation runtime readiness details."""
    version_info = version_info or sys.version_info
    if camel_import_error is _MISSING:
        camel_import_error = _CAMEL_IMPORT_ERROR

    supported_version = f"{SUPPORTED_SIMULATION_PYTHON[0]}.{SUPPORTED_SIMULATION_PYTHON[1]}"
    current_version = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
    python_ready = (version_info.major, version_info.minor) == SUPPORTED_SIMULATION_PYTHON
    dependencies_ready = camel_import_error is None
    error = get_simulation_runtime_error(version_info=version_info, camel_import_error=camel_import_error)

    return {
        "ready": python_ready and dependencies_ready,
        "python": {
            "current": current_version,
            "supported": supported_version,
            "ready": python_ready,
        },
        "dependencies": {
            "simulation_extra_installed": dependencies_ready,
            "ready": dependencies_ready,
            "missing_import": None if camel_import_error is None else str(camel_import_error),
        },
        "error": error,
    }


def get_simulation_runtime_error(
    version_info: Any | None = None,
    camel_import_error: ImportError | None | object = _MISSING,
) -> str | None:
    """Return a human-readable simulation runtime preflight error, if any."""
    version_info = version_info or sys.version_info
    if camel_import_error is _MISSING:
        camel_import_error = _CAMEL_IMPORT_ERROR

    current_version = f"{version_info.major}.{version_info.minor}"
    supported_version = f"{SUPPORTED_SIMULATION_PYTHON[0]}.{SUPPORTED_SIMULATION_PYTHON[1]}"

    if (version_info.major, version_info.minor) != SUPPORTED_SIMULATION_PYTHON:
        return (
            f"Simulation runtime is only supported on Python {supported_version} for this fork; "
            f"current interpreter is Python {current_version}. "
            "Create or switch to a Python 3.11 environment, then install the pinned simulation extra with "
            "`pip install 'agentcy-echo[simulation]'` or `uv sync --extra simulation`."
        )

    if camel_import_error is not None:
        return (
            "Optional simulation dependencies are not installed. "
            "Install the pinned simulation extra for this fork with `pip install 'agentcy-echo[simulation]'` "
            "or `uv sync --extra simulation`. "
            f"Simulation currently requires Python {supported_version} because upstream camel-oasis does not support 3.12."
        )

    return None


def require_simulation_runtime() -> None:
    """Raise a clear error when the optional OASIS/CAMEL simulation runtime is unavailable."""
    error_message = get_simulation_runtime_error()
    if error_message is None:
        return
    if _CAMEL_IMPORT_ERROR is not None and sys.version_info[:2] == SUPPORTED_SIMULATION_PYTHON:
        raise ModuleNotFoundError(error_message) from _CAMEL_IMPORT_ERROR
    raise RuntimeError(error_message)


class CLIModel(OpenAIModel):
    """CAMEL model backend that proxies requests to Claude/Codex CLI."""

    def __init__(
        self,
        model_type: str,
        provider: str,
        model_config_dict: Dict[str, Any] | None = None,
        api_key: str | None = None,
        url: str | None = None,
        timeout: float | None = None,
        max_retries: int = 3,
    ) -> None:
        self.provider = (provider or '').lower()
        self._llm = LLMClient(provider=self.provider)
        super().__init__(
            model_type=model_type,
            model_config_dict=model_config_dict,
            api_key=api_key or 'cli-bridge',
            url=url,
            timeout=timeout,
            max_retries=max_retries,
        )

    def _estimate_tokens(self, value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, str):
            return max(1, math.ceil(len(value) / 4)) if value else 0
        if isinstance(value, list):
            return sum(self._estimate_tokens(item) for item in value)
        if isinstance(value, dict):
            return self._estimate_tokens(json.dumps(value, ensure_ascii=False))
        return self._estimate_tokens(str(value))

    def _build_completion(self, messages: List[Dict[str, Any]], content: str) -> ChatCompletion:
        prompt_tokens = sum(self._estimate_tokens(message.get('content')) for message in messages)
        completion_tokens = self._estimate_tokens(content)

        return ChatCompletion.model_validate(
            {
                'id': f'chatcmpl-cli-{uuid.uuid4().hex[:24]}',
                'object': 'chat.completion',
                'created': int(time.time()),
                'model': self.provider,
                'choices': [
                    {
                        'index': 0,
                        'message': {
                            'role': 'assistant',
                            'content': content,
                        },
                        'finish_reason': 'stop',
                    }
                ],
                'usage': {
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'total_tokens': prompt_tokens + completion_tokens,
                },
            }
        )

    def _request_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] | None = None,
    ) -> ChatCompletion:
        if tools:
            logger.warning('CLIModel ignores tool schemas; tool calling is not supported in OASIS CLI mode')

        temperature = float((self.model_config_dict or {}).get('temperature', 0.7) or 0.7)
        max_tokens = int((self.model_config_dict or {}).get('max_tokens', 4096) or 4096)
        content = self._llm.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return self._build_completion(messages, content)

    async def _arequest_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] | None = None,
    ) -> ChatCompletion:
        return await asyncio.to_thread(self._request_chat_completion, messages, tools)

    def _request_parse(
        self,
        messages: List[Dict[str, Any]],
        response_format,
        tools: List[Dict[str, Any]] | None = None,
    ) -> ChatCompletion:
        if tools:
            logger.warning('CLIModel ignores tool schemas during structured output requests')

        temperature = float((self.model_config_dict or {}).get('temperature', 0.3) or 0.3)
        max_tokens = int((self.model_config_dict or {}).get('max_tokens', 4096) or 4096)
        payload = self._llm.chat_json(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return self._build_completion(messages, json.dumps(payload, ensure_ascii=False))

    async def _arequest_parse(
        self,
        messages: List[Dict[str, Any]],
        response_format,
        tools: List[Dict[str, Any]] | None = None,
    ) -> ChatCompletion:
        return await asyncio.to_thread(self._request_parse, messages, response_format, tools)


def create_oasis_model(config: Dict[str, Any], use_boost: bool = False):
    """Create the CAMEL model used by OASIS simulations."""
    _ = use_boost
    require_simulation_runtime()

    provider = (
        os.environ.get('LLM_PROVIDER')
        or config.get('llm_provider')
        or Config.LLM_PROVIDER
        or 'claude-cli'
    ).lower()

    model = config.get('llm_model') or provider

    logger.info(f"OASIS model: provider={provider}, model={model}, mode=cli-bridge")
    return CLIModel(
        model_type=model,
        provider=provider,
        model_config_dict={},
        api_key='cli-bridge',
    )


def get_oasis_semaphore(config: Dict[str, Any], use_boost: bool = False) -> int:
    """Get CLI-appropriate OASIS concurrency limit."""
    _ = (config, use_boost)
    return int(os.environ.get('OASIS_CLI_SEMAPHORE', str(DEFAULT_CLI_SEMAPHORE)))
