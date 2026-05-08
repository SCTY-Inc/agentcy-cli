import type {
  ArtifactRecord,
  ArtifactType,
  BrandFoundation,
  ImportedBriefInput,
  StepName,
  WorkflowName,
} from '../domain/types'
import { generateSocialDraftSet } from '../generate/copy'
import { generateExploreGrid } from '../generate/explore'
import { generateSourceImage } from '../generate/image'
import { generateText } from '../render/gemini'
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
    { name: 'explore', run: buildExploreArtifacts },
    { name: 'image', run: buildImageArtifacts },
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

export function cloneArtifactData(data: Record<string, unknown>): Record<string, unknown> {
  return JSON.parse(JSON.stringify(data)) as Record<string, unknown>
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
  const pillar = brand.pillars[Math.floor(Math.random() * brand.pillars.length)]
  if (!pillar) return null

  const prompt = [
    `You track signals for ${brand.name}: ${brand.positioning}`,
    `Pillar: ${pillar.id} — ${pillar.perspective}`,
    `Signal areas: ${pillar.signals.join(', ')}`,
    '',
    'Generate ONE specific, timely social post topic. Return only the topic as a short phrase (5-12 words). No quotes, no explanation.',
  ].join('\n')

  const topic = await generateText(prompt)
  return topic || null
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
  })

  return [
    {
      type: 'draft_set' as const,
      data: draftSet as unknown as Record<string, unknown>,
    },
  ]
}

async function buildExploreArtifacts(context: WorkflowContext): Promise<StepOutput[]> {
  const topic = resolveTopicFromContext(context)

  if (!process.env.GEMINI_API_KEY && !process.env.GOOGLE_API_KEY) {
    return [{ type: 'explore_grid' as const, data: { skipped: true } }]
  }

  const result = await generateExploreGrid({
    brand: context.brand,
    paths: context.paths,
    runId: context.runId,
    topic,
  })

  return [
    {
      type: 'explore_grid' as const,
      data: { gridImagePath: result.gridImagePath, prompt: result.prompt, provider: result.provider },
    },
  ]
}

async function buildImageArtifacts(context: WorkflowContext): Promise<StepOutput[]> {
  const topic = resolveTopicFromContext(context)

  const sourceImage = await generateSourceImage({
    brand: context.brand,
    paths: context.paths,
    runId: context.runId,
    topic,
  })

  return [
    {
      type: 'source_image' as const,
      data: sourceImage
        ? { channel: 'social', ...sourceImage }
        : { channel: 'social', skipped: true },
    },
  ]
}

async function buildAssetArtifacts(context: WorkflowContext): Promise<StepOutput[]> {
  const draft = findArtifact(context.priorArtifacts, 'draft_set')
  const sourceImage = findArtifact(context.priorArtifacts, 'source_image')
  const mainVariant = Array.isArray(draft?.data.variants) ? draft?.data.variants[0] as Record<string, unknown> : null
  const headline = typeof draft?.data.headline === 'string'
    ? draft.data.headline
    : String(mainVariant?.hook ?? context.input.topic ?? 'Untitled')
  const body = String(mainVariant?.body ?? context.brand.positioning)
  const cta = typeof mainVariant?.cta === 'string' ? mainVariant.cta : undefined
  const sourceImagePath = typeof sourceImage?.data.imagePath === 'string' ? sourceImage.data.imagePath : ''

  const { renderSocialAssets } = await import('../render/social')
  const platformAssets = await renderSocialAssets({
    brand: context.brand,
    paths: context.paths,
    runId: context.runId,
    headline,
    body,
    cta,
    sourceImagePath,
  })

  return [
    {
      type: 'asset_set' as const,
      data: {
        channel: 'social',
        topic: resolveTopicFromContext(context),
        visualIntent: typeof draft?.data.imageDirection === 'string' ? draft.data.imageDirection : null,
        suggestedHeadline: headline,
        palette: context.brand.visual.palette,
        imagePath: platformAssets.twitter,
        platformAssets,
        sourceImagePath: sourceImagePath || null,
        headline,
        body,
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

