"""Notification actions - alert humans when needed."""

from __future__ import annotations

import os

import httpx

from agentcy.brand.core.decision import Decision


class NotifyAction:
    """Send notifications via various channels."""

    def __init__(self):
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL")

    async def slack(self, decision: Decision, message: str | None = None) -> dict:
        """Send Slack notification."""
        if not self.slack_webhook:
            return {"status": "skipped", "reason": "SLACK_WEBHOOK_URL not set"}

        text = message or self._format_slack_message(decision)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.slack_webhook,
                json={"text": text},
                timeout=10,
            )

        return {
            "status": "sent" if response.status_code == 200 else "failed",
            "status_code": response.status_code,
        }

    def _format_slack_message(self, decision: Decision) -> str:
        """Format decision for Slack."""
        emoji = {
            "pending_review": "🔔",
            "executed": "✅",
            "failed": "❌",
            "rejected": "🚫",
        }.get(decision.status.value, "📋")

        return (
            f"{emoji} *{decision.type.value.replace('_', ' ').title()}* "
            f"for `{decision.brand}`\n"
            f"Confidence: {decision.confidence:.0%}\n"
            f"_{decision.rationale[:200]}_\n"
            f"ID: `{decision.id}`"
        )

    def cli(self, decision: Decision) -> dict:
        """Log to CLI (passive notification via decision list)."""
        return {"status": "logged", "decision_id": decision.id}
