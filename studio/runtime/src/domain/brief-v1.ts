import { readFileSync } from 'fs'

export interface CanonicalBriefV1 {
  artifact_type: 'brief.v1'
  schema_version: 'v1'
  brief_id: string
  brand_id: string
  voice_pack_id: string
  writer: {
    repo: 'brand-os'
    module: 'agentcy-compass'
  }
  objective: string
  signal: {
    source: string
    summary: string
    evidence?: string[]
  }
  strategy: {
    angle: string
    cta: string
    platforms: string[]
  }
  policy: {
    verdict: 'approved' | 'escalate' | 'deny'
    confidence: number
    notes?: string[]
  }
  creative: {
    headline: string
    copy: string
    tone_notes: string[]
    deliverables?: Array<{
      kind: string
      channel: string
      notes?: string
    }>
  }
  lineage?: {
    source_voice_pack_id?: string
    campaign_id?: string
    signal_id?: string
  }
}

function expectRecord(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`Invalid brief.v1: ${label} must be an object`)
  }
  return value as Record<string, unknown>
}

function expectNonEmptyString(value: unknown, label: string): string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new Error(`Invalid brief.v1: ${label} must be a non-empty string`)
  }
  return value.trim()
}

function expectStringArray(value: unknown, label: string, options: { minItems?: number } = {}): string[] {
  if (!Array.isArray(value)) {
    throw new Error(`Invalid brief.v1: ${label} must be an array`)
  }
  const strings = value.map((item, index) => expectNonEmptyString(item, `${label}[${index}]`))
  if ((options.minItems ?? 0) > strings.length) {
    throw new Error(`Invalid brief.v1: ${label} must contain at least ${options.minItems} item(s)`)
  }
  return strings
}

export function parseBriefV1(input: unknown): CanonicalBriefV1 {
  const brief = expectRecord(input, 'brief.v1 payload')
  if (brief.artifact_type !== 'brief.v1') {
    throw new Error('Invalid brief.v1: artifact_type must equal "brief.v1"')
  }
  if (brief.schema_version !== 'v1') {
    throw new Error('Invalid brief.v1: schema_version must equal "v1"')
  }

  const writer = expectRecord(brief.writer, 'writer')
  if (writer.repo !== 'brand-os' || writer.module !== 'agentcy-compass') {
    throw new Error('Invalid brief.v1: writer must be brand-os / agentcy-compass')
  }

  const signal = expectRecord(brief.signal, 'signal')
  const strategy = expectRecord(brief.strategy, 'strategy')
  const policy = expectRecord(brief.policy, 'policy')
  const creative = expectRecord(brief.creative, 'creative')
  const lineage = brief.lineage === undefined ? undefined : expectRecord(brief.lineage, 'lineage')

  const parsed: CanonicalBriefV1 = {
    artifact_type: 'brief.v1',
    schema_version: 'v1',
    brief_id: expectNonEmptyString(brief.brief_id, 'brief_id'),
    brand_id: expectNonEmptyString(brief.brand_id, 'brand_id'),
    voice_pack_id: expectNonEmptyString(brief.voice_pack_id, 'voice_pack_id'),
    writer: {
      repo: 'brand-os',
      module: 'agentcy-compass',
    },
    objective: expectNonEmptyString(brief.objective, 'objective'),
    signal: {
      source: expectNonEmptyString(signal.source, 'signal.source'),
      summary: expectNonEmptyString(signal.summary, 'signal.summary'),
      evidence: signal.evidence === undefined ? undefined : expectStringArray(signal.evidence, 'signal.evidence'),
    },
    strategy: {
      angle: expectNonEmptyString(strategy.angle, 'strategy.angle'),
      cta: expectNonEmptyString(strategy.cta, 'strategy.cta'),
      platforms: expectStringArray(strategy.platforms, 'strategy.platforms', { minItems: 1 }),
    },
    policy: {
      verdict: (() => {
        const verdict = expectNonEmptyString(policy.verdict, 'policy.verdict')
        if (!['approved', 'escalate', 'deny'].includes(verdict)) {
          throw new Error('Invalid brief.v1: policy.verdict must be one of approved, escalate, deny')
        }
        return verdict as CanonicalBriefV1['policy']['verdict']
      })(),
      confidence: (() => {
        if (typeof policy.confidence !== 'number' || Number.isNaN(policy.confidence) || policy.confidence < 0 || policy.confidence > 1) {
          throw new Error('Invalid brief.v1: policy.confidence must be a number between 0 and 1')
        }
        return policy.confidence
      })(),
      notes: policy.notes === undefined ? undefined : expectStringArray(policy.notes, 'policy.notes'),
    },
    creative: {
      headline: expectNonEmptyString(creative.headline, 'creative.headline'),
      copy: expectNonEmptyString(creative.copy, 'creative.copy'),
      tone_notes: expectStringArray(creative.tone_notes, 'creative.tone_notes', { minItems: 1 }),
      deliverables: undefined,
    },
    lineage: lineage === undefined
      ? undefined
      : {
        source_voice_pack_id: lineage.source_voice_pack_id === undefined
          ? undefined
          : expectNonEmptyString(lineage.source_voice_pack_id, 'lineage.source_voice_pack_id'),
        campaign_id: lineage.campaign_id === undefined
          ? undefined
          : expectNonEmptyString(lineage.campaign_id, 'lineage.campaign_id'),
        signal_id: lineage.signal_id === undefined
          ? undefined
          : expectNonEmptyString(lineage.signal_id, 'lineage.signal_id'),
      },
  }

  if (creative.deliverables !== undefined) {
    if (!Array.isArray(creative.deliverables)) {
      throw new Error('Invalid brief.v1: creative.deliverables must be an array')
    }
    parsed.creative.deliverables = creative.deliverables.map((item, index) => {
      const deliverable = expectRecord(item, `creative.deliverables[${index}]`)
      return {
        kind: expectNonEmptyString(deliverable.kind, `creative.deliverables[${index}].kind`),
        channel: expectNonEmptyString(deliverable.channel, `creative.deliverables[${index}].channel`),
        notes: deliverable.notes === undefined ? undefined : expectNonEmptyString(deliverable.notes, `creative.deliverables[${index}].notes`),
      }
    })
  }

  if (parsed.lineage && parsed.lineage.source_voice_pack_id === undefined) {
    throw new Error('Invalid brief.v1: lineage.source_voice_pack_id is required when lineage is present')
  }
  if (parsed.lineage?.source_voice_pack_id && parsed.lineage.source_voice_pack_id !== parsed.voice_pack_id) {
    throw new Error('Invalid brief.v1: lineage.source_voice_pack_id must equal voice_pack_id')
  }

  return parsed
}

export function loadBriefV1(path: string): CanonicalBriefV1 {
  let payload: unknown
  try {
    payload = JSON.parse(readFileSync(path, 'utf8')) as unknown
  } catch (error) {
    throw new Error(`Invalid brief.v1: failed to parse JSON at ${path}: ${error instanceof Error ? error.message : String(error)}`)
  }
  return parseBriefV1(payload)
}
