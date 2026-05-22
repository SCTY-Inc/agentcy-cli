import type { BrandFoundation } from '../domain/types'

export interface SocialDraftVariant {
  id: string
  hook: string
  body: string
  cta: string
}

export interface SocialDraftSet {
  channel: 'social'
  headline: string
  imageDirection: string
  variants: SocialDraftVariant[]
}

interface SocialDraftOptions {
  brand: BrandFoundation
  topic: string
  perspective?: string
  copy?: string
  cta?: string
}

function compact(value: string): string {
  return value.replace(/\s+/g, ' ').trim()
}

function resolveCta(options: SocialDraftOptions): string {
  if (options.cta?.trim()) return options.cta.trim()
  const brand = options.brand
  const offerId = brand.channels.social.defaultOffer
  if (offerId) {
    const offer = brand.offers.find(o => o.id === offerId)
    if (offer?.cta) return offer.cta
  }
  return brand.channels.social.objective
}

function buildImageDirection(brand: BrandFoundation, topic: string): string {
  const motif = brand.visual.motif ?? 'strong brand geometry'
  const imageStyle = brand.visual.imageStyle ?? `${brand.voice.tone.toLowerCase()} ${brand.voice.style.toLowerCase()}`
  return compact(`${imageStyle}. ${motif} around the idea of ${topic}.`)
}

function stripInstruction(value: string): string {
  return value
    .replace(/^(create|write|generate|draft)\s+(a\s+|an\s+)?[\w\s-]*?(post|update|caption|thread)\s+(about|explaining that|on)\s+/i, '')
    .replace(/,?\s+and\s+point\s+.+$/i, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function sentenceCase(value: string): string {
  const cleaned = stripInstruction(value).replace(/[.!?]+$/, '')
  if (!cleaned) return 'A signal worth acting on'
  return `${cleaned.charAt(0).toUpperCase()}${cleaned.slice(1)}.`
}

function sentence(value: string): string {
  const cleaned = compact(value).replace(/[.!?]+$/, '')
  if (!cleaned) return ''
  return `${cleaned.charAt(0).toUpperCase()}${cleaned.slice(1)}.`
}

function usefulCopy(value: string | undefined, topic: string): string | null {
  if (!value?.trim()) return null
  const copy = compact(value)
  if (copy.toLowerCase() === topic.toLowerCase()) return null
  if (/^(create|write|generate|draft)\b/i.test(copy)) return null
  return copy
}

function firstProof(brand: BrandFoundation, pattern: RegExp, fallbackIndex = 0): string {
  return brand.proofPoints.find((point) => pattern.test(point))
    ?? brand.proofPoints[fallbackIndex]
    ?? brand.positioning
}

function concreteBody(options: SocialDraftOptions, hook: string): string {
  const { brand, topic, perspective } = options
  const copy = usefulCopy(options.copy, topic)
  if (copy) return copy

  const normalized = `${topic} ${hook}`.toLowerCase()
  if (/caregiver|caregiving|care/.test(normalized) && /burnout|operational|risk|sms|support/.test(normalized)) {
    return compact([
      'Burnout shows up as missed work, delayed decisions, and 2am crisis calls.',
      'The answer is lower-friction support, not another app.',
      `${brand.name} meets caregivers by SMS: no download, no setup, available when the hard part is happening.`,
    ].join(' '))
  }

  const angle = perspective ?? brand.positioning
  const proof = firstProof(brand, /no app|sms|available|24\/7|2am|proof|predictor|without/i)
  const hookText = hook.replace(/[.!?]+$/, '')

  return compact([
    `${hookText} needs a practical operating model.`,
    sentence(angle),
    sentence(proof),
  ].join(' '))
}

function templateFallback(options: SocialDraftOptions): SocialDraftVariant[] {
  const { brand, topic, perspective } = options
  const angle = perspective ?? brand.positioning
  const dont = brand.voice.dont[0] ?? 'generic language'
  const cta = resolveCta(options)
  const hook = sentenceCase(topic)
  const topicLabel = stripInstruction(topic) || 'this work'
  const body = concreteBody(options, hook)

  return [
    {
      id: 'social-main',
      hook,
      body,
      cta,
    },
    {
      id: 'social-alt',
      hook: `The usual story about ${topicLabel} hides the real failure.`,
      body: compact(`The weak version falls into this trap: ${dont.replace(/[.!?]+$/, '')}. ${brand.name} should name the constraint, show the consequence, and give one concrete next step. ${sentence(angle)}`),
      cta,
    },
  ]
}

export async function generateSocialDraftSet(options: SocialDraftOptions): Promise<SocialDraftSet> {
  const { brand } = options
  const topic = options.topic.trim().replace(/\s+/g, ' ')

  return {
    channel: 'social',
    headline: sentenceCase(topic),
    imageDirection: buildImageDirection(brand, topic),
    variants: templateFallback({ ...options, topic }),
  }
}
