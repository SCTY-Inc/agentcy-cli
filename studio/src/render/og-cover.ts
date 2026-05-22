import satori from 'satori'
import { Resvg } from '@resvg/resvg-js'
import { getFonts } from './fonts'
import type { BrandFoundation } from '../domain/types'

export const OG_COVER_WIDTH = 1200
export const OG_COVER_HEIGHT = 630

export interface OgCoverInput {
  brand: BrandFoundation
  title: string
  subtitle?: string
  eyebrow?: string
  seed?: string
  sourcePath?: string
  outputPath?: string
  backgroundDataUrl?: string
}

type S = Record<string, string | number | undefined>
type NodeChildren = Node | string | (Node | string)[]
type Node = { type: string; props: { style?: S; children?: NodeChildren } }

const el = (type: string, style: S, children?: (Node | string | null | undefined)[]): Node => ({
  type,
  props: { style, children: children?.filter(Boolean) as (Node | string)[] ?? [] },
})

const span = (content: string, style: S): Node => ({
  type: 'span',
  props: { style, children: content },
})

function clamp(value: number): number {
  return Math.max(0, Math.min(255, Math.round(value)))
}

function parseHex(hex: string): [number, number, number] {
  const normalized = hex.trim().replace(/^#/, '')
  const expanded = normalized.length === 3
    ? normalized.split('').map((char) => `${char}${char}`).join('')
    : normalized
  if (!/^[0-9a-f]{6}$/i.test(expanded)) return [255, 255, 255]
  return [
    parseInt(expanded.slice(0, 2), 16),
    parseInt(expanded.slice(2, 4), 16),
    parseInt(expanded.slice(4, 6), 16),
  ]
}

function toHex(value: number): string {
  return clamp(value).toString(16).padStart(2, '0')
}

function mixHex(from: string, to: string, amount: number): string {
  const a = parseHex(from)
  const b = parseHex(to)
  return `#${toHex(a[0] + (b[0] - a[0]) * amount)}${toHex(a[1] + (b[1] - a[1]) * amount)}${toHex(a[2] + (b[2] - a[2]) * amount)}`
}

function hash(value: string): number {
  let h = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    h ^= value.charCodeAt(index)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

function wrapText(text: string, approxChars: number, maxLines: number): string[] {
  const words = text.split(/\s+/).filter(Boolean)
  const lines: string[] = []
  let current = ''

  for (const word of words) {
    const next = current ? `${current} ${word}` : word
    if (next.length > approxChars && current) {
      lines.push(current)
      current = word
      continue
    }
    current = next
  }

  if (current) lines.push(current)
  if (lines.length <= maxLines) return lines

  const trimmed = lines.slice(0, maxLines)
  const last = trimmed[maxLines - 1]
  trimmed[maxLines - 1] = last.length > 3 ? `${last.slice(0, Math.max(0, approxChars - 3)).trimEnd()}...` : last
  return trimmed
}

function titleSize(title: string): number {
  if (title.length > 96) return 54
  if (title.length > 72) return 60
  if (title.length > 48) return 68
  return 78
}

function slugSeed(input: OgCoverInput): string {
  return input.seed?.trim() || `${input.brand.id}:${input.title}`
}

function shortLabel(value: string, maxLength: number): string {
  return value.length > maxLength ? `${value.slice(0, Math.max(0, maxLength - 3)).trimEnd()}...` : value
}

export function buildOgCoverBackgroundPrompt(input: OgCoverInput): string {
  const palette = input.brand.visual.palette
  const paletteParts = [
    `background ${palette.background}`,
    `primary ${palette.primary}`,
    palette.secondary ? `secondary ${palette.secondary}` : undefined,
    `accent ${palette.accent}`,
    palette.text ? `text ${palette.text}` : undefined,
  ].filter(Boolean)
  return [
    `Editorial OG cover background for ${input.brand.name}.`,
    `Theme: ${input.title}.`,
    `Palette: ${paletteParts.join(', ')}.`,
    `Mood: ${input.brand.visual.imageStyle || input.brand.positioning}.`,
    'Background only. No text. No logos. No watermarks. No people. 16:9 web cover composition.',
  ].join(' ')
}

export function buildOgCoverSidecar(input: OgCoverInput): Record<string, unknown> {
  return {
    artifact_type: 'og_cover.v1',
    schema_version: 'v1',
    renderer: 'satori-resvg',
    width: OG_COVER_WIDTH,
    height: OG_COVER_HEIGHT,
    brand_id: input.brand.id,
    brand_name: input.brand.name,
    title: input.title,
    subtitle: input.subtitle,
    eyebrow: input.eyebrow,
    seed: slugSeed(input),
    source_path: input.sourcePath,
    output_path: input.outputPath,
    composition: {
      background: input.backgroundDataUrl ? 'provided_image' : 'deterministic_palette',
      text: 'local_svg_text',
    },
    background_prompt: buildOgCoverBackgroundPrompt(input),
    created_at: new Date().toISOString(),
  }
}

export async function renderOgCover(input: OgCoverInput): Promise<Buffer> {
  const palette = input.brand.visual.palette
  const background = palette.background
  const primary = palette.primary
  const secondary = palette.secondary || mixHex(primary, background, 0.32)
  const accent = palette.accent
  const text = palette.text || primary
  const seedHash = hash(slugSeed(input))
  const titleFontSize = titleSize(input.title)
  const titleLines = wrapText(input.title, Math.round(690 / (titleFontSize * 0.54)), 4)
  const subtitleLines = input.subtitle ? wrapText(input.subtitle, 42, 2) : []
  const muted = mixHex(text, background, 0.34)
  const paleRule = mixHex(primary, background, 0.78)
  const railTint = mixHex(secondary, primary, 0.35)
  const railVariantHeight = 162 + (seedHash % 70)

  const element = el('div', {
    display: 'flex',
    flexDirection: 'row',
    width: OG_COVER_WIDTH,
    height: OG_COVER_HEIGHT,
    color: text,
    backgroundColor: primary,
  }, [
    el('div', {
      display: 'flex',
      width: 824,
      height: OG_COVER_HEIGHT,
      flexDirection: 'column',
      justifyContent: 'space-between',
      backgroundColor: background,
      paddingTop: 58,
      paddingRight: 72,
      paddingBottom: 56,
      paddingLeft: 76,
    }, [
      el('div', {
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
      }, [
        el('div', {
          display: 'flex',
          width: 14,
          height: 14,
          backgroundColor: accent,
          marginRight: 16,
        }, []),
        span(shortLabel(input.eyebrow || input.brand.name, 56).toUpperCase(), {
          fontFamily: 'JetBrains Mono',
          fontSize: 21,
          fontWeight: 500,
          color: primary,
          letterSpacing: 0,
        }),
      ]),
      el('div', {
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        width: 676,
        flexGrow: 1,
      }, [
        ...titleLines.map((line) =>
          span(line, {
            fontFamily: 'Alegreya',
            fontSize: titleFontSize,
            fontWeight: 700,
            lineHeight: 1.02,
            color: primary,
            wordBreak: 'break-word',
          }),
        ),
        subtitleLines.length > 0
          ? el('div', {
              display: 'flex',
              flexDirection: 'column',
              marginTop: 26,
              width: 620,
            }, subtitleLines.map((line) =>
              span(line, {
                fontFamily: 'Inter',
                fontSize: 30,
                fontWeight: 400,
                lineHeight: 1.35,
                color: text,
              }),
            ))
          : null,
      ]),
      el('div', {
        display: 'flex',
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        width: '100%',
        borderTopWidth: 1,
        borderTopStyle: 'solid',
        borderTopColor: paleRule,
        paddingTop: 22,
      }, [
        span(shortLabel(input.brand.name, 42).toUpperCase(), {
          fontFamily: 'JetBrains Mono',
          fontSize: 20,
          fontWeight: 500,
          color: primary,
          letterSpacing: 0,
        }),
        span(shortLabel(slugSeed(input), 52), {
          fontFamily: 'JetBrains Mono',
          fontSize: 16,
          fontWeight: 400,
          color: muted,
          letterSpacing: 0,
        }),
      ]),
    ]),
    el('div', {
      display: 'flex',
      position: 'relative',
      width: OG_COVER_WIDTH - 824,
      height: OG_COVER_HEIGHT,
      backgroundColor: primary,
      overflow: 'hidden',
    }, [
      input.backgroundDataUrl
        ? el('div', {
            display: 'flex',
            position: 'absolute',
            left: 0,
            top: 0,
            width: OG_COVER_WIDTH - 824,
            height: OG_COVER_HEIGHT,
            backgroundImage: `url(${input.backgroundDataUrl})`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            opacity: 0.42,
          }, [])
        : null,
      el('div', {
        display: 'flex',
        position: 'absolute',
        left: 0,
        top: 0,
        width: OG_COVER_WIDTH - 824,
        height: 22,
        backgroundColor: accent,
      }, []),
      el('div', {
        display: 'flex',
        position: 'absolute',
        right: 0,
        bottom: 0,
        width: OG_COVER_WIDTH - 824,
        height: railVariantHeight,
        backgroundColor: secondary,
      }, []),
      el('div', {
        display: 'flex',
        position: 'absolute',
        left: 56,
        top: 90,
        width: 238,
        height: 116,
        borderTopWidth: 2,
        borderTopStyle: 'solid',
        borderTopColor: background,
        borderBottomWidth: 2,
        borderBottomStyle: 'solid',
        borderBottomColor: background,
        opacity: 0.8,
      }, []),
      el('div', {
        display: 'flex',
        position: 'absolute',
        left: 56,
        top: 248,
        width: 180,
        height: 62,
        backgroundColor: railTint,
      }, []),
      el('div', {
        display: 'flex',
        position: 'absolute',
        left: 56,
        top: 336,
        width: 250,
        height: 62,
        backgroundColor: mixHex(accent, primary, 0.18),
      }, []),
      el('div', {
        display: 'flex',
        position: 'absolute',
        left: 56,
        bottom: 52,
        width: 232,
        height: 88,
        borderLeftWidth: 8,
        borderLeftStyle: 'solid',
        borderLeftColor: accent,
        paddingLeft: 22,
        alignItems: 'center',
      }, [
        span('SMS-FIRST CARE', {
          fontFamily: 'JetBrains Mono',
          fontSize: 19,
          fontWeight: 500,
          color: background,
          letterSpacing: 0,
        }),
      ]),
    ]),
  ])

  const svg = await satori(element as unknown as Parameters<typeof satori>[0], {
    width: OG_COVER_WIDTH,
    height: OG_COVER_HEIGHT,
    fonts: getFonts(),
  })
  return Buffer.from(new Resvg(svg, { font: { loadSystemFonts: false } }).render().asPng())
}
