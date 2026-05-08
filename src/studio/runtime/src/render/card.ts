/**
 * Card renderer — proportional typographic system.
 *
 * Three decisions: figure, gravity, ground → PNG.
 *
 * Typography: √2 modular scale from base unit (1% of width).
 * Margins: Renner ratios 2:3:4:6 (inner:top:outer:bottom).
 * Text area: 5/8 of canvas width (Hochuli/Kinross).
 * Optical center: content anchor sits above mathematical center.
 * Leading: 1.2× for display, 1.5× for body (Hochuli optimal).
 * Capitals: always letterspaced (Hochuli rule).
 * Dither image: fills right margin zone, clipped to available space.
 */

import { createCanvas, Image, type CanvasRenderingContext2D } from 'canvas'
import { writeFileSync, existsSync, readFileSync } from 'fs'
import { ensureParentDir } from '../core/paths'
import { ditherCanvas, drawSubject, IMAGE_SUBJECTS, type ImageSubject } from './dither'
import { muted } from './colors'
import { ensureFontsRegistered } from './fonts'

ensureFontsRegistered()

// ── Types ──

export type Figure = 'statement' | 'stat' | 'passage' | 'index'
export type Gravity = 'high' | 'center' | 'low'

export interface Ground {
  id: string
  bg: string
  fg: string
  dark: boolean
  gradient?: { from: string; to: string; angle: number }
}

export interface CardInput {
  figure: Figure
  gravity: Gravity
  ground: Ground
  eyebrow: string
  headline: string
  body: string
  stat?: { num: string; label: string }
  image?: string
  brandName: string
  logoPath?: string
}

export interface PlatformSpec { width: number; height: number; label: string }

export const PLATFORMS: Record<string, PlatformSpec> = {
  linkedin:  { width: 1200, height: 1200, label: 'LinkedIn 1:1' },
  twitter:   { width: 1600, height: 900,  label: 'Twitter 16:9' },
  instagram: { width: 1080, height: 1350, label: 'Instagram 4:5' },
  story:     { width: 1080, height: 1920, label: 'Story 9:16' },
}

export const FIGURES: Figure[] = ['statement', 'stat', 'passage', 'index']
export const GRAVITIES: Gravity[] = ['high', 'center', 'low']
export { IMAGE_SUBJECTS }

export const GROUNDS: Ground[] = [
  { id: 'cream', bg: '#FDF9EC', fg: '#3D1600', dark: false },
  { id: 'warm', bg: '#F0DCC0', fg: '#3D1600', dark: false },
  { id: 'slate', bg: '#E8E6E1', fg: '#1C1C1C', dark: false },
  { id: 'sage', bg: '#E4E8DC', fg: '#2A3328', dark: false },
  { id: 'grounded', bg: '#3D1600', fg: '#FDF9EC', dark: true },
  { id: 'mute', bg: '#1A0A00', fg: '#FDF9EC', dark: true },
  { id: 'ink', bg: '#1C1C1C', fg: '#E8E6E1', dark: true },
  { id: 'dusk', bg: '#2C2438', fg: '#E8E0F0', dark: true },
  { id: 'dawn', bg: '#FFF5E6', fg: '#3D1600', dark: false, gradient: { from: '#FFF5E6', to: '#F0D4C0', angle: 170 } },
  { id: 'ember', bg: '#3D1600', fg: '#FDF9EC', dark: true, gradient: { from: '#3D1600', to: '#5C2800', angle: 160 } },
  { id: 'fog', bg: '#F2F0ED', fg: '#1C1C1C', dark: false, gradient: { from: '#F2F0ED', to: '#D4D0CA', angle: 180 } },
  { id: 'storm', bg: '#1C1C1C', fg: '#E8E6E1', dark: true, gradient: { from: '#1C1C1C', to: '#2A2A30', angle: 160 } },
]

// ── Typography ──

const TYPE: Record<string, { family: string; weight: number; style?: string }> = {
  eyebrow:  { family: '"JetBrains Mono", monospace', weight: 500 },
  headline: { family: '"Alegreya", Georgia, serif', weight: 400 },
  body:     { family: 'Inter, sans-serif', weight: 400 },
  stat:     { family: '"JetBrains Mono", monospace', weight: 400 },
  label:    { family: 'Inter, sans-serif', weight: 500 },
  quote:    { family: '"Alegreya", Georgia, serif', weight: 400, style: 'italic' },
  brand:    { family: '"JetBrains Mono", monospace', weight: 500 },
}

function font(role: string, sizePx: number): string {
  const t = TYPE[role]
  return `${t.style || ''} ${t.weight} ${sizePx}px ${t.family}`.trimStart()
}

// ── Scale + primitives ──

const SQRT2 = Math.SQRT2

function s(base: number, step: number): number {
  return Math.round(base * Math.pow(SQRT2, step))
}

function seededRng(seed: string): () => number {
  let v = 2166136261
  for (let i = 0; i < seed.length; i++) { v ^= seed.charCodeAt(i); v = Math.imul(v, 16777619) }
  return () => { v += 0x6D2B79F5; let t = v; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296 }
}

function splitBullets(text: string): string[] {
  return (text.includes('|') ? text.split('|') : text.split(/\n+/)).map(s => s.trim()).filter(Boolean)
}

function drawSpaced(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, spacing: number): void {
  let curX = x
  for (const char of text) {
    ctx.fillText(char, curX, y)
    curX += ctx.measureText(char).width + spacing
  }
}

function wrapText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const words = text.split(/\s+/).filter(Boolean)
  const lines: string[] = []
  let current = ''
  for (const word of words) {
    const test = current ? current + ' ' + word : word
    if (ctx.measureText(test).width > maxWidth && current) {
      lines.push(current)
      current = word
    } else {
      current = test
    }
  }
  if (current) lines.push(current)
  return lines
}

// ── Main render ──

export function renderCard(input: CardInput, platform: PlatformSpec, seed: string): Buffer {
  const { width, height } = platform
  const canvas = createCanvas(width, height)
  const ctx = canvas.getContext('2d')
  const g = input.ground
  const base = Math.round(width / 100)
  const sz = (step: number) => s(base * 1.2, step)

  // ── Margins (Renner 2:3:4:6) ──
  const unit = base * 2
  const mTop = unit * 3    // 3 parts
  const mSide = unit * 3   // 3 parts (outer)
  const mBottom = unit * 6  // 6 parts
  // Text area = 5/8 of width (Hochuli)
  const textW = Math.round(width * 5 / 8) - mSide
  // Bottom limit — text must not cross this
  const textFloor = height - mBottom

  // Gravity: shift the content anchor vertically
  // Optical center sits above mathematical center (Hochuli)
  let anchorY: number
  if (input.gravity === 'high') {
    anchorY = mTop
  } else if (input.gravity === 'low') {
    anchorY = Math.round(height * 0.45)
  } else {
    // Optical center ≈ 3/8 from top (above mathematical 1/2)
    anchorY = Math.round(height * 3 / 8) - sz(3)
  }

  // ── Background ──
  ctx.fillStyle = g.bg
  ctx.fillRect(0, 0, width, height)
  if (g.gradient) {
    const grad = ctx.createLinearGradient(0, 0, width * 0.3, height)
    grad.addColorStop(0, g.gradient.from)
    grad.addColorStop(1, g.gradient.to)
    ctx.fillStyle = grad
    ctx.fillRect(0, 0, width, height)
  }

  // ── Dithered image ──
  // Fills the right margin zone (outside text area) and extends down
  const imgX = mSide + textW + unit * 2
  const imgW = width - imgX
  if (imgW > 0) {
    const ditherSize = Math.max(imgW, height)
    const ditherCvs = createCanvas(ditherSize, ditherSize)
    const ditherCtx = ditherCvs.getContext('2d')
    ditherCtx.fillStyle = '#fff'
    ditherCtx.fillRect(0, 0, ditherSize, ditherSize)
    drawSubject(input.image || 'topography')(ditherCtx, ditherSize, ditherSize, seededRng(seed + '|img'))
    ditherCanvas(ditherCtx, ditherSize, ditherSize, g.dark)

    ctx.globalAlpha = 0.35
    // Draw proportionally — image fills right zone, vertically centered
    const srcAspect = imgW / height
    const srcW = ditherSize * Math.min(1, srcAspect * 2)
    const srcH = ditherSize
    ctx.drawImage(ditherCvs, 0, 0, srcW, srcH, imgX, 0, imgW, height)
    ctx.globalAlpha = 1
  }

  // ── Text cursor ──
  let cursorY = anchorY
  ctx.textBaseline = 'alphabetic'

  // ── Eyebrow (capitals, letterspaced per Hochuli) ──
  const eyeSize = sz(0)
  ctx.font = font('eyebrow', eyeSize)
  ctx.fillStyle = muted(g.fg, g.bg, 0.5)
  drawSpaced(ctx, input.eyebrow.toUpperCase(), mSide, cursorY, eyeSize * 0.15)
  cursorY += eyeSize + sz(2)

  // ── Figure ──
  ctx.fillStyle = g.fg

  if (input.figure === 'statement') {
    const headSize = sz(5)
    const headLead = headSize * 1.2
    ctx.font = font('headline', headSize)
    const lines = wrapText(ctx, input.headline, textW)
    for (const line of lines) {
      if (cursorY + headSize > textFloor) break
      ctx.fillText(line, mSide, cursorY + headSize)
      cursorY += headLead
    }
    cursorY += sz(1)
    // Body
    const bodySize = sz(1)
    const bodyLead = bodySize * 1.5
    ctx.font = font('body', bodySize)
    ctx.fillStyle = muted(g.fg, g.bg, 0.65)
    const bodyText = splitBullets(input.body).slice(0, 3).join('. ')
    for (const line of wrapText(ctx, bodyText, textW)) {
      if (cursorY + bodySize > textFloor) break
      ctx.fillText(line, mSide, cursorY + bodySize)
      cursorY += bodyLead
    }

  } else if (input.figure === 'stat' && input.stat) {
    const numSize = sz(7)
    ctx.font = font('stat', numSize)
    if (cursorY + numSize <= textFloor) {
      ctx.fillText(input.stat.num, mSide, cursorY + numSize)
      cursorY += numSize + sz(0)
    }
    // Label (capitals, letterspaced)
    const labelSize = sz(0)
    ctx.font = font('label', labelSize)
    ctx.fillStyle = muted(g.fg, g.bg, 0.5)
    if (cursorY + labelSize <= textFloor) {
      drawSpaced(ctx, input.stat.label.toUpperCase(), mSide, cursorY + labelSize, labelSize * 0.1)
      cursorY += labelSize + sz(2)
    }
    // Context body
    const bodySize = sz(1)
    const bodyLead = bodySize * 1.5
    ctx.font = font('body', bodySize)
    ctx.fillStyle = muted(g.fg, g.bg, 0.65)
    for (const line of wrapText(ctx, splitBullets(input.body).join('. '), textW)) {
      if (cursorY + bodySize > textFloor) break
      ctx.fillText(line, mSide, cursorY + bodySize)
      cursorY += bodyLead
    }

  } else if (input.figure === 'passage') {
    // Open quote mark
    const quoteMarkSize = sz(5)
    ctx.font = font('headline', quoteMarkSize)
    ctx.fillStyle = muted(g.fg, g.bg, 0.25)
    ctx.fillText('\u201C', mSide, cursorY + quoteMarkSize)
    cursorY += quoteMarkSize * 0.6
    // Quote body
    const quoteSize = sz(3)
    const quoteLead = quoteSize * 1.3
    ctx.font = font('quote', quoteSize)
    ctx.fillStyle = g.fg
    const quoteText = splitBullets(input.body)[0] || input.body
    for (const line of wrapText(ctx, quoteText, textW)) {
      if (cursorY + quoteSize > textFloor) break
      ctx.fillText(line, mSide, cursorY + quoteSize)
      cursorY += quoteLead
    }

  } else if (input.figure === 'index') {
    const items = splitBullets(input.body).slice(0, 5)
    const itemSize = sz(3)
    const itemLead = itemSize * 1.4
    for (let i = 0; i < items.length; i++) {
      if (cursorY + itemSize + sz(1) > textFloor) break
      // Divider
      ctx.strokeStyle = i === 0
        ? muted(g.fg, g.bg, 0.3)
        : muted(g.fg, g.bg, 0.1)
      ctx.lineWidth = i === 0 ? 2 : 1
      ctx.beginPath()
      ctx.moveTo(mSide, cursorY)
      ctx.lineTo(mSide + textW, cursorY)
      ctx.stroke()
      cursorY += sz(1)
      // Item text
      ctx.font = font('headline', itemSize)
      ctx.fillStyle = g.fg
      ctx.fillText(items[i], mSide, cursorY + itemSize)
      cursorY += itemLead
    }
  }

  // ── Brand mark ──
  // Positioned at bottom margin, adapts opacity to ground contrast
  const markY = height - Math.round(mBottom * 0.4)
  const logoOpacity = g.dark ? 0.35 : 0.5
  if (input.logoPath && existsSync(input.logoPath)) {
    try {
      const img = new Image()
      img.src = readFileSync(input.logoPath)
      const logoH = sz(1) * 1.2
      const logoW = (img.width / img.height) * logoH
      ctx.globalAlpha = logoOpacity
      ctx.drawImage(img, mSide, markY - logoH, logoW, logoH)
    } finally {
      ctx.globalAlpha = 1
    }
  } else {
    ctx.font = font('brand', sz(0))
    ctx.fillStyle = muted(g.fg, g.bg, logoOpacity)
    drawSpaced(ctx, input.brandName.toUpperCase(), mSide, markY, sz(0) * 0.15)
  }

  return canvas.toBuffer('image/png')
}

// ── CLI entry point ──

export interface RenderCardOptions {
  figure: Figure
  gravity: Gravity
  ground: string
  platform: string
  eyebrow: string
  headline: string
  body: string
  statNum?: string
  statLabel?: string
  image?: string
  brandName?: string
  logoPath?: string
  seed?: string
  out: string
}

export function renderCardToFile(opts: RenderCardOptions): { path: string } {
  const ground = GROUNDS.find(g => g.id === opts.ground) || GROUNDS[0]
  const platform = PLATFORMS[opts.platform] || PLATFORMS.linkedin
  const seed = opts.seed || opts.ground + '|' + opts.figure + '|' + Date.now()

  const input: CardInput = {
    figure: opts.figure,
    gravity: opts.gravity,
    ground,
    eyebrow: opts.eyebrow,
    headline: opts.headline,
    body: opts.body,
    stat: opts.statNum ? { num: opts.statNum, label: opts.statLabel || '' } : undefined,
    image: opts.image,
    brandName: opts.brandName || 'GiveCare',
    logoPath: opts.logoPath,
  }

  const png = renderCard(input, platform, seed)
  ensureParentDir(opts.out)
  writeFileSync(opts.out, png)
  return { path: opts.out }
}
