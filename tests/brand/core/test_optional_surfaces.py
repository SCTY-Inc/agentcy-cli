from __future__ import annotations

import pytest

from agentcy.brand.produce.image.providers.reve import generate_with_reve
from agentcy.brand.produce.video.generate import generate_video
from agentcy.brand.server import create_app, run_server
from agentcy.brand.server.mcp import create_mcp_server
from agentcy.brand.workflows import execute_decision, submit_for_review


def test_generate_video_returns_explicit_unsupported_result():
    result = generate_video("Launch teaser", brand="acme", duration=12)

    assert result["success"] is False
    assert "not implemented in this build" in result["error"]
    assert result["brand"] == "acme"
    assert result["duration"] == 12


def test_reve_provider_returns_explicit_unsupported_result(tmp_path):
    result = generate_with_reve("Caregiver portrait", brand="acme", output_path=tmp_path / "out.png")

    assert result["success"] is False
    assert "not implemented in this build" in result["error"]
    assert result["brand"] == "acme"
    assert result["output_path"].endswith("out.png")


def test_mcp_surface_is_explicitly_unavailable():
    with pytest.raises(NotImplementedError, match="not implemented in this build"):
        create_mcp_server()


def test_server_package_exports_callable_surfaces():
    assert callable(create_app)
    assert callable(run_server)


def test_workflows_package_exports_full_review_helpers():
    assert callable(submit_for_review)
    assert callable(execute_decision)
