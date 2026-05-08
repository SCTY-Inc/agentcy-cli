import { existsSync, mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'
import { afterEach, describe, expect, test, vi } from 'vitest'
import { runCli } from './index'
import { createRuntime } from '../runtime/runtime'
import { writeBrandFixture } from '../test-fixtures'

const roots: string[] = []
const IMAGE_API_KEYS = ['GEMINI_API_KEY', 'GOOGLE_API_KEY'] as const
const savedImageApiKeys = new Map<string, string | undefined>()
const originalHome = process.env.HOME

function createWorkspace(): string {
  const root = mkdtempSync(join(tmpdir(), 'loom-cli-'))
  roots.push(root)
  writeBrandFixture(root, { pillars: false })
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
      runCli(['inspect', 'artifact', join(root, 'brands', 'givecare', 'brand.md'), '--json']),
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
        message: expect.stringContaining(join(root, 'brands', 'givecare', 'brand.md')),
      },
    })
  })

  test('rejects brand validation when referenced assets are missing', async () => {
    const root = createWorkspace()
    process.env.LOOM_ROOT = root
    process.env.HOME = root

    mkdirSync(join(root, 'brands', 'broken'), { recursive: true })
    writeFileSync(
      join(root, 'brands', 'broken', 'brand.md'),
      `---
id: broken
name: Broken Brand
positioning: Broken positioning.
audiences:
  - id: primary
    summary: Someone.
offers:
  - id: primary
    summary: Something.
proof_points:
  - One proof point.
pillars:
  - id: primary-theme
    perspective: One angle.
    signals:
      - one signal
    format: analysis
    frequency: weekly
voice:
  tone: Direct.
  style: Plain.
  do:
    - Say the real thing plainly.
  dont:
    - Hide behind abstractions.
channels:
  social:
    objective: Build signal.
  blog:
    objective: Publish thinking.
  outreach:
    objective: Start conversations.
  respond:
    objective: Reply clearly.
response_playbooks:
  - id: default-response
    trigger: inbound-question
    approach: Clarify the claim and answer directly.
outreach_playbooks:
  - id: default-outreach
    trigger: first-touch
    approach: Lead with one specific observation and one ask.
---
`,
      'utf8',
    )
    writeFileSync(
      join(root, 'brands', 'broken', 'design.md'),
      `---
palette:
  background: "#FFFFFF"
  primary: "#111111"
  accent: "#FF6600"
logo: missing-logo.png
---
`,
      'utf8',
    )

    const { result, stdout } = await captureStdout(() =>
      runCli(['brand', 'validate', 'broken', '--json']),
    )

    expect(result).toBe(1)
    expect(JSON.parse(stdout)).toMatchObject({
      status: 'error',
      error: {
        message: expect.stringContaining(join(root, 'brands', 'broken', 'missing-logo.png')),
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
