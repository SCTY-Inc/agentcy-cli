import { mkdirSync, writeFileSync } from 'fs'
import { join } from 'path'

const PILLARS_BLOCK = `
pillars:
  - id: care-economy
    perspective: Caregiving is infrastructure and should be discussed as such.
    signals:
      - caregiver benefits
      - care deserts
    format: analysis
    frequency: weekly
  - id: policy
    perspective: Policy should be judged by whether it reduces caregiver burden.
    signals:
      - paid leave
      - Medicaid waivers
    format: opinionated-take
    frequency: weekly`

function brandMd(options: { pillars?: boolean } = {}): string {
  return `---
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
  - Caregiving is operational work.${options.pillars !== false ? PILLARS_BLOCK : ''}
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
}

const TEST_DESIGN_MD = `---
palette:
  background: "#FDF9EC"
  primary: "#3D1600"
  accent: "#FF9F00"
typography:
  headline: "Alegreya, serif, bold"
  body: "Inter, sans-serif, regular"
  accent: "Gabarito, sans-serif, bold"
logo: logo.png
layout: calm-editorial
---

## Style

Agnes Martin. Pale gesso ground.

## Motif

Soft concentric rings.
`

export function writeBrandFixture(root: string, options: { brandId?: string; pillars?: boolean } = {}): void {
  const { brandId = 'givecare', pillars = true } = options
  const dir = join(root, 'brands', brandId)
  mkdirSync(dir, { recursive: true })
  writeFileSync(join(dir, 'brand.md'), brandMd({ pillars }))
  writeFileSync(join(dir, 'design.md'), TEST_DESIGN_MD)
}
