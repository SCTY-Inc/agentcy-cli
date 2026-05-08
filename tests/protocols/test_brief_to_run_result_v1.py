from __future__ import annotations

import json
import os
import subprocess
import textwrap
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
PROTOCOLS_DIR = ROOT / "src" / "agentcy" / "protocols"
EXAMPLES_DIR = PROTOCOLS_DIR / "examples"
LOOM_RUNTIME_DIR = ROOT / "src" / "studio" / "runtime"
LOOM_BIN = LOOM_RUNTIME_DIR / "bin" / "loom.js"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _run_cli(args: list[str], *, env: dict[str, str]) -> dict:
    result = subprocess.run(
        ["node", str(LOOM_BIN), *args, "--json"],
        cwd=LOOM_RUNTIME_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok", payload
    return payload


def _write_brand_fixture(root: Path) -> None:
    brand_dir = root / "brands" / "givecare"
    brand_dir.mkdir(parents=True, exist_ok=True)
    (brand_dir / "brand.md").write_text(textwrap.dedent("""\
        ---
        id: givecare
        name: GiveCare
        positioning: Care as infrastructure.
        audiences:
          - id: caregivers
            summary: Family caregivers balancing work and care.
        offers:
          - id: invisiblebench
            summary: Benchmarking and care tooling.
        proof_points:
          - Caregiving is operational work.
        pillars:
          - id: care-economy
            perspective: Caregiving is infrastructure and should be discussed as such.
            signals:
              - caregiver benefits
            format: analysis
            frequency: weekly
        voice:
          tone: Warm, direct, specific.
          style: Human, plainspoken.
          do:
            - Name the problem directly.
          dont:
            - Use therapeutic cliches.
        channels:
          social:
            objective: Build signal and authority.
          blog:
            objective: Publish durable longform thinking.
          outreach:
            objective: Start useful conversations.
          respond:
            objective: Reply with clarity and care.
        response_playbooks:
          - id: skeptical-comment
            trigger: skepticism
            approach: Clarify the claim and add evidence.
        outreach_playbooks:
          - id: intro
            trigger: first-touch
            approach: Lead with a sharp observation and one ask.
        ---
        """))
    (brand_dir / "design.md").write_text(textwrap.dedent("""\
        ---
        palette:
          background: "#FDF9EC"
          primary: "#3D1600"
          accent: "#FF9F00"
        ---
        """))


def test_canonical_brief_v1_dry_run_handoff_emits_schema_valid_run_result(tmp_path: Path):
    brief = _load_json(EXAMPLES_DIR / "brief.v1.rich.json")
    run_result_schema = _load_json(PROTOCOLS_DIR / "schemas" / "run_result.v1.schema.json")
    validator = Draft202012Validator(run_result_schema)

    _write_brand_fixture(tmp_path)

    env = os.environ.copy()
    env["LOOM_ROOT"] = str(tmp_path)
    env["HOME"] = str(tmp_path)
    env["TWITTER_GIVECARE_API_KEY"] = "api-key"
    env["TWITTER_GIVECARE_API_SECRET"] = "api-secret"
    env["TWITTER_GIVECARE_ACCESS_TOKEN"] = "access-token"
    env["TWITTER_GIVECARE_ACCESS_SECRET"] = "access-secret"
    env.pop("GEMINI_API_KEY", None)
    env.pop("GOOGLE_API_KEY", None)

    run_payload = _run_cli(
        [
            "run",
            "social.post",
            "--brand",
            "givecare",
            "--brief-file",
            str(EXAMPLES_DIR / "brief.v1.rich.json"),
        ],
        env=env,
    )
    run_id = run_payload["data"]["id"]

    _run_cli(["review", "approve", run_id, "--variant", "social-main"], env=env)
    publish_payload = _run_cli(
        ["publish", run_id, "--platforms", "twitter", "--dry-run"],
        env=env,
    )

    run_result = publish_payload["data"]["runResult"]
    validator.validate(run_result)

    assert run_result["artifact_type"] == "run_result.v1"
    assert run_result["writer"] == {"repo": "cli-phantom", "module": "agentcy-loom"}
    assert run_result["status"] == "dry_run"
    assert run_result["delivery"]["dry_run"] is True
    assert run_result["delivery"]["platforms"] == [
        {
            "platform": "twitter",
            "status": "simulated",
            "message": "Dry-run only; no post was sent.",
        }
    ]

    assert run_result["brand_id"] == brief["brand_id"]
    assert run_result["brief_id"] == brief["brief_id"]
    assert run_result["lineage"]["source_voice_pack_id"] == brief["lineage"]["source_voice_pack_id"]
    assert run_result["lineage"]["campaign_id"] == brief["lineage"]["campaign_id"]
    assert run_result["lineage"]["signal_id"] == brief["lineage"]["signal_id"]
