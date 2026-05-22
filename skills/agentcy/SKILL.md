---
name: agentcy
description: Use when working on the Agentcy brand/content stack, its voice/brief/forecast/studio/measure pipeline, or extensions that turn brand, voice, visual, and content foundations into artifacts.
---

# Agentcy

Agentcy is a protocol-first brand and content stack. Treat brand, voice, visual design, and content strategy as the foundation; treat channels and formats as extensions that transform that foundation into artifacts.

## Workflow

1. Identify the layer being changed: foundation, protocol, runtime, extension, or docs.
2. Keep ownership narrow:
   - Voice owns personas and `voice_pack.v1`.
   - Briefs owns strategy and `brief.v1`.
   - Forecast owns audience/social reaction and `forecast.v1`.
   - Studio owns content generation, rendering, review, publish, and `run_result.v1`.
   - Measure owns performance, calibration, study, and `performance.v1`.
3. Use machine-readable CLI surfaces for verification.
4. Preserve explicit artifact handoffs; avoid hidden cross-runtime state.

## References

- Read `references/core.md` for foundation, runtime ownership, and product boundaries.
- Read `references/usage.md` when running the repo or explaining operator workflows.
- Read `references/extensions.md` when adding or shaping a capability such as image, carousel, video, campaign, or publishing modes.
- Read `../../docs/design-md-fidelity.md` when changing `DESIGN.md`, renderer mappings, or visual QA behavior.
