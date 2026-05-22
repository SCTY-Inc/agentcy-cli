import { scale, mix } from './tokens'
import type { Ground, Platform } from './tokens'
import type { BrandVisualStyle } from '../domain/types'

export interface CardContent {
  ground: Ground
  platform: Platform
  eyebrow: string
  headline: string
  body: string
  cta?: string
  style?: BrandVisualStyle
  stat?: { num: string; label: string }
  brandName: string
  logoDataUri?: string
}

type S = Record<string, string | number | undefined>
type NodeChildren = Node | string | (Node | string)[]
export type Node = { type: string; props: { style?: S; children?: NodeChildren; src?: string; alt?: string } }

const el = (type: string, style: S, children?: (Node | string | null | undefined)[]): Node => ({
  type,
  props: { style, children: children?.filter(Boolean) as (Node | string)[] ?? [] },
})

const span = (content: string, style: S): Node =>
  ({ type: 'span', props: { style, children: content } })

const img = (src: string, alt: string, style: S): Node =>
  ({ type: 'img', props: { src, alt, style } })

function wrap(text: string, approxChars: number): string[] {
  const words = text.split(/\s+/).filter(Boolean)
  const lines: string[] = []
  let current = ''
  for (const word of words) {
    const next = current ? `${current} ${word}` : word
    if (next.length > approxChars && current) {
      lines.push(current)
      current = word
    } else {
      current = next
    }
  }
  if (current) lines.push(current)
  return lines
}

function clampLines(text: string, approxChars: number, maxLines: number): string[] {
  const lines = wrap(text.replace(/\s+/g, ' ').trim(), approxChars)
  if (lines.length <= maxLines) return lines

  const kept = lines.slice(0, maxLines)
  const words = kept[maxLines - 1].split(/\s+/).filter(Boolean)
  while (words.length > 1 && `${words.join(' ')}...`.length > approxChars) {
    words.pop()
  }
  kept[maxLines - 1] = `${words.join(' ').replace(/[.,;:!?]+$/, '')}...`
  return kept
}

function firstSupportingSentence(body: string, headline: string): string {
  const headlineText = headline.replace(/[.!?]+$/, '').toLowerCase()
  const sentences = (body.match(/[^.!?]+[.!?]?/g) ?? [body])
    .map((line) => line.replace(/\s+/g, ' ').trim())
    .filter(Boolean)
    .filter((line) => line.replace(/[.!?]+$/, '').toLowerCase() !== headlineText)
  return sentences[0] ?? body
}

function lineStack(lines: string[], style: S): Node {
  return el('div', { display: 'flex', flexDirection: 'column' }, lines.map((line) => span(line, style)))
}

function densityScale(style?: BrandVisualStyle): number {
  if (style?.density === 'low') return 1.1
  if (style?.density === 'high') return 0.94
  return 1
}

export function designCard(opts: CardContent): Node {
  const { ground, platform, eyebrow, headline, body, cta, style, stat, brandName, logoDataUri } = opts
  const { w, h } = platform
  const base = Math.round(w / 100) * 1.2
  const sz = (step: number) => scale(base, step)
  const unit = Math.round(base * 2)
  const density = densityScale(style)
  const primary = ground.primary ?? ground.fg
  const accent = ground.accent ?? primary
  const muted = (t: number) => mix(ground.fg, ground.bg, t)
  const padTop = Math.round(unit * 2.7 * density)
  const padBottom = Math.round(unit * 3.1 * density)
  const contentW = Math.round(Math.min(w - unit * 6, w * 0.84))
  const centerX = Math.round((w - contentW) / 2)
  const heroText = stat ? `${stat.num} ${stat.label}`.trim() : headline
  const supportText = stat ? firstSupportingSentence(body, heroText) : firstSupportingSentence(body, headline)
  const headlineSizeBase = h > w ? sz(5) : sz(6)
  const headlineChars = Math.max(15, Math.round(contentW / (headlineSizeBase * 0.43)))
  const headlineLines = clampLines(heroText, headlineChars, h > w ? 5 : 4)
  const headlineSize = headlineLines.length > 3 ? Math.round(headlineSizeBase * 0.86) : headlineSizeBase
  const bodySize = Math.round(sz(1) * 1.12)
  const bodyLines = clampLines(supportText, Math.max(34, Math.round(contentW / (bodySize * 0.49))), h > w ? 4 : 3)
  const ctaText = cta ? clampLines(cta, Math.max(18, Math.round(contentW / (sz(0) * 0.74))), 1).join('') : undefined
  const logoW = Math.round(Math.min(contentW * 0.2, Math.max(132, w * 0.14)))
  const logoH = Math.round(logoW / 6.57)

  const brandMark = logoDataUri
    ? img(logoDataUri, `${brandName} logo`, {
        width: logoW,
        height: logoH,
        objectFit: 'contain',
        objectPosition: 'left center',
      })
    : span(brandName.toUpperCase(), {
        fontSize: sz(0),
        fontFamily: 'JetBrains Mono',
        fontWeight: 500,
        color: primary,
        letterSpacing: sz(0) * 0.14,
      })

  return el('div', {
    display: 'flex',
    width: w,
    height: h,
    paddingTop: padTop,
    paddingLeft: centerX,
    paddingRight: centerX,
    paddingBottom: padBottom,
    backgroundColor: ground.bg,
    color: ground.fg,
  }, [
    el('div', {
      display: 'flex',
      flexDirection: 'column',
      width: contentW,
      height: h - padTop - padBottom,
    }, [
      el('div', {
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottomWidth: 1,
        borderBottomStyle: 'solid',
        borderBottomColor: mix(primary, ground.bg, 0.14),
        paddingBottom: sz(1),
      }, [
        brandMark,
        span(eyebrow.toUpperCase(), {
          fontSize: sz(0),
          fontFamily: 'JetBrains Mono',
          fontWeight: 500,
          color: muted(0.54),
          letterSpacing: sz(0) * 0.14,
        }),
      ]),
      el('div', {
        display: 'flex',
        flexDirection: 'column',
        flexGrow: 1,
        justifyContent: 'center',
      }, [
        lineStack(headlineLines, {
          fontSize: headlineSize,
          fontFamily: 'Alegreya',
          fontWeight: 400,
          color: ground.fg,
          lineHeight: 0.94,
        }),
        el('div', {
          display: 'flex',
          width: Math.max(82, Math.round(contentW * 0.16)),
          height: Math.max(4, Math.round(w * 0.004)),
          backgroundColor: accent,
          marginTop: sz(2),
          marginBottom: sz(2),
        }, []),
        el('div', { display: 'flex', flexDirection: 'column', maxWidth: Math.round(contentW * 0.88) },
          bodyLines.map((line) => span(line, {
            fontSize: bodySize,
            fontFamily: 'Alegreya',
            fontWeight: 400,
            color: muted(0.72),
            lineHeight: 1.42,
          }))
        ),
        ctaText ? el('div', {
          display: 'flex',
          alignSelf: 'flex-start',
          borderRadius: 999,
          backgroundColor: primary,
          paddingTop: Math.round(sz(0) * 0.85),
          paddingBottom: Math.round(sz(0) * 0.85),
          paddingLeft: Math.round(sz(1) * 1.35),
          paddingRight: Math.round(sz(1) * 1.35),
          marginTop: sz(3),
          maxWidth: Math.round(contentW * 0.78),
        }, [
          span(ctaText, {
            fontSize: sz(0),
            fontFamily: 'JetBrains Mono',
            fontWeight: 500,
            color: ground.bg,
            lineHeight: 1,
            letterSpacing: sz(0) * 0.08,
          }),
        ]) : null,
      ]),
      el('div', {
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderTopWidth: 1,
        borderTopStyle: 'solid',
        borderTopColor: mix(primary, ground.bg, 0.14),
        paddingTop: sz(1),
      }, [
        span('SIGNAL', {
          fontSize: sz(0),
          fontFamily: 'JetBrains Mono',
          fontWeight: 500,
          color: muted(0.5),
          letterSpacing: sz(0) * 0.14,
        }),
        el('div', {
          display: 'flex',
          flexDirection: 'row',
          gap: sz(0),
        }, [0, 1, 2, 3, 4].map((_, index) =>
          el('div', {
            display: 'flex',
            width: Math.max(5, Math.round(w * 0.005)),
            height: Math.max(5, Math.round(w * 0.005)),
            borderRadius: 999,
            backgroundColor: index === 0 ? accent : mix(accent, ground.bg, 0.32),
          }, [])
        )),
      ]),
    ]),
  ])
}
