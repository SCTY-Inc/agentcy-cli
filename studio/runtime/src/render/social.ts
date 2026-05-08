/**
 * Social asset renderer.
 *
 * Two-phase pipeline:
 *   1. Gemini generates art-only image (no text, no logos)
 *   2. Composite text on top deterministically
 *
 * Falls back to SVG rendering when the optional native canvas binding is
 * unavailable in the current environment.
 */

import { existsSync, readFileSync, writeFileSync } from 'fs'
import { join } from 'path'
import { Resvg } from '@resvg/resvg-js'
import type { BrandFoundation, SocialPlatform } from '../domain/types'
import { ensureParentDir, type RuntimePaths } from '../core/paths'
import { generateImage } from './gemini'

interface RenderSocialAssetsOptions {
  brand: BrandFoundation
  paths: RuntimePaths
  runId: string
  headline: string
  body: string
  cta?: string
  sourceImagePath: string
  contentType?: string
}

interface PlatformSpec {
  platform: SocialPlatform
  width: number
  height: number
  aspect: string
  layout: 'wide' | 'square' | 'tall'
}

interface TextMeasureContext {
  measureText(text: string): { width: number }
}

const PLATFORM_SPECS: PlatformSpec[] = [
  { platform: 'facebook', width: 1200, height: 1200, aspect: '1:1', layout: 'square' },
  { platform: 'instagram', width: 1080, height: 1350, aspect: '4:5', layout: 'tall' },
  { platform: 'linkedin', width: 1200, height: 1200, aspect: '1:1', layout: 'square' },
  { platform: 'threads', width: 1080, height: 1350, aspect: '4:5', layout: 'tall' },
  { platform: 'twitter', width: 1600, height: 900, aspect: '16:9', layout: 'wide' },
]

function wrapText(ctx: TextMeasureContext, text: string, maxWidth: number): string[] {
  const words = text.split(/\s+/).filter(Boolean)
  const lines: string[] = []
  let current = ''
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word
    if (ctx.measureText(candidate).width <= maxWidth) {
      current = candidate
    } else {
      if (current) lines.push(current)
      current = word
    }
  }
  if (current) lines.push(current)
  return lines
}

function buildArtPrompt(spec: PlatformSpec, brand: BrandFoundation, headline: string): string {
  if (brand.visual.imagePrompt) {
    const base = brand.visual.imagePrompt.replace(/\[SUBJECT\]/gi, headline)
    return `${base.replace(/1:1 square/gi, `${spec.aspect} at ${spec.width}x${spec.height}`)}
IMPORTANT: No text, no words, no letters, no logos, no brand names. Background visual only.`
  }

  const lines: string[] = []
  lines.push(`A ${spec.aspect} abstract visual at ${spec.width}x${spec.height} pixels.`)
  if (brand.visual.style) lines.push(brand.visual.style)
  if (brand.visual.composition) lines.push(`Composition: ${brand.visual.composition}`)
  if (brand.visual.texture) lines.push(`Texture: ${brand.visual.texture}`)
  lines.push(
    `Palette: background ${brand.visual.palette.background}, primary ${brand.visual.palette.primary}, accent ${brand.visual.palette.accent}.`,
  )
  if (brand.visual.negative) lines.push(`Avoid: ${brand.visual.negative}`)
  lines.push('IMPORTANT: No text, no words, no letters, no logos, no brand names. Background visual only.')
  return lines.join('\n')
}

function outputPath(paths: RuntimePaths, runId: string, platform: SocialPlatform): string {
  return join(paths.artifactsDir, runId, `${platform}.png`)
}

function toDataUri(bytes: Buffer, mime: string): string {
  return `data:${mime};base64,${bytes.toString('base64')}`
}

function escapeXml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function approximateMeasure(fontSize: number): TextMeasureContext {
  return {
    measureText(text: string) {
      return { width: Math.max(text.length * fontSize * 0.56, fontSize * 0.8) }
    },
  }
}

function buildSvgAsset(
  artDataUri: string | undefined,
  spec: PlatformSpec,
  brand: BrandFoundation,
  headline: string,
  body: string,
  cta?: string,
): string {
  const palette = brand.visual.palette
  const margin = Math.round(spec.width * 0.06)
  const headSize = spec.layout === 'wide'
    ? Math.round(spec.height * 0.09)
    : Math.round(spec.width * 0.07)
  const maxWidth = spec.width - margin * 2
  const lines = wrapText(approximateMeasure(headSize), headline, maxWidth).slice(0, 3)
  const bodySize = Math.max(Math.round(headSize * 0.34), 26)
  const bodyLines = wrapText(approximateMeasure(bodySize), body, maxWidth).slice(0, spec.layout === 'wide' ? 2 : 3)
  const footer = [cta, spec.platform.toUpperCase()].filter(Boolean).join(' • ')
  const footerSize = Math.max(Math.round(bodySize * 0.9), 20)
  const headlineBlockHeight = lines.length * Math.round(headSize * 1.05)
  const bodyBlockHeight = bodyLines.length * Math.round(bodySize * 1.35)
  const footerHeight = footer ? Math.round(footerSize * 1.4) : 0
  const startY = spec.height - margin - headlineBlockHeight - bodyBlockHeight - footerHeight - 20
  const overlayY = Math.max(startY - margin, Math.round(spec.height * 0.48))
  const overlayHeight = spec.height - overlayY

  let currentY = startY
  const textBlocks: string[] = []

  for (const line of lines) {
    textBlocks.push(
      `<text x="${margin}" y="${currentY}" font-family="Georgia, serif" font-size="${headSize}" fill="${palette.primary}" font-weight="400">${escapeXml(line)}</text>`,
    )
    currentY += Math.round(headSize * 1.05)
  }

  currentY += 14
  for (const line of bodyLines) {
    textBlocks.push(
      `<text x="${margin}" y="${currentY}" font-family="Inter, Arial, sans-serif" font-size="${bodySize}" fill="${palette.primary}" opacity="0.92">${escapeXml(line)}</text>`,
    )
    currentY += Math.round(bodySize * 1.35)
  }

  if (footer) {
    currentY += 18
    textBlocks.push(
      `<text x="${margin}" y="${currentY}" font-family="Inter, Arial, sans-serif" font-size="${footerSize}" fill="${palette.primary}" opacity="0.78">${escapeXml(footer)}</text>`,
    )
  }

  const artLayer = artDataUri
    ? `<image href="${artDataUri}" x="0" y="0" width="${spec.width}" height="${spec.height}" preserveAspectRatio="xMidYMid slice" opacity="0.55" />`
    : `<rect x="0" y="0" width="${spec.width}" height="${spec.height}" fill="${palette.accent}" opacity="0.18" />`

  return `
    <svg xmlns="http://www.w3.org/2000/svg" width="${spec.width}" height="${spec.height}" viewBox="0 0 ${spec.width} ${spec.height}">
      <defs>
        <linearGradient id="overlay" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${palette.background}" stop-opacity="0.12" />
          <stop offset="100%" stop-color="${palette.background}" stop-opacity="0.94" />
        </linearGradient>
      </defs>
      <rect width="100%" height="100%" fill="${palette.background}" />
      ${artLayer}
      <rect x="0" y="${overlayY}" width="${spec.width}" height="${overlayHeight}" fill="url(#overlay)" />
      <rect x="${margin}" y="${Math.max(startY - 28, margin)}" width="${Math.max(maxWidth * 0.36, 220)}" height="6" rx="3" fill="${palette.accent}" opacity="0.88" />
      ${textBlocks.join('\n')}
    </svg>
  `.trim()
}

async function renderWithCanvas(
  artBytes: Buffer | undefined,
  spec: PlatformSpec,
  brand: BrandFoundation,
  headline: string,
): Promise<Buffer> {
  const canvasModule = await import('canvas')
  const { ensureFontsRegistered } = await import('./fonts')
  ensureFontsRegistered()

  const { createCanvas, Image } = canvasModule
  const { width, height } = spec
  const canvas = createCanvas(width, height)
  const ctx = canvas.getContext('2d')
  const palette = brand.visual.palette
  const margin = Math.round(width * 0.06)

  ctx.fillStyle = palette.background
  ctx.fillRect(0, 0, width, height)

  if (artBytes) {
    const artImage = new Image()
    artImage.src = artBytes
    const scale = Math.max(width / artImage.width, height / artImage.height)
    const drawWidth = artImage.width * scale
    const drawHeight = artImage.height * scale
    ctx.drawImage(artImage, (width - drawWidth) / 2, (height - drawHeight) / 2, drawWidth, drawHeight)
  }

  ctx.fillStyle = palette.background
  ctx.globalAlpha = 0.8
  ctx.fillRect(0, Math.round(height * 0.5), width, Math.round(height * 0.5))
  ctx.globalAlpha = 1

  ctx.textBaseline = 'top'
  const headSize = spec.layout === 'wide' ? Math.round(height * 0.09) : Math.round(width * 0.07)
  ctx.font = `400 ${headSize}px "Alegreya", Georgia, serif`
  ctx.fillStyle = palette.primary
  const lines = wrapText(ctx, headline, width - margin * 2).slice(0, 3)
  const lineHeight = headSize * 1.05
  const blockHeight = lines.length * lineHeight
  const startY = height - margin - blockHeight

  for (const [index, line] of lines.entries()) {
    ctx.fillText(line, margin, startY + index * lineHeight)
  }

  return canvas.toBuffer('image/png')
}

function renderWithSvg(
  artBytes: Buffer | undefined,
  spec: PlatformSpec,
  brand: BrandFoundation,
  headline: string,
  body: string,
  cta?: string,
): Buffer {
  const svg = buildSvgAsset(
    artBytes ? toDataUri(artBytes, 'image/png') : undefined,
    spec,
    brand,
    headline,
    body,
    cta,
  )
  return new Resvg(svg).render().asPng()
}

async function renderAsset(
  artBytes: Buffer | undefined,
  spec: PlatformSpec,
  brand: BrandFoundation,
  headline: string,
  body: string,
  cta?: string,
): Promise<Buffer> {
  try {
    return await renderWithCanvas(artBytes, spec, brand, headline)
  } catch {
    return renderWithSvg(artBytes, spec, brand, headline, body, cta)
  }
}

function readSourceImage(path: string): Buffer | undefined {
  if (!path || !existsSync(path)) return undefined
  return readFileSync(path)
}

export async function renderSocialAssets(
  options: RenderSocialAssetsOptions,
): Promise<Record<SocialPlatform, string>> {
  const hasApiKey = !!(process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY)

  let artBytes: Buffer | undefined
  if (hasApiKey) {
    const artPrompt = buildArtPrompt(
      { platform: 'linkedin', width: 1200, height: 1200, aspect: '1:1', layout: 'square' },
      options.brand,
      options.headline,
    )
    const generated = await generateImage(artPrompt)
    if (generated) {
      artBytes = Buffer.isBuffer(generated) ? generated : Buffer.from(generated)
    }
  }

  if (!artBytes) {
    artBytes = readSourceImage(options.sourceImagePath)
  }

  const assets = {} as Record<SocialPlatform, string>

  for (const spec of PLATFORM_SPECS) {
    const png = await renderAsset(artBytes, spec, options.brand, options.headline, options.body, options.cta)
    const path = outputPath(options.paths, options.runId, spec.platform)
    ensureParentDir(path)
    writeFileSync(path, png)
    assets[spec.platform] = path
  }

  return assets
}
