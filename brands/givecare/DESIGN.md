---
design_system:
  name: "GiveCare"
  version: "1.0.0"
  description: "Mobile-first editorial care support system extracted from givecareapp.com."
tokens:
  colors:
    primary: "#FF8600"
    secondary: "#632405"
    accent: "#FFEEE1"
    background: "#FFF7ED"
    surface: "#FDF4E7"
    text: "#3F0F00"
    muted: "#F9EDDD"
    muted_text: "#80421A"
    border: "#F4E6D2"
    signal: "#3BDF89"
    logo: "#54340E"
  typography:
    font_family: "\"Alegreya Variable\", \"Alegreya\", \"Alegreya Fallback\", Georgia, serif"
    headline: "\"Alegreya Variable\", \"Alegreya\", \"Alegreya Fallback\", Georgia, serif"
    body: "\"Alegreya Variable\", \"Alegreya\", \"Alegreya Fallback\", Georgia, serif"
    accent: "\"JetBrains Mono\", ui-monospace, monospace"
    display: "\"Gabarito\", \"Gabarito Fallback\", sans-serif"
    scale:
      hero: { size: "clamp(3rem, 13vw, 3.5rem)", weight: 400, line_height: 0.94, letter_spacing: "-0.055em" }
      h1: { size: "clamp(3rem, 13vw, 3.5rem)", weight: 400, line_height: 0.94, letter_spacing: "-0.055em" }
      h2: { size: "clamp(2.05rem, 8.5vw, 2.6rem)", weight: 400, line_height: 1.05, letter_spacing: "-0.035em" }
      body: { size: "1.05rem", weight: 400, line_height: 1.75 }
      label: { size: "0.68rem", weight: 500, line_height: 1.4, letter_spacing: "0.16em" }
      nav: { size: "0.66rem", weight: 500, line_height: 1.2, letter_spacing: "0.14em" }
  rounded:
    small: "4px"
    medium: "10px"
    large: "18px"
    full: "9999px"
  spacing:
    unit: 4
    scale:
      xs: 1
      sm: 2
      md: 4
      lg: 5
      xl: 8
      section: 12
  motion:
    default_duration: "150ms"
    rise_duration: "560ms"
    easing: "cubic-bezier(.23, 1, .32, 1)"
components:
  Shell:
    description: "Centered mobile-first page shell."
    variants:
      default:
        background: "background"
        color: "text"
        max_width: "430px"
        min_height: "100vh"
  Header:
    description: "Sticky narrow header with thin bottom rule and blurred cream surface."
    variants:
      default:
        background: "background"
        border_color: "border"
        height: "3.5rem"
        text_transform: "uppercase"
  Hero:
    description: "Large serif editorial statement with tight tracking and calm support copy."
    variants:
      home:
        heading: "hero"
        body: "body"
        spacing: "section"
  Button:
    description: "Pill action button with mono uppercase label."
    variants:
      primary:
        background: "text"
        color: "background"
        rounded: "full"
        padding: "sm lg"
      secondary:
        background: "transparent"
        color: "text"
        border_color: "border"
        rounded: "full"
  Kicker:
    description: "Small mono uppercase section label with wide tracking."
    variants:
      default:
        typography: "label"
        color: "muted_text"
  DotMatrix:
    description: "Small operational signal field used as quiet motion and loading texture."
    variants:
      signal:
        color: "signal"
        density: "low"
agentcy:
  source:
    type: extracted
    url: "https://givecareapp.com"
    captured_at: "2026-05-22"
    assets:
      - "/assets/editorial-Bc1RH6cj.css"
      - "/assets/site-ByNhV3Tj.css"
      - "/fonts/alegreya-latin-wght-normal.woff2"
      - "/fonts/gabarito-latin-400-normal.woff2"
      - "/gc.svg"
      - "/og-image.webp"
    viewports:
      - mobile shell max-width 430px
      - desktop page still centered at 430px
      - social card 1200x630 derived from site tokens
    evidence:
      - "Body uses bg-background and text-foreground with a centered max-width 430px site shell."
      - "Hero type uses Alegreya serif, clamp(3rem, 13vw, 3.5rem), line-height .94, tracking -.055em."
      - "Section labels and nav use mono uppercase labels around .66-.68rem with .14-.16em tracking."
      - "Primary CTA uses a full pill shape, dark text token fill, cream text, and mono uppercase labeling."
      - "CSS variables define warm cream, clay, orange, border, muted, and green signal tokens rather than teal or clinical blue."
  visual:
    logo: "assets/gc.svg"
    default_style: givecare-site-card
    motif: "warm narrow editorial care interface with operational signal details"
    image_style: "cream paper, clay text, orange action accent, sparse green signal dots, mobile editorial composition"
    image_prompt: "Warm cream editorial background for [SUBJECT]. Clay typography space, orange action accent, sparse green signal dots, mobile care-operations mood. Background only. No text, no logos, no watermarks, no people, no UI chrome."
    composition:
      - "Keep the composition narrow and centered, derived from the 430px site shell."
      - "Use a large serif statement, compact mono label, thin rules, and generous cream negative space."
      - "Use orange as the primary action accent and clay brown for text and structure."
      - "Use green only as a small signal detail, never as the dominant brand color."
      - "Cards must reserve fixed text boxes so headlines wrap instead of overlapping or clipping."
    texture:
      - "warm cream page surface"
      - "thin editorial border rules"
      - "sparse signal-dot detail"
    negative:
      - "text in generated backgrounds"
      - "logos in generated backgrounds"
      - "watermarks"
      - "stock-photo caregiving scenes"
      - "medical clip art"
      - "generic teal healthcare palette"
      - "dark navy dashboard palette"
      - "purple or neon gradients"
  artifacts:
    social_card:
      renderer: satori-design-card
      required_tokens:
        - colors.background
        - colors.primary
        - colors.secondary
        - colors.accent
        - colors.text
        - typography.headline
        - typography.body
        - typography.accent
      styles:
        givecare-site-card:
          density: medium
          tone: "warm, direct, operational"
          texture: "cream page with thin rules and signal dots"
          palette:
            background: "#FFF7ED"
            primary: "#632405"
            secondary: "#80421A"
            accent: "#FF8600"
            text: "#3F0F00"
          description: "Default card derived from the GiveCare site: narrow editorial statement, mono label, orange action accent, and small signal detail."
          must:
            - "Use cream as the dominant field."
            - "Keep all text local, crisp, and aligned to a clear vertical grid."
            - "Do not use teal as a primary brand color."
  fidelity:
    mode: measured_source_ready
    gates:
      - "Rendered artifacts must use the extracted warm cream, clay, orange, muted, border, and signal tokens from this DESIGN.md."
      - "Typography roles must map to Alegreya serif for headline and body, JetBrains Mono for labels, and Gabarito only for display accents when explicitly needed."
      - "Layouts must preserve the narrow editorial shell, large serif statement, mono uppercase label, and thin-rule hierarchy."
      - "Unknown style profiles must fail instead of falling back to a generic renderer style."
      - "No card may contain overlapping text, clipped CTA text, or text that exits its reserved panel."
      - "Generated backgrounds must not contain text, logos, watermarks, people, UI chrome, medical clip art, teal healthcare defaults, or dark dashboard palettes."
---

# Overview

GiveCare feels like a calm mobile editorial product for care coordination, not a generic healthcare SaaS dashboard. The source site is narrow, warm, text-led, and operational: large serif statements, compact mono labels, cream surfaces, clay text, orange action accents, and small green signal details.

## Design Tokens

The token set is extracted from `https://givecareapp.com` CSS variables and visible component classes. The source palette is warm cream and clay, with orange as the action color and green as a small signal color. Teal and generic blue are not part of the observed brand system.

## Components

The important reusable components are the centered 430px shell, sticky header, oversized serif hero, mono uppercase kicker, pill CTA, thin editorial rules, and sparse signal-dot motif. Studio artifacts should translate those patterns into platform-specific output sizes instead of inventing layout families.

## Usage Guidelines

For social cards and covers, start from `givecare-site-card`. Platform output formats such as LinkedIn square, X/Twitter landscape, and Instagram portrait may change dimensions, but they must not switch to unrelated split panels, posters, reports, or other hardcoded layout types. If an artifact cannot preserve the source hierarchy at its target size, reduce copy before changing the visual system.

## Accessibility

Keep body copy large enough for mobile reading, preserve high contrast between clay text and cream backgrounds, disable decorative motion for reduced-motion contexts, and avoid placing text over generated imagery. Mono uppercase labels should stay short because tracking is wide.

## Examples

The canonical source example is the GiveCare homepage at `https://givecareapp.com`. Its first viewport establishes the brand: centered narrow mobile shell, sticky cream header, large serif headline, warm clay text, orange/dark pill actions, and signal-dot operational details.

## Quality Gates

A generated artifact is acceptable only when it visibly matches the extracted source system: warm cream field, clay text, orange action accent, serif editorial hierarchy, mono labels, narrow-shell composition, and no overlapping or clipped text.
