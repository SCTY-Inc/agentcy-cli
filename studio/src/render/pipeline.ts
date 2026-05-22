import satori from 'satori'
import { Resvg } from '@resvg/resvg-js'
import { designCard } from './design-card'
import { getFonts } from './fonts'
import { GROUNDS, PLATFORMS } from './tokens'
import type { Ground, GroundId, PlatformId } from './tokens'
import type { BrandVisualStyle } from '../domain/types'

export interface RenderOptions {
  ground?: Ground
  groundId?: GroundId
  platformId: PlatformId
  topic: string
  eyebrow: string
  headline: string
  body: string
  cta?: string
  style?: BrandVisualStyle
  stat?: { num: string; label: string }
  brandName: string
  logoDataUri?: string
}

export async function renderCard(opts: RenderOptions): Promise<Buffer> {
  const ground    = opts.ground ?? GROUNDS[opts.groundId ?? 'cream']
  const platform  = PLATFORMS[opts.platformId]
  const fonts     = getFonts()

  const element = designCard({
    ground,
    platform,
    eyebrow:   opts.eyebrow,
    headline:  opts.headline,
    body:      opts.body,
    cta:       opts.cta,
    style:     opts.style,
    stat:      opts.stat,
    brandName: opts.brandName,
    logoDataUri: opts.logoDataUri,
  })

  const svg = await satori(element as unknown as Parameters<typeof satori>[0], { width: platform.w, height: platform.h, fonts })
  return Buffer.from(new Resvg(svg, { font: { loadSystemFonts: false } }).render().asPng())
}
