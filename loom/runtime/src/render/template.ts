import { scale, mix } from './tokens'
import type { Figure, Gravity, Ground, Platform } from './tokens'

export interface CardContent {
  figure: Figure
  gravity: Gravity
  ground: Ground
  platform: Platform
  eyebrow: string
  headline: string
  body: string
  stat?: { num: string; label: string }
  brandName: string
  bgDataUrl?: string
}

type S = Record<string, string | number | undefined>
type Node = { type: string; props: Record<string, any> }

const el = (type: string, style: S, children?: (Node | string | null | undefined)[]): Node => ({
  type,
  props: { style, children: children?.filter(Boolean) as (Node | string)[] ?? [] },
})

const span = (content: string, style: S): Node =>
  ({ type: 'span', props: { style, children: content } })

function wrap(text: string, approxChars: number): string[] {
  const words = text.split(/\s+/).filter(Boolean)
  const lines: string[] = []
  let cur = ''
  for (const w of words) {
    const next = cur ? `${cur} ${w}` : w
    if (next.length > approxChars && cur) { lines.push(cur); cur = w }
    else cur = next
  }
  if (cur) lines.push(cur)
  return lines
}

function bullets(text: string): string[] {
  return (text.includes('|') ? text.split('|') : text.split(/\n+/)).map(s => s.trim()).filter(Boolean)
}

export function cardTemplate(opts: CardContent): Node {
  const { figure, gravity, ground, platform, eyebrow, headline, body, stat, brandName, bgDataUrl } = opts
  const { w, h } = platform
  const base = Math.round(w / 100) * 1.2
  const sz = (step: number) => scale(base, step)
  const unit = Math.round(base * 2)
  const pad = { top: unit * 3, side: unit * 3, bottom: unit * 6 }
  const textW = Math.round(w * 0.625) - pad.side * 2
  const chars = Math.round(textW / (sz(1) * 0.55))
  const muted = (t: number) => mix(ground.fg, ground.bg, t)

  // ── Figure content ──

  let figureNode: Node

  if (figure === 'stat' && stat) {
    figureNode = el('div', { display: 'flex', flexDirection: 'column' }, [
      span(stat.num, { fontSize: sz(7), fontFamily: 'JetBrains Mono', fontWeight: 400, color: ground.fg, lineHeight: 1 }),
      span(stat.label.toUpperCase(), {
        fontSize: sz(0), fontFamily: 'JetBrains Mono', fontWeight: 500,
        color: muted(0.5), letterSpacing: sz(0) * 0.1, marginTop: sz(0),
      }),
      el('div', { display: 'flex', flexDirection: 'column', marginTop: sz(2) },
        wrap(bullets(body).join('. '), chars).slice(0,3).map(line =>
          span(line, { fontSize: sz(1), fontFamily: 'Inter', fontWeight: 400, color: muted(0.65), lineHeight: 1.5 })
        )
      ),
    ])
  } else if (figure === 'passage') {
    const quote = bullets(body)[0] ?? body
    figureNode = el('div', { display: 'flex', flexDirection: 'column' }, [
      span('“', { fontSize: sz(5), fontFamily: 'Alegreya', fontWeight: 400, color: muted(0.25), lineHeight: 1 }),
      el('div', { display: 'flex', flexDirection: 'column' },
        wrap(quote, chars).map(line =>
          span(line, { fontSize: sz(3), fontFamily: 'Alegreya', fontStyle: 'italic', fontWeight: 400, color: ground.fg, lineHeight: 1.3 })
        )
      ),
    ])
  } else if (figure === 'index') {
    figureNode = el('div', { display: 'flex', flexDirection: 'column' },
      bullets(body).slice(0,5).map((item, i) =>
        el('div', {
          display: 'flex', flexDirection: 'column',
          borderTopWidth: i === 0 ? 2 : 1, borderTopStyle: 'solid', borderTopColor: muted(i === 0 ? 0.3 : 0.1),
          paddingTop: sz(1), marginTop: sz(1),
        }, [
          span(item, { fontSize: sz(3), fontFamily: 'Alegreya', fontWeight: 400, color: ground.fg, lineHeight: 1.3 }),
        ])
      )
    )
  } else {
    // statement (default)
    figureNode = el('div', { display: 'flex', flexDirection: 'column' }, [
      el('div', { display: 'flex', flexDirection: 'column' },
        wrap(headline, Math.round(chars * 0.7)).map(line =>
          span(line, { fontSize: sz(5), fontFamily: 'Alegreya', fontWeight: 400, color: ground.fg, lineHeight: 1.2 })
        )
      ),
      el('div', { display: 'flex', flexDirection: 'column', marginTop: sz(2) },
        wrap(bullets(body)[0] ?? body, chars).slice(0,3).map(line =>
          span(line, { fontSize: sz(1), fontFamily: 'Inter', fontWeight: 400, color: muted(0.65), lineHeight: 1.5 })
        )
      ),
    ])
  }

  // ── Gravity: position figure within content area ──
  const contentAlign: S =
    gravity === 'high' ? { justifyContent: 'flex-start' } :
    gravity === 'low'  ? { justifyContent: 'flex-end' } :
                         { justifyContent: 'center' }

  // ── Text panel (left 5/8) ──
  const textPanel = el('div', {
    display: 'flex', flexDirection: 'column',
    width: Math.round(w * 0.625), height: h,
    paddingTop: pad.top, paddingLeft: pad.side, paddingRight: pad.side, paddingBottom: pad.bottom,
    backgroundColor: ground.bg,
  }, [
    span(eyebrow.toUpperCase(), {
      fontSize: sz(0), fontFamily: 'JetBrains Mono', fontWeight: 500,
      color: muted(0.5), letterSpacing: sz(0) * 0.15, marginBottom: sz(2),
    }),
    el('div', { display: 'flex', flexDirection: 'column', flexGrow: 1, ...contentAlign }, [figureNode]),
    span(brandName.toUpperCase(), {
      fontSize: sz(0), fontFamily: 'JetBrains Mono', fontWeight: 500,
      color: muted(ground.dark ? 0.35 : 0.5), letterSpacing: sz(0) * 0.15,
    }),
  ])

  // ── Art panel (right 3/8, Gemini background) ──
  const artPanel = el('div', {
    display: 'flex', flexGrow: 1, height: h,
    ...(bgDataUrl
      ? { backgroundImage: `url(${bgDataUrl})`, backgroundSize: 'cover', backgroundPosition: 'center', opacity: 0.75 }
      : { backgroundColor: ground.bg }
    ),
  }, [])

  // ── Outer container ──
  const outerBg: S = ground.gradient
    ? { backgroundImage: `linear-gradient(${ground.gradient.angle}deg, ${ground.gradient.from}, ${ground.gradient.to})` }
    : { backgroundColor: ground.bg }

  return el('div', { display: 'flex', flexDirection: 'row', width: w, height: h, ...outerBg }, [
    textPanel,
    artPanel,
  ])
}
