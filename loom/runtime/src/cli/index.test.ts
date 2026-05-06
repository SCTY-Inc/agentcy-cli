import { existsSync, mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'
import { afterEach, describe, expect, test, vi } from 'vitest'
import { runCli } from './index'
import { createRuntime } from '../runtime/runtime'

const roots: string[] = []
const IMAGE_API_KEYS = ['GEMINI_API_KEY', 'GOOGLE_API_KEY'] as const
const savedImageApiKeys = new Map<string, string | undefined>()
const originalHome = process.env.HOME

function createWorkspace(): string {
  const root = mkdtempSync(join(tmpdir(), 'loom-cli-'))
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

function suppressImageApiKeys(): void {
  for (const key of IMAGE_API_KEYS) {
    if (!savedImageApiKeys.has(key)) {
      savedImageApiKeys.set(key, process.env[key])
    }
    delete process.env[key]
  }
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

  delete process.env.LOOM_ROOT
  if (originalHome === undefined) {
    delete process.env.HOME
  } else {
    process.env.HOME = originalHome
  }

  for (const key of IMAGE_API_KEYS) {
    const value = savedImageApiKeys.get(key)
    if (value === undefined) {
      delete process.env[key]
    } else {
      process.env[key] = value
    }
  }
  savedImageApiKeys.clear()
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
    process.env.LOOM_ROOT = root
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
    process.env.LOOM_ROOT = root
    process.env.HOME = root
    suppressImageApiKeys()
    const briefPath = join(process.cwd(), '..', '..', 'protocols', 'examples', 'brief.v1.rich.json')

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
    process.env.LOOM_ROOT = root
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
    process.env.LOOM_ROOT = root
    process.env.HOME = root
    suppressImageApiKeys()

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
    process.env.LOOM_ROOT = root
    process.env.HOME = root
    suppressImageApiKeys()

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
    process.env.LOOM_ROOT = root
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
    process.env.LOOM_ROOT = root
    process.env.HOME = root
    suppressImageApiKeys()

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
        message: 'Requested platforms not configured for givecare: twitter. Run "loom ops auth check --brand givecare" first.',
      },
    })
  })

  test('rejects brand init when the brand already exists', async () => {
    const root = createWorkspace()
    process.env.LOOM_ROOT = root
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

  test('rejects brand validation when BRAND.md is malformed', async () => {
    const root = createWorkspace()
    process.env.LOOM_ROOT = root
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
    process.env.LOOM_ROOT = root
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

  test('returns an actionable error for unsupported auth refresh', async () => {
    const root = createWorkspace()
    process.env.LOOM_ROOT = root
    process.env.HOME = root

    const { result, stdout } = await captureStdout(() =>
      runCli(['ops', 'auth', 'refresh', '--json']),
    )

    expect(result).toBe(1)
    expect(JSON.parse(stdout)).toEqual({
      status: 'error',
      error: {
        message: 'Auth refresh is not available in the active runtime. Update env credentials manually and rerun "loom ops auth check --brand <id>".',
      },
    })
  })
})
