import { existsSync, readFileSync } from 'fs'
import yaml from 'js-yaml'
import { basename, dirname, isAbsolute, join, resolve } from 'path'
import { resolveRuntimePaths } from '../core/paths'
import { isSocialPlatform, type BrandFoundation, type BrandPolicy, type BrandSensitiveTopic } from '../domain/types'

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

function expectRecord(value: unknown, name: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`Invalid BRAND.md: ${name} must be an object`)
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
  const raw = readFileSync(path, 'utf8')
  const match = raw.match(/^---\n([\s\S]+?)\n---(?:\n([\s\S]*))?$/)
  if (!match) {
    throw new Error(`Invalid BRAND.md: missing YAML front matter in ${path}`)
  }
  return expectRecord(yaml.load(match[1]), 'front matter')
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

export function loadBrandFoundation(id: string, options: LoadBrandOptions = {}): BrandFoundation {
  const paths = resolveRuntimePaths(options.root)
  const brandPath = findBrandPath(id, paths.root)
  const data = parseBrandMd(brandPath)
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
    id: optionalString(data.id) ?? brandIdFromPath(brandPath) ?? slug(expectString(data.name, 'name')),
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
      palette: (() => {
        const visualRaw = data.visual ? expectRecord(data.visual, 'visual') : {}
        const paletteRaw = visualRaw.palette ? expectRecord(visualRaw.palette, 'visual.palette') : {}
        return {
          background: optionalString(paletteRaw.background) ?? '#FFFFFF',
          primary:    optionalString(paletteRaw.primary)    ?? '#111111',
          accent:     optionalString(paletteRaw.accent)     ?? '#FF6600',
        }
      })(),
      imageStyle: stringifyList(voice.tone),
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
