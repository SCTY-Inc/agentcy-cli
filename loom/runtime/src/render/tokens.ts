import { readFileSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'
import yaml from 'js-yaml'

const __dir = dirname(fileURLToPath(import.meta.url))
const raw = readFileSync(join(__dir, '../../brand.design.md'), 'utf8')
const fm = raw.match(/^---\n([\s\S]+?)\n---/)!
const t = yaml.load(fm[1]) as Record<string, any>

export interface Ground {
  bg: string
  fg: string
  dark: boolean
  gradient?: { from: string; to: string; angle: number }
}

export interface Platform { w: number; h: number; label: string }

export type GroundId   = keyof typeof GROUNDS
export type PlatformId = keyof typeof PLATFORMS
export type Figure     = 'statement' | 'stat' | 'passage' | 'index'
export type Gravity    = 'high' | 'center' | 'low'

export const GROUNDS   = t.grounds   as Record<string, Ground>
export const PLATFORMS = t.platforms as Record<string, Platform>
export const FIGURES   = t.figures   as Figure[]
export const GRAVITIES = t.gravities as Gravity[]

const SQRT2 = Math.SQRT2
export const scale = (base: number, step: number): number =>
  Math.round(base * Math.pow(SQRT2, step))

export const mix = (hex1: string, hex2: string, t: number): string => {
  const p = (s: string) => [parseInt(s.slice(1,3),16), parseInt(s.slice(3,5),16), parseInt(s.slice(5,7),16)] as const
  const [r1,g1,b1] = p(hex1), [r2,g2,b2] = p(hex2)
  return `rgb(${Math.round(r1*t+r2*(1-t))},${Math.round(g1*t+g2*(1-t))},${Math.round(b1*t+b2*(1-t))})`
}
