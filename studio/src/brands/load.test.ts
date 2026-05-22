import { mkdtempSync, mkdirSync, writeFileSync, rmSync, realpathSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'
import { afterEach, describe, expect, test } from 'vitest'
import { loadBrandFoundation } from './load'
import { resolveRuntimePaths } from '../core/paths'

const roots: string[] = []
const originalCwd = process.cwd()

function createWorkspace(): string {
  const root = mkdtempSync(join(tmpdir(), 'studio-brand-'))
  roots.push(root)
  mkdirSync(join(root, 'brands', 'givecare'), { recursive: true })
  writeFileSync(
    join(root, 'brands', 'givecare', 'BRAND.md'),
    `
---
name: GiveCare
positioning: Care as infrastructure.
voice:
  tone: [warm, direct, specific]
  style: [human, plainspoken]
  do:
    - Name the problem directly.
  dont:
    - Use therapeutic cliches.
audience:
  segments:
    - id: caregivers
      description: Family caregivers balancing work and care.
message:
  proof_points:
    - 63 million Americans are caregivers.
topics:
  pillars:
    - id: care-economy
      angle: Caregiving is infrastructure and should be discussed as such.
      signals:
        - caregiver benefits
        - care deserts
      formats: [analysis]
      frequency: weekly
behavior:
  engage:
    - Inbound skepticism.
  escalate:
    - Legal or safety concerns.
  channels:
    linkedin:
      primary_job: Build signal and authority.
---

## Overview
Caregiving is infrastructure.
`.trim(),
  )
  return root
}

afterEach(() => {
  process.chdir(originalCwd)
  while (roots.length > 0) {
    rmSync(roots.pop()!, { recursive: true, force: true })
  }
})

describe('loadBrandFoundation', () => {
  test('loads a first-principles brand foundation from BRAND.md', () => {
    const root = createWorkspace()

    const brand = loadBrandFoundation('givecare', { root })

    expect(brand.id).toBe('givecare')
    expect(brand.channels.blog.objective).toContain('durable')
    expect(brand.responsePlaybooks).toHaveLength(1)
    expect(brand.pillars).toEqual([
      {
        id: 'care-economy',
        perspective: 'Caregiving is infrastructure and should be discussed as such.',
        signals: ['caregiver benefits', 'care deserts'],
        format: 'analysis',
        frequency: 'weekly',
        defaultFormat: 'analysis',
      },
    ])
  })

  test('loads an agent-facing BRAND.md behavioral contract', () => {
    const root = mkdtempSync(join(tmpdir(), 'studio-brand-md-'))
    roots.push(root)
    mkdirSync(join(root, 'brands', 'givecare'), { recursive: true })
    writeFileSync(
      join(root, 'brands', 'givecare', 'BRAND.md'),
      `
---
name: GiveCare
positioning: "AI caregiving coordination that reduces caregiver burnout"
archetype: caregiver
voice:
  tone: [warm, authoritative]
  style: [plainspoken, evidence-based]
  do:
    - Acknowledge before advising.
  dont:
    - Use generic wellness language.
message:
  proof_points:
    - 63 million Americans provide unpaid care.
audience:
  primary: Adult children managing care remotely.
  segments:
    - id: distant-child
      description: Working professional managing care from another city.
      pain: Coordination overhead.
      goal: Feel in control.
topics:
  pillars:
    - id: coordination-gap
      angle: "The problem is not love — it is logistics"
      signals:
        - care coordination
      formats: [statement card]
      frequency: weekly
behavior:
  engage:
    - Inbound questions about caregiving logistics.
  escalate:
    - Medical or safety claims.
  channels:
    linkedin:
      primary_job: Authority building and partner credibility.
      default_cta: Learn more.
visual:
  palette:
    primary: "#FF8600"
    secondary: "#632405"
    accent: "#3BDF89"
    background: "#FFF7ED"
    text: "#3F0F00"
---

## Overview

GiveCare should execute with practical care.
`.trim(),
      'utf8',
    )

    const brand = loadBrandFoundation('givecare', { root })

    expect(brand.id).toBe('givecare')
    expect(brand.voice.tone).toBe('warm, authoritative')
    expect(brand.channels.social.objective).toContain('Authority')
    expect(brand.proofPoints).toEqual(['63 million Americans provide unpaid care.'])
    expect(brand.policy.escalationRules).toEqual(['Medical or safety claims.'])
    expect(brand.visual.palette).toMatchObject({
      background: '#FFF7ED',
      primary: '#FF8600',
      secondary: '#632405',
      accent: '#3BDF89',
      text: '#3F0F00',
    })
    expect(brand.pillars[0]).toMatchObject({
      id: 'coordination-gap',
      perspective: 'The problem is not love — it is logistics',
      format: 'statement card',
      frequency: 'weekly',
    })
    expect(brand.responsePlaybooks[0]?.trigger).toBe('Inbound questions about caregiving logistics.')
  })

  test('loads DESIGN.md as a visual-system supplement over BRAND.md defaults', () => {
    const root = createWorkspace()
    writeFileSync(
      join(root, 'brands', 'givecare', 'BRAND.md'),
      `
---
name: GiveCare
positioning: Care as infrastructure.
voice:
  tone: [warm, direct]
  style: [plainspoken]
  do:
    - Name the problem directly.
  dont:
    - Use generic wellness language.
audience:
  primary: Family caregivers.
message:
  proof_points:
    - Caregiving is operational work.
topics:
  pillars:
    - id: care-economy
      angle: Caregiving is infrastructure.
      signals:
        - caregiver benefits
visual:
  palette:
    background: "#FFFFFF"
    primary: "#111111"
    accent: "#FF6600"
---

## Overview
Caregiving is infrastructure.
`.trim(),
      'utf8',
    )
    writeFileSync(
      join(root, 'brands', 'givecare', 'DESIGN.md'),
      `
---
design_system:
  name: "GiveCare"
  version: "1.0.0"
  description: "Warm editorial care infrastructure system."
tokens:
  colors:
    background: "#FDF9EC"
    primary: "#3D1600"
    accent: "#FF9F00"
    text: "#3D1600"
  typography:
    font_family: "Alegreya, Georgia, serif"
    headline: "Alegreya, Georgia, serif"
    body: "Inter, sans-serif"
    accent: "JetBrains Mono, monospace"
components:
  Card:
    description: "Editorial social card shell."
agentcy:
  source:
    type: extracted
    url: "https://example.com"
    captured_at: "2026-05-22"
    viewports:
      - desktop 1440x900
    evidence:
      - computed colors and typography from live site
  visual:
    default_style: editorial-care
    motif: editorial care infrastructure
    image_style: warm editorial abstraction
    image_prompt: "Background only for [SUBJECT]. No text, no logos."
    composition:
      - Left-aligned type with open right-side art space.
    negative:
      - text
      - logos
  artifacts:
    social_card:
      styles:
        editorial-care:
          density: medium
        campaign-bold:
          density: low
          palette:
            background: "#3D1600"
            text: "#FDF9EC"
            accent: "#FF9F00"
  fidelity:
    gates:
      - Render with extracted tokens only.
      - Fail unknown styles.
---

## Design System
Warm editorial system.
`.trim(),
      'utf8',
    )

    const brand = loadBrandFoundation('givecare', { root })

    expect(brand.visual.designSource).toMatch(/brands\/givecare\/DESIGN\.md$/)
    expect(brand.visual.palette).toMatchObject({
      background: '#FDF9EC',
      primary: '#3D1600',
      text: '#3D1600',
    })
    expect(brand.visual.typography).toMatchObject({
      headline: 'Alegreya, Georgia, serif',
      body: 'Inter, sans-serif',
      accent: 'JetBrains Mono, monospace',
    })
    expect(brand.visual.motif).toBe('editorial care infrastructure')
    expect(brand.visual.imageStyle).toBe('warm editorial abstraction')
    expect(brand.visual.imagePrompt).toContain('Background only')
    expect(brand.visual.composition).toEqual(['Left-aligned type with open right-side art space.'])
    expect(brand.visual.negative).toEqual(['text', 'logos'])
    expect(brand.visual.defaultStyle).toBe('editorial-care')
    expect(brand.visual.fidelity).toMatchObject({
      sourceType: 'extracted',
      sourceUrl: 'https://example.com',
      viewports: ['desktop 1440x900'],
      evidence: ['computed colors and typography from live site'],
      gates: ['Render with extracted tokens only.', 'Fail unknown styles.'],
    })
    expect(brand.visual.styles).toMatchObject([
      {
        id: 'editorial-care',
        density: 'medium',
      },
      {
        id: 'campaign-bold',
        density: 'low',
        palette: {
          background: '#3D1600',
          text: '#FDF9EC',
          accent: '#FF9F00',
        },
      },
    ])
  })

  test('loads a direct .brand.md file path', () => {
    const root = mkdtempSync(join(tmpdir(), 'studio-brand-path-'))
    roots.push(root)
    const filePath = join(root, 'scty.brand.md')
    writeFileSync(
      filePath,
      `
---
name: SCTY
positioning: "AI systems studio building infrastructure for intelligent organizations"
voice:
  tone: [precise, direct]
  style: [technical, evidence-first]
  do:
    - State the claim before the evidence.
  dont:
    - Use hype.
audience:
  primary: Technical and operational leaders.
topics:
  pillars:
    - id: systems-thinking
      angle: "AI problems are systems problems"
      signals:
        - AI systems design
      formats: [thread]
---

## Overview
SCTY is direct and systems-oriented.
`.trim(),
      'utf8',
    )

    const brand = loadBrandFoundation(filePath, { root })

    expect(brand.id).toBe('scty')
    expect(brand.name).toBe('SCTY')
    expect(brand.pillars[0]?.defaultFormat).toBe('thread')
  })

  test('rejects unsupported handle keys', () => {
    const root = createWorkspace()
    writeFileSync(
      join(root, 'brands', 'givecare', 'BRAND.md'),
      `
---
name: GiveCare
positioning: Care as infrastructure.
voice:
  tone: [warm, direct, specific]
  style: [human, plainspoken]
  do:
    - Name the problem directly.
  dont:
    - Use therapeutic cliches.
topics:
  pillars:
    - id: care-economy
      angle: Caregiving is infrastructure and should be discussed as such.
      signals:
        - caregiver benefits
handles:
  mastodon: '@givecare'
---

## Overview
Bad handle example.
`.trim(),
      'utf8',
    )

    expect(() => loadBrandFoundation('givecare', { root })).toThrow('Invalid BRAND.md: handles.mastodon is not a supported platform')
  })

  test('resolves the workspace root when invoked from the agent directory', () => {
    const root = createWorkspace()
    const agentDir = join(root, 'agent')
    mkdirSync(agentDir, { recursive: true })
    process.chdir(agentDir)

    const paths = resolveRuntimePaths()

    expect(paths.root).toBe(realpathSync(root))
    expect(paths.brandsDir).toBe(join(realpathSync(root), 'brands'))
  })
})
