/**
 * Procedural art subjects + Bayer 4×4 ordered dithering.
 *
 * Each subject draws grayscale shapes onto a canvas, then ditherCanvas()
 * converts them to 1-bit halftone with alpha transparency.
 */

import type { CanvasRenderingContext2D } from 'canvas'

export type ImageSubject = typeof IMAGE_SUBJECTS[number]
export const IMAGE_SUBJECTS = ['topography', 'watershed', 'strata', 'grid-erosion', 'root-system', 'threshold'] as const

type DrawFn = (ctx: CanvasRenderingContext2D, w: number, h: number, rng: () => number) => void

const DRAW: Record<ImageSubject, DrawFn> = {
  topography(ctx, w, h, rng) {
    const layers = 8 + Math.floor(rng() * 6)
    const cx = w * (0.2 + rng() * 0.6), cy = h * (0.2 + rng() * 0.6)
    for (let i = layers; i > 0; i--) {
      const t = i / layers; ctx.beginPath()
      for (let p = 0; p <= 60; p++) {
        const a = (p / 60) * Math.PI * 2, bR = t * Math.min(w, h) * 0.45
        const n = bR * 0.3 * (Math.sin(a * 3 + rng() * 10) * 0.5 + Math.sin(a * 7 + rng() * 5) * 0.3 + Math.sin(a * 13 + rng() * 3) * 0.2)
        const x = cx + Math.cos(a) * (bR + n), y = cy + Math.sin(a) * (bR + n)
        p === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
      }
      ctx.closePath(); ctx.fillStyle = `rgba(0,0,0,${0.04 + t * 0.12})`; ctx.fill()
    }
  },
  watershed(ctx, w, _h, rng) {
    ctx.strokeStyle = 'rgba(0,0,0,0.15)'; ctx.lineCap = 'round'
    function br(x: number, y: number, a: number, d: number, lw: number) {
      if (d <= 0 || lw < 0.5) return
      const len = 20 + rng() * 40 * (d / 6), ex = x + Math.cos(a) * len, ey = y + Math.sin(a) * len
      ctx.lineWidth = lw; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(ex, ey); ctx.stroke()
      const dr = (rng() - 0.5) * 0.6
      br(ex, ey, a + dr - 0.3, d - 1, lw * 0.7)
      if (rng() > 0.3) br(ex, ey, a + dr + 0.4, d - 1, lw * 0.6)
      if (rng() > 0.7) br(ex, ey, a + dr + 0.8, d - 1, lw * 0.4)
    }
    br(w * (0.3 + rng() * 0.4), -10, Math.PI / 2 + (rng() - 0.5) * 0.3, 8, 4)
  },
  strata(ctx, w, h, rng) {
    const n = 6 + Math.floor(rng() * 5)
    for (let i = 0; i < n; i++) {
      const by = (h / (n + 1)) * (i + 1); ctx.beginPath(); ctx.moveTo(0, by)
      for (let x = 0; x <= w; x += 4) ctx.lineTo(x, by + Math.sin(x * 0.01 + rng() * 20) * 15 + Math.sin(x * 0.03 + rng() * 10) * 8 + Math.sin(x * 0.07 + rng() * 5) * 4)
      ctx.lineTo(w, h + 10); ctx.lineTo(0, h + 10); ctx.closePath()
      ctx.fillStyle = `rgba(0,0,0,${0.02 + (i / n) * 0.08})`; ctx.fill()
    }
  },
  'grid-erosion'(ctx, w, h, rng) {
    ctx.strokeStyle = 'rgba(0,0,0,0.08)'; ctx.lineWidth = 1
    const sp = 16 + Math.floor(rng() * 12)
    for (let x = sp; x < w; x += sp) { ctx.beginPath(); for (let y = 0; y <= h; y += 3) { const d = Math.sin(y * 0.02 + x * 0.01) * (x / w) * 20 * rng(); y === 0 ? ctx.moveTo(x + d, y) : ctx.lineTo(x + d, y) } ctx.stroke() }
    for (let y = sp; y < h; y += sp) { ctx.beginPath(); for (let x = 0; x <= w; x += 3) { const d = Math.cos(x * 0.015 + y * 0.02) * (y / h) * 20 * rng(); x === 0 ? ctx.moveTo(x, y + d) : ctx.lineTo(x, y + d) } ctx.stroke() }
    for (let i = 0; i < 3 + Math.floor(rng() * 4); i++) { ctx.beginPath(); ctx.arc(rng() * w, rng() * h, 20 + rng() * 60, 0, Math.PI * 2); ctx.fillStyle = `rgba(0,0,0,${0.03 + rng() * 0.06})`; ctx.fill() }
  },
  'root-system'(ctx, w, _h, rng) {
    ctx.strokeStyle = 'rgba(0,0,0,0.12)'; ctx.lineCap = 'round'
    function rt(x: number, y: number, a: number, d: number, lw: number) {
      if (d <= 0 || lw < 0.3) return
      const len = 12 + rng() * 30, c = (rng() - 0.5) * 1.2, ex = x + Math.cos(a) * len, ey = y + Math.sin(a) * len
      ctx.lineWidth = lw; ctx.beginPath(); ctx.moveTo(x, y)
      ctx.quadraticCurveTo(x + Math.cos(a + c) * len * 0.5, y + Math.sin(a + c) * len * 0.5, ex, ey); ctx.stroke()
      rt(ex, ey, a + (rng() - 0.5) * 0.8, d - 1, lw * 0.75)
      if (rng() > 0.4) rt(ex, ey, a + (rng() - 0.3) * 1.2, d - 1, lw * 0.5)
    }
    for (let i = 0; i < 2 + Math.floor(rng() * 3); i++) rt(w * (0.15 + rng() * 0.7), -5, Math.PI / 2 + (rng() - 0.5) * 0.4, 7, 3)
  },
  threshold(ctx, w, h, rng) {
    const dw = w * (0.25 + rng() * 0.2), dh = h * (0.5 + rng() * 0.3), dx = w * (0.3 + rng() * 0.2), dy = h - dh - h * 0.08
    const gr = ctx.createRadialGradient(dx + dw / 2, dy + dh / 2, dw * 0.3, dx + dw / 2, dy + dh / 2, Math.max(w, h) * 0.6)
    gr.addColorStop(0, 'rgba(0,0,0,0.12)'); gr.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.fillStyle = gr; ctx.fillRect(0, 0, w, h)
    ctx.fillStyle = 'rgba(0,0,0,0.08)'; ctx.fillRect(dx, dy, dw, dh)
    ctx.strokeStyle = 'rgba(0,0,0,0.06)'; ctx.lineWidth = 2; ctx.strokeRect(dx - 4, dy - 4, dw + 8, dh + 8)
  },
}

const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map(v => v / 16)

export function ditherCanvas(
  sourceCtx: CanvasRenderingContext2D,
  w: number, h: number,
  dark: boolean,
): void {
  const imageData = sourceCtx.getImageData(0, 0, w, h)
  const data = imageData.data
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const i = (y * w + x) * 4
    const gray = data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114
    const bit = gray < BAYER[(y % 4) * 4 + (x % 4)] * 255 ? 0 : 255
    if (dark) {
      data[i] = 255; data[i + 1] = 255; data[i + 2] = 255
    } else {
      data[i] = 0; data[i + 1] = 0; data[i + 2] = 0
    }
    data[i + 3] = bit === 0 ? 140 : 0
  }
  sourceCtx.putImageData(imageData, 0, 0)
}

export function drawSubject(subject: string): DrawFn {
  return DRAW[subject as ImageSubject] || DRAW.topography
}
