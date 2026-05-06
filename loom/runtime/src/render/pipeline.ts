import { readFileSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'
import satori from 'satori'
import { Resvg } from '@resvg/resvg-js'
import { generateImage } from './gemini'
import { cardTemplate, type Node as CardNode } from './template'
import { GROUNDS, PLATFORMS } from './tokens'
import type { Figure, Gravity, GroundId, PlatformId } from './tokens'

export interface RenderOptions {
  figure?: Figure
  gravity?: Gravity
  groundId?: GroundId
  platformId: PlatformId
  topic: string
  eyebrow: string
  headline: string
  body: string
  stat?: { num: string; label: string }
  brandName: string
}

const FONTS_DIR = join(dirname(fileURLToPath(import.meta.url)), '../../fonts')

type FontEntry = { name: string; data: ArrayBuffer; weight: 100|200|300|400|500|600|700|800|900; style: 'normal'|'italic' }

let _fonts: FontEntry[] | null = null

function loadFont(file: string): ArrayBuffer {
  const buf = readFileSync(join(FONTS_DIR, file))
  return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer
}

function getFonts(): FontEntry[] {
  if (_fonts) return _fonts
  _fonts = [
    { name: 'Alegreya',       data: loadFont('Alegreya-Regular.ttf'),       weight: 400, style: 'normal'  },
    { name: 'Alegreya',       data: loadFont('Alegreya-Bold.ttf'),           weight: 700, style: 'normal'  },
    { name: 'JetBrains Mono', data: loadFont('JetBrainsMono-Regular.ttf'),  weight: 400, style: 'normal'  },
    { name: 'JetBrains Mono', data: loadFont('JetBrainsMono-Medium.ttf'),   weight: 500, style: 'normal'  },
    { name: 'Inter',          data: loadFont('Inter-Regular.ttf'),           weight: 400, style: 'normal'  },
    { name: 'Inter',          data: loadFont('Inter-Bold.ttf'),              weight: 700, style: 'normal'  },
  ]
  return _fonts
}

function buildArtPrompt(opts: Pick<RenderOptions, 'topic' | 'groundId'>): string {
  const ground = GROUNDS[opts.groundId ?? 'cream']
  return [
    `Abstract painterly background image about: ${opts.topic}.`,
    `Color palette inspired by: ${ground.bg} (background), ${ground.fg} (foreground).`,
    'No text. No logos. No watermarks. No people. Soft, warm, editorial aesthetic.',
  ].join(' ')
}

export async function renderCard(opts: RenderOptions): Promise<Buffer> {
  const ground    = GROUNDS[opts.groundId ?? 'cream']
  const platform  = PLATFORMS[opts.platformId]
  const fonts     = getFonts()

  const artBuf   = await generateImage(buildArtPrompt(opts))
  const bgDataUrl = artBuf ? `data:image/png;base64,${artBuf.toString('base64')}` : undefined

  const element = cardTemplate({
    figure:    opts.figure   ?? 'statement',
    gravity:   opts.gravity  ?? 'center',
    ground,
    platform,
    eyebrow:   opts.eyebrow,
    headline:  opts.headline,
    body:      opts.body,
    stat:      opts.stat,
    brandName: opts.brandName,
    bgDataUrl,
  })

  const svg = await satori(element as unknown as Parameters<typeof satori>[0], { width: platform.w, height: platform.h, fonts })
  return Buffer.from(new Resvg(svg, { font: { loadSystemFonts: false } }).render().asPng())
}
