# Agentcy Capability Model

Agentcy should be shaped as one brand/content foundation with extensions on top, not as a pile of cute package names or disconnected generators.

See [principal-patterns.md](principal-patterns.md) for the small-core operating model.

## Foundation

The durable core is the material every downstream artifact should reuse:

| Core | What It Means | Current Owner |
| --- | --- | --- |
| Brand | identity, audience, offers, proof, constraints, policies | `BRAND.md` + Briefs brand config |
| Voice | persona, tone, traits, boundaries, examples, drift evidence | Voice / `voice_pack.v1` |
| Visual | palette, typography, logo, image style, composition rules | Studio `DESIGN.md` + brand assets |
| Content | signals, pillars, campaign intent, CTA, channel guidance, risks | Briefs / `brief.v1` |
| Outcomes | publish result, measurements, calibration, learnings | Studio + Measure |

Protocols are the spine between those pieces. Runtimes should not smuggle hidden state between each other; they should read and write explicit artifacts.

## Turnkey Brand Kits

A brand should be portable as a folder:

```text
brands/<brand>/
  BRAND.md    # behavior, voice, audience, offer, proof, policy
  DESIGN.md   # source evidence, tokens, artifact mappings, fidelity gates
  assets/     # optional logos, fonts, references
```

`BRAND.md` is enough for behavior. `DESIGN.md` makes the kit artifact-ready by overriding or completing the visual system without changing the brand strategy file. It uses Google's public `design.md` shape for `design_system`, `tokens`, and `components`; Agentcy-specific execution data lives under `agentcy`. For visual reproduction, `DESIGN.md` should be evidence-first: source capture, semantic tokens, component rules, artifact mappings, and pass/fail fidelity gates.

Validate a kit before running it:

```bash
uv run agentcy studio brand validate <brand> --json
```

The validation output reports whether the kit has design, typography, image grammar, composition rules, proof points, pillars, fidelity gates, and enough learning inputs to be useful repeatedly.

## Runtimes

| Runtime | Job | Boundary |
| --- | --- | --- |
| Voice | author and evaluate personas | does not plan campaigns or publish |
| Briefs | turn brand, voice, and signals into content briefs | does not own rendering or publishing |
| Forecast | predict audience/social reaction | does not generate final content |
| Studio | turn the foundation into artifacts and publishable runs | does not own strategy or measurement truth |
| Measure | adapt outcomes into performance and study output | does not generate content |

## Extensions

An extension is a capability package that turns the same foundation into a specific output. It should declare:

- foundation inputs it needs
- output artifact or sidecar it owns
- runtime owner
- provider dependencies, if any
- fixture or smoke verification

Good extension names are functional: `og.cover`, `social.card`, `carousel`, `short.video`, `ugc.ad`, `longform.script`, `campaign.pack`. They describe the job, not the internal package personality.

## Near-Term Extension Families

| Family | Owner | Current | Next |
| --- | --- | --- | --- |
| Studio generation | Studio | `social.post`, `blog.post`, `outreach.touch`, `respond.reply`, lab card/cover/render | `og.cover`, `carousel`, `short.video`, `ugc.ad`, `longform.script`, `campaign.pack` |
| Forecasting | Forecast | document + brief reaction forecast, run-eval sidecar | objection lanes, variant risk forecast, channel forecast |
| Measurement | Measure | `adapt`, `calibrate`, `study` | channel benchmarks, voice drift feedback, creative pattern memory |
| Agent instruction | `skills/agentcy` | one nested Agentcy skill with reference files | mode-specific reference packs for image/video/content workflows |

## Product Rule

Brand, voice, visual, and content are the foundation. Everything else is a mode that transforms that foundation into an artifact, forecast, or measurement.

The default path should be deterministic and inspectable. Provider-backed generation, simulation, publishing, and learning loops are opt-in extensions with explicit cost and verification.
