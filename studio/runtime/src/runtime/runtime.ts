import { readFileSync, writeFileSync } from 'fs'
import { join } from 'path'
import type { DatabaseSync } from 'node:sqlite'
import { loadBrandFoundation } from '../brands/load'
import { loadRuntimeEnv } from '../core/env'
import { ensureParentDir, ensureRuntimePaths, resolveRuntimePaths, type RuntimePaths } from '../core/paths'
import { createId, nowIso } from '../core/ids'
import { buildSocialPublishPlan, publishSocialPost, type SocialPublisher } from '../publish/social'
import { parseBriefV1, type CanonicalBriefV1 } from '../domain/brief-v1'
import { buildRunResultV1, type CanonicalRunResultV1 } from '../domain/run-result-v1'
import {
  WORKFLOWS,
  cloneArtifactData,
  findArtifact,
  formatSocialPostText,
  resolveFormat,
  selectStepIndex,
  workflowChannel,
  type WorkflowContext,
} from './steps'
import type {
  ArtifactRecord,
  ArtifactType,
  BrandFoundation,
  PublishInput,
  RetryInput,
  ReviewInput,
  RunRecord,
  RunWorkflowInput,
  RunStatus,
  SocialPlatform,
  StepName,
} from '../domain/types'
import { openRuntimeDb } from './db'

export interface RunDetails {
  run: RunRecord
  artifacts: ArtifactRecord[]
  runResult?: CanonicalRunResultV1
}

interface RuntimeOptions {
  root?: string
  socialPublisher?: SocialPublisher
}

function normalizeImportedBrief(
  imported: Record<string, unknown>,
  workflow: RunWorkflowInput['workflow'],
  brand: BrandFoundation,
): Record<string, unknown> {
  const path = String(imported.path ?? '')
  const payload = parseBriefV1(imported.payload) as CanonicalBriefV1
  const brandPrefix = payload.brand_id.split('.')[0]
  if (brandPrefix !== brand.id) {
    throw new Error(`Invalid brief.v1: brand_id ${payload.brand_id} does not match --brand ${brand.id}`)
  }

  const channel = workflowChannel(workflow)
  const matchingDeliverable = payload.creative.deliverables?.find((deliverable) => deliverable.channel === channel)
  return {
    importedFrom: path || null,
    briefId: payload.brief_id,
    sourceArtifactType: payload.artifact_type,
    workflow,
    channel,
    brand: brand.name,
    objective: payload.objective,
    audience: brand.audiences[0]?.id ?? 'general',
    positioning: brand.positioning,
    offer: brand.offers[0]?.id ?? null,
    proofPoints: brand.proofPoints.slice(0, 2),
    pillar: null,
    perspective: payload.strategy.angle,
    format: matchingDeliverable?.kind ?? null,
    signals: payload.signal.evidence ?? [payload.signal.source],
    topic: payload.creative.headline,
    headline: payload.creative.headline,
    copy: payload.creative.copy,
    toneNotes: payload.creative.tone_notes,
    cta: payload.strategy.cta,
    platforms: payload.strategy.platforms,
    policyVerdict: payload.policy.verdict,
    policyConfidence: payload.policy.confidence,
    policyNotes: payload.policy.notes ?? [],
    signalSource: payload.signal.source,
    signalSummary: payload.signal.summary,
    signalEvidence: payload.signal.evidence ?? [],
    lineage: {
      briefId: payload.brief_id,
      brandId: payload.brand_id,
      voicePackId: payload.voice_pack_id,
      campaignId: payload.lineage?.campaign_id ?? null,
      signalId: payload.lineage?.signal_id ?? null,
      sourceVoicePackId: payload.lineage?.source_voice_pack_id ?? payload.voice_pack_id,
    },
  }
}

export class Runtime {
  private readonly root?: string
  private readonly db: DatabaseSync
  private readonly paths: RuntimePaths
  private socialPublisher: SocialPublisher

  constructor(options: RuntimeOptions = {}) {
    this.root = options.root
    this.paths = resolveRuntimePaths(this.root)
    loadRuntimeEnv(this.paths.root)
    ensureRuntimePaths(this.paths)
    this.db = openRuntimeDb(this.paths.root)
    this.socialPublisher = options.socialPublisher ?? publishSocialPost
  }

  async runWorkflow(input: RunWorkflowInput): Promise<RunRecord> {
    const brand = loadBrandFoundation(input.brand, { root: this.paths.root })
    const importedBrief = input.input.importedBrief
    if (importedBrief && typeof importedBrief !== 'object') {
      throw new Error('Invalid brief.v1 import: importedBrief must be an object')
    }
    const normalizedImportedBrief = importedBrief && !Array.isArray(importedBrief)
      ? {
        ...(importedBrief as Record<string, unknown>),
        normalized: normalizeImportedBrief(importedBrief as Record<string, unknown>, input.workflow, brand),
      }
      : undefined
    const runtimeInput = normalizedImportedBrief
      ? { ...input.input, importedBrief: normalizedImportedBrief }
      : input.input
    const format = resolveFormat(brand, runtimeInput)
    const runId = createId('run')
    const createdAt = nowIso()
    const steps = WORKFLOWS[input.workflow]
    const enrichedInput = format !== 'standard'
      ? { ...runtimeInput, format }
      : runtimeInput
    const finalStatus: RunStatus = input.autoApprove ? 'approved' : 'in_review'
    const run: RunRecord = {
      id: runId,
      workflow: input.workflow,
      brand: input.brand,
      status: finalStatus,
      input: enrichedInput,
      currentStep: steps[0].name,
      createdAt,
      updatedAt: createdAt,
    }

    this.insertRun(run)
    await this.executeWorkflow(run, brand, [], 0)

    if (input.autoApprove) {
      this.writeArtifact(runId, 'approval', 'review', {
        decision: 'approve',
        note: 'auto-approved',
        selectedVariantId: null,
      })
      this.updateRun(runId, 'approved', 'review')
    }

    return this.getRun(runId)
  }

  inspectRun(runId: string): RunDetails {
    const run = this.getRun(runId)
    const artifacts = this.listArtifacts(runId)
    return {
      run,
      artifacts,
      runResult: this.tryBuildRunResult(run, artifacts),
    }
  }

  listReviewRuns(): RunRecord[] {
    const rows = this.db.prepare(
      `SELECT * FROM runs WHERE status = 'in_review' ORDER BY created_at DESC`,
    ).all() as Array<Record<string, unknown>>
    return rows.map((row) => this.rowToRun(row))
  }

  reviewRun(runId: string, input: ReviewInput): RunRecord {
    const run = this.getRun(runId)
    if (run.status === 'published') {
      throw new Error(`Run ${runId} is already published and cannot be reviewed again`)
    }
    if (run.status === 'failed') {
      throw new Error(`Run ${runId} failed at step ${run.currentStep} and cannot be reviewed. Retry the run first.`)
    }

    const status: RunStatus = input.decision === 'approve' ? 'approved' : 'rejected'

    if (input.selectedVariantId) {
      const artifacts = this.listArtifacts(runId)
      const draft = findArtifact(artifacts, 'draft_set')
      const variants = Array.isArray(draft?.data.variants) ? draft.data.variants as Array<Record<string, unknown>> : []
      const hasSelectedVariant = variants.some((variant) => variant.id === input.selectedVariantId)
      if (!hasSelectedVariant) {
        throw new Error(`Variant not found for run ${runId}: ${input.selectedVariantId}`)
      }
    }

    this.writeArtifact(runId, 'approval', 'review', {
      decision: input.decision,
      note: input.note ?? null,
      selectedVariantId: input.selectedVariantId ?? null,
    })

    this.updateRun(runId, status, 'review')
    return this.getRun(runId)
  }

  setSocialPublisher(publisher: SocialPublisher): void {
    this.socialPublisher = publisher
  }

  buildRunResult(runId: string): CanonicalRunResultV1 {
    const run = this.getRun(runId)
    const artifacts = this.listArtifacts(runId)
    return buildRunResultV1(run, artifacts)
  }

  async publishRun(runId: string, input: PublishInput = {}): Promise<RunRecord> {
    const run = this.getRun(runId)
    if (run.status === 'published') {
      return run
    }
    if (run.status !== 'approved') {
      throw new Error(`Run ${runId} must be approved before publish`)
    }

    const artifacts = this.listArtifacts(runId)
    const channel = workflowChannel(run.workflow)
    const payload: Record<string, unknown> = {
      workflow: run.workflow,
      channel,
      simulated: run.workflow !== 'social.post',
    }

    if (run.workflow === 'social.post') {
      const draft = findArtifact(artifacts, 'draft_set')
      const assetSet = findArtifact(artifacts, 'asset_set')
      const approval = findArtifact([...artifacts].reverse(), 'approval')
      const variants = Array.isArray(draft?.data.variants) ? draft.data.variants as Array<Record<string, unknown>> : []
      const selectedVariantId = typeof approval?.data.selectedVariantId === 'string'
        ? approval.data.selectedVariantId
        : undefined
      const selectedVariant = selectedVariantId
        ? variants.find((variant) => variant.id === selectedVariantId)
        : variants[0]
      if (!selectedVariant) {
        if (selectedVariantId) {
          throw new Error(`Run ${runId} selected variant is missing from draft set: ${selectedVariantId}`)
        }
        throw new Error(`Run ${runId} has no social draft variant to publish`)
      }

      const platformAssets = assetSet?.data.platformAssets && typeof assetSet.data.platformAssets === 'object'
        ? assetSet.data.platformAssets as Record<SocialPlatform, string>
        : undefined
      if (!platformAssets) {
        throw new Error(`Run ${runId} has no platform assets to publish`)
      }

      const plan = buildSocialPublishPlan(run.brand, input)
      const results = await this.socialPublisher({
        brand: run.brand,
        text: formatSocialPostText(selectedVariant),
        platformAssets,
        platforms: plan.platforms,
        dryRun: input.dryRun,
        root: this.paths.root,
      })

      const allSucceeded = results.every((result) => result.success)
      payload.platforms = plan.platforms
      payload.results = results
      payload.selectedVariantId = selectedVariant.id ?? null
      payload.text = formatSocialPostText(selectedVariant)
      payload.imagePath = typeof assetSet?.data.imagePath === 'string' ? assetSet.data.imagePath : null
      payload.platformAssets = platformAssets
      payload.auth = plan.auth
      payload.simulated = false
      payload.dryRun = Boolean(input.dryRun)

      this.writeArtifact(runId, 'delivery', 'publish', payload)
      const status: RunStatus = input.dryRun ? 'approved' : allSucceeded ? 'published' : 'approved'
      const step: StepName = input.dryRun ? 'review' : allSucceeded ? 'publish' : 'review'
      this.updateRun(runId, status, step)
      return this.getRun(runId)
    }

    if (run.workflow === 'blog.post') {
      const article = findArtifact(artifacts, 'article_draft')
      const exportPath = join(this.paths.exportsDir, `${runId}.md`)
      ensureParentDir(exportPath)
      writeFileSync(exportPath, String(article?.data.markdown ?? ''), 'utf8')
      payload.exportPath = exportPath
    }

    this.writeArtifact(runId, 'delivery', 'publish', payload)
    this.updateRun(runId, 'published', 'publish')
    return this.getRun(runId)
  }

  async retryRun(runId: string, input: RetryInput): Promise<RunRecord> {
    const original = this.getRun(runId)
    const brand = loadBrandFoundation(original.brand, { root: this.paths.root })
    const createdAt = nowIso()
    const steps = WORKFLOWS[original.workflow]
    const startIndex = selectStepIndex(original.workflow, input.fromStep)
    const newRun: RunRecord = {
      id: createId('run'),
      workflow: original.workflow,
      brand: original.brand,
      status: 'in_review',
      input: {
        ...original.input,
        retry: {
          fromRunId: runId,
          fromStep: input.fromStep,
        },
      },
      currentStep: steps[startIndex].name,
      createdAt,
      updatedAt: createdAt,
      parentRunId: runId,
    }

    this.insertRun(newRun)

    const originalArtifacts = this.listArtifacts(runId)

    const reused = originalArtifacts
      .filter((artifact) => {
        const stepIndex = steps.findIndex((step) => step.name === artifact.step)
        return stepIndex > -1 && stepIndex < startIndex
      })
      .map((artifact) => ({
        type: artifact.type,
        step: artifact.step,
        data: cloneArtifactData(artifact.data),
      }))

    const priorArtifacts = reused.map((artifact) =>
      this.writeArtifact(newRun.id, artifact.type, artifact.step, artifact.data),
    )
    await this.executeWorkflow(newRun, brand, priorArtifacts, startIndex)
    return this.getRun(newRun.id)
  }

  health(): Record<string, unknown> {
    const counts = this.db.prepare(`SELECT status, COUNT(*) as count FROM runs GROUP BY status`).all() as Array<Record<string, unknown>>
    const byStatus = Object.fromEntries(
      counts.map((row) => [String(row.status), Number(row.count)]),
    ) as Partial<Record<RunStatus, number>>

    return {
      root: this.paths.root,
      dbPath: this.paths.dbPath,
      brandsDir: this.paths.brandsDir,
      stateDir: this.paths.stateDir,
      reviewRuns: byStatus.in_review ?? 0,
      failedRuns: byStatus.failed ?? 0,
      totalRuns: Object.values(byStatus).reduce((sum, count) => sum + (count ?? 0), 0),
    }
  }

  private async executeWorkflow(
    run: RunRecord,
    brand: BrandFoundation,
    seedArtifacts: ArtifactRecord[],
    startIndex: number,
  ): Promise<void> {
    let priorArtifacts = [...seedArtifacts]
    const steps = WORKFLOWS[run.workflow]

    for (const step of steps.slice(startIndex)) {
      try {
        const outputs = await step.run({
          brand,
          workflow: run.workflow,
          runId: run.id,
          input: run.input,
          priorArtifacts,
          paths: this.paths,
        })

        const writtenArtifacts = outputs.map((output) =>
          this.writeArtifact(run.id, output.type, step.name, output.data),
        )

        priorArtifacts = [...priorArtifacts, ...writtenArtifacts]
        this.updateRun(run.id, 'in_review', step.name)
      } catch (error) {
        this.updateRunFailure(run.id, step.name, error)
        throw error
      }
    }
  }

  private insertRun(run: RunRecord): void {
    this.db.prepare(`
      INSERT INTO runs (id, workflow, brand, status, input_json, current_step, created_at, updated_at, parent_run_id, error_message)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      run.id,
      run.workflow,
      run.brand,
      run.status,
      JSON.stringify(run.input),
      run.currentStep,
      run.createdAt,
      run.updatedAt,
      run.parentRunId ?? null,
      run.errorMessage ?? null,
    )
  }

  private updateRun(runId: string, status: RunStatus, currentStep: StepName): void {
    this.db.prepare(`
      UPDATE runs
      SET status = ?, current_step = ?, updated_at = ?, error_message = NULL
      WHERE id = ?
    `).run(status, currentStep, nowIso(), runId)
  }

  private updateRunFailure(runId: string, currentStep: StepName, error: unknown): void {
    const message = error instanceof Error ? error.message : String(error)
    this.db.prepare(`
      UPDATE runs
      SET status = 'failed', current_step = ?, updated_at = ?, error_message = ?
      WHERE id = ?
    `).run(currentStep, nowIso(), message, runId)
  }

  private writeArtifact(runId: string, type: ArtifactType, step: StepName, data: Record<string, unknown>): ArtifactRecord {
    const artifactId = createId('artifact')
    const path = join(this.paths.artifactsDir, runId, `${artifactId}.json`)
    const createdAt = nowIso()

    ensureParentDir(path)
    writeFileSync(path, JSON.stringify(data, null, 2), 'utf8')
    this.db.prepare(`
      INSERT INTO artifacts (id, run_id, type, step, path, created_at, data_json)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(artifactId, runId, type, step, path, createdAt, JSON.stringify(data))

    return {
      id: artifactId,
      runId,
      type,
      step,
      path,
      createdAt,
      data,
    }
  }

  private listArtifacts(runId: string): ArtifactRecord[] {
    const rows = this.db.prepare(`
      SELECT * FROM artifacts
      WHERE run_id = ?
      ORDER BY created_at ASC
    `).all(runId) as Array<Record<string, unknown>>

    return rows.map((row) => ({
      id: String(row.id),
      runId: String(row.run_id),
      type: row.type as ArtifactType,
      step: row.step as StepName,
      path: String(row.path),
      createdAt: String(row.created_at),
      data: JSON.parse(String(row.data_json)) as Record<string, unknown>,
    }))
  }

  private getRun(runId: string): RunRecord {
    const row = this.db.prepare(`SELECT * FROM runs WHERE id = ?`).get(runId) as Record<string, unknown> | undefined
    if (!row) {
      throw new Error(`Run not found: ${runId}`)
    }
    return this.rowToRun(row)
  }

  private rowToRun(row: Record<string, unknown>): RunRecord {
    return {
      id: String(row.id),
      workflow: row.workflow as RunRecord['workflow'],
      brand: String(row.brand),
      status: row.status as RunRecord['status'],
      input: JSON.parse(String(row.input_json)) as Record<string, unknown>,
      currentStep: row.current_step as RunRecord['currentStep'],
      createdAt: String(row.created_at),
      updatedAt: String(row.updated_at),
      parentRunId: row.parent_run_id ? String(row.parent_run_id) : undefined,
      errorMessage: row.error_message ? String(row.error_message) : undefined,
    }
  }

  private tryBuildRunResult(run: RunRecord, artifacts: ArtifactRecord[]): CanonicalRunResultV1 | undefined {
    try {
      return buildRunResultV1(run, artifacts)
    } catch {
      return undefined
    }
  }
}

export function createRuntime(options: RuntimeOptions = {}): Runtime {
  return new Runtime(options)
}
