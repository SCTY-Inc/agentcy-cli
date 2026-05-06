import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'
import { afterEach, describe, expect, test } from 'vitest'
import { loadBrandFoundation } from '../brands/load'
import { buildCardLabHtml } from './build'

const roots: string[] = []

function createWorkspace(): string {
  const root = mkdtempSync(join(tmpdir(), 'loom-lab-'))
  roots.push(root)
  mkdirSync(join(root, 'brands', 'givecare'), { recursive: true })
  writeFileSync(
    join(root, 'brands', 'givecare', 'logo.png'),
    Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wn7n6cAAAAASUVORK5CYII=', 'base64'),
  )
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
    'utf8',
  )
  return root
}

afterEach(() => {
  while (roots.length > 0) {
    rmSync(roots.pop()!, { recursive: true, force: true })
  }
})

describe('buildCardLabHtml', () => {
  test('builds a self-contained interactive card lab document', () => {
    const root = createWorkspace()
    const brand = loadBrandFoundation('givecare', { root })

    const html = buildCardLabHtml({
      brand,
      brandAssetBasePath: join(root, 'brands', 'givecare'),
      initialCardType: 'quote',
      initialHeadline: 'Care is infrastructure',
      initialBody: 'Invisible labor should be visible labor.',
      initialPlatform: 'linkedin',
    })

    expect(html).toContain('<title>GiveCare Card Lab</title>')
    expect(html).toContain('Generate 20 Variations')
    expect(html).toContain('Head to head')
    expect(html).toContain('Choose between two directions')
    expect(html).toContain('Prefer left')
    expect(html).toContain('Current leaning')
    expect(html).toContain('Care is infrastructure')
    expect(html).toContain('brand-mark')
    expect(html).toContain('Copy top preset JSON')
  })
})
