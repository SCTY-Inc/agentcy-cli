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
    return { id: brandId, path: brandPath }
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
        pillars: brand.pillars.length,
      },
    }
  }

  throw new Error('Usage: brand <init|show|validate> ...')
}
