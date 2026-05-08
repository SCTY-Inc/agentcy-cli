"""
LLM Client — CLI-only providers (Claude Code, Codex).
"""

import json
import os
import re
import subprocess
from typing import Optional, Dict, Any, List

from ..config import Config
from .logger import get_logger

logger = get_logger('mirofish.llm_client')


def _telemetry_path() -> str | None:
    value = os.environ.get("AGENTCY_LLM_TELEMETRY_FILE", "").strip()
    return value or None


def _append_telemetry(record: dict) -> None:
    path = _telemetry_path()
    if not path:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


class LLMClient:
    """LLM Client — supports claude-cli and codex-cli."""

    def __init__(self, provider: Optional[str] = None):
        self.provider = (provider or Config.LLM_PROVIDER or "claude-cli").lower()
        if self.provider not in ("claude-cli", "codex-cli"):
            raise ValueError(f"Unsupported LLM provider: {self.provider!r}. Use 'claude-cli' or 'codex-cli'.")

    def _split_system_message(self, messages: List[Dict[str, str]]):
        """Split system message from conversation messages."""
        system_text = None
        conversation = []

        for msg in messages:
            if msg.get("role") == "system":
                if system_text is None:
                    system_text = msg["content"]
                else:
                    system_text += "\n\n" + msg["content"]
            else:
                conversation.append(msg)

        return system_text, conversation

    def _clean_content(self, content: str) -> str:
        """Remove <think> tags from reasoning models."""
        return re.sub(r'<think>[\s\S]*?</think>', '', content).strip()

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """Send a chat request via CLI."""
        if self.provider == "codex-cli":
            return self._chat_codex_cli(messages, temperature, max_tokens, response_format)
        return self._chat_claude_cli(messages, temperature, max_tokens, response_format)

    def _chat_claude_cli(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict] = None
    ) -> str:
        """Chat via Claude Code CLI."""
        system_text, conversation = self._split_system_message(messages)

        prompt_parts = []
        if system_text:
            prompt_parts.append(f"SYSTEM INSTRUCTIONS:\n{system_text}\n")

        if response_format and response_format.get("type") == "json_object":
            prompt_parts.append("IMPORTANT: Respond with valid JSON only. No markdown, no explanation, just pure JSON.\n")

        for msg in conversation:
            role = msg.get("role", "user").upper()
            prompt_parts.append(f"{role}: {msg['content']}")

        prompt = "\n\n".join(prompt_parts)

        try:
            command = ["claude", "-p"]
            if Config.CLAUDE_MODEL:
                command.extend(["--model", Config.CLAUDE_MODEL])
            command.extend(["--output-format", "json", prompt])

            result = subprocess.run(
                command,
                capture_output=True, text=True, timeout=300,
                cwd="/tmp"
            )

            if result.returncode != 0:
                logger.error(f"Claude CLI error: {result.stderr[:200]}")
                raise RuntimeError(f"Claude CLI failed: {result.stderr[:200]}")

            try:
                output = json.loads(result.stdout)
                content = output.get("result", result.stdout)
                _append_telemetry(
                    {
                        "provider": "claude-cli",
                        "model": Config.CLAUDE_MODEL,
                        "duration_ms": output.get("duration_ms"),
                        "total_cost_usd": output.get("total_cost_usd"),
                        "usage": output.get("usage"),
                        "modelUsage": output.get("modelUsage"),
                    }
                )
            except json.JSONDecodeError:
                content = result.stdout.strip()

            return self._clean_content(content)

        except subprocess.TimeoutExpired:
            raise RuntimeError("Claude CLI timed out after 300s")

    def _chat_codex_cli(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict] = None
    ) -> str:
        """Chat via Codex CLI."""
        system_text, conversation = self._split_system_message(messages)

        prompt_parts = []
        if system_text:
            prompt_parts.append(f"SYSTEM INSTRUCTIONS:\n{system_text}\n")

        if response_format and response_format.get("type") == "json_object":
            prompt_parts.append("IMPORTANT: Respond with valid JSON only. No markdown, no explanation, just pure JSON.\n")

        for msg in conversation:
            role = msg.get("role", "user").upper()
            prompt_parts.append(f"{role}: {msg['content']}")

        prompt = "\n\n".join(prompt_parts)

        try:
            result = subprocess.run(
                ["codex", "exec", "--skip-git-repo-check"],
                input=prompt,
                capture_output=True, text=True, timeout=180,
                cwd="/tmp"
            )

            if result.returncode != 0:
                logger.error(f"Codex CLI error: {result.stderr[:200]}")
                raise RuntimeError(f"Codex CLI failed: {result.stderr[:200]}")

            raw = result.stdout.strip()
            parts = raw.split("\ncodex\n")
            if len(parts) > 1:
                content = parts[-1].strip()
                lines = content.split("\n")
                clean_lines = []
                for line in lines:
                    if line.strip() == "tokens used":
                        break
                    clean_lines.append(line)
                content = "\n".join(clean_lines).strip()
            else:
                content = raw
            _append_telemetry(
                {
                    "provider": "codex-cli",
                    "model": None,
                    "duration_ms": None,
                    "total_cost_usd": None,
                }
            )
            return self._clean_content(content)

        except subprocess.TimeoutExpired:
            raise RuntimeError("Codex CLI timed out after 180s")

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """Send a chat request and return parsed JSON."""
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON returned by LLM: {cleaned_response[:500]}")
