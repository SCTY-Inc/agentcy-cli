import { existsSync, mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'
import { afterAll, afterEach, describe, expect, test } from 'vitest'
import { createRuntime } from './runtime'
import { openRuntimeDb } from './db'
import { getSocialAuthReport, type SocialPublishRequest } from '../publish/social'
import { loadBriefV1 } from '../domain/brief-v1'
import { isPerformanceSourceRunResultV1, type CanonicalRunResultV1 } from '../domain/run-result-v1'
import { writeBrandFixture } from '../test-fixtures'

const roots: string[] = []
const envKeys = new Set<string>()
const savedImageApiKeys: Record<string, string | undefined> = {}
const IMAGE_API_KEYS = ['GEMINI_API_KEY', 'GOOGLE_API_KEY']

function suppressImageApiKeys(): void {
  for (const key of IMAGE_API_KEYS) {
    delete process.env[key]
  }
}

function createWorkspace(): string {
  const root = mkdtempSync(join(tmpdir(), 'loom-runtime-'))
  roots.push(root)
  writeBrandFixture(root)
  return root
}

function setEnv(key: string, value: string): void {
  process.env[key] = value
  envKeys.add(key)
}

// Suppress image API keys during tests so explore step uses skip path
for (const key of IMAGE_API_KEYS) {
  savedImageApiKeys[key] = process.env[key]
  delete process.env[key]
}

afterEach(() => {
  while (roots.length > 0) {
    rmSync(roots.pop()!, { recursive: true, force: true })
  }

  for (const key of envKeys) {
    delete process.env[key]
  }
  envKeys.clear()

  // Keep image API keys suppressed across tests
  for (const key of IMAGE_API_KEYS) {
    delete process.env[key]
  }
})

// Restore after all tests
afterAll(() => {
  for (const key of IMAGE_API_KEYS) {
    if (savedImageApiKeys[key] !== undefined) {
      process.env[key] = savedImageApiKeys[key]
    }
  }
})

describe('runtime workflows', () => {
  test('imports canonical brief.v1 input and normalizes it into the internal brief artifact', async () => {
    const root = createWorkspace()
    const runtime = createRuntime({ root })
    suppressImageApiKeys()
    const briefPath = join(process.cwd(), '..', '..', 'protocols', 'examples', 'brief.v1.rich.json')

    const run = await runtime.runWorkflow({
      workflow: 'social.post',
      brand: 'givecare',
      input: {
        importedBrief: {
          path: briefPath,
          payload: loadBriefV1(briefPath),
        },
      },
    })

    const details = runtime.inspectRun(run.id)
    const signal = details.artifacts.find((artifact) => artifact.type === 'signal_packet')
    const brief = details.artifacts.find((artifact) => artifact.type === 'brief')
    const draftSet = details.artifacts.find((artifact) => artifact.type === 'draft_set')
    const socialMain = Array.isArray(draftSet?.data.variants)
      ? draftSet.data.variants.find((variant) => typeof variant === 'object' && variant && (variant as Record<string, unknown>).id === 'social-main') as Record<string, unknown> | undefined
      : undefined

    expect(run.input).toHaveProperty('importedBrief.normalized')
    expect(signal?.data).toMatchObject({
      topic: 'Before fall gets busy, make caregiving feel lighter',
      source: 'support-call-notes',
      goal: 'Increase caregiver response to seasonal planning content and convert high-intent readers to checklist downloads.',
    })
    expect(brief?.data).toMatchObject({
      sourceArtifactType: 'brief.v1',
      perspective: 'Frame early planning as an act of care that reduces stress for the whole family.',
      topic: 'Before fall gets busy, make caregiving feel lighter',
      cta: 'Download the fall care checklist and share it with one family member.',
    })
    expect(String(socialMain?.body)).toContain('Frame early planning as an act of care that reduces stress for the whole family.')
  })

  test('rejects brief.v1 imports missing required fields', async () => {
    const root = createWorkspace()
    const runtime = createRuntime({ root })
    suppressImageApiKeys()

    await expect(runtime.runWorkflow({
      workflow: 'social.post',
      brand: 'givecare',
      input: {
        importedBrief: {
          path: 'missing-voice-pack.json',
          payload: {
            artifact_type: 'brief.v1',
            schema_version: 'v1',
            brief_id: 'givecare.brief.test',
            brand_id: 'givecare.brand.core',
            writer: { repo: 'brand-os', module: 'agentcy-compass' },
            objective: 'Test objective',
            signal: { source: 'source', summary: 'summary' },
            strategy: { angle: 'angle', cta: 'cta', platforms: ['linkedin'] },
            policy: { verdict: 'approved', confidence: 0.9 },
            creative: { headline: 'headline', copy: 'copy', tone_notes: ['warm'] },
          },
        },
      },
    })).rejects.toThrow('Invalid brief.v1: voice_pack_id must be a non-empty string')
  })

  test('rejects brief.v1 imports with missing lineage source_voice_pack_id when lineage is present', async () => {
    const root = createWorkspace()
    const runtime = createRuntime({ root })
    suppressImageApiKeys()

    await expect(runtime.runWorkflow({
      workflow: 'social.post',
      brand: 'givecare',
      input: {
        importedBrief: {
          path: 'missing-lineage.json',
          payload: {
            artifact_type: 'brief.v1',
            schema_version: 'v1',
            brief_id: 'givecare.brief.test',
            brand_id: 'givecare.brand.core',
            voice_pack_id: 'givecare.voice.default.v1',
            writer: { repo: 'brand-os', module: 'agentcy-compass' },
            objective: 'Test objective',
            signal: { source: 'source', summary: 'summary' },
            strategy: { angle: 'angle', cta: 'cta', platforms: ['linkedin'] },
            policy: { verdict: 'approved', confidence: 0.9 },
            creative: { headline: 'headline', copy: 'copy', tone_notes: ['warm'] },
            lineage: {},
          },
        },
      },
    })).rejects.toThrow('Invalid brief.v1: lineage.source_voice_pack_id is required when lineage is present')
  })
  test('runs social.post and stores review-ready artifacts', async () => {
    const root = createWorkspace()
    const runtime = createRuntime({ root })
    suppressImageApiKeys()

    const run = await runtime.runWorkflow({
      workflow: 'social.post',
      brand: 'givecare',
      input: { topic: 'caregiver benefits gap' },
    })

    expect(run.status).toBe('in_review')

    const details = runtime.inspectRun(run.id)
    expect(details.artifacts.map((artifact) => artifact.type)).toEqual([
      'signal_packet',
      'brief',
      'draft_set',
      'explore_grid',
      'source_image',
      'asset_set',
    ])

    const draftSet = details.artifacts.find((artifact) => artifact.type === 'draft_set')
    const socialMain = Array.isArray(draftSet?.data.variants)
      ? draftSet.data.variants.find((variant) => typeof variant === 'object' && variant && (variant as Record<string, unknown>).id === 'social-main') as Record<string, unknown> | undefined
      : undefined
    expect(String(socialMain?.body)).toContain('Caregiving is infrastructure and should be discussed as such.')

    const sourceImage = details.artifacts.find((artifact) => artifact.type === 'source_image')
    expect(sourceImage?.data).toMatchObject({ channel: 'social', skipped: true })

    const asset = details.artifacts.find((artifact) => artifact.type === 'asset_set')
    const platformAssets = asset?.data.platformAssets as Record<string, string> | undefined
    expect(Object.keys(platformAssets ?? {})).toEqual(['facebook', 'instagram', 'linkedin', 'threads', 'twitter'])
    expect(existsSync(String(platformAssets?.twitter))).toBe(true)
    expect(existsSync(String(platformAssets?.instagram))).toBe(true)
  })

  test('runs blog.post and creates outline and article draft artifacts', async () => {
    const root = createWorkspace()
    const runtime = createRuntime({ root })
    suppressImageApiKeys()

    const run = await runtime.runWorkflow({
      workflow: 'blog.post',
      brand: 'givecare',
      input: {
        topic: 'why caregiver benefits fail',
        sources: ['State of caregiving support'],
      },
    })

    const details = runtime.inspectRun(run.id)
    expect(run.status).toBe('in_review')
    expect(details.artifacts.map((artifact) => artifact.type)).toEqual([
      'signal_packet',
      'brief',
      'outline',
      'article_draft',
    ])
  })

  test('includes the selected brand pillar in the brief', async () => {
    const root = createWorkspace()
    const runtime = createRuntime({ root })
    suppressImageApiKeys()

    const run = await runtime.runWorkflow({
      workflow: 'blog.post',
      brand: 'givecare',
      input: {
        topic: 'why caregiver benefits fail',
        pillar: 'policy',
      },
    })

    const details = runtime.inspectRun(run.id)
    const brief = details.artifacts.find((artifact) => artifact.type === 'brief')
    const article = details.artifacts.find((artifact) => artifact.type === 'article_draft')

    expect(brief?.data).toMatchObject({
      pillar: 'policy',
      format: 'opinionated-take',
      perspective: 'Policy should be judged by whether it reduces caregiver burden.',
      signals: ['paid leave', 'Medicaid waivers'],
    })
    expect(String(article?.data.markdown)).toContain('Policy should be judged by whether it reduces caregiver burden.')
    expect(String(article?.data.markdown)).toContain('paid leave and Medicaid waivers')
  })

  test('marks runs as failed with the failing step and error message', async () => {
    const root = createWorkspace()
    const runtime = createRuntime({ root })
    suppressImageApiKeys()

    await expect(runtime.runWorkflow({
      workflow: 'blog.post',
      brand: 'givecare',
      input: {
        topic: 'why caregiver benefits fail',
        pillar: 'missing-pillar',
      },
    })).rejects.toThrow('Unknown pillar for brand givecare: missing-pillar')

    const db = openRuntimeDb(root)
    const row = db.prepare(`SELECT * FROM runs ORDER BY created_at DESC LIMIT 1`).get() as Record<string, unknown>

    expect(row.status).toBe('failed')
    expect(row.current_step).toBe('brief')
    expect(row.error_message).toBe('Unknown pillar for brand givecare: missing-pillar')
    expect(runtime.health()).toMatchObject({ failedRuns: 1, totalRuns: 1 })
    expect(() => runtime.reviewRun(String(row.id), { decision: 'approve' })).toThrow(
      `Run ${String(row.id)} failed at step brief and cannot be reviewed. Retry the run first.`,
    )
  })

  test('does not allow reviewing a published run again', async () => {
    const root = createWorkspace()
    setEnv('TWITTER_GIVECARE_API_KEY', 'api-key')
    setEnv('TWITTER_GIVECARE_API_SECRET', 'api-secret')
    setEnv('TWITTER_GIVECARE_ACCESS_TOKEN', 'access-token')
    setEnv('TWITTER_GIVECARE_ACCESS_SECRET', 'access-secret')

    const runtime = createRuntime({ root })
    suppressImageApiKeys()
    runtime.setSocialPublisher(async (request) =>
      request.platforms.map((platform) => ({
        platform,
        success: true,
        postId: `post-${platform}`,
      })),
    )

    const run = await runtime.runWorkflow({
      workflow: 'social.post',
      brand: 'givecare',
      input: { topic: 'caregiver systems' },
    })

    runtime.reviewRun(run.id, { decision: 'approve', selectedVariantId: 'social-main' })
    await runtime.publishRun(run.id)

    expect(() => runtime.reviewRun(run.id, { decision: 'reject', note: 'too late' })).toThrow(
      `Run ${run.id} is already published and cannot be reviewed again`,
    )
  })

  test('builds canonical run_result.v1 for dry-run publish outcomes', async () => {
    const root = createWorkspace()
    setEnv('TWITTER_GIVECARE_API_KEY', 'api-key')
    setEnv('TWITTER_GIVECARE_API_SECRET', 'api-secret')
    setEnv('TWITTER_GIVECARE_ACCESS_TOKEN', 'access-token')
    setEnv('TWITTER_GIVECARE_ACCESS_SECRET', 'access-secret')

    const runtime = createRuntime({ root })
    suppressImageApiKeys()
    const briefPath = join(process.cwd(), '..', '..', 'protocols', 'examples', 'brief.v1.rich.json')

    const run = await runtime.runWorkflow({
      workflow: 'social.post',
      brand: 'givecare',
      input: {
        importedBrief: {
          path: briefPath,
          payload: loadBriefV1(briefPath),
        },
      },
    })

    runtime.reviewRun(run.id, {
      decision: 'approve',
      selectedVariantId: 'social-main',
    })

    await runtime.publishRun(run.id, { dryRun: true, platforms: ['twitter'] })

    const result = runtime.buildRunResult(run.id)
    expect(result.completed_at).toBeTypeOf('string')
    expect(isPerformanceSourceRunResultV1(result)).toBe(false)
    expect(result).toMatchObject({
      artifact_type: 'run_result.v1',
      schema_version: 'v1',
      run_id: run.id,
      brief_id: 'givecare.brief.fall-checkin.social-email.2026-04-12',
      brand_id: 'givecare.brand.core',
      workflow: 'social.post',
      status: 'dry_run',
      review: {
        decision: 'approved',
      },
      delivery: {
        dry_run: true,
        selected_variant_id: 'social-main',
        platforms: [
          {
            platform: 'twitter',
            status: 'simulated',
            message: 'Dry-run only; no post was sent.',
          },
        ],
      },
      lineage: {
        source_voice_pack_id: 'givecare.voice.fall-checkin.v1',
        campaign_id: 'givecare.campaign.fall-checkin.2026q2',
        signal_id: 'givecare.signal.support-calls.fall-2026-04',
      },
    } satisfies Partial<CanonicalRunResultV1>)
  })

  test('approves, publishes through the social publisher, and retries a run with lineage intact', async () => {
    const root = createWorkspace()
    setEnv('TWITTER_GIVECARE_API_KEY', 'api-key')
    setEnv('TWITTER_GIVECARE_API_SECRET', 'api-secret')
    setEnv('TWITTER_GIVECARE_ACCESS_TOKEN', 'access-token')
    setEnv('TWITTER_GIVECARE_ACCESS_SECRET', 'access-secret')
    setEnv('LINKEDIN_GIVECARE_ACCESS_TOKEN', 'linkedin-token')
    setEnv('LINKEDIN_GIVECARE_ORG_ID', '12345')
    setEnv('FACEBOOK_GIVECARE_PAGE_ACCESS_TOKEN', 'facebook-token')
    setEnv('FACEBOOK_GIVECARE_PAGE_ID', '54321')
    setEnv('INSTAGRAM_GIVECARE_ACCESS_TOKEN', 'instagram-token')
    setEnv('INSTAGRAM_GIVECARE_USER_ID', 'ig-user')
    setEnv('THREADS_GIVECARE_ACCESS_TOKEN', 'threads-token')
    setEnv('THREADS_GIVECARE_USER_ID', 'threads-user')

    const publishCalls: SocialPublishRequest[] = []
    const runtime = createRuntime({ root })
    suppressImageApiKeys()
    runtime.setSocialPublisher(async (request) => {
      publishCalls.push(request)
      return request.platforms.map((platform) => ({
        platform,
        success: true,
        postId: `post-${platform}`,
        postUrl: `https://example.com/${platform}`,
      }))
    })

    const run = await runtime.runWorkflow({
      workflow: 'social.post',
      brand: 'givecare',
      input: { topic: 'caregiver burnout is operational, not personal failure' },
    })

    const approved = runtime.reviewRun(run.id, {
      decision: 'approve',
      note: 'Use variant A',
      selectedVariantId: 'social-alt',
    })
    expect(approved.status).toBe('approved')

    const published = await runtime.publishRun(run.id)
    expect(published.status).toBe('published')
    const publishedResult = runtime.buildRunResult(run.id)
    expect(publishedResult.completed_at).toBeTypeOf('string')
    expect(isPerformanceSourceRunResultV1(publishedResult)).toBe(true)
    expect(publishedResult).toMatchObject({
      run_id: run.id,
      status: 'published',
      delivery: {
        dry_run: false,
        selected_variant_id: 'social-alt',
        platforms: [
          {
            platform: 'twitter',
            status: 'published',
            post_id: 'post-twitter',
            url: 'https://example.com/twitter',
          },
          {
            platform: 'linkedin',
            status: 'published',
            post_id: 'post-linkedin',
            url: 'https://example.com/linkedin',
          },
          {
            platform: 'facebook',
            status: 'published',
            post_id: 'post-facebook',
            url: 'https://example.com/facebook',
          },
        ],
      },
    } satisfies Partial<CanonicalRunResultV1>)
    expect(publishCalls).toHaveLength(1)
    expect(publishCalls[0].platforms).toEqual(['twitter', 'linkedin', 'facebook'])
    expect(publishCalls[0].text).toContain('caregiver burnout is operational, not personal failure')
    expect(publishCalls[0].text).toContain('GiveCare')
    expect(Object.keys(publishCalls[0].platformAssets)).toEqual(['facebook', 'instagram', 'linkedin', 'threads', 'twitter'])
    expect(existsSync(publishCalls[0].platformAssets.twitter)).toBe(true)
    expect(existsSync(publishCalls[0].platformAssets.instagram)).toBe(true)

    const retried = await runtime.retryRun(run.id, { fromStep: 'draft' })
    expect(retried.parentRunId).toBe(run.id)
    expect(retried.status).toBe('in_review')

    runtime.reviewRun(retried.id, {
      decision: 'approve',
      selectedVariantId: 'social-main',
    })
    await runtime.publishRun(retried.id, { dryRun: true, platforms: ['twitter'] })
    expect(runtime.buildRunResult(retried.id).parent_run_id).toBe(run.id)
  })

  test('reports per-platform credential status for social publishing', () => {
    setEnv('TWITTER_GIVECARE_API_KEY', 'api-key')
    setEnv('TWITTER_GIVECARE_API_SECRET', 'api-secret')
    setEnv('TWITTER_GIVECARE_ACCESS_TOKEN', 'access-token')
    setEnv('TWITTER_GIVECARE_ACCESS_SECRET', 'access-secret')
    setEnv('INSTAGRAM_GIVECARE_ACCESS_TOKEN', 'instagram-token')
    setEnv('INSTAGRAM_GIVECARE_USER_ID', 'ig-user')

    const report = getSocialAuthReport('givecare')
    const twitter = report.platforms.find((platform) => platform.platform === 'twitter')
    const linkedin = report.platforms.find((platform) => platform.platform === 'linkedin')
    const instagram = report.platforms.find((platform) => platform.platform === 'instagram')

    expect(twitter).toMatchObject({ configured: true, supported: true })
    expect(linkedin?.configured).toBe(false)
    expect(linkedin?.missing.length).toBeGreaterThan(0)
    expect(instagram?.configured).toBe(false)
    expect(instagram?.missing).toContain('R2_CONFIG')
  })

  test('builds canonical run_result.v1 for failures', async () => {
    const root = createWorkspace()
    suppressImageApiKeys()
    const runtime = createRuntime({ root })

    await expect(runtime.runWorkflow({
      workflow: 'blog.post',
      brand: 'givecare',
      input: {
        topic: 'why caregiver benefits fail',
        pillar: 'missing-pillar',
      },
    })).rejects.toThrow('Unknown pillar for brand givecare: missing-pillar')

    const db = openRuntimeDb(root)
    const failedRunId = String((db.prepare(`SELECT id FROM runs ORDER BY created_at DESC LIMIT 1`).get() as Record<string, unknown>).id)
    const failedResult = runtime.buildRunResult(failedRunId)
    expect(failedResult.completed_at).toBeTypeOf('string')
    expect(isPerformanceSourceRunResultV1(failedResult)).toBe(false)
    expect(failedResult).toMatchObject({
      run_id: failedRunId,
      brief_id: `${'givecare'}.brief.${failedRunId}`,
      brand_id: 'givecare.brand.runtime',
      status: 'failed',
      current_step: 'brief',
      error: {
        step: 'brief',
        message: 'Unknown pillar for brand givecare: missing-pillar',
      },
    } satisfies Partial<CanonicalRunResultV1>)
  })

  test('dry-run social publish does not mark the run as published', async () => {
    const root = createWorkspace()
    setEnv('TWITTER_GIVECARE_API_KEY', 'api-key')
    setEnv('TWITTER_GIVECARE_API_SECRET', 'api-secret')
    setEnv('TWITTER_GIVECARE_ACCESS_TOKEN', 'access-token')
    setEnv('TWITTER_GIVECARE_ACCESS_SECRET', 'access-secret')

    const runtime = createRuntime({ root })
    suppressImageApiKeys()
    const run = await runtime.runWorkflow({
      workflow: 'social.post',
      brand: 'givecare',
      input: { topic: 'caregiver systems' },
    })

    runtime.reviewRun(run.id, {
      decision: 'approve',
      selectedVariantId: 'social-main',
    })

    const result = await runtime.publishRun(run.id, { dryRun: true })
    expect(result.status).toBe('approved')
  })

  test('enriches input with format from pillar default_format', async () => {
    const root = createWorkspace()

    writeFileSync(
      join(root, 'brands', 'givecare', 'brand.md'),
      `---
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
    perspective: Caregiving is infrastructure.
    signals:
      - caregiver benefits
    format: data-driven
    frequency: weekly
    default_format: infographic
  - id: policy
    perspective: Policy should reduce caregiver burden.
    signals:
      - paid leave
    format: opinionated-take
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
`,
    )

    const runtime = createRuntime({ root })
    suppressImageApiKeys()

    // care-economy pillar auto-resolves format to infographic
    const run = await runtime.runWorkflow({
      workflow: 'social.post',
      brand: 'givecare',
      input: { topic: 'unpaid care labor', pillar: 'care-economy' },
    })
    expect(run.input).toMatchObject({ format: 'infographic' })

    // policy pillar has no default_format — stays standard
    const run2 = await runtime.runWorkflow({
      workflow: 'social.post',
      brand: 'givecare',
      input: { topic: 'paid leave', pillar: 'policy' },
    })
    expect(run2.input).not.toHaveProperty('format')
  })
})
