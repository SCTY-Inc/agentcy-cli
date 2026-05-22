import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'
import { afterEach, describe, expect, test, vi } from 'vitest'
import { runCli } from './index'
import { createRuntime } from '../runtime/runtime'

const roots: string[] = []
const originalHome = process.env.HOME

function createWorkspace(): string {
  const root = mkdtempSync(join(tmpdir(), 'studio-cli-'))
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
    - Caregiving is operational work.
topics:
  pillars:
    - id: care-economy
      angle: Caregiving is infrastructure and should be discussed as such.
      signals:
        - caregiver benefits
      formats: [analysis]
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

async function captureStdout<T>(fn: () => Promise<T>): Promise<{ result: T; stdout: string }> {
  const chunks: string[] = []
  const spy = vi.spyOn(process.stdout, 'write').mockImplementation(((chunk: string | Uint8Array) => {
    chunks.push(typeof chunk === 'string' ? chunk : Buffer.from(chunk).toString('utf8'))
    return true
  }) as typeof process.stdout.write)

  try {
    const result = await fn()
    return { result, stdout: chunks.join('') }
  } finally {
    spy.mockRestore()
  }
}

afterEach(() => {
  while (roots.length > 0) {
    rmSync(roots.pop()!, { recursive: true, force: true })
  }

  delete process.env.STUDIO_ROOT
  if (originalHome === undefined) {
    delete process.env.HOME
  } else {
    process.env.HOME = originalHome
  }
})

describe.sequential('runCli', () => {
  test('returns help without loading the native render stack', async () => {
    const { result, stdout } = await captureStdout(() => runCli(['help', '--json']))

    expect(result).toBe(0)
    expect(JSON.parse(stdout)).toMatchObject({
      status: 'ok',
      command: 'help',
    })
  })

  test('returns a JSON error envelope for invalid workflows', async () => {
    const root = createWorkspace()
    process.env.STUDIO_ROOT = root
    process.env.HOME = root

    const { result, stdout } = await captureStdout(() =>
      runCli(['run', 'not-a-workflow', '--brand', 'givecare', '--json']),
    )

    expect(result).toBe(1)
    expect(JSON.parse(stdout)).toEqual({
      status: 'error',
      error: {
        message: 'Invalid workflow: not-a-workflow. Expected one of: social.post, blog.post, outreach.touch, respond.reply',
      },
    })
  })

  test('imports canonical brief.v1 files through the run command', async () => {
    const root = createWorkspace()
    process.env.STUDIO_ROOT = root
    process.env.HOME = root
    const briefPath = join(process.cwd(), '..', 'protocols', 'examples', 'brief.v1.rich.json')

    const { result, stdout } = await captureStdout(() =>
      runCli(['run', 'social.post', '--brand', 'givecare', '--brief-file', briefPath, '--json']),
    )

    expect(result).toBe(0)
    const response = JSON.parse(stdout)
    expect(response).toMatchObject({
      status: 'ok',
      command: 'run',
      data: {
        workflow: 'social.post',
        brand: 'givecare',
      },
    })
    expect(response.data.input.importedBrief.normalized.topic).toBe('Before fall gets busy, make caregiving feel lighter')
  })

  test('returns a JSON error envelope for malformed brief.v1 input files', async () => {
    const root = createWorkspace()
    process.env.STUDIO_ROOT = root
    process.env.HOME = root

    const malformedPath = join(root, 'malformed-brief.json')
    writeFileSync(malformedPath, '{not-json', 'utf8')

    const { result, stdout } = await captureStdout(() =>
      runCli(['run', 'social.post', '--brand', 'givecare', '--brief-file', malformedPath, '--json']),
    )

    expect(result).toBe(1)
    expect(JSON.parse(stdout)).toEqual({
      status: 'error',
      error: {
        message: expect.stringContaining(`Invalid brief.v1: failed to parse JSON at ${malformedPath}`),
      },
    })
  })

  test('rejects invalid review variants', async () => {
    const root = createWorkspace()
    process.env.STUDIO_ROOT = root
    process.env.HOME = root

    const runtime = createRuntime({ root })
    const run = await runtime.runWorkflow({
      workflow: 'social.post',
      brand: 'givecare',
      input: { topic: 'caregiver systems' },
    })

    const { result, stdout } = await captureStdout(() =>
      runCli(['review', 'approve', run.id, '--variant', 'missing-variant', '--json']),
    )

    expect(result).toBe(1)
    expect(JSON.parse(stdout)).toEqual({
      status: 'error',
      error: {
        message: `Variant not found for run ${run.id}: missing-variant`,
      },
    })
  })

  test('rejects invalid publish platforms', async () => {
    const root = createWorkspace()
    process.env.STUDIO_ROOT = root
    process.env.HOME = root

    const runtime = createRuntime({ root })
    const run = await runtime.runWorkflow({
      workflow: 'social.post',
      brand: 'givecare',
      input: { topic: 'caregiver systems' },
    })
    runtime.reviewRun(run.id, { decision: 'approve', selectedVariantId: 'social-main' })

    const { result, stdout } = await captureStdout(() =>
      runCli(['publish', run.id, '--platforms', 'mastodon', '--dry-run', '--json']),
    )

    expect(result).toBe(1)
    expect(JSON.parse(stdout)).toEqual({
      status: 'error',
      error: {
        message: 'Invalid platform(s): mastodon. Expected one of: twitter, linkedin, facebook, instagram, threads',
      },
    })
  })

  test('rejects inspect artifact paths outside state artifacts', async () => {
    const root = createWorkspace()
    process.env.STUDIO_ROOT = root
    process.env.HOME = root

    const { result, stdout } = await captureStdout(() =>
      runCli(['inspect', 'artifact', join(root, 'brands', 'givecare', 'BRAND.md'), '--json']),
    )

    expect(result).toBe(1)
    expect(JSON.parse(stdout)).toMatchObject({
      status: 'error',
      error: {
        message: expect.stringContaining(join(root, 'state', 'artifacts')),
      },
    })
  })

  test('rejects publish requests for unconfigured platforms', async () => {
    const root = createWorkspace()
    process.env.STUDIO_ROOT = root
    process.env.HOME = root

    const runtime = createRuntime({ root })
    const run = await runtime.runWorkflow({
      workflow: 'social.post',
      brand: 'givecare',
      input: { topic: 'caregiver systems' },
    })
    runtime.reviewRun(run.id, { decision: 'approve', selectedVariantId: 'social-main' })

    const { result, stdout } = await captureStdout(() =>
      runCli(['publish', run.id, '--platforms', 'twitter', '--json']),
    )

    expect(result).toBe(1)
    expect(JSON.parse(stdout)).toEqual({
      status: 'error',
      error: {
        message: 'Requested platforms not configured for givecare: twitter. Run "agentcy-studio ops auth check --brand givecare" first.',
      },
    })
  })

  test('rejects brand init when the brand already exists', async () => {
    const root = createWorkspace()
    process.env.STUDIO_ROOT = root
    process.env.HOME = root

    const { result, stdout } = await captureStdout(() =>
      runCli(['brand', 'init', 'givecare', '--json']),
    )

    expect(result).toBe(1)
    expect(JSON.parse(stdout)).toMatchObject({
      status: 'error',
      error: {
        message: expect.stringContaining(join(root, 'brands', 'givecare', 'BRAND.md')),
      },
    })
  })

  test('brand init creates a plug-and-play BRAND.md and DESIGN.md kit', async () => {
    const root = mkdtempSync(join(tmpdir(), 'studio-cli-init-'))
    roots.push(root)
    mkdirSync(join(root, 'brands'), { recursive: true })
    process.env.STUDIO_ROOT = root
    process.env.HOME = root

    const { result, stdout } = await captureStdout(() =>
      runCli(['brand', 'init', 'acme-care', '--json']),
    )

    expect(result).toBe(0)
    const response = JSON.parse(stdout)
    expect(response).toMatchObject({
      status: 'ok',
      command: 'brand',
      data: { id: 'acme-care' },
    })
    expect(existsSync(join(root, 'brands', 'acme-care', 'BRAND.md'))).toBe(true)
    expect(existsSync(join(root, 'brands', 'acme-care', 'DESIGN.md'))).toBe(true)
    expect(response.data.designPath).toMatch(/brands\/acme-care\/DESIGN\.md$/)
  })

  test('brand validate reports turnkey kit readiness from DESIGN.md', async () => {
    const root = createWorkspace()
    process.env.STUDIO_ROOT = root
    process.env.HOME = root
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
    font_family: "Alegreya"
    headline: "Alegreya"
    body: "Inter"
    accent: "JetBrains Mono"
components:
  Card:
    description: "Editorial social card shell."
agentcy:
  source:
    type: authored
    viewports:
      - desktop 1200x1200
    evidence:
      - authored brand kit tokens
  visual:
    default_style: editorial
    image_prompt: "Background only for [SUBJECT]. No text, no logos."
    composition:
      - Left text panel, open art field.
    negative:
      - text
      - logos
  artifacts:
    social_card:
      styles:
        editorial:
          density: medium
  fidelity:
    gates:
      - Render with DESIGN.md token colors.
      - Fail unknown styles.
---

## Design System
Warm editorial.
`.trim(),
      'utf8',
    )

    const { result, stdout } = await captureStdout(() =>
      runCli(['brand', 'validate', 'givecare', '--json']),
    )

    expect(result).toBe(0)
    const response = JSON.parse(stdout)
    expect(response.data.checks.kit).toMatchObject({
      production_ready: true,
      learning_ready: true,
      design: 'found',
      visual: {
        typography: 'set',
        image_grammar: 'set',
        default_style: 'editorial',
        style_profiles: 1,
        negative_prompts: 2,
        composition_rules: 1,
      },
      fidelity: {
        source_type: 'authored',
        viewports: 1,
        evidence_items: 1,
        gates: 2,
        measured_ready: 'set',
      },
    })
  })

  test('rejects brand validation when BRAND.md is malformed', async () => {
    const root = createWorkspace()
    process.env.STUDIO_ROOT = root
    process.env.HOME = root

    mkdirSync(join(root, 'brands', 'broken'), { recursive: true })
    writeFileSync(
      join(root, 'brands', 'broken', 'BRAND.md'),
      `name: Broken Brand\npositioning: Broken positioning.\n`,
      'utf8',
    )

    const { result, stdout } = await captureStdout(() =>
      runCli(['brand', 'validate', 'broken', '--json']),
    )

    expect(result).toBe(1)
    expect(JSON.parse(stdout)).toMatchObject({
      status: 'error',
      error: {
        message: expect.stringContaining('missing YAML front matter'),
      },
    })
  })

  test('builds a browser card lab for a brand', async () => {
    const root = createWorkspace()
    process.env.STUDIO_ROOT = root
    process.env.HOME = root

    const { result, stdout } = await captureStdout(() =>
      runCli([
        'lab',
        'card',
        '--brand',
        'givecare',
        '--series',
        'weekly-recap',
        '--type',
        'quote',
        '--headline',
        'Care is infrastructure',
        '--body',
        'Make invisible work visible.',
        '--json',
      ]),
    )

    expect(result).toBe(0)
    const response = JSON.parse(stdout)
    expect(response).toMatchObject({
      status: 'ok',
      command: 'lab',
      data: {
        brand: 'givecare',
        type: 'quote',
        series: 'weekly-recap',
      },
    })

    const htmlPath = String(response.data.path)
    expect(htmlPath).toContain(join(root, 'state', 'lab'))
    expect(existsSync(htmlPath)).toBe(true)
  })

  test('renders a 1200x630 OG cover with a sidecar contract', async () => {
    const root = createWorkspace()
    process.env.STUDIO_ROOT = root
    process.env.HOME = root

    const { result, stdout } = await captureStdout(() =>
      runCli([
        'lab',
        'cover',
        '--brand',
        'givecare',
        '--title',
        'Care is infrastructure',
        '--subtitle',
        'Make invisible work visible.',
        '--seed',
        'kitchen-table',
        '--json',
      ]),
    )

    expect(result).toBe(0)
    const response = JSON.parse(stdout)
    expect(response).toMatchObject({
      status: 'ok',
      command: 'lab',
      data: {
        brand: 'givecare',
        title: 'Care is infrastructure',
        width: 1200,
        height: 630,
      },
    })

    const coverPath = String(response.data.path)
    const sidecarPath = String(response.data.sidecarPath)
    expect(coverPath).toContain(join(root, 'state', 'covers'))
    expect(existsSync(coverPath)).toBe(true)
    expect(existsSync(sidecarPath)).toBe(true)

    const png = readFileSync(coverPath)
    expect([...png.subarray(0, 8)]).toEqual([137, 80, 78, 71, 13, 10, 26, 10])
    expect(png.readUInt32BE(16)).toBe(1200)
    expect(png.readUInt32BE(20)).toBe(630)

    const sidecar = JSON.parse(readFileSync(sidecarPath, 'utf8'))
    expect(sidecar).toMatchObject({
      artifact_type: 'og_cover.v1',
      renderer: 'satori-resvg',
      width: 1200,
      height: 630,
      brand_id: 'givecare',
      title: 'Care is infrastructure',
      seed: 'kitchen-table',
      composition: {
        background: 'deterministic_palette',
        text: 'local_svg_text',
      },
    })
  })

  test('returns an actionable error for unsupported auth refresh', async () => {
    const root = createWorkspace()
    process.env.STUDIO_ROOT = root
    process.env.HOME = root

    const { result, stdout } = await captureStdout(() =>
      runCli(['ops', 'auth', 'refresh', '--json']),
    )

    expect(result).toBe(1)
    expect(JSON.parse(stdout)).toEqual({
      status: 'error',
      error: {
        message: 'Auth refresh is not available in the active runtime. Update env credentials manually and rerun "agentcy-studio ops auth check --brand <id>".',
      },
    })
  })
})
