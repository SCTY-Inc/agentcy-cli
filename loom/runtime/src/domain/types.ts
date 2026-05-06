export const WORKFLOW_NAMES = ['social.post', 'blog.post', 'outreach.touch', 'respond.reply'] as const
export type WorkflowName = typeof WORKFLOW_NAMES[number]

export const SOCIAL_PLATFORMS = ['twitter', 'linkedin', 'facebook', 'instagram', 'threads'] as const
export type SocialPlatform = typeof SOCIAL_PLATFORMS[number]

export type RunStatus =
  | 'in_review'
  | 'approved'
  | 'rejected'
  | 'published'
  | 'failed'

export type ArtifactType =
  | 'signal_packet'
  | 'brief'
  | 'draft_set'
  | 'explore_grid'
  | 'source_image'
  | 'asset_set'
  | 'outline'
  | 'article_draft'
  | 'approval'
  | 'delivery'

export const STEP_NAMES = [
  'signal',
  'brief',
  'draft',
  'explore',
  'image',
  'render',
  'outline',
  'publish',
  'review',
] as const
export type StepName = typeof STEP_NAMES[number]

export interface BrandAudience {
  id: string
  summary: string
}

export interface BrandOffer {
  id: string
  summary: string
  url?: string
  cta?: string
}

export interface BrandPlaybook {
  id: string
  trigger: string
  approach: string
}

export interface BrandChannel {
  objective: string
  platforms?: string[]
  defaultOffer?: string
}

export interface BrandPillar {
  id: string
  perspective: string
  signals: string[]
  format: string
  frequency: string
  defaultFormat?: string
}

export interface BrandFormat {
  id: string
  description: string
  promptOverlay?: string
}

export interface BrandApprovalLane {
  description?: string
  examples: string[]
}

export interface BrandSensitiveTopic {
  topic: string
  handling: string
  note?: string
}

export interface BrandPolicy {
  approvalLanes?: Partial<Record<'green' | 'yellow' | 'red', BrandApprovalLane>>
  approvalRequired: string[]
  autonomousActions: string[]
  humanRequiredActions: string[]
  forbiddenClaims: string[]
  regulatedClaims: string[]
  sensitiveTopics: BrandSensitiveTopic[]
  escalationRules: string[]
  citationPolicy?: string
  crisisPolicy?: {
    triggers: string[]
    response?: string
    owner?: string
  }
}

export interface BrandFoundation {
  id: string
  name: string
  positioning: string
  audiences: BrandAudience[]
  offers: BrandOffer[]
  proofPoints: string[]
  pillars: BrandPillar[]
  voice: {
    tone: string
    style: string
    do: string[]
    dont: string[]
  }
  channels: {
    social: BrandChannel
    blog: BrandChannel
    outreach: BrandChannel
    respond: BrandChannel
  }
  handles?: Partial<Record<SocialPlatform, string>>
  visual: {
    logo?: string
    palette: {
      background: string
      primary: string
      accent: string
    }
    typography?: {
      headline?: string
      body?: string
      accent?: string
    }
    style?: string
    composition?: string[]
    texture?: string[]
    negative?: string[]
    motif?: string
    imageStyle?: string
    imagePrompt?: string
    layout?: string
  }
  formats?: BrandFormat[]
  responsePlaybooks: BrandPlaybook[]
  outreachPlaybooks: BrandPlaybook[]
  policy: BrandPolicy
}

export interface RunRecord {
  id: string
  workflow: WorkflowName
  brand: string
  status: RunStatus
  input: Record<string, unknown>
  currentStep: StepName
  createdAt: string
  updatedAt: string
  parentRunId?: string
  errorMessage?: string
}

export interface ArtifactRecord {
  id: string
  runId: string
  type: ArtifactType
  step: StepName
  path: string
  createdAt: string
  data: Record<string, unknown>
}

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

export interface RunDetails {
  run: RunRecord
  artifacts: ArtifactRecord[]
  runResult?: CanonicalRunResultV1
}

export interface ReviewInput {
  decision: 'approve' | 'reject'
  note?: string
  selectedVariantId?: string
}

export interface RetryInput {
  fromStep: StepName
}

export interface ImportedBriefInput {
  path: string
  payload: Record<string, unknown>
  normalized: Record<string, unknown>
}

export interface RunWorkflowInput {
  workflow: WorkflowName
  brand: string
  input: Record<string, unknown>
  autoApprove?: boolean
}

export interface PublishInput {
  dryRun?: boolean
  platforms?: SocialPlatform[]
}

export function isWorkflowName(value: string): value is WorkflowName {
  return WORKFLOW_NAMES.includes(value as WorkflowName)
}

export function isSocialPlatform(value: string): value is SocialPlatform {
  return SOCIAL_PLATFORMS.includes(value as SocialPlatform)
}

export function isStepName(value: string): value is StepName {
  return STEP_NAMES.includes(value as StepName)
}
