# DESIGN.md Fidelity Contract

Agentcy `DESIGN.md` files follow the public Google `design.md` shape: YAML front matter first, Markdown guidance second. The core fields are `design_system`, `tokens`, and `components`. Agentcy-specific execution rules live under `agentcy` so the file stays portable instead of becoming a private schema.

The useful lesson from browser extractors such as `bergside/design-md-chrome` is the sequence:

1. Extract visible DOM, screenshots, assets, and computed styles from a real source.
2. Normalize repeated values into semantic tokens.
3. Infer reusable component and layout patterns from evidence.
4. Map those patterns to artifact types such as cards, covers, carousels, and video frames.
5. Validate output against explicit pass/fail gates.

A hand-authored `DESIGN.md` is allowed, but it must label itself as authored. It is not a fidelity source until it carries measured evidence from a site, screenshot, Figma frame, or reference capture.

## Required Shape

```yaml
design_system:
  name: "Brand Name"
  version: "1.0.0"
  description: "Visual system to reproduce."
tokens:
  colors:
    primary: "#FF8600"
    secondary: "#632405"
    accent: "#FFEEE1"
    background: "#FFF7ED"
    surface: "#FDF4E7"
    text: "#3F0F00"
  typography:
    font_family: "Alegreya, Georgia, serif"
    headline: "Alegreya, Georgia, serif"
    body: "Alegreya, Georgia, serif"
    accent: "JetBrains Mono, ui-monospace, monospace"
  rounded:
    small: "4px"
    medium: "10px"
    large: "18px"
  spacing:
    unit: 4
    scale:
      sm: 2
      md: 4
      lg: 6
components:
  Button:
    description: "Primary action button."
    variants:
      primary:
        background: "primary"
        color: "text"
        rounded: "large"
agentcy:
  source:
    type: extracted
    url: "https://example.com"
    captured_at: "2026-05-22"
    viewports:
      - mobile 430px
    evidence:
      - measured color, type, and layout observation
  visual:
    default_style: editorial
    motif: "recurring visual motif"
    image_prompt: "Background only for [SUBJECT]. No text, no logos."
  artifacts:
    social_card:
      styles:
        editorial:
          density: medium
          description: "Style controls tokens and tone, not layout."
  fidelity:
    gates:
      - pass/fail rule
```

## What Must Be Explicit

- Source: where the visual system came from, when captured, and at what viewport.
- Evidence: observations that justify tokens and component patterns.
- Tokens: semantic colors, typography roles, spacing, radius, and motion.
- Components: anatomy, variants, states, overflow, responsive behavior, and accessibility.
- Artifact mappings: which output formats exist for cards, covers, carousels, scripts, or videos.
- Fidelity gates: concrete checks that make drift visible before an artifact ships.

## Studio Mapping

Studio reads official `tokens.colors` and `tokens.typography` as the canonical visual tokens.

Agentcy execution fields are:

- `agentcy.visual.default_style` for the default renderer profile
- `agentcy.visual.image_prompt`, `composition`, and `negative` for generation constraints
- `agentcy.artifacts.social_card.styles` for token and tone profiles
- `agentcy.fidelity.gates` for validation readiness

Unknown style profiles must fail. Style profiles must not select unrelated hardcoded layouts.

## Quality Bar

To claim 1:1 reproduction, the kit needs measured source evidence plus visual QA. At minimum:

- token colors match the source palette
- type roles map to the source families, weights, line heights, and tracking
- spacing and layout measurements are within declared tolerance
- required component states are covered
- rendered artifact screenshots are reviewed against the source or reference frame
- generated media cannot contain text, logos, watermarks, people, or UI chrome unless explicitly required

Until screenshot diff or perceptual comparison is wired into CI, call this "measured source ready," not 1:1.
