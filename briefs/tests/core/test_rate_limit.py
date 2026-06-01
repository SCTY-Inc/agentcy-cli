from __future__ import annotations

from agentcy_briefs.publish import rate_limit


def test_rate_limit_records_and_reports_recent_post(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCY_BRIEFS_DATA_DIR", str(tmp_path))

    rate_limit.record_post("twitter", "givecare")

    assert rate_limit.can_post("twitter", "givecare") is True
    status = rate_limit.get_rate_status()
    assert status["twitter:givecare"]["posts_last_hour"] == 1
    assert status["twitter:givecare"]["can_post"] is True
