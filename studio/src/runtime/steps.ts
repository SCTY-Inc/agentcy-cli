import type {
  ArtifactRecord,
  ArtifactType,
  BrandFoundation,
  BrandVisualPalette,
  BrandVisualStyle,
  ImportedBriefInput,
  StepName,
  WorkflowName,
} from '../domain/types'
import { brandLogoDataUri } from '../brands/assets'
import { generateSocialDraftSet } from '../generate/copy'
import { renderCard } from '../render/pipeline'
import type { Ground } from '../render/tokens'
import type { RuntimePaths } from '../core/paths'

export interface WorkflowContext {
  brand: BrandFoundation
  workflow: WorkflowName
  runId: string
  input: Record<string, unknown>
  priorArtifacts: ArtifactRecord[]
  paths: RuntimePaths
}

export interface StepOutput {
  type: ArtifactType
  data: Record<string, unknown>
}

export interface StepDefinition {
  name: StepName
  run: (context: WorkflowContext) => Promise<StepOutput[]>
}

export const WORKFLOWS: Record<WorkflowName, StepDefinition[]> = {
  'social.post': [
    { name: 'signal', run: buildSignalArtifacts },
    { name: 'brief', run: buildBriefArtifacts },
    { name: 'draft', run: buildSocialDraftArtifacts },
    { name: 'render', run: buildAssetArtifacts },
  ],
  'blog.post': [
    { name: 'signal', run: buildSignalArtifacts },
    { name: 'brief', run: buildBriefArtifacts },
    { name: 'outline', run: buildOutlineArtifacts },
    { name: 'draft', run: buildArticleDraftArtifacts },
  ],
  'outreach.touch': [
    { name: 'signal', run: buildSignalArtifacts },
    { name: 'brief', run: buildBriefArtifacts },
    { name: 'draft', run: buildOutreachDraftArtifacts },
  ],
  'respond.reply': [
    { name: 'signal', run: buildSignalArtifacts },
    { name: 'brief', run: buildBriefArtifacts },
    { name: 'draft', run: buildResponseDraftArtifacts },
  ],
}

/**
 * Resolve the effective format for a run. Priority:
 * 1. Explicit input.format
 * 2. Selected pillar's defaultFormat
 * 3. 'standard' (default behavior)
 */
export function resolveFormat(brand: BrandFoundation, input: Record<string, unknown>): string {
  if (typeof input.format === 'string' && input.format.trim().length > 0) {
    return input.format.trim()
  }
  if (typeof input.pillar === 'string') {
    const pillar = brand.pillars.find((p) => p.id === input.pillar)
    if (pillar?.defaultFormat) return pillar.defaultFormat
  }
  return 'standard'
}

export function workflowChannel(workflow: WorkflowName): 'social' | 'blog' | 'outreach' | 'respond' {
  if (workflow === 'social.post') return 'social'
  if (workflow === 'blog.post') return 'blog'
  if (workflow === 'outreach.touch') return 'outreach'
  return 'respond'
}

export function selectStepIndex(workflow: WorkflowName, fromStep?: StepName): number {
  if (!fromStep) return 0
  const index = WORKFLOWS[workflow].findIndex((step) => step.name === fromStep)
  return index === -1 ? 0 : index
}

export function findArtifact(artifacts: ArtifactRecord[], type: ArtifactType): ArtifactRecord | undefined {
  return artifacts.find((artifact) => artifact.type === type)
}

export function formatSocialPostText(variant: Record<string, unknown>): string {
  return [variant.hook, variant.body, variant.cta]
    .filter((value) => typeof value === 'string' && value.trim().length > 0)
    .join('\n\n')
}

function nonEmptyString(value: unknown): string | null {
  return typeof value === 'string' && value.trim().length > 0 ? value.trim() : null
}

function titleCaseLabel(value: string): string {
  return value
    .replace(/[-_]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .split(' ')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function findPillarForTopic(brand: BrandFoundation, topic: string): string | null {
  const normalized = topic.toLowerCase()
  const matched = brand.pillars.find((pillar) => {
    const labels = [
      pillar.id.replace(/[-_]+/g, ' '),
      ...pillar.signals,
    ].map((label) => label.toLowerCase())

    return labels.some((label) => label.length > 0 && normalized.includes(label))
  })
  return matched?.id ?? null
}

function hexLuminance(hex: string): number {
  const match = hex.trim().match(/^#?([0-9a-f]{6})$/i)
  if (!match) return 1
  const value = match[1]
  const channels = [0, 2, 4].map((index) => parseInt(value.slice(index, index + 2), 16) / 255)
  const linear = channels.map((channel) =>
    channel <= 0.03928 ? channel / 12.92 : Math.pow((channel + 0.055) / 1.055, 2.4),
  )
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
}

function mergePalette(base: BrandFoundation['visual']['palette'], override?: BrandVisualPalette): BrandFoundation['visual']['palette'] {
  return {
    background: override?.background ?? base.background,
    primary: override?.primary ?? base.primary,
    secondary: override?.secondary ?? base.secondary,
    accent: override?.accent ?? base.accent,
    text: override?.text ?? base.text,
  }
}

function brandGround(brand: BrandFoundation, style?: BrandVisualStyle): Ground {
  const palette = mergePalette(brand.visual.palette, style?.palette)
  const bg = palette.background || '#FFFFFF'
  const fg = palette.text || palette.primary || '#111111'
  return {
    bg,
    fg,
    primary: palette.primary,
    secondary: palette.secondary,
    accent: palette.accent,
    dark: hexLuminance(bg) < 0.45,
  }
}

function resolveVisualStyle(brand: BrandFoundation, input: Record<string, unknown>): BrandVisualStyle | undefined {
  const requestedStyle = nonEmptyString(input.style)
  const styles = brand.visual.styles

  if (requestedStyle) {
    const found = styles.find((style) => style.id === requestedStyle)
    if (!found) {
      throw new Error(`Unknown visual style for brand ${brand.id}: ${requestedStyle}`)
    }
    return found
  }

  if (brand.visual.defaultStyle) {
    return styles.find((style) => style.id === brand.visual.defaultStyle)
  }

  return styles[0]
}

function resolveCardEyebrow(context: WorkflowContext): string {
  const brief = findArtifact(context.priorArtifacts, 'brief')
  const pillar = nonEmptyString(brief?.data.pillar)
  if (pillar) return titleCaseLabel(pillar)

  const format = nonEmptyString(brief?.data.format)
  if (format) return titleCaseLabel(format)

  const inferredPillar = findPillarForTopic(context.brand, resolveTopicFromContext(context))
  if (inferredPillar) return titleCaseLabel(inferredPillar)

  return context.workflow === 'social.post' ? 'Social Post' : titleCaseLabel(workflowChannel(context.workflow))
}

function resolveCardHeadline(
  draft: ArtifactRecord | undefined,
  mainVariant: Record<string, unknown> | null,
  context: WorkflowContext,
): string {
  return nonEmptyString(mainVariant?.hook)
    ?? nonEmptyString(draft?.data.headline)
    ?? nonEmptyString(context.input.topic)
    ?? 'Untitled'
}

export function cloneArtifactData(data: Record<string, unknown>): Record<string, unknown> {
  return JSON.parse(JSON.stringify(data)) as Record<string, unknown>
}

function brandPolicySummary(brand: BrandFoundation): Record<string, unknown> | null {
  const policy = brand.policy
  const hasPolicy = Boolean(
    policy.approvalLanes
    || policy.autonomousActions.length
    || policy.humanRequiredActions.length
    || policy.forbiddenClaims.length
    || policy.regulatedClaims.length
    || policy.sensitiveTopics.length
    || policy.escalationRules.length
    || policy.citationPolicy
    || policy.crisisPolicy,
  )
  if (!hasPolicy) return null

  return {
    approvalLanes: policy.approvalLanes ?? null,
    approvalRequired: policy.approvalRequired,
    autonomousActions: policy.autonomousActions,
    humanRequiredActions: policy.humanRequiredActions,
    forbiddenClaims: policy.forbiddenClaims,
    regulatedClaims: policy.regulatedClaims,
    sensitiveTopics: policy.sensitiveTopics,
    escalationRules: policy.escalationRules,
    citationPolicy: policy.citationPolicy ?? null,
    crisisPolicy: policy.crisisPolicy ?? null,
  }
}

function getImportedBrief(input: Record<string, unknown>): ImportedBriefInput | undefined {
  const imported = input.importedBrief
  if (!imported || typeof imported !== 'object' || Array.isArray(imported)) return undefined

  const record = imported as Record<string, unknown>
  const normalized = record.normalized
  if (!normalized || typeof normalized !== 'object' || Array.isArray(normalized)) return undefined
  if (typeof record.path !== 'string') return undefined
  if (!record.payload || typeof record.payload !== 'object' || Array.isArray(record.payload)) return undefined

  return record as unknown as ImportedBriefInput
}

// --- Step implementations ---

async function discoverTopic(brand: BrandFoundation): Promise<string | null> {
  const pillar = brand.pillars[0]
  if (!pillar) return null

  return pillar.signals[0] ?? pillar.perspective
}

async function buildSignalArtifacts(context: WorkflowContext): Promise<StepOutput[]> {
  const importedBrief = getImportedBrief(context.input)
  if (importedBrief) {
    const brief = importedBrief.normalized
    return [
      {
        type: 'signal_packet' as const,
        data: {
          workflow: context.workflow,
          channel: workflowChannel(context.workflow),
          topic: brief.topic ?? brief.objective ?? brief.headline ?? 'Untitled',
          discovered: false,
          source: brief.signalSource ?? null,
          sources: Array.isArray(brief.signalEvidence) ? brief.signalEvidence : [],
          account: context.input.account ?? null,
          goal: brief.objective ?? null,
        },
      },
    ]
  }

  let topic = context.input.topic as string | null ?? null

  if (!topic) {
    topic = await discoverTopic(context.brand)
    if (!topic) throw new Error('No --topic provided and signal discovery failed (no API key?)')
  }

  return [
    {
      type: 'signal_packet' as const,
      data: {
        workflow: context.workflow,
        channel: workflowChannel(context.workflow),
        topic,
        discovered: !context.input.topic,
        source: context.input.source ?? null,
        sources: context.input.sources ?? [],
        account: context.input.account ?? null,
        goal: context.input.goal ?? null,
      },
    },
  ]
}

function resolveTopicFromContext(context: WorkflowContext): string {
  const signal = findArtifact(context.priorArtifacts, 'signal_packet')
  return String(
    signal?.data.topic ?? context.input.topic ?? context.input.goal ?? context.input.source ?? 'Untitled',
  )
}

async function buildBriefArtifacts(context: WorkflowContext): Promise<StepOutput[]> {
  const importedBrief = getImportedBrief(context.input)
  if (importedBrief) {
    return [
      {
        type: 'brief' as const,
        data: cloneArtifactData(importedBrief.normalized),
      },
    ]
  }

  const channel = workflowChannel(context.workflow)
  const primaryAudience = context.brand.audiences[0]?.id ?? 'general'
  const requestedPillarId = typeof context.input.pillar === 'string' ? context.input.pillar : undefined
  const selectedPillar = requestedPillarId
    ? context.brand.pillars.find((pillar) => pillar.id === requestedPillarId)
    : context.brand.pillars[0]

  if (requestedPillarId && !selectedPillar) {
    throw new Error(`Unknown pillar for brand ${context.brand.id}: ${requestedPillarId}`)
  }

  return [
    {
      type: 'brief' as const,
      data: {
        workflow: context.workflow,
        channel,
        brand: context.brand.name,
        objective: context.brand.channels[channel].objective,
        audience: primaryAudience,
        positioning: context.brand.positioning,
        offer: context.brand.offers[0]?.id ?? null,
        proofPoints: context.brand.proofPoints.slice(0, 2),
        pillar: selectedPillar?.id ?? null,
        perspective: selectedPillar?.perspective ?? null,
        format: selectedPillar?.format ?? null,
        signals: selectedPillar?.signals ?? [],
        brandPolicy: brandPolicySummary(context.brand),
        topic: resolveTopicFromContext(context),
      },
    },
  ]
}

async function buildSocialDraftArtifacts(context: WorkflowContext): Promise<StepOutput[]> {
  const brief = findArtifact(context.priorArtifacts, 'brief')
  const topic = String(brief?.data.topic ?? context.input.topic ?? 'Untitled')
  const perspective = typeof brief?.data.perspective === 'string' ? brief.data.perspective : undefined
  const draftSet = await generateSocialDraftSet({
    brand: context.brand,
    topic,
    perspective,
    copy: typeof brief?.data.copy === 'string' ? brief.data.copy : undefined,
    cta: typeof brief?.data.cta === 'string' ? brief.data.cta : undefined,
  })

  return [
    {
      type: 'draft_set' as const,
      data: draftSet as unknown as Record<string, unknown>,
    },
  ]
}

async function buildAssetArtifacts(context: WorkflowContext): Promise<StepOutput[]> {
  const draft = findArtifact(context.priorArtifacts, 'draft_set')
  const mainVariant = Array.isArray(draft?.data.variants) ? draft?.data.variants[0] as Record<string, unknown> : null
  const headline = resolveCardHeadline(draft, mainVariant, context)
  const body = String(mainVariant?.body ?? context.brand.positioning)
  const cta = nonEmptyString(mainVariant?.cta) ?? undefined
  const topic = resolveTopicFromContext(context)
  const eyebrow = resolveCardEyebrow(context)
  const visualStyle = resolveVisualStyle(context.brand, context.input)
  const effectivePalette = mergePalette(context.brand.visual.palette, visualStyle?.palette)
  const logoDataUri = brandLogoDataUri(context.brand, context.paths.brandsDir)

  const groundId = typeof context.input.ground === 'string' ? context.input.ground : undefined
  const ground = groundId ? undefined : brandGround(context.brand, visualStyle)
  const { writeFileSync, mkdirSync } = await import('fs')
  const { join } = await import('path')
  const outDir = join(context.paths.artifactsDir, context.runId, 'cards')
  mkdirSync(outDir, { recursive: true })

  const platformAssets: Record<string, string> = {}
  for (const platformId of ['facebook', 'instagram', 'linkedin', 'threads', 'twitter'] as const) {
    const png = await renderCard({
      ground, groundId, platformId,
      topic, eyebrow, headline, body, cta,
      style: visualStyle,
      brandName: context.brand.name,
      logoDataUri,
    })
    const outPath = join(outDir, `${platformId}.png`)
    writeFileSync(outPath, png)
    platformAssets[platformId] = outPath
  }

  return [
    {
      type: 'asset_set' as const,
      data: {
        channel: 'social',
        topic,
        eyebrow,
        visualIntent: typeof draft?.data.imageDirection === 'string' ? draft.data.imageDirection : null,
        suggestedHeadline: headline,
        palette: effectivePalette,
        style: visualStyle ? {
          id: visualStyle.id,
          density: visualStyle.density,
        } : null,
        logo: context.brand.visual.logo ?? null,
        imagePath: platformAssets.twitter ?? null,
        platformAssets,
        headline,
        body,
        cta: cta ?? null,
      },
    },
  ]
}

async function buildOutreachDraftArtifacts(context: WorkflowContext): Promise<StepOutput[]> {
  const account = String(context.input.account ?? 'the account')
  const goal = String(context.input.goal ?? 'start a useful conversation')

  return [
    {
      type: 'draft_set' as const,
      data: {
        channel: 'outreach',
        variants: [
          {
            id: 'outreach-main',
            subject: `A sharp thought about ${account}`,
            body: `I noticed a gap in how ${account} talks about the problem. ${goal}. If useful, I can send a tighter point of view.`,
          },
        ],
      },
    },
  ]
}

async function buildResponseDraftArtifacts(context: WorkflowContext): Promise<StepOutput[]> {
  const source = String(context.input.source ?? 'the message')

  return [
    {
      type: 'draft_set' as const,
      data: {
        channel: 'respond',
        variants: [
          {
            id: 'respond-main',
            body: `Thanks for raising ${source}. The useful response is to clarify the claim, anchor it in evidence, and answer without getting defensive.`,
          },
        ],
      },
    },
  ]
}

async function buildOutlineArtifacts(context: WorkflowContext): Promise<StepOutput[]> {
  const topic = resolveTopicFromContext(context)

  return [
    {
      type: 'outline' as const,
      data: {
        title: topic,
        sections: [
          'What is actually happening',
          'Why common advice misses',
          'What a better approach looks like',
          'Where to go next',
        ],
      },
    },
  ]
}

async function buildArticleDraftArtifacts(context: WorkflowContext): Promise<StepOutput[]> {
  const outline = findArtifact(context.priorArtifacts, 'outline')
  const brief = findArtifact(context.priorArtifacts, 'brief')
  const sections = Array.isArray(outline?.data.sections) ? outline?.data.sections : []
  const title = String(outline?.data.title ?? resolveTopicFromContext(context))
  const perspective = typeof brief?.data.perspective === 'string'
    ? brief.data.perspective
    : `${context.brand.name} treats this as an operational problem, not a branding problem.`
  const signals = Array.isArray(brief?.data.signals)
    ? brief.data.signals.filter((value): value is string => typeof value === 'string')
    : []
  const body = [
    `# ${title}`,
    '',
    perspective,
    '',
    `## ${sections[0] ?? 'What is actually happening'}`,
    `${context.brand.name} treats this as an operational problem, not a branding problem.`,
    '',
    `## ${sections[1] ?? 'Why common advice misses'}`,
    `Most guidance stays generic. The better move is to name the structural constraint and show one concrete consequence.`,
    '',
    `## ${sections[2] ?? 'What a better approach looks like'}`,
    `Build around audience reality, specific evidence, and one strong claim that the reader can test.`,
    '',
    `## ${sections[3] ?? 'Where to go next'}`,
    signals.length > 0
      ? `Track signals like ${signals.slice(0, 2).join(' and ')} and turn the argument into action.`
      : `Turn the argument into action: a sharper post, a better reply, or a more grounded outreach touch.`,
  ].join('\n')

  return [
    {
      type: 'article_draft' as const,
      data: {
        title,
        markdown: body,
      },
    },
  ]
}
