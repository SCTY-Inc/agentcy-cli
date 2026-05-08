"""File output action - write analysis and content to disk.

The simplest execution target. Creates audit trail and enables
human review of autonomous outputs.
"""

from __future__ import annotations

import json
from pathlib import Path

from agentcy.brand.core.config import utc_now
from agentcy.brand.core.decision import Decision
from agentcy.brand.core.storage import data_dir


class WriteAction:
    """Write decision outputs to files.

    Creates structured output in the current compatibility runtime path:
        ~/.brand-os/outputs/{brand}/{date}/{decision_id}.json
        ~/.brand-os/outputs/{brand}/{date}/{decision_id}.md

    This intentionally follows `brand_os.core.storage.data_dir()` rather than the
    config-model `BrandOpsConfig.data_dir` surface, which currently defaults to
    `~/.brandos`.
    """

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or (data_dir() / "outputs")

    def execute(self, decision: Decision, analysis: dict | None = None) -> dict:
        """Write decision and analysis to files."""
        # Create output directory
        date_str = utc_now().strftime("%Y-%m-%d")
        output_dir = self.base_dir / decision.brand / date_str
        output_dir.mkdir(parents=True, exist_ok=True)

        # Write JSON (machine-readable)
        json_path = output_dir / f"{decision.id}.json"
        json_data = {
            "decision": decision.model_dump(mode="json"),
            "analysis": analysis,
            "written_at": utc_now().isoformat(),
        }
        json_path.write_text(json.dumps(json_data, indent=2, default=str))

        # Write markdown (human-readable)
        md_path = output_dir / f"{decision.id}.md"
        md_content = self._format_markdown(decision, analysis)
        md_path.write_text(md_content)

        return {
            "status": "written",
            "json_path": str(json_path),
            "md_path": str(md_path),
        }

    def _format_markdown(self, decision: Decision, analysis: dict | None) -> str:
        """Format decision as readable markdown."""
        lines = [
            f"# {decision.type.value.replace('_', ' ').title()}",
            "",
            f"**Brand**: {decision.brand}",
            f"**ID**: {decision.id}",
            f"**Created**: {decision.created_at.isoformat()}",
            f"**Confidence**: {decision.confidence:.0%}",
            f"**Status**: {decision.status.value}",
            "",
            "## Rationale",
            "",
            decision.rationale,
            "",
            "## Proposal",
            "",
            "```json",
            json.dumps(decision.proposal, indent=2, default=str),
            "```",
        ]

        if analysis:
            lines.extend([
                "",
                "## Analysis",
                "",
            ])

            if "summary" in analysis:
                lines.append(analysis["summary"])
                lines.append("")

            if "trends" in analysis and analysis["trends"]:
                lines.append("### Trends")
                for trend in analysis["trends"]:
                    topic = trend.get("topic", "Unknown")
                    direction = trend.get("direction", "?")
                    lines.append(f"- **{topic}**: {direction}")
                lines.append("")

            if "opportunities" in analysis and analysis["opportunities"]:
                lines.append("### Opportunities")
                for opp in analysis["opportunities"]:
                    lines.append(f"- {opp.get('description', 'N/A')}")
                lines.append("")

            if "risks" in analysis and analysis["risks"]:
                lines.append("### Risks")
                for risk in analysis["risks"]:
                    lines.append(f"- {risk.get('description', 'N/A')}")
                lines.append("")

        return "\n".join(lines)
