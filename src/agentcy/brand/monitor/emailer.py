"""Email delivery for reports."""
from __future__ import annotations

import os
from typing import Any

from agentcy.brand.monitor.reports import BrandReport, format_report_html


def send_report(
    report: BrandReport,
    to: list[str],
    subject: str | None = None,
) -> dict[str, Any]:
    """Send a report via email.

    Args:
        report: BrandReport to send
        to: List of recipient email addresses
        subject: Optional custom subject

    Returns:
        Result dict with success status
    """
    try:
        import resend
    except ImportError:
        return {
            "success": False,
            "error": "resend required. Install with: pip install agentcy-compass[email]",
        }

    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        return {
            "success": False,
            "error": "RESEND_API_KEY environment variable required",
        }

    resend.api_key = api_key

    from_email = os.getenv("BRANDOPS_FROM_EMAIL", "reports@brandos.dev")
    subject = subject or f"Brand Report: {report.brand} ({report.report_date})"

    html_content = format_report_html(report)

    try:
        result = resend.Emails.send({
            "from": from_email,
            "to": to,
            "subject": subject,
            "html": html_content,
        })

        return {
            "success": True,
            "message_id": result.get("id"),
            "recipients": to,
        }

    except (OSError, ValueError, RuntimeError) as e:
        return {
            "success": False,
            "error": str(e),
        }


def validate_email_config() -> bool:
    """Check if email is configured."""
    return bool(os.getenv("RESEND_API_KEY"))
