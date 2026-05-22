import { existsSync, mkdirSync, writeFileSync } from 'fs'
import { join } from 'path'
import { loadBrandFoundation } from '../brands/load'
import { resolveRuntimePaths } from '../core/paths'

function validateBrandAssets(brand: ReturnType<typeof loadBrandFoundation>, brandsDir: string): { logo: 'not_set' | 'found' } {
  if (!brand.visual.logo) {
    return { logo: 'not_set' }
  }

  const logoPath = join(brandsDir, brand.id, brand.visual.logo)
  if (!existsSync(logoPath)) {
    throw new Error(`Brand asset missing: ${logoPath}`)
  }

  return { logo: 'found' }
}

function validateBrandKit(brand: ReturnType<typeof loadBrandFoundation>) {
  const visual = brand.visual
  const hasTypography = Boolean(
    visual.typography?.headline || visual.typography?.body || visual.typography?.accent,
  )
  const hasImageGrammar = Boolean(
    visual.imagePrompt || visual.imageStyle || visual.style || visual.motif,
  )
  const hasStyleProfiles = visual.styles.length > 0 && Boolean(visual.defaultStyle)
  const hasFidelityGates = (visual.fidelity?.gates.length ?? 0) > 0
  const hasLearningInputs = brand.proofPoints.length > 0 && brand.pillars.length > 0
  return {
    foundation_ready: true,
    production_ready: hasTypography && hasImageGrammar && hasStyleProfiles && hasFidelityGates && brand.pillars.length > 0,
    learning_ready: hasLearningInputs,
    design: visual.designSource ? 'found' : 'embedded_or_default',
    visual: {
      palette: 'set',
      typography: hasTypography ? 'set' : 'not_set',
      image_grammar: hasImageGrammar ? 'set' : 'not_set',
      default_style: visual.defaultStyle ?? null,
      style_profiles: visual.styles.length,
      negative_prompts: visual.negative?.length ?? 0,
      composition_rules: visual.composition?.length ?? 0,
    },
    fidelity: {
      source: visual.fidelity?.sourceUrl ?? 'not_set',
      source_type: visual.fidelity?.sourceType ?? null,
      viewports: visual.fidelity?.viewports.length ?? 0,
      evidence_items: visual.fidelity?.evidence.length ?? 0,
      gates: visual.fidelity?.gates.length ?? 0,
      measured_ready: hasFidelityGates ? 'set' : 'not_set',
    },
    content: {
      pillars: brand.pillars.length,
      proof_points: brand.proofPoints.length,
      offers: brand.offers.length,
      response_playbooks: brand.responsePlaybooks.length,
    },
    quality_loop: {
      review_required: brand.policy.humanRequiredActions.length > 0,
      can_emit_run_result: true,
      can_feed_measure: true,
    },
  }
}

const TEMPLATE = `---
name: __NAME__
positioning: Replace with the sharpest explanation of the brand.
voice:
  tone: [direct, specific]
  style: [plainspoken, credible]
  do:
    - Say the real thing plainly.
  dont:
    - Hide behind generic positioning.
audience:
  primary: Replace with the core audience.
message:
  proof_points:
    - Replace with one concrete proof point.
topics:
  pillars:
    - id: primary-theme
      angle: Replace with the recurring angle this brand should own.
      signals:
        - Replace with one signal to monitor.
      formats: [opinionated-take]
behavior:
  engage:
    - Inbound questions.
  escalate:
    - Legal, safety, or confidential matters.
  channels:
    linkedin:
      primary_job: Build signal and authority.
safety:
  delegation:
    human_required:
      - legal_or_safety_claims
---

## Overview

Replace with the brand behavior rationale.
`

const DESIGN_TEMPLATE = `---
design_system:
  name: "Replace With Brand Name"
  version: "1.0.0"
  description: "Replace with the visual system this file is meant to reproduce."
tokens:
  colors:
    primary: "#FF9F00"
    secondary: "#6E5A43"
    accent: "#FFEEE1"
    background: "#FDF9EC"
    surface: "#F8F1E6"
    text: "#3D1600"
  typography:
    font_family: "Alegreya, Georgia, serif"
    headline: "Alegreya, Georgia, serif"
    body: "Inter, system-ui, sans-serif"
    accent: "JetBrains Mono, ui-monospace, monospace"
    scale:
      h1: { size: "3rem", weight: 400, line_height: 1.0 }
      body: { size: "1rem", weight: 400, line_height: 1.6 }
      label: { size: "0.72rem", weight: 500, line_height: 1.2 }
  rounded:
    small: "4px"
    medium: "8px"
    large: "16px"
  spacing:
    unit: 4
    scale:
      xs: 1
      sm: 2
      md: 4
      lg: 6
      xl: 10
components:
  Button:
    description: "Rounded action button using semantic color tokens."
    variants:
      primary:
        background: "primary"
        color: "text"
        rounded: "large"
        padding: "sm md"
  Card:
    description: "Artifact container for social cards and covers."
    variants:
      editorial:
        background: "background"
        color: "text"
        rounded: "medium"
agentcy:
  source:
    type: authored
    url: ""
    captured_at: ""
    viewports:
      - desktop 1440x900
      - mobile 390x844
    evidence:
      - Replace with a concrete source observation, screenshot, or measured style signal.
  visual:
    default_style: editorial
    motif: "Replace with the recurring visual motif."
    image_style: "Replace with the generated-image art direction."
    image_prompt: "Background only for [SUBJECT]. No text, no logos, no watermarks."
    composition:
      - Replace with one repeatable composition rule.
    negative:
      - text
      - logos
      - watermarks
  artifacts:
    social_card:
      renderer: satori-design-card
      styles:
        editorial:
          density: medium
          tone: "Replace with the default artifact mood."
          description: "Default social card style. Style controls tokens and tone, not layout."
  fidelity:
    mode: manual_until_extracted
    gates:
      - Rendered artifacts must use only semantic token colors from this DESIGN.md unless an asset supplies imagery.
      - Typography roles must map to the listed headline, body, and accent families.
      - Layout must match the selected artifact style profile; do not silently fall back to generic defaults.
      - Generated backgrounds must not contain text, logos, watermarks, or UI chrome.
---

## Overview

Replace with the target visual experience in one paragraph.

## Design Tokens

Explain why the token values above are the canonical visual system.

## Components

Define component anatomy, states, responsive behavior, overflow behavior, and accessibility.

## Usage Guidelines

Explain how source patterns become cards, covers, carousels, scripts, or videos.

## Accessibility

Document contrast, type sizing, focus, motion, and reduced-motion expectations.

## Examples

Replace with source screenshots, URLs, viewport sizes, computed colors, type samples, and repeated component patterns. A DESIGN.md that cannot point to evidence is concept art, not a reproducible visual system.

## Quality Gates

List pass/fail checks for color, typography, layout, accessibility, and artifact-specific constraints.
`

function displayNameFromId(id: string): string {
  return id
    .split(/[-_]/g)
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(' ')
}

export function runBrandCommand(args: string[], root?: string): unknown {
  const [subcommand, brandId] = args
  const paths = resolveRuntimePaths(root)

  if (subcommand === 'init') {
    if (!brandId) {
      throw new Error('Usage: brand init <id>')
    }
    const dir = join(paths.brandsDir, brandId)
    const brandPath = join(dir, 'BRAND.md')
    const designPath = join(dir, 'DESIGN.md')
    if (existsSync(brandPath)) {
      throw new Error(`Brand already exists: ${brandPath}`)
    }
    mkdirSync(dir, { recursive: true })
    const name = displayNameFromId(brandId)
    writeFileSync(
      brandPath,
      TEMPLATE.replaceAll('__ID__', brandId).replaceAll('__NAME__', name),
      'utf8',
    )
    writeFileSync(designPath, DESIGN_TEMPLATE, 'utf8')
    return { id: brandId, path: brandPath, designPath }
  }

  if (subcommand === 'show') {
    if (!brandId) {
      throw new Error('Usage: brand show <id>')
    }
    return loadBrandFoundation(brandId, { root: paths.root })
  }

  if (subcommand === 'validate') {
    if (!brandId) {
      throw new Error('Usage: brand validate <id>')
    }
    const brand = loadBrandFoundation(brandId, { root: paths.root })
    return {
      valid: true,
      brand: brand.id,
      checks: {
        assets: validateBrandAssets(brand, paths.brandsDir),
        kit: validateBrandKit(brand),
        pillars: brand.pillars.length,
      },
    }
  }

  throw new Error('Usage: brand <init|show|validate> ...')
}
