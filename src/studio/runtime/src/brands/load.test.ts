import { mkdtempSync, mkdirSync, writeFileSync, rmSync, realpathSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'
import { afterEach, describe, expect, test } from 'vitest'
import { loadBrandFoundation } from './load'
import { resolveRuntimePaths } from '../core/paths'

const roots: string[] = []
const originalCwd = process.cwd()

const BRAND_MD = `---
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
  - 63 million Americans are caregivers.
pillars:
  - id: care-economy
    perspective: Caregiving is infrastructure and should be discussed as such.
    signals:
      - caregiver benefits
      - care deserts
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
`

const DESIGN_MD = `---
palette:
  background: "#FDF9EC"
  primary: "#3D1600"
  accent: "#FF9F00"
typography:
  headline: "Alegreya Variable, serif, bold"
  body: "Inter, sans-serif, regular"
logo: logo.png
layout: calm-editorial
video:
  textAlign: left
  contentRatio: 0.6
  entrance: spring
  timing: smooth
  texture:
    type: pencil-grid
    opacity: 0.04
---

## Style

Agnes Martin. Pale gesso ground with faint pencil lines.

## Composition

Horizontal bands of varying width. Quiet asymmetry in spacing.

## Texture

Gesso tooth on canvas. Graphite pencil lines.

## Avoid

Photography or photorealism. Bold saturated color.

## Motif

Horizontal bands and pencil grids on warm pale grounds.
`

function createWorkspace(): string {
  const root = mkdtempSync(join(tmpdir(), 'loom-brand-'))
  roots.push(root)
  mkdirSync(join(root, 'brands', 'givecare'), { recursive: true })
  writeFileSync(join(root, 'brands', 'givecare', 'brand.md'), BRAND_MD)
  writeFileSync(join(root, 'brands', 'givecare', 'design.md'), DESIGN_MD)
  return root
}

afterEach(() => {
  process.chdir(originalCwd)
  while (roots.length > 0) {
    rmSync(roots.pop()!, { recursive: true, force: true })
  }
})

describe('loadBrandFoundation', () => {
  test('loads brand identity from brand.md', () => {
    const root = createWorkspace()

    const brand = loadBrandFoundation('givecare', { root })

    expect(brand.id).toBe('givecare')
    expect(brand.channels.blog.objective).toContain('longform')
    expect(brand.responsePlaybooks).toHaveLength(1)
    expect(brand.pillars).toEqual([
      {
        id: 'care-economy',
        perspective: 'Caregiving is infrastructure and should be discussed as such.',
        signals: ['caregiver benefits', 'care deserts'],
        format: 'analysis',
        frequency: 'weekly',
      },
    ])
  })

  test('loads visual system from design.md', () => {
    const root = createWorkspace()

    const brand = loadBrandFoundation('givecare', { root })

    expect(brand.visual.palette.accent).toBe('#FF9F00')
    expect(brand.visual.logo).toBe('logo.png')
    expect(brand.visual.layout).toBe('calm-editorial')
    expect(brand.visual.typography?.headline).toContain('Alegreya')
    expect(brand.visual.style).toContain('Agnes Martin')
    expect(brand.visual.composition).toContain('Horizontal bands')
    expect(brand.visual.texture).toContain('Gesso')
    expect(brand.visual.negative).toContain('photorealism')
    expect(brand.visual.motif).toContain('pencil grids')
  })

  test('loads video props from design.md frontmatter', () => {
    const root = createWorkspace()

    const brand = loadBrandFoundation('givecare', { root })

    expect(brand.visual.video).toEqual({
      textAlign: 'left',
      contentRatio: 0.6,
      entrance: 'spring',
      timing: 'smooth',
      texture: { type: 'pencil-grid', opacity: 0.04 },
    })
  })

  test('falls back to default palette without design.md', () => {
    const root = createWorkspace()
    rmSync(join(root, 'brands', 'givecare', 'design.md'))

    const brand = loadBrandFoundation('givecare', { root })

    expect(brand.visual.palette.background).toBe('#FFFFFF')
    expect(brand.visual.video).toBeUndefined()
  })

  test('rejects unsupported handle keys', () => {
    const root = createWorkspace()
    writeFileSync(
      join(root, 'brands', 'givecare', 'brand.md'),
      BRAND_MD.replace('---\n', '---\nhandles:\n  mastodon: "@givecare"\n'),
    )

    expect(() => loadBrandFoundation('givecare', { root })).toThrow('handles.mastodon is not a supported platform')
  })

  test('resolves the workspace root when invoked from a subdirectory', () => {
    const root = createWorkspace()
    const agentDir = join(root, 'agent')
    mkdirSync(agentDir, { recursive: true })
    process.chdir(agentDir)

    const paths = resolveRuntimePaths()

    expect(paths.root).toBe(realpathSync(root))
    expect(paths.brandsDir).toBe(join(realpathSync(root), 'brands'))
  })
})
