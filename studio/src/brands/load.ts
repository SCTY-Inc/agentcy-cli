import { existsSync, readFileSync } from 'fs'
import yaml from 'js-yaml'
import { basename, dirname, isAbsolute, join, resolve } from 'path'
import { resolveRuntimePaths } from '../core/paths'
import {
  isSocialPlatform,
  type BrandDensity,
  type BrandFoundation,
  type BrandVisualFidelity,
  type BrandPolicy,
  type BrandSensitiveTopic,
  type BrandVisualPalette,
  type BrandVisualStyle,
} from '../domain/types'

interface LoadBrandOptions {
  root?: string
}

function expectString(value: unknown, name: string): string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new Error(`Invalid BRAND.md: missing ${name}`)
  }
  return value.trim()
}

function expectStringArray(value: unknown, name: string): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== 'string')) {
    throw new Error(`Invalid BRAND.md: ${name} must be a string array`)
  }
  return value
}

function expectRecord(value: unknown, name: string, label = 'BRAND.md'): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`Invalid ${label}: ${name} must be an object`)
  }
  return value as Record<string, unknown>
}

function optionalString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim().length > 0 ? value.trim() : undefined
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : []
}

function stringifyList(value: unknown): string {
  return Array.isArray(value) ? value.map(String).join(', ') : String(value ?? '')
}

function slug(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}

function brandIdFromPath(path: string): string {
  const name = basename(path)
  if (/^BRAND\.md$/i.test(name)) {
    return slug(basename(dirname(path)))
  }
  return slug(name.replace(/\.brand\.md$/i, '').replace(/\.md$/i, ''))
}

function parseBrandMd(path: string): Record<string, unknown> {
  return parseFrontMatter(path, 'BRAND.md').data
}

function parseFrontMatter(path: string, label: 'BRAND.md' | 'DESIGN.md'): { data: Record<string, unknown>; body: string } {
  const raw = readFileSync(path, 'utf8')
  const match = raw.match(/^---\n([\s\S]+?)\n---(?:\n([\s\S]*))?$/)
  if (!match) {
    throw new Error(`Invalid ${label}: missing YAML front matter in ${path}`)
  }
  return {
    data: expectRecord(yaml.load(match[1]), 'front matter', label),
    body: (match[2] ?? '').trim(),
  }
}

function findBrandPath(id: string, root: string): string {
  const directPath = isAbsolute(id) ? id : resolve(root, id)
  if (existsSync(directPath)) {
    if (/\.brand\.md$/i.test(directPath) || /(^|\/)BRAND\.md$/i.test(directPath)) {
      return directPath
    }
    throw new Error(`Brand foundation must be BRAND.md or <brand>.brand.md: ${directPath}`)
  }

  const paths = resolveRuntimePaths(root)
  const dir = join(paths.brandsDir, id)
  const candidates = [
    join(dir, 'BRAND.md'),
    join(dir, `${id}.brand.md`),
  ]
  const found = candidates.find((candidate) => existsSync(candidate))
  if (!found) {
    throw new Error(`Brand foundation not found: ${join(dir, 'BRAND.md')}`)
  }
  return found
}

function loadApprovalRequired(required: string[]): BrandPolicy['approvalLanes'] {
  if (required.length === 0) return undefined
  return {
    red: {
      description: 'Explicit human approval required by BRAND.md safety policy.',
      examples: required,
    },
  }
}

function loadSensitiveTopics(value: unknown): BrandSensitiveTopic[] {
  return Array.isArray(value)
    ? value.map((entry) => {
        const item = expectRecord(entry, 'safety.sensitive_topics[]')
        return {
          topic: expectString(item.topic, 'safety.sensitive_topics[].topic'),
          handling: expectString(item.handling, 'safety.sensitive_topics[].handling'),
          note: optionalString(item.note),
        }
      })
    : []
}

function loadPolicy(behavior: Record<string, unknown>, safety: Record<string, unknown>): BrandPolicy {
  const delegation = safety.delegation ? expectRecord(safety.delegation, 'safety.delegation') : {}
  const crisis = safety.crisis_policy ? expectRecord(safety.crisis_policy, 'safety.crisis_policy') : undefined
  const approvalRequired = stringArray(safety.approval_required)
  const humanRequired = stringArray(delegation.human_required)
  return {
    approvalLanes: loadApprovalRequired(approvalRequired),
    approvalRequired,
    autonomousActions: stringArray(delegation.autonomous),
    humanRequiredActions: [...new Set([...humanRequired, ...approvalRequired])],
    forbiddenClaims: stringArray(safety.forbidden_claims),
    regulatedClaims: stringArray(safety.regulated_claims),
    sensitiveTopics: loadSensitiveTopics(safety.sensitive_topics),
    escalationRules: stringArray(behavior.escalate),
    citationPolicy: optionalString(safety.citation_policy),
    crisisPolicy: crisis
      ? {
          triggers: stringArray(crisis.triggers),
          response: optionalString(crisis.response),
          owner: optionalString(crisis.owner),
        }
      : undefined,
  }
}

function loadAudience(value: unknown) {
  const audience = value ? expectRecord(value, 'audience') : {}
  const segments = Array.isArray(audience.segments) ? audience.segments : []
  if (segments.length > 0) {
    return segments.map((entry) => {
      const item = expectRecord(entry, 'audience.segments[]')
      return {
        id: expectString(item.id, 'audience.segments[].id'),
        summary: [
          expectString(item.description, 'audience.segments[].description'),
          optionalString(item.pain) ? `Pain: ${optionalString(item.pain)}` : '',
          optionalString(item.goal) ? `Goal: ${optionalString(item.goal)}` : '',
        ].filter(Boolean).join(' '),
      }
    })
  }
  return optionalString(audience.primary)
    ? [{ id: 'primary', summary: optionalString(audience.primary)! }]
    : []
}

function loadPillars(topics: Record<string, unknown>) {
  const pillars = Array.isArray(topics.pillars) ? topics.pillars : []
  return pillars.map((entry) => {
    const item = expectRecord(entry, 'topics.pillars[]')
    const formats = stringArray(item.formats)
    const format = formats[0] ?? 'standard'
    return {
      id: expectString(item.id, 'topics.pillars[].id'),
      perspective: expectString(item.angle, 'topics.pillars[].angle'),
      signals: expectStringArray(item.signals, 'topics.pillars[].signals'),
      format,
      frequency: optionalString(item.frequency) ?? 'as-needed',
      defaultFormat: format,
    }
  })
}

function findDesignPath(brandPath: string, brandId: string): string | undefined {
  const dir = dirname(brandPath)
  const candidates = [
    join(dir, 'DESIGN.md'),
    join(dir, `${brandId}.design.md`),
    join(dir, 'brand.design.md'),
  ]
  return candidates.find((candidate) => existsSync(candidate))
}

function visualRecord(value: unknown, name: string, label = 'BRAND.md'): Record<string, unknown> {
  return value ? expectRecord(value, name, label) : {}
}

function optionalRecord(value: unknown, name: string, label = 'DESIGN.md'): Record<string, unknown> | undefined {
  return value ? expectRecord(value, name, label) : undefined
}

function firstString(records: Record<string, unknown>[], keys: string[]): string | undefined {
  for (const record of records) {
    for (const key of keys) {
      const value = optionalString(record[key])
      if (value) return value
    }
  }
  return undefined
}

function firstStringArray(records: Record<string, unknown>[], key: string): string[] {
  for (const record of records) {
    const values = stringArray(record[key])
    if (values.length > 0) return values
  }
  return []
}

function paletteFromGrounds(value: unknown): Record<string, unknown> {
  const grounds = value ? expectRecord(value, 'grounds', 'DESIGN.md') : {}
  const preferred = ['cream', 'default', 'primary', ...Object.keys(grounds)]
  for (const key of preferred) {
    const ground = grounds[key]
    if (!ground) continue
    const item = expectRecord(ground, `grounds.${key}`, 'DESIGN.md')
    return {
      background: item.bg,
      primary: item.fg,
      text: item.fg,
      accent: item.accent,
    }
  }
  return {}
}

function designTokenGroup(designVisual: Record<string, unknown>, keys: string[]): Record<string, unknown> {
  const tokens = optionalRecord(designVisual.tokens, 'tokens', 'DESIGN.md')
  if (!tokens) return {}
  for (const key of keys) {
    const group = optionalRecord(tokens[key], `tokens.${key}`, 'DESIGN.md')
    if (group) return group
  }
  return {}
}

function loadPalette(brandVisual: Record<string, unknown>, designVisual: Record<string, unknown>) {
  const tokenPalette = designTokenGroup(designVisual, ['color', 'colors'])
  const designPalette = designVisual.palette
    ? expectRecord(designVisual.palette, 'palette', 'DESIGN.md')
    : Object.keys(tokenPalette).length > 0
      ? tokenPalette
      : paletteFromGrounds(designVisual.grounds)
  const brandPalette = brandVisual.palette ? expectRecord(brandVisual.palette, 'visual.palette') : {}
  const paletteRecords = [designPalette, brandPalette]
  return {
    background: firstString(paletteRecords, ['background', 'surface', 'canvas', 'bg']) ?? '#FFFFFF',
    primary:    firstString(paletteRecords, ['primary', 'brand', 'fg'])    ?? '#111111',
    secondary:  firstString(paletteRecords, ['secondary']),
    accent:     firstString(paletteRecords, ['accent'])           ?? '#FF6600',
    text:       firstString(paletteRecords, ['text', 'foreground']),
  }
}

function loadTypography(brandVisual: Record<string, unknown>, designVisual: Record<string, unknown>) {
  const tokenTypography = designTokenGroup(designVisual, ['typography', 'type'])
  const designTypography = designVisual.typography
    ? expectRecord(designVisual.typography, 'typography', 'DESIGN.md')
    : tokenTypography
  const brandTypography = visualRecord(brandVisual.typography, 'visual.typography')
  const designFamilies = visualRecord(designTypography.families, 'typography.families', 'DESIGN.md')
  const records = [designTypography, brandTypography]
  const fontFamily = firstString(records, ['font_family', 'fontFamily'])
  const headline = firstString(records, ['headline', 'display']) ?? optionalString(designFamilies.display) ?? fontFamily
  const body = firstString(records, ['body', 'sans']) ?? optionalString(designFamilies.body) ?? fontFamily
  const accent = firstString(records, ['accent', 'mono']) ?? optionalString(designFamilies.mono)
  if (!headline && !body && !accent) return undefined
  return { headline, body, accent }
}

function normalizeDensity(value: string | undefined): BrandDensity {
  const normalized = value?.trim().toLowerCase()
  if (!normalized) return 'medium'
  if (normalized === 'low' || normalized === 'medium' || normalized === 'high') return normalized
  throw new Error(`Invalid DESIGN.md: unsupported visual style density "${value}"`)
}

function loadStylePalette(value: unknown): BrandVisualPalette | undefined {
  if (!value) return undefined
  const palette = expectRecord(value, 'visual.styles[].palette', 'DESIGN.md')
  return {
    background: optionalString(palette.background) ?? optionalString(palette.bg),
    primary: optionalString(palette.primary) ?? optionalString(palette.fg),
    secondary: optionalString(palette.secondary),
    accent: optionalString(palette.accent),
    text: optionalString(palette.text),
  }
}

function socialCardStyleSource(designVisual: Record<string, unknown>): unknown {
  const agentcy = optionalRecord(designVisual.agentcy, 'agentcy', 'DESIGN.md')
  const artifacts = optionalRecord(designVisual.artifacts, 'agentcy.artifacts', 'DESIGN.md')
    ?? optionalRecord(agentcy?.artifacts, 'agentcy.artifacts', 'DESIGN.md')
  if (!artifacts) return undefined
  const socialCard = optionalRecord(
    artifacts.social_card ?? artifacts.socialCard,
    'artifacts.social_card',
    'DESIGN.md',
  )
  return socialCard?.styles
}

function loadVisualStyles(brandVisual: Record<string, unknown>, designVisual: Record<string, unknown>): BrandVisualStyle[] {
  const source = designVisual.styles ?? socialCardStyleSource(designVisual) ?? brandVisual.styles
  if (!source) return []

  const entries: Array<[string | undefined, unknown]> = Array.isArray(source)
    ? source.map((item) => [undefined, item])
    : Object.entries(expectRecord(source, 'agentcy.artifacts.social_card.styles', 'DESIGN.md'))

  return entries.map(([key, value], index) => {
    const item = expectRecord(value, `agentcy.artifacts.social_card.styles.${key ?? index}`, 'DESIGN.md')
    const id = optionalString(item.id) ?? key
    if (!id) {
      throw new Error(`Invalid DESIGN.md: social_card.styles[${index}].id is required`)
    }

    return {
      id,
      density: normalizeDensity(optionalString(item.density)),
      palette: loadStylePalette(item.palette),
      texture: optionalString(item.texture),
      tone: optionalString(item.tone),
      description: optionalString(item.description),
    }
  })
}

function loadDesignSupplement(brandPath: string, brandId: string) {
  const designPath = findDesignPath(brandPath, brandId)
  if (!designPath) {
    return { path: undefined, data: {}, visual: {}, body: '' }
  }
  const parsed = parseFrontMatter(designPath, 'DESIGN.md')
  const agentcy = optionalRecord(parsed.data.agentcy, 'agentcy', 'DESIGN.md') ?? {}
  const agentcyVisual = optionalRecord(agentcy.visual, 'agentcy.visual', 'DESIGN.md') ?? {}
  const legacyVisual = parsed.data.visual ? expectRecord(parsed.data.visual, 'visual', 'DESIGN.md') : {}
  const visual: Record<string, unknown> = {
    ...parsed.data,
    ...agentcyVisual,
    ...legacyVisual,
  }
  if (!visual.artifacts && agentcy.artifacts) visual.artifacts = agentcy.artifacts
  if (!visual.fidelity && agentcy.fidelity) visual.fidelity = agentcy.fidelity
  if (!visual.source && agentcy.source) visual.source = agentcy.source
  return {
    path: designPath,
    data: parsed.data,
    visual,
    body: parsed.body,
  }
}

function loadVisualFidelity(data: Record<string, unknown>, designVisual: Record<string, unknown>): BrandVisualFidelity | undefined {
  const design = optionalRecord(data.design, 'design', 'DESIGN.md') ?? {}
  const source = optionalRecord(design.source, 'design.source', 'DESIGN.md')
    ?? optionalRecord(designVisual.source, 'visual.source', 'DESIGN.md')
    ?? {}
  const fidelity = optionalRecord(designVisual.fidelity, 'visual.fidelity', 'DESIGN.md')
    ?? optionalRecord(data.fidelity, 'fidelity', 'DESIGN.md')
    ?? {}

  const gates = [
    ...stringArray(fidelity.gates),
    ...stringArray(fidelity.quality_gates),
  ]
  const evidence = [
    ...stringArray(source.evidence),
    ...stringArray(fidelity.evidence),
  ]
  const viewports = [
    ...stringArray(source.viewports),
    ...stringArray(fidelity.viewports),
  ]
  const result: BrandVisualFidelity = {
    sourceType: optionalString(source.type) ?? optionalString(design.extraction) ?? optionalString(fidelity.mode),
    sourceUrl: optionalString(source.url),
    capturedAt: optionalString(source.captured_at) ?? optionalString(source.capturedAt),
    viewports: [...new Set(viewports)],
    evidence: [...new Set(evidence)],
    gates: [...new Set(gates)],
  }

  const hasData = Boolean(
    result.sourceType
    || result.sourceUrl
    || result.capturedAt
    || result.viewports.length
    || result.evidence.length
    || result.gates.length,
  )
  return hasData ? result : undefined
}

export function loadBrandFoundation(id: string, options: LoadBrandOptions = {}): BrandFoundation {
  const paths = resolveRuntimePaths(options.root)
  const brandPath = findBrandPath(id, paths.root)
  const data = parseBrandMd(brandPath)
  const brandId = optionalString(data.id) ?? brandIdFromPath(brandPath) ?? slug(expectString(data.name, 'name'))
  const design = loadDesignSupplement(brandPath, brandId)
  const brandVisual = data.visual ? expectRecord(data.visual, 'visual') : {}
  const voice = data.voice ? expectRecord(data.voice, 'voice') : {}
  const message = data.message ? expectRecord(data.message, 'message') : {}
  const topics = data.topics ? expectRecord(data.topics, 'topics') : {}
  const behavior = data.behavior ? expectRecord(data.behavior, 'behavior') : {}
  const channels = behavior.channels ? expectRecord(behavior.channels, 'behavior.channels') : {}
  const social = channels.linkedin
    ? expectRecord(channels.linkedin, 'behavior.channels.linkedin')
    : channels.twitter
      ? expectRecord(channels.twitter, 'behavior.channels.twitter')
      : channels.social
        ? expectRecord(channels.social, 'behavior.channels.social')
        : {}
  const safety = data.safety ? expectRecord(data.safety, 'safety') : {}
  const offer = data.offer ? expectRecord(data.offer, 'offer') : undefined
  const handlesRaw = data.handles ? expectRecord(data.handles, 'handles') : undefined
  const channelFormats = stringArray(social.formats)
  const visualStyles = loadVisualStyles(brandVisual, design.visual)
  const defaultStyle = firstString([design.visual, brandVisual], ['default_style', 'defaultStyle'])
    ?? visualStyles[0]?.id

  const handles = handlesRaw
    ? Object.fromEntries(
        Object.entries(handlesRaw)
          .filter(([, value]) => typeof value === 'string' && value.trim().length > 0)
          .map(([key, value]) => {
            if (!isSocialPlatform(key)) {
              throw new Error(`Invalid BRAND.md: handles.${key} is not a supported platform`)
            }
            return [key, String(value).trim()]
          }),
      )
    : undefined

  return {
    id: brandId,
    name: expectString(data.name, 'name'),
    positioning: expectString(data.positioning, 'positioning'),
    audiences: loadAudience(data.audience),
    offers: offer
      ? [{
          id: 'primary',
          summary: expectString(offer.core, 'offer.core'),
          url: optionalString(offer.url),
          cta: optionalString(offer.cta),
        }]
      : [],
    proofPoints: stringArray(message.proof_points),
    pillars: loadPillars(topics),
    voice: {
      tone: stringifyList(voice.tone),
      style: stringifyList(voice.style),
      do: expectStringArray(voice.do, 'voice.do'),
      dont: expectStringArray(voice.dont, 'voice.dont'),
    },
    channels: {
      social: {
        objective: optionalString(social.primary_job) ?? 'Execute approved social brand communication.',
        defaultOffer: offer ? 'primary' : undefined,
      },
      blog: { objective: 'Publish durable brand thinking.' },
      outreach: { objective: 'Start useful brand-aligned conversations.' },
      respond: { objective: 'Reply according to brand voice and escalation rules.' },
    },
    handles,
    visual: {
      designSource: design.path,
      logo: firstString([design.visual, brandVisual], ['logo']),
      palette: loadPalette(brandVisual, design.visual),
      typography: loadTypography(brandVisual, design.visual),
      style: firstString([design.visual, brandVisual], ['style'])
        ?? (design.body ? design.body.slice(0, 1200) : undefined),
      composition: firstStringArray([design.visual, brandVisual], 'composition'),
      texture: firstStringArray([design.visual, brandVisual], 'texture'),
      negative: firstStringArray([design.visual, brandVisual], 'negative'),
      motif: firstString([design.visual, brandVisual], ['motif']),
      imageStyle: firstString([design.visual, brandVisual], ['imageStyle', 'image_style'])
        ?? stringifyList(voice.tone),
      imagePrompt: firstString([design.visual, brandVisual], ['imagePrompt', 'image_prompt']),
      layout: firstString([design.visual, brandVisual], ['layout']),
      defaultStyle,
      styles: visualStyles,
      fidelity: loadVisualFidelity(design.data, design.visual),
    },
    formats: channelFormats.map((format) => ({ id: format, description: format })),
    responsePlaybooks: stringArray(behavior.engage).map((trigger, index) => ({
      id: `engage-${index + 1}`,
      trigger,
      approach: 'Respond only if the interaction stays within brand delegation and escalation rules.',
    })),
    outreachPlaybooks: [],
    policy: loadPolicy(behavior, safety),
  }
}
