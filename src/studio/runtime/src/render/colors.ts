/** Shared color utilities for all renderers. */

export function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}

export function muted(fg: string, bg: string, t: number): string {
  const [r1, g1, b1] = hexToRgb(fg)
  const [r2, g2, b2] = hexToRgb(bg)
  const mix = (a: number, b: number) => Math.round(a * t + b * (1 - t))
  return `rgb(${mix(r1, r2)}, ${mix(g1, g2)}, ${mix(b1, b2)})`
}
