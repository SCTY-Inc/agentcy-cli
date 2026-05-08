import { existsSync, readFileSync } from 'fs'
import yaml from 'js-yaml'
import { join } from 'path'
import { resolveRuntimePaths } from '../core/paths'
import { isSocialPlatform, type BrandFoundation, type BrandFormat } from '../domain/types'

interface LoadBrandOptions {
  root?: string
}

function expectString(value: unknown, name: string): string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new Error(`Invalid brand foundation: missing ${name}`)
  }
  return value.trim()
}

function expectStringArray(value: unknown, name: string): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== 'string')) {
    throw new Error(`Invalid brand foundation: ${name} must be a string array`)
  }
  return value
}

function expectRecord(value: unknown, name: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`Invalid brand foundation: ${name} must be an object`)
  }
  return value as Record<string, unknown>
}

function optionalString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim().length > 0 ? value.trim() : undefined
}

function parseFrontmatter(content: string): { data: Record<string, unknown>; body: string } {
  const match = content.match(/^---\n([\s\S]*?)\n---\s*\n?([\s\S]*)$/)
  if (!match) throw new Error('No frontmatter found')
  return {
    data: (yaml.load(match[1]) ?? {}) as Record<string, unknown>,
    body: match[2].trim(),
  }
}

function parseSections(body: string): Record<string, string> {
  const sections: Record<string, string> = {}
  const parts = body.split(/^## /m)
  for (const part of parts) {
    if (!part.trim()) continue
    const newline = part.indexOf('\n')
    if (newline === -1) continue
    const heading = part.slice(0, newline).trim().toLowerCase().replace(/\s+/g, '_')
    sections[heading] = part.slice(newline + 1).trim()
  }
  return sections
}

export function loadBrandFoundation(id: string, options: LoadBrandOptions = {}): BrandFoundation {
  const paths = resolveRuntimePaths(options.root)
  const brandDir = join(paths.brandsDir, id)
  const brandPath = join(brandDir, 'brand.md')
  const designPath = join(brandDir, 'design.md')

  if (!existsSync(brandPath)) {
    throw new Error(`Brand foundation not found: ${brandPath}`)
  }

  const brand = parseFrontmatter(readFileSync(brandPath, 'utf8'))
  const data = brand.data

  const voice = expectRecord(data.voice, 'voice')
  const channels = expectRecord(data.channels, 'channels')
  const handlesRaw = data.handles ? expectRecord(data.handles, 'handles') : undefined

  function loadChannel(raw: unknown, label: string) {
    const ch = expectRecord(raw, label)
    return {
      objective: expectString(ch.objective, `${label}.objective`),
      platforms: Array.isArray(ch.platforms) ? ch.platforms.map(String) : undefined,
      defaultOffer: optionalString(ch.default_offer),
    }
  }

  const audiences = (data.audiences as unknown[] | undefined)?.map((entry) => {
    const item = expectRecord(entry, 'audience')
    return {
      id: expectString(item.id, 'audience.id'),
      summary: expectString(item.summary, 'audience.summary'),
    }
  }) ?? []

  const offers = (data.offers as unknown[] | undefined)?.map((entry) => {
    const item = expectRecord(entry, 'offer')
    return {
      id: expectString(item.id, 'offer.id'),
      summary: expectString(item.summary, 'offer.summary'),
      url: optionalString(item.url),
      cta: optionalString(item.cta),
    }
  }) ?? []

  const pillars = (data.pillars as unknown[] | undefined)?.map((entry) => {
    const item = expectRecord(entry, 'pillar')
    return {
      id: expectString(item.id, 'pillar.id'),
      perspective: expectString(item.perspective, 'pillar.perspective'),
      signals: expectStringArray(item.signals, 'pillar.signals'),
      format: expectString(item.format, 'pillar.format'),
      frequency: expectString(item.frequency, 'pillar.frequency'),
      defaultFormat: optionalString(item.default_format),
    }
  }) ?? []

  const responsePlaybooks = (data.response_playbooks as unknown[] | undefined)?.map((entry) => {
    const item = expectRecord(entry, 'response_playbook')
    return {
      id: expectString(item.id, 'response_playbook.id'),
      trigger: expectString(item.trigger, 'response_playbook.trigger'),
      approach: expectString(item.approach, 'response_playbook.approach'),
    }
  }) ?? []

  const formats: BrandFormat[] = Array.isArray(data.formats)
    ? (data.formats as unknown[]).map((entry) => {
        const item = expectRecord(entry, 'format')
        return {
          id: expectString(item.id, 'format.id'),
          description: expectString(item.description, 'format.description'),
          promptOverlay: optionalString(item.prompt_overlay),
        }
      })
    : []

  const outreachPlaybooks = (data.outreach_playbooks as unknown[] | undefined)?.map((entry) => {
    const item = expectRecord(entry, 'outreach_playbook')
    return {
      id: expectString(item.id, 'outreach_playbook.id'),
      trigger: expectString(item.trigger, 'outreach_playbook.trigger'),
      approach: expectString(item.approach, 'outreach_playbook.approach'),
    }
  }) ?? []

  let visual: BrandFoundation['visual'] = {
    palette: { background: '#FFFFFF', primary: '#111111', accent: '#FF6600' },
  }

  if (existsSync(designPath)) {
    const design = parseFrontmatter(readFileSync(designPath, 'utf8'))
    const d = design.data
    const palette = expectRecord(d.palette, 'palette')
    const sections = parseSections(design.body)

    const videoRaw = d.video ? expectRecord(d.video, 'video') : undefined
    const videoTextureRaw = videoRaw?.texture ? expectRecord(videoRaw.texture, 'video.texture') : undefined

    visual = {
      logo: optionalString(d.logo),
      palette: {
        background: expectString(palette.background, 'palette.background'),
        primary: expectString(palette.primary, 'palette.primary'),
        accent: expectString(palette.accent, 'palette.accent'),
      },
      typography: d.typography
        ? {
            headline: optionalString((d.typography as Record<string, unknown>).headline),
            body: optionalString((d.typography as Record<string, unknown>).body),
            accent: optionalString((d.typography as Record<string, unknown>).accent),
          }
        : undefined,
      style: sections.style ?? optionalString(d.style),
      composition: sections.composition,
      texture: sections.texture,
      negative: sections.avoid,
      motif: sections.motif,
      imageStyle: sections.image_style,
      imagePrompt: sections.image_prompt,
      layout: optionalString(d.layout),
      video: videoRaw
        ? {
            textAlign: optionalString(videoRaw.textAlign),
            contentRatio: typeof videoRaw.contentRatio === 'number' ? videoRaw.contentRatio : undefined,
            entrance: optionalString(videoRaw.entrance),
            timing: optionalString(videoRaw.timing),
            texture: videoTextureRaw
              ? {
                  type: optionalString(videoTextureRaw.type),
                  opacity: typeof videoTextureRaw.opacity === 'number' ? videoTextureRaw.opacity : undefined,
                }
              : undefined,
          }
        : undefined,
    }
  }

  return {
    id: expectString(data.id, 'id'),
    name: expectString(data.name, 'name'),
    positioning: expectString(data.positioning, 'positioning'),
    audiences,
    offers,
    proofPoints: expectStringArray(data.proof_points, 'proof_points'),
    pillars,
    voice: {
      tone: expectString(voice.tone, 'voice.tone'),
      style: expectString(voice.style, 'voice.style'),
      do: expectStringArray(voice.do, 'voice.do'),
      dont: expectStringArray(voice.dont, 'voice.dont'),
    },
    channels: {
      social: loadChannel(channels.social, 'channels.social'),
      blog: loadChannel(channels.blog, 'channels.blog'),
      outreach: loadChannel(channels.outreach, 'channels.outreach'),
      respond: loadChannel(channels.respond, 'channels.respond'),
    },
    handles: handlesRaw
      ? Object.fromEntries(
          Object.entries(handlesRaw)
            .filter(([, value]) => typeof value === 'string' && value.trim().length > 0)
            .map(([key, value]) => {
              if (!isSocialPlatform(key)) {
                throw new Error(`Invalid brand foundation: handles.${key} is not a supported platform`)
              }
              return [key, String(value).trim()]
            }),
        )
      : undefined,
    visual,
    formats: formats.length > 0 ? formats : undefined,
    responsePlaybooks,
    outreachPlaybooks,
  }
}
