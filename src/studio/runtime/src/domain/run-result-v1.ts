import type { ArtifactRecord, RunRecord } from './types'

export type CanonicalRunResultStatus = 'dry_run' | 'published' | 'failed'

/**
 * Canonical loom-owned publish outcome exported for family handoffs.
 *
 * Loop-5 `performance.v1` readers should treat only published `social.post`
 * results as measurement sources. `dry_run` and `failed` outcomes are explicit
 * non-sources even though they remain exportable for operator inspection.
 */
export interface CanonicalRunResultV1 {
  artifact_type: 'run_result.v1'
  schema_version: 'v1'
  run_id: string
  parent_run_id?: string
  brief_id: string
  brand_id: string
  writer: {
    repo: 'cli-phantom'
    module: 'agentcy-loom'
  }
  workflow: string
  status: CanonicalRunResultStatus
  current_step: string
  started_at: string
  completed_at: string
  review?: {
    decision?: 'approved' | 'rejected' | 'needs_revision'
    summary?: string
  }
  delivery?: {
    dry_run?: boolean
    platforms?: Array<{
      platform: string
      status: 'simulated' | 'published' | 'failed' | 'skipped'
      post_id?: string
      url?: string
      message?: string
    }>
    export_paths?: string[]
    selected_variant_id?: string
  }
  error?: {
    step: string
    message: string
  }
  lineage?: {
    source_voice_pack_id?: string
    campaign_id?: string
    signal_id?: string
  }
}

function findLatestArtifact(artifacts: ArtifactRecord[], type: ArtifactRecord['type']): ArtifactRecord | undefined {
  for (let index = artifacts.length - 1; index >= 0; index -= 1) {
    if (artifacts[index]?.type === type) return artifacts[index]
  }
  return undefined
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined
  return value as Record<string, unknown>
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim().length > 0 ? value : undefined
}

function inferBriefId(run: RunRecord, brief: Record<string, unknown> | undefined): string {
  const lineage = asRecord(brief?.lineage)
  const importedBrief = asRecord(run.input.importedBrief)
  const normalizedImportedBrief = asRecord(importedBrief?.normalized)
  return asString(brief?.briefId)
    ?? asString(lineage?.briefId)
    ?? asString(normalizedImportedBrief?.briefId)
    ?? `${run.brand}.brief.${run.id}`
}

function inferBrandId(run: RunRecord, brief: Record<string, unknown> | undefined): string {
  const lineage = asRecord(brief?.lineage)
  const importedBrief = asRecord(run.input.importedBrief)
  const normalizedImportedBrief = asRecord(importedBrief?.normalized)
  return asString(lineage?.brandId)
    ?? asString(asRecord(normalizedImportedBrief?.lineage)?.brandId)
    ?? `${run.brand}.brand.runtime`
}

function buildReviewSummary(run: RunRecord, approval: Record<string, unknown> | undefined): CanonicalRunResultV1['review'] | undefined {
  const decision = asString(approval?.decision)
  const note = asString(approval?.note)

  if (!decision && !note) return undefined

  const normalizedDecision = decision === 'approve'
    ? 'approved'
    : decision === 'reject'
      ? 'rejected'
      : undefined

  let summary = note
  if (!summary && normalizedDecision === 'approved') {
    summary = run.status === 'published'
      ? 'Approved after review; published to the selected channels.'
      : 'Operator approved simulated delivery for external review.'
  }
  if (!summary && normalizedDecision === 'rejected') {
    summary = 'Run was rejected during review.'
  }

  if (!normalizedDecision && !summary) return undefined
  return {
    ...(normalizedDecision ? { decision: normalizedDecision } : {}),
    ...(summary ? { summary } : {}),
  }
}

function buildDeliverySummary(delivery: Record<string, unknown> | undefined): CanonicalRunResultV1['delivery'] | undefined {
  if (!delivery) return undefined

  const resultItems = Array.isArray(delivery.results) ? delivery.results : []
  const platforms = resultItems
    .map((result) => asRecord(result))
    .filter((result): result is Record<string, unknown> => Boolean(result))
    .map((result) => {
      const success = Boolean(result.success)
      const dryRun = Boolean(delivery.dryRun)
      const status = dryRun ? 'simulated' : success ? 'published' : 'failed'
      const item: NonNullable<NonNullable<CanonicalRunResultV1['delivery']>['platforms']>[number] = {
        platform: asString(result.platform) ?? 'unknown',
        status,
      }
      const postId = asString(result.postId)
      const postUrl = asString(result.postUrl)
      const message = asString(result.error) ?? (dryRun ? 'Dry-run only; no post was sent.' : undefined)
      if (postId) item.post_id = postId
      if (postUrl) item.url = postUrl
      if (message) item.message = message
      return item
    })

  const exportPaths = [asString(delivery.exportPath)].filter((value): value is string => Boolean(value))
  const selectedVariantId = asString(delivery.selectedVariantId)
  const dryRun = typeof delivery.dryRun === 'boolean' ? delivery.dryRun : undefined

  if (!platforms.length && !exportPaths.length && dryRun === undefined && !selectedVariantId) {
    return undefined
  }

  return {
    ...(dryRun !== undefined ? { dry_run: dryRun } : {}),
    ...(platforms.length > 0 ? { platforms } : {}),
    ...(exportPaths.length > 0 ? { export_paths: exportPaths } : {}),
    ...(selectedVariantId ? { selected_variant_id: selectedVariantId } : {}),
  }
}

export function isPerformanceSourceRunResultV1(result: CanonicalRunResultV1): boolean {
  return result.workflow === 'social.post' && result.status === 'published'
}

export function buildRunResultV1(run: RunRecord, artifacts: ArtifactRecord[]): CanonicalRunResultV1 {
  const briefArtifact = findLatestArtifact(artifacts, 'brief')
  const brief = asRecord(briefArtifact?.data)

  const approval = asRecord(findLatestArtifact(artifacts, 'approval')?.data)
  const delivery = asRecord(findLatestArtifact(artifacts, 'delivery')?.data)
  const importedBrief = asRecord(run.input.importedBrief)
  const normalizedImportedBrief = asRecord(importedBrief?.normalized)
  const lineage = asRecord(brief?.lineage) ?? asRecord(normalizedImportedBrief?.lineage)

  const status: CanonicalRunResultStatus = run.status === 'failed'
    ? 'failed'
    : delivery?.dryRun === true
      ? 'dry_run'
      : run.status === 'published'
        ? 'published'
        : (() => { throw new Error(`Run ${run.id} has not reached an exportable run_result.v1 state`) })()

  const payload: CanonicalRunResultV1 = {
    artifact_type: 'run_result.v1',
    schema_version: 'v1',
    run_id: run.id,
    brief_id: inferBriefId(run, brief),
    brand_id: inferBrandId(run, brief),
    writer: {
      repo: 'cli-phantom',
      module: 'agentcy-loom',
    },
    workflow: run.workflow,
    status,
    current_step: run.currentStep,
    started_at: run.createdAt,
    completed_at: run.updatedAt,
  }

  if (run.parentRunId) payload.parent_run_id = run.parentRunId

  const review = buildReviewSummary(run, approval)
  if (review) payload.review = review

  const deliverySummary = buildDeliverySummary(delivery)
  if (deliverySummary) payload.delivery = deliverySummary

  if (lineage) {
    const resultLineage = {
      ...(asString(lineage.sourceVoicePackId) ? { source_voice_pack_id: asString(lineage.sourceVoicePackId) } : {}),
      ...(asString(lineage.campaignId) ? { campaign_id: asString(lineage.campaignId) } : {}),
      ...(asString(lineage.signalId) ? { signal_id: asString(lineage.signalId) } : {}),
    }
    if (Object.keys(resultLineage).length > 0) payload.lineage = resultLineage
  }

  if (status === 'failed') {
    payload.error = {
      step: run.currentStep,
      message: run.errorMessage ?? 'Run failed without a recorded error message',
    }
  }

  return payload
}
