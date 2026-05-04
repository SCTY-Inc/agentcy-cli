---
name: GiveCare
version: "1.0"

grounds:
  cream:    { bg: "#FDF9EC", fg: "#3D1600", dark: false }
  warm:     { bg: "#F0DCC0", fg: "#3D1600", dark: false }
  slate:    { bg: "#E8E6E1", fg: "#1C1C1C", dark: false }
  sage:     { bg: "#E4E8DC", fg: "#2A3328", dark: false }
  grounded: { bg: "#3D1600", fg: "#FDF9EC", dark: true }
  mute:     { bg: "#1A0A00", fg: "#FDF9EC", dark: true }
  ink:      { bg: "#1C1C1C", fg: "#E8E6E1", dark: true }
  dusk:     { bg: "#2C2438", fg: "#E8E0F0", dark: true }
  dawn:     { bg: "#FFF5E6", fg: "#3D1600", dark: false, gradient: { from: "#FFF5E6", to: "#F0D4C0", angle: 170 } }
  ember:    { bg: "#3D1600", fg: "#FDF9EC", dark: true,  gradient: { from: "#3D1600", to: "#5C2800", angle: 160 } }
  fog:      { bg: "#F2F0ED", fg: "#1C1C1C", dark: false, gradient: { from: "#F2F0ED", to: "#D4D0CA", angle: 180 } }
  storm:    { bg: "#1C1C1C", fg: "#E8E6E1", dark: true,  gradient: { from: "#1C1C1C", to: "#2A2A30", angle: 160 } }

typography:
  scale: sqrt2
  baseUnit: "1% of canvas width"
  families:
    display: "Alegreya, Georgia, serif"
    mono: "JetBrains Mono, monospace"
    body: "Inter, sans-serif"
  roles:
    eyebrow:  { family: mono,    weight: 500, transform: uppercase, letterSpacing: "0.15em" }
    headline: { family: display, weight: 400 }
    body:     { family: body,    weight: 400 }
    stat:     { family: mono,    weight: 400 }
    label:    { family: body,    weight: 500, transform: uppercase, letterSpacing: "0.10em" }
    quote:    { family: display, weight: 400, style: italic }
    brand:    { family: mono,    weight: 500, transform: uppercase, letterSpacing: "0.15em" }

spacing:
  system: renner
  ratios: [2, 3, 4, 6]
  note: "inner:top:outer:bottom — multiply by 2× base type unit"

layout:
  textAreaFraction: 0.625
  opticalCenterFraction: 0.375
  textFloorFraction: 0.83

platforms:
  linkedin:  { w: 1200, h: 1200, label: "LinkedIn 1:1" }
  twitter:   { w: 1600, h: 900,  label: "Twitter 16:9" }
  instagram: { w: 1080, h: 1350, label: "Instagram 4:5" }
  facebook:  { w: 1200, h: 1200, label: "Facebook 1:1" }
  threads:   { w: 1080, h: 1350, label: "Threads 4:5" }
  story:     { w: 1080, h: 1920, label: "Story 9:16" }

figures: [statement, stat, passage, index]
gravities: [high, center, low]
---

## Overview

GiveCare is a warm, editorial brand rooted in caregiving. The visual system is print-quality — it borrows from magazine typography and applies strict typographic rules so that cards feel considered, not generated.

Pipeline: agent selects ground + figure + gravity based on content tone → Gemini generates background art (right panel, no text, no logos) → Satori renders typographic layer deterministically on top.

## Colors

**Grounds** are bg/fg pairs. Never mix bg from one ground with fg from another. The `dark` flag controls whether to use light or dark color mixing for muted tones.

- Default editorial: `cream`
- High-urgency or campaign: `grounded` or `ember`
- Data-forward: `slate` or `fog`
- Avoid `dusk` for text-heavy layouts — low contrast for body copy

Agent guidance: match ground warmth to content tone. Caregiving content skews warm (cream, warm, grounded). Metric/data content skews neutral (slate, fog, ink).

## Typography

**Scale:** √2 modular (ratio ≈1.414) from base = 1% of canvas width × 1.2. Step 0 = eyebrow/label. Step 1 = body. Step 3 = passage/index. Step 5 = headline. Step 7 = stat number.

Rules that are never broken:
- Alegreya for display/editorial only. Never for UI labels or data.
- JetBrains Mono for eyebrows, stat numbers, brand marks, and monospaced data only.
- Inter for body copy only.
- Eyebrows and labels: always uppercase with letter-spacing (Hochuli rule for small text readability).
- Leading: 1.2× for display (headlines), 1.5× for body.

## Layout

Text occupies the left 5/8 of canvas (Hochuli/Kinross text-area rule). Right 3/8 is the art zone — the Gemini-generated background is visible here. The left panel background is always the solid (or gradient) ground color — never transparent over the art.

Optical center: 3/8 from top, not mathematical center. `gravity: center` anchors here. `gravity: high` anchors at top margin. `gravity: low` anchors at ~45% from top.

Margins: Renner ratios 2:3:4:6 (inner:top:outer:bottom), scaled from base unit = 2× base type size.

Brand mark sits at the bottom of the text panel, always.

## Figures

- **statement**: Large Alegreya headline + body copy. Use for insights, opinions, positioning claims. Most common.
- **stat**: Large mono number + uppercase label + context body. Use for metrics, proof points, data storytelling.
- **passage**: Opening quote mark + italic Alegreya quote body. Use for testimonials, founder voice, community stories.
- **index**: Divider-separated list items in Alegreya. Use for frameworks, steps, listicles. Max 5 items.

Agent guidance: match figure to content structure. A sentence → statement. A number with context → stat. A quote → passage. A list → index.

## Generative Art

Prompt must include: brand palette colors, topic keyword, and explicit negatives ("no text, no logos, no watermarks"). Style should be abstract/painterly to complement rather than compete with typography.

When IMAGE_PROVIDER is unset or no API key is available, the card renders with solid ground color and optional gradient only — a clean, acceptable fallback for development.
