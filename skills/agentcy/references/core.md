# Agentcy Core

## Foundation

Agentcy starts from reusable foundation material:

- Brand: identity, audience, offers, proof, constraints, policies.
- Voice: persona, tone, traits, boundaries, examples, drift evidence.
- Visual: palette, typography, logo, image style, composition rules.
- Content: signals, pillars, campaign intent, CTA, channel guidance, risks.
- Outcomes: publish result, measurements, calibration, learnings.

The foundation should be reusable across artifacts. A LinkedIn post, OG cover, carousel, short video, and long-form script should all read the same brand/voice/visual/content inputs.

## Brand Kits

Studio should treat a brand as a portable folder:

```text
brands/<brand>/
  BRAND.md
  DESIGN.md
  assets/
```

`BRAND.md` owns behavior, voice, audience, proof, offer, policy, and pillars. `DESIGN.md` follows Google's public `design.md` shape for `design_system`, `tokens`, and `components`; Agentcy-specific source evidence, image grammar, artifact mappings, and fidelity gates live under `agentcy`. It should override visual defaults without forcing strategy or voice edits. A palette-only `DESIGN.md` is a rough style note, not a reproducible design system.

## Runtime Boundaries

| Runtime | Owns | Does Not Own |
| --- | --- | --- |
| Voice | persona authoring, evals, `voice_pack.v1` | campaigns, rendering, analytics |
| Briefs | strategy, signals, `brief.v1` | final generation, publishing |
| Forecast | audience reaction, `forecast.v1` | content writing, measurement |
| Studio | generation, rendering, review, publishing, `run_result.v1` | strategy truth, measured performance |
| Measure | performance, calibration, study, `performance.v1` | content generation |

## Naming

Use functional public names: `voice`, `briefs`, `forecast`, `studio`, `measure`. Directory names may lag behind public names, but new user-facing language should be functional and atomic.
