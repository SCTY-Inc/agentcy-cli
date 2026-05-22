# Agentcy Extensions

An extension turns the same brand, voice, visual, and content foundation into one output family. Prefer extension work over adding another package unless ownership truly changes.

## Extension Contract

Each extension should declare:

- foundation inputs: brand, voice, visual, content, outcomes
- brand-kit requirements: whether it needs `BRAND.md`, `DESIGN.md`, assets, or measured outcomes
- runtime owner: usually Studio, Forecast, or Measure
- output artifact or sidecar
- provider requirements
- fixture or smoke verification

## Studio Generation Modes

Use Studio for artifacts that need brand-safe rendering, review, or publishing:

| Mode | Output | Notes |
| --- | --- | --- |
| `social.post` | reviewed post variants and optional rendered asset | implemented |
| `blog.post` | outline and article draft | implemented |
| `og.cover` | 1200x630 cover image + sidecar | lab cover exists; promote when stable |
| `social.card` | static social image | lab render/card exists; promote when stable |
| `carousel` | multi-slide static story | natural next step before full video |
| `short.video` | vertical video draft | needs storyboard, asset generation, assembly |
| `ugc.ad` | multi-shot product/ad script and video | needs provider adapter and stitcher |
| `longform.script` | script, outline, shot plan | should precede long-form video rendering |
| `campaign.pack` | grouped assets across formats | should orchestrate smaller modes |

## Forecast Extensions

Use Forecast for prediction or risk probes:

- audience reaction
- likely objections
- channel fit
- creative variant risk
- message fatigue

## Measure Extensions

Use Measure for feedback loops:

- forecast vs actual calibration
- channel benchmarks
- creative pattern memory
- voice drift signals
- campaign outcome study
