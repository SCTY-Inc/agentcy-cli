import type { BrandFoundation } from '../domain/types'
import { generateText } from '../render/gemini'

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
}

function compact(value: string): string {
  return value.replace(/\s+/g, ' ').trim()
}

function resolveCtaFromBrand(brand: BrandFoundation): string {
  const offerId = brand.channels.social.defaultOffer
  if (offerId) {
    const offer = brand.offers.find(o => o.id === offerId)
    if (offer?.cta) return offer.cta
  }
  return brand.channels.social.objective
}

function buildVoicePrompt(brand: BrandFoundation): string {
  const lines: string[] = [
    `You are writing social copy for ${brand.name}.`,
    `Positioning: ${brand.positioning}`,
    `Tone: ${brand.voice.tone}`,
    `Style: ${brand.voice.style}`,
    '',
    'Rules:',
    ...brand.voice.do.map(r => `- DO: ${r}`),
    ...brand.voice.dont.map(r => `- DON'T: ${r}`),
  ]
  if (brand.proofPoints.length > 0) {
    lines.push('', 'Evidence you can use:', ...brand.proofPoints.map(p => `- ${p}`))
  }
  return lines.join('\n')
}

function buildImageDirection(brand: BrandFoundation, topic: string): string {
  const motif = brand.visual.motif ?? 'strong brand geometry'
  const imageStyle = brand.visual.imageStyle ?? `${brand.voice.tone.toLowerCase()} ${brand.voice.style.toLowerCase()}`
  return compact(`${imageStyle}. ${motif} around the idea of ${topic}.`)
}

function parseVariants(raw: string, cta: string): SocialDraftVariant[] | null {
  // Expect JSON array of [{hook, body}] or object with {main: {hook, body}, alt: {hook, body}}
  try {
    const cleaned = raw.replace(/```json\s*/g, '').replace(/```\s*/g, '').trim()
    const parsed = JSON.parse(cleaned)

    if (Array.isArray(parsed) && parsed.length >= 2) {
      return parsed.slice(0, 2).map((v, i) => ({
        id: i === 0 ? 'social-main' : 'social-alt',
        hook: String(v.hook ?? ''),
        body: String(v.body ?? ''),
        cta,
      }))
    }

    if (parsed.main && parsed.alt) {
      return [
        { id: 'social-main', hook: String(parsed.main.hook), body: String(parsed.main.body), cta },
        { id: 'social-alt', hook: String(parsed.alt.hook), body: String(parsed.alt.body), cta },
      ]
    }
  } catch { /* fall through */ }
  return null
}

function templateFallback(options: SocialDraftOptions): SocialDraftVariant[] {
  const { brand, topic, perspective } = options
  const audience = brand.audiences[0]?.summary ?? 'the audience'
  const evidence = brand.proofPoints[0] ?? brand.positioning
  const angle = perspective ?? brand.positioning
  const dont = brand.voice.dont[0] ?? 'generic language'
  const cta = resolveCtaFromBrand(brand)
  const cap = topic.charAt(0).toUpperCase() + topic.slice(1)

  return [
    {
      id: 'social-main',
      hook: `${cap} is usually treated like a personal problem. It is not.`,
      body: compact(`${brand.name} frames it as a systems issue for ${audience}. ${angle} ${evidence}`),
      cta,
    },
    {
      id: 'social-alt',
      hook: `The usual story about ${topic} hides the real failure.`,
      body: compact(`Most takes fall into ${dont}. ${brand.name} starts with this angle: ${angle}. Then it names one concrete consequence.`),
      cta,
    },
  ]
}

export async function generateSocialDraftSet(options: SocialDraftOptions): Promise<SocialDraftSet> {
  const { brand } = options
  const topic = options.topic.trim().replace(/\s+/g, ' ')
  const cta = resolveCtaFromBrand(brand)

  const prompt = [
    buildVoicePrompt(brand),
    '',
    `Topic: ${topic}`,
    options.perspective ? `Angle: ${options.perspective}` : '',
    `Audience: ${brand.audiences[0]?.summary ?? 'general'}`,
    '',
    'Write 2 social post variants. Each has a "hook" (1 punchy sentence) and "body" (2-3 sentences max).',
    'Do NOT include a CTA — that is added separately.',
    'Return JSON array: [{hook, body}, {hook, body}]',
    'No markdown fences. Just the JSON.',
  ].filter(Boolean).join('\n')

  const raw = await generateText(prompt)
  const parsed = raw ? parseVariants(raw, cta) : null

  return {
    channel: 'social',
    headline: topic.charAt(0).toUpperCase() + topic.slice(1),
    imageDirection: buildImageDirection(brand, topic),
    variants: parsed ?? templateFallback(options),
  }
}
