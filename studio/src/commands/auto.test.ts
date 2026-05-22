import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'
import { afterEach, describe, expect, test } from 'vitest'
import { runAutoCommand } from './auto'

const roots: string[] = []
const originalHome = process.env.HOME

function isolateHome(): void {
  const home = mkdtempSync(join(tmpdir(), 'studio-auto-home-'))
  roots.push(home)
  process.env.HOME = home
}

function createPolicyBrandWorkspace(): string {
  const root = mkdtempSync(join(tmpdir(), 'studio-auto-brand-'))
  roots.push(root)
  mkdirSync(join(root, 'brands', 'scty'), { recursive: true })
  writeFileSync(
    join(root, 'brands', 'scty', 'BRAND.md'),
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
behavior:
  escalate:
    - Legal or confidential client details.
safety:
  approval_required:
    - product_claims
  delegation:
    human_required:
      - product_claims
---

## Overview
SCTY executes directly and technically.
`.trim(),
    'utf8',
  )
  return root
}

afterEach(() => {
  while (roots.length > 0) {
    rmSync(roots.pop()!, { recursive: true, force: true })
  }
  process.env.HOME = originalHome
})

describe('auto command policy gates', () => {
  test('refuses live auto publish when BRAND.md requires human approval', async () => {
    const root = createPolicyBrandWorkspace()

    await expect(runAutoCommand([
      '--brand', 'scty',
      '--topic', 'AI deployment failures',
    ], root)).rejects.toThrow('Use "run", "review approve", then "publish" instead of auto publish')
  })

  test('allows dry-run auto execution for a policy-gated BRAND.md', async () => {
    const root = createPolicyBrandWorkspace()
    isolateHome()

    const result = await runAutoCommand([
      '--brand', 'scty',
      '--topic', 'AI deployment failures',
      '--dry-run',
      '--platforms', 'twitter',
    ], root) as Record<string, any>

    expect(result.run.brand).toBe('scty')
    expect(result.runResult.status).toBe('dry_run')
  })
})
