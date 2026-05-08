import { existsSync, readFileSync } from 'fs'
import { extname, join } from 'path'
import type { BrandFoundation } from '../domain/types'

export const CARD_LAB_TYPES = ['quote', 'hero-stat', 'fact-list', 'signal-post', 'photo-text'] as const
export type CardLabType = typeof CARD_LAB_TYPES[number]

interface BuildCardLabOptions {
  brand: BrandFoundation
  brandAssetBasePath: string
  fontHrefPrefix?: string
  initialCardType?: CardLabType
  initialHeadline?: string
  initialBody?: string
  initialEyebrow?: string
  initialPlatform?: 'twitter' | 'linkedin' | 'instagram'
  initialSeed?: string
  initialSeries?: 'weekly-insights' | 'weekly-recap' | 'signal-drop' | 'custom'
}

interface CardLabBootData {
  brand: {
    id: string
    name: string
    positioning: string
    palette: BrandFoundation['visual']['palette']
    typography: {
      headline: string
      body: string
      accent: string
    }
    motif?: string
    layout?: string
    logoDataUri?: string
  }
  initial: {
    cardType: CardLabType
    headline: string
    body: string
    eyebrow: string
    platform: 'twitter' | 'linkedin' | 'instagram'
    seed: string
    series: 'weekly-insights' | 'weekly-recap' | 'signal-drop' | 'custom'
  }
}

function imageMimeType(path: string): string {
  switch (extname(path).toLowerCase()) {
    case '.png':
      return 'image/png'
    case '.jpg':
    case '.jpeg':
      return 'image/jpeg'
    case '.gif':
      return 'image/gif'
    case '.webp':
      return 'image/webp'
    case '.svg':
      return 'image/svg+xml'
    default:
      return 'application/octet-stream'
  }
}

function maybeEmbedLogo(brand: BrandFoundation, brandAssetBasePath: string): string | undefined {
  if (!brand.visual.logo) return undefined
  const filePath = join(brandAssetBasePath, brand.visual.logo)
  if (!existsSync(filePath)) return undefined
  const bytes = readFileSync(filePath)
  return `data:${imageMimeType(filePath)};base64,${bytes.toString('base64')}`
}

function fallbackHeadline(brand: BrandFoundation): string {
  return brand.proofPoints[0] ?? brand.positioning
}

function fallbackBody(brand: BrandFoundation): string {
  return brand.pillars[0]?.perspective ?? brand.channels.social.objective
}

function fallbackEyebrow(brand: BrandFoundation): string {
  return brand.pillars[0]?.id.replace(/[-_]/g, ' ').toUpperCase() ?? brand.name.toUpperCase()
}

function defaultTypography(brand: BrandFoundation): CardLabBootData['brand']['typography'] {
  return {
    headline: brand.visual.typography?.headline ?? 'Georgia, serif',
    body: brand.visual.typography?.body ?? 'system-ui, sans-serif',
    accent: brand.visual.typography?.accent ?? 'system-ui, sans-serif',
  }
}

function escapeJson(value: unknown): string {
  return JSON.stringify(value).replace(/</g, '\\u003c')
}

function buildFontCss(fontHrefPrefix: string): string {
  return [
    `@font-face { font-family: "Loom Alegreya Body"; src: url("${fontHrefPrefix}/alegreya-400.woff2") format("woff2"); font-weight: 400; font-style: normal; font-display: swap; }`,
    `@font-face { font-family: "Loom Alegreya Headline"; src: url("${fontHrefPrefix}/alegreya-latin-wght-normal.woff2") format("woff2"); font-weight: 400 900; font-style: normal; font-display: swap; }`,
    `@font-face { font-family: "Loom Gabarito"; src: url("${fontHrefPrefix}/gabarito-latin-400-normal.woff2") format("woff2"); font-weight: 400; font-style: normal; font-display: swap; }`,
  ].join('\n')
}

export function buildCardLabHtml(options: BuildCardLabOptions): string {
  const boot: CardLabBootData = {
    brand: {
      id: options.brand.id,
      name: options.brand.name,
      positioning: options.brand.positioning,
      palette: options.brand.visual.palette,
      typography: defaultTypography(options.brand),
      motif: options.brand.visual.motif,
      layout: options.brand.visual.layout,
      logoDataUri: maybeEmbedLogo(options.brand, options.brandAssetBasePath),
    },
    initial: {
      cardType: options.initialCardType ?? 'quote',
      headline: options.initialHeadline ?? fallbackHeadline(options.brand),
      body: options.initialBody ?? fallbackBody(options.brand),
      eyebrow: options.initialEyebrow ?? fallbackEyebrow(options.brand),
      platform: options.initialPlatform ?? 'linkedin',
      seed: options.initialSeed ?? `${options.brand.id}-${Date.now()}`,
      series: options.initialSeries ?? 'weekly-insights',
    },
  }

  const fontCss = buildFontCss(options.fontHrefPrefix ?? './fonts')

  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${options.brand.name} Card Lab</title>
    <style>
      ${fontCss}
      :root {
        --bg: ${options.brand.visual.palette.background};
        --fg: ${options.brand.visual.palette.primary};
        --accent: ${options.brand.visual.palette.accent};
        --line: color-mix(in srgb, var(--fg) 16%, transparent);
        --muted: color-mix(in srgb, var(--fg) 62%, var(--bg) 38%);
      }

      * { box-sizing: border-box; }
      html, body { margin: 0; min-height: 100%; }
      body {
        background: var(--bg);
        color: var(--fg);
        font-family: "Loom Alegreya Body", Georgia, serif;
      }

      .app {
        min-height: 100vh;
        display: grid;
        grid-template-columns: 280px minmax(0, 1fr);
      }

      .rail {
        border-right: 1px solid var(--line);
        padding: 14px;
        display: grid;
        gap: 14px;
        align-content: start;
      }

      .main {
        padding: 14px;
        display: grid;
        gap: 14px;
        align-content: start;
      }

      .section {
        display: grid;
        gap: 10px;
        padding-top: 10px;
        border-top: 1px solid var(--line);
      }

      .eyebrow-label {
        font-size: 10px;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--muted);
      }

      .title {
        margin: 0;
        font-size: 22px;
        line-height: 1;
        letter-spacing: -0.04em;
      }

      .meta,
      .small {
        margin: 0;
        color: var(--muted);
        font-size: 13px;
        line-height: 1.45;
      }

      label {
        display: grid;
        gap: 6px;
        font-size: 10px;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: var(--muted);
      }

      input, textarea, select, button {
        font: inherit;
      }

      input, textarea, select {
        width: 100%;
        padding: 8px 9px;
        border: 1px solid var(--line);
        background: #fff;
        color: var(--fg);
        border-radius: 4px;
      }

      textarea {
        min-height: 74px;
        resize: vertical;
        line-height: 1.4;
      }

      .json-input {
        min-height: 320px;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 12px;
        line-height: 1.45;
      }

      .row {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }

      button {
        padding: 8px 10px;
        border: 1px solid var(--line);
        border-radius: 4px;
        background: var(--fg);
        color: var(--bg);
        cursor: pointer;
      }

      button.secondary {
        background: transparent;
        color: var(--fg);
      }

      .main {
        height: 100vh;
        grid-template-rows: auto minmax(0, 1fr) auto;
        min-height: 0;
      }

      .stage {
        border: 1px solid var(--line);
        background: var(--bg);
        padding: 12px;
        min-height: 0;
        height: min(68vh, 700px);
        display: grid;
        grid-template-rows: auto minmax(0, 1fr) auto;
        gap: 12px;
        overflow: hidden;
      }

      .stage-head {
        display: flex;
        align-items: start;
        justify-content: space-between;
        gap: 12px;
      }

      .selection-meta {
        color: var(--muted);
        font-size: 12px;
      }

      .pair-grid {
        min-height: 0;
        height: 100%;
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
        align-items: stretch;
        overflow: hidden;
      }

      .pair-option {
        min-height: 0;
        overflow: hidden;
        display: grid;
        grid-template-rows: minmax(0, 1fr) auto;
        gap: 8px;
        align-content: start;
      }

      .pair-button {
        padding: 0;
        border: 0;
        background: transparent;
        color: inherit;
        text-align: left;
        min-height: 0;
        overflow: hidden;
        display: grid;
        place-items: center;
      }

      .pair-button.active .card {
        outline: 2px solid color-mix(in srgb, var(--accent) 46%, transparent);
        outline-offset: 0;
      }

      .pair-meta {
        display: flex;
        justify-content: space-between;
        gap: 8px;
        color: var(--muted);
        font-size: 11px;
      }

      .choice-bar {
        display: grid;
        grid-template-columns: 1fr auto auto 1fr;
        gap: 8px;
        align-self: end;
      }

      .choice-bar button {
        width: 100%;
      }

      .result-grid {
        display: none;
        grid-template-columns: 280px minmax(0, 1fr);
        gap: 12px;
      }

      .result-grid.ready {
        display: grid;
      }

      .result-panel {
        border: 1px solid var(--line);
        padding: 10px;
        display: grid;
        gap: 8px;
        align-content: start;
        min-height: 0;
      }

      .score-list {
        display: grid;
        gap: 6px;
      }

      .score-row {
        display: grid;
        gap: 4px;
      }

      .score-bar {
        height: 6px;
        background: color-mix(in srgb, var(--fg) 8%, transparent);
        position: relative;
      }

      .score-fill {
        position: absolute;
        inset: 0 auto 0 0;
        background: var(--accent);
      }

      .result-note {
        font-size: 12px;
        line-height: 1.45;
        color: var(--muted);
      }

      .card {
        position: relative;
        overflow: hidden;
        width: 100%;
        max-width: min(100%, 620px);
        margin-inline: auto;
        border: 1px solid color-mix(in srgb, var(--card-fg, var(--fg)) 12%, transparent);
        background: var(--card-bg, var(--bg));
        color: var(--card-fg, var(--fg));
        border-radius: 4px;
      }

      .pair-button .card {
        width: auto;
        height: 100%;
        max-width: min(100%, 560px);
        max-height: 100%;
      }

      .card-inner {
        position: relative;
        min-height: 100%;
        padding: var(--pad, 36px);
        display: grid;
        grid-template-rows: minmax(0, 1fr) auto;
        align-content: space-between;
        gap: 12px;
        isolation: isolate;
      }

      .card-inner::before,
      .card-inner::after {
        content: "";
        position: absolute;
        pointer-events: none;
      }

      .texture-paper::before {
        inset: 0;
        opacity: var(--texture, 0.12);
        background:
          radial-gradient(circle at 20% 18%, rgba(255,255,255,0.5), transparent 32%),
          linear-gradient(180deg, rgba(0,0,0,0), rgba(0,0,0,0.05));
        mix-blend-mode: multiply;
        z-index: -2;
      }

      .texture-scan::before {
        inset: 0;
        opacity: calc(var(--texture, 0.18) + 0.04);
        background:
          repeating-linear-gradient(180deg, rgba(0,0,0,0.05) 0, rgba(0,0,0,0.05) 1px, transparent 1px, transparent 5px),
          radial-gradient(circle at 16% 10%, rgba(255,255,255,0.24), transparent 24%);
        mix-blend-mode: multiply;
        z-index: -2;
      }

      .motif-rings::after {
        right: -6%;
        top: -8%;
        width: 40%;
        aspect-ratio: 1;
        opacity: calc(var(--motif, 0.12) + 0.04);
        background:
          radial-gradient(circle, transparent 42%, color-mix(in srgb, var(--card-fg, var(--fg)) 10%, transparent) 42%, color-mix(in srgb, var(--card-fg, var(--fg)) 10%, transparent) 47%, transparent 47%, transparent 57%, color-mix(in srgb, var(--accent) 16%, transparent) 57%, color-mix(in srgb, var(--accent) 16%, transparent) 61%, transparent 61%);
        z-index: -1;
      }

      .motif-bars::after {
        right: 10%;
        top: 12%;
        width: calc(8px + var(--motif, 0.18) * 32px);
        height: 58%;
        opacity: calc(var(--motif, 0.18) + 0.06);
        background: linear-gradient(180deg, var(--accent), color-mix(in srgb, var(--card-fg, var(--fg)) 28%, transparent));
        z-index: -1;
      }

      .align-center { text-align: center; }
      .align-left { text-align: left; }

      .card-header {
        position: relative;
        display: grid;
        gap: 10px;
      }

      .accent-rule .card-header::after,
      .accent-band .card-header::after,
      .accent-corner .card-header::after {
        content: "";
        position: absolute;
      }

      .accent-rule .card-header::after {
        left: 0;
        bottom: -6px;
        width: min(140px, 34%);
        height: 3px;
        background: var(--accent);
      }

      .align-center.accent-rule .card-header::after {
        left: 50%;
        transform: translateX(-50%);
      }

      .accent-band .card-header::after {
        right: calc(var(--pad, 36px) * -1);
        bottom: calc(var(--pad, 36px) * -0.35);
        width: 34%;
        height: 10px;
        background: var(--accent);
      }

      .accent-corner .card-header::after {
        right: calc(var(--pad, 36px) * -0.12);
        top: calc(var(--pad, 36px) * -0.18);
        width: 20%;
        aspect-ratio: 1;
        border-top: 4px solid var(--accent);
        border-right: 4px solid var(--accent);
      }

      .eyebrow {
        display: inline-flex;
        align-items: center;
        align-self: start;
        max-width: fit-content;
        font-size: 10px;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: color-mix(in srgb, var(--card-fg, var(--fg)) 72%, var(--card-bg, var(--bg)) 28%);
        font-family: "JetBrains Mono", ui-monospace, monospace;
      }

      .headline {
        margin: 0;
        max-width: var(--measure, 11ch);
        font-size: calc(30px * var(--headline-scale, 1));
        line-height: 0.92;
        letter-spacing: -0.05em;
        font-weight: 700;
        font-family: "Loom Alegreya Headline", Georgia, serif;
        overflow-wrap: anywhere;
        text-wrap: balance;
      }

      .headline.stat {
        font-size: calc(50px * var(--headline-scale, 1));
      }

      .body,
      .facts {
        margin: 0;
        max-width: var(--body-measure, 28ch);
        color: color-mix(in srgb, var(--card-fg, var(--fg)) 82%, var(--card-bg, var(--bg)) 18%);
        font-size: calc(12px + var(--density-step, 0) * 1px);
        line-height: 1.44;
        font-family: "Loom Alegreya Body", Georgia, serif;
        overflow-wrap: anywhere;
      }

      .facts {
        padding: 0;
        list-style: none;
        display: grid;
        gap: 8px;
      }

      .facts li {
        display: grid;
        grid-template-columns: 12px 1fr;
        gap: 8px;
        align-items: start;
      }

      .facts li::before {
        content: "";
        width: 6px;
        height: 6px;
        background: var(--accent);
        margin-top: 0.55em;
      }

      .card-footer {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        align-items: end;
      }

      .brand-lockup {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: 10px;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        font-family: "JetBrains Mono", ui-monospace, monospace;
      }

      .brand-lockup.has-logo {
        gap: 0;
      }

      .brand-lockup.has-logo span {
        display: none;
      }

      .brand-mark {
        width: 12px;
        height: 12px;
        background: var(--accent);
        flex: 0 0 auto;
      }

      .brand-logo {
        width: 92px;
        max-width: 100%;
        height: auto;
        max-height: 24px;
        object-fit: contain;
        object-position: left center;
        flex: 0 0 auto;
      }

      .media-block {
        border: 1px solid color-mix(in srgb, var(--card-fg, var(--fg)) 12%, transparent);
        background: linear-gradient(145deg, color-mix(in srgb, var(--accent) 16%, transparent), color-mix(in srgb, var(--card-fg) 8%, transparent));
        min-height: 120px;
      }

      .layout-center .card-inner {
        align-content: center;
      }

      .layout-center .card-header {
        justify-items: center;
      }

      .layout-center .eyebrow,
      .layout-center .body,
      .layout-center .facts {
        justify-self: center;
      }

      .layout-footer-band .card-footer {
        padding-top: 10px;
        border-top: 2px solid color-mix(in srgb, var(--accent) 55%, transparent);
      }

      .layout-split .card-inner {
        grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
        grid-template-rows: minmax(0, 1fr) auto;
        column-gap: 16px;
      }

      .layout-split .card-header {
        grid-column: 1;
        grid-row: 1;
      }

      .layout-split .card-footer {
        grid-column: 1 / -1;
        grid-row: 2;
      }

      .layout-split .media-block {
        grid-column: 2;
        grid-row: 1;
        align-self: stretch;
        min-height: 0;
      }

      .layout-poster .headline {
        max-width: 8ch;
        letter-spacing: -0.06em;
      }

      .layout-poster .body {
        max-width: 20ch;
      }

      .platform-pill {
        font-size: 10px;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: color-mix(in srgb, var(--card-fg, var(--fg)) 58%, var(--card-bg, var(--bg)) 42%);
      }

      .stat-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
      }

      .stat-chip,
      .preset-json {
        border: 1px solid var(--line);
        border-radius: 4px;
      }

      .stat-chip {
        padding: 8px;
        background: rgba(255,255,255,0.14);
        font-size: 12px;
        font-family: "JetBrains Mono", ui-monospace, monospace;
        letter-spacing: 0.02em;
      }

      .preset-json {
        margin: 0;
        padding: 10px;
        background: #fff;
        color: var(--fg);
        font-size: 12px;
        line-height: 1.45;
        white-space: pre-wrap;
        word-break: break-word;
      }

      @media (max-width: 1200px) {
        .result-grid {
          grid-template-columns: 1fr;
        }
      }

      @media (max-width: 900px) {
        .app {
          grid-template-columns: 1fr;
        }

        .rail {
          border-right: 0;
          border-bottom: 1px solid var(--line);
        }

        .main {
          height: auto;
        }

        .pair-grid,
        .choice-bar {
          grid-template-columns: 1fr;
        }
      }
    </style>
  </head>
  <body>
    <div class="app">
      <aside class="rail">
        <div>
          <div class="eyebrow-label">Card Lab</div>
          <h1 class="title">${options.brand.name}</h1>
          <p class="meta">20 variations. 4 approaches. Pick from the board.</p>
        </div>

        <div class="section">
          <p class="small">${options.brand.positioning}</p>
        </div>

        <div class="section">
          <div class="eyebrow-label">Brief JSON</div>
          <p class="small">This is the normalized brief driving the variation board. Edit it if you want, but it should already be populated.</p>
          <textarea id="briefJson" class="json-input"></textarea>
          <div id="jsonStatus" class="small"></div>
          <div class="row">
            <button id="generate">Generate 20 Variations</button>
            <button id="shuffle" class="secondary">Shuffle</button>
          </div>
        </div>

        <div class="section">
          <div class="eyebrow-label">Brand tokens</div>
          <p class="small">Headline: ${defaultTypography(options.brand).headline}<br />Body: ${defaultTypography(options.brand).body}<br />Accent: ${defaultTypography(options.brand).accent}<br />Motif: ${options.brand.visual.motif ?? 'Not set'}</p>
        </div>
      </aside>

      <main class="main">
        <div class="stage-head">
          <div>
            <div class="eyebrow-label">Head to head</div>
            <h2 class="title">Choose between two directions</h2>
          </div>
          <div class="row">
            <button id="copyPreset" class="secondary">Copy top preset JSON</button>
          </div>
        </div>

        <section class="stage">
          <div class="selection-meta" id="selectionMeta">20 candidates. 10 rounds. Pick what you prefer.</div>
          <div id="pairGrid" class="pair-grid"></div>
          <div class="choice-bar">
            <button id="chooseLeft">Prefer left</button>
            <button id="chooseBothBad" class="secondary">Both bad</button>
            <button id="chooseBothGood" class="secondary">Both good</button>
            <button id="chooseRight">Prefer right</button>
          </div>
        </section>

        <section id="resultGrid" class="result-grid">
          <div class="result-panel">
            <div class="eyebrow-label">Current leaning</div>
            <div id="recommendationSummary" class="result-note">No picks yet.</div>
            <div id="scoreList" class="score-list"></div>
          </div>
          <div class="result-panel">
            <div class="eyebrow-label">Top preset JSON</div>
            <pre id="presetJson" class="preset-json"></pre>
          </div>
        </section>
      </main>
    </div>

    <script>
      const boot = ${escapeJson(boot)}
      const aspectMap = {
        linkedin: { width: 1, height: 1, label: 'LinkedIn 1:1' },
        twitter: { width: 16, height: 9, label: 'Twitter 16:9' },
        instagram: { width: 4, height: 5, label: 'Instagram 4:5' },
      }

      const densitySettings = {
        quiet: { measure: '12ch', bodyMeasure: '30ch', densityStep: -1 },
        balanced: { measure: '10.5ch', bodyMeasure: '28ch', densityStep: 0 },
        dense: { measure: '9ch', bodyMeasure: '24ch', densityStep: 1 },
      }

      const els = {
        briefJson: document.getElementById('briefJson'),
        jsonStatus: document.getElementById('jsonStatus'),
        generate: document.getElementById('generate'),
        shuffle: document.getElementById('shuffle'),
        copyPreset: document.getElementById('copyPreset'),
        pairGrid: document.getElementById('pairGrid'),
        presetJson: document.getElementById('presetJson'),
        selectionMeta: document.getElementById('selectionMeta'),
        recommendationSummary: document.getElementById('recommendationSummary'),
        scoreList: document.getElementById('scoreList'),
        resultGrid: document.getElementById('resultGrid'),
        chooseLeft: document.getElementById('chooseLeft'),
        chooseRight: document.getElementById('chooseRight'),
        chooseBothBad: document.getElementById('chooseBothBad'),
        chooseBothGood: document.getElementById('chooseBothGood'),
      }

      const state = {
        groups: [],
        candidates: [],
        pairs: [],
        pairIndex: 0,
        picks: [],
      }

      setInitialValues()
      wireEvents()
      regenerate()

      function setInitialValues() {
        els.briefJson.value = JSON.stringify(defaultBrief(), null, 2)
        els.jsonStatus.textContent = 'Loaded from the current GiveCare brief.'
      }

      function wireEvents() {
        els.generate.addEventListener('click', regenerate)
        els.shuffle.addEventListener('click', () => {
          const brief = readBriefFromJson() || defaultBrief()
          brief.seed = boot.brand.id + '-' + Math.random().toString(36).slice(2, 8)
          els.briefJson.value = JSON.stringify(brief, null, 2)
          regenerate()
        })
        els.copyPreset.addEventListener('click', copyPresetJson)
        els.chooseLeft.addEventListener('click', () => vote('left'))
        els.chooseRight.addEventListener('click', () => vote('right'))
        els.chooseBothBad.addEventListener('click', () => vote('bad'))
        els.chooseBothGood.addEventListener('click', () => vote('good'))
        window.addEventListener('keydown', (event) => {
          if (event.metaKey || event.ctrlKey || event.altKey) return
          if (event.key === 'ArrowLeft') vote('left')
          if (event.key === 'ArrowRight') vote('right')
          if (event.key === 'ArrowDown') vote('bad')
          if (event.key === 'ArrowUp') vote('good')
        })
      }

      function regenerate() {
        const input = readInput()
        if (!input) {
          state.groups = []
          state.candidates = []
          state.pairs = []
          state.pairIndex = 0
          state.picks = []
          renderCurrent()
          return
        }

        state.groups = buildApproachGroups(input)
        state.candidates = shuffleCandidates(state.groups.flatMap((group) => group.variants), input.seed)
        state.pairs = buildPairs(state.candidates)
        state.pairIndex = 0
        state.picks = []
        renderCurrent()
      }

      function defaultBrief() {
        return {
          brand: boot.brand.id,
          series: boot.initial.series,
          platform: boot.initial.platform,
          seed: boot.initial.seed,
          direction: boot.initial.headline,
          notes: splitBullets(boot.initial.body),
          editorNote: [boot.initial.headline, boot.initial.body].filter(Boolean).join('\\n\\n'),
        }
      }

      function readBriefFromJson() {
        try {
          const parsed = JSON.parse(els.briefJson.value)
          els.jsonStatus.textContent = 'Using brief JSON from the left rail.'
          return parsed
        } catch (error) {
          els.jsonStatus.textContent = 'Brief JSON is invalid. Fix the JSON and regenerate.'
          return null
        }
      }

      function normalizeBrief(brief) {
        const series = typeof brief.series === 'string' ? brief.series : boot.initial.series
        const platform = typeof brief.platform === 'string' ? brief.platform : boot.initial.platform
        const seed = typeof brief.seed === 'string' ? brief.seed : boot.initial.seed
        const direction = typeof brief.direction === 'string' && brief.direction.trim().length > 0
          ? brief.direction.trim()
          : boot.brand.positioning
        const notes = Array.isArray(brief.notes)
          ? brief.notes.map((item) => String(item).trim()).filter(Boolean)
          : splitBullets(typeof brief.notes === 'string' ? brief.notes : boot.initial.body)

        return {
          brand: boot.brand.id,
          series,
          platform,
          seed,
          direction,
          notes,
          editorNote: typeof brief.editorNote === 'string' ? brief.editorNote : '',
          ...deriveContentPackage(series, direction, notes.join(' | ')),
        }
      }

      function readInput() {
        const brief = readBriefFromJson()
        if (!brief) return null
        return normalizeBrief(brief)
      }

      function deriveContentPackage(series, direction, notes) {
        if (series === 'weekly-insights') {
          return {
            eyebrow: boot.brand.name.toUpperCase() + ' PULSE',
            headline: direction,
            body: notes || 'Three signals shaping care right now.',
          }
        }

        if (series === 'weekly-recap') {
          return {
            eyebrow: 'WEEKLY RECAP',
            headline: direction || 'What shifted this week in care',
            body: notes || 'What mattered, what changed, what operators should watch next.',
          }
        }

        if (series === 'signal-drop') {
          return {
            eyebrow: 'SIGNAL DROP',
            headline: direction || 'A market signal worth paying attention to',
            body: notes || 'One signal. One sharp implication. One next move.',
          }
        }

        return {
          eyebrow: boot.initial.eyebrow,
          headline: direction,
          body: notes,
        }
      }

      function resolveCardTypeForApproach(series, approachId, index) {
        const byApproach = {
          'pulse-masthead': 'quote',
          'editors-note': 'quote',
          'weekly-callouts': 'fact-list',
          'lead-signal': 'signal-post',
          'signal-grid': 'signal-post',
          'broken-copy': 'photo-text',
          'type-poster': 'hero-stat',
          'brief-sheet': 'fact-list',
        }
        const fallback = byApproach[approachId] || 'quote'
        if (series === 'custom') {
          return ['quote', 'signal-post', 'fact-list', 'photo-text', 'hero-stat'][index % 5]
        }
        return fallback
      }

      function buildApproachGroups(input) {
        return approachDefinitions().map((approach, approachIndex) => {
          const variants = []
          for (let index = 0; index < 5; index += 1) {
            const rng = seededRandom(input.seed + '|' + approach.id + '|' + input.series + '|' + input.headline + '|' + index)
            variants.push({
              id: approach.id + '-' + (index + 1),
              approachId: approach.id,
              approachLabel: approach.label,
              label: approach.shortLabel + ' ' + (index + 1),
              note: approach.note,
              series: input.series,
              brandId: boot.brand.id,
              brandName: boot.brand.name,
              cardType: resolveCardTypeForApproach(input.series, approach.id, index),
              eyebrow: input.eyebrow,
              headline: input.headline,
              body: input.body,
              direction: input.direction,
              notes: input.notes,
              platform: input.platform,
              alignment: pick(rng, approach.alignment),
              density: pick(rng, approach.density),
              accentMode: pick(rng, approach.accentMode),
              texture: Number((approach.texture[0] + rng() * (approach.texture[1] - approach.texture[0])).toFixed(2)),
              motif: Number((approach.motif[0] + rng() * (approach.motif[1] - approach.motif[0])).toFixed(2)),
              headlineScale: Number((approach.scale[0] + rng() * (approach.scale[1] - approach.scale[0])).toFixed(2)),
              padding: Math.round(approach.padding[0] + rng() * (approach.padding[1] - approach.padding[0])),
              layoutVariant: pick(rng, approach.layoutVariants ?? ['layout-footer-band']),
              familyOrder: approachIndex,
            })
          }
          return { ...approach, variants, order: approachIndex }
        })
      }

      function approachDefinitions() {
        if (boot.brand.layout === 'signal-grid') {
          return [
            { id: 'signal-grid', label: 'Signal Grid', shortLabel: 'Signal', note: 'Sharp hierarchy, clean interruption, operator framing.', alignment: ['left', 'left', 'center'], density: ['balanced', 'dense', 'balanced'], accentMode: ['band', 'rule', 'corner'], texture: [0.18, 0.34], motif: [0.18, 0.34], scale: [0.92, 1.12], padding: [28, 42], layoutVariants: ['layout-split', 'layout-footer-band'] },
            { id: 'broken-copy', label: 'Broken Copy', shortLabel: 'Broken', note: 'More damaged, more thresholded, more interruption.', alignment: ['left', 'left', 'left'], density: ['dense', 'dense', 'balanced'], accentMode: ['band', 'band', 'corner'], texture: [0.24, 0.42], motif: [0.2, 0.38], scale: [0.88, 1.06], padding: [26, 38], layoutVariants: ['layout-split', 'layout-poster'] },
            { id: 'type-poster', label: 'Type Poster', shortLabel: 'Type', note: 'Larger type, simpler surfaces, harder statement.', alignment: ['left', 'center', 'left'], density: ['quiet', 'balanced', 'balanced'], accentMode: ['rule', 'corner', 'rule'], texture: [0.08, 0.22], motif: [0.12, 0.26], scale: [1.04, 1.24], padding: [30, 44], layoutVariants: ['layout-poster', 'layout-center'] },
            { id: 'brief-sheet', label: 'Brief Sheet', shortLabel: 'Brief', note: 'More structured, more scan-friendly, still on-brand.', alignment: ['left', 'left', 'center'], density: ['balanced', 'dense', 'dense'], accentMode: ['rule', 'band', 'rule'], texture: [0.12, 0.26], motif: [0.08, 0.18], scale: [0.9, 1.04], padding: [28, 40], layoutVariants: ['layout-footer-band', 'layout-split'] },
          ]
        }

        return [
          { id: 'pulse-masthead', label: 'Pulse Masthead', shortLabel: 'Masthead', note: 'Big editorial thesis with a restrained deck and strong breathing room.', alignment: ['left', 'center', 'left'], density: ['quiet', 'quiet', 'balanced'], accentMode: ['rule', 'corner'], texture: [0.03, 0.1], motif: [0.04, 0.12], scale: [1.04, 1.22], padding: [36, 54], layoutVariants: ['layout-center', 'layout-poster'] },
          { id: 'editors-note', label: 'Editor’s Note', shortLabel: 'Note', note: 'Lead paragraph first, softer hierarchy, more reading-oriented.', alignment: ['left', 'left', 'center'], density: ['quiet', 'balanced'], accentMode: ['rule', 'corner'], texture: [0.04, 0.14], motif: [0.05, 0.14], scale: [0.94, 1.06], padding: [38, 56], layoutVariants: ['layout-footer-band', 'layout-center'] },
          { id: 'weekly-callouts', label: 'Weekly Callouts', shortLabel: 'Callouts', note: 'Structured recap with 2–3 takeaway blocks and a tighter editorial system.', alignment: ['left', 'left'], density: ['balanced', 'dense'], accentMode: ['band', 'rule'], texture: [0.06, 0.16], motif: [0.04, 0.1], scale: [0.9, 1.0], padding: [30, 42], layoutVariants: ['layout-split', 'layout-footer-band'] },
          { id: 'lead-signal', label: 'Lead Signal', shortLabel: 'Signal', note: 'Single strongest idea with source-like framing and one clear implication.', alignment: ['left', 'center'], density: ['balanced', 'quiet'], accentMode: ['rule', 'band', 'corner'], texture: [0.08, 0.18], motif: [0.08, 0.2], scale: [0.96, 1.1], padding: [32, 46], layoutVariants: ['layout-split', 'layout-center'] },
        ]
      }

      function shuffleCandidates(candidates, seed) {
        const rng = seededRandom(seed + '|shuffle')
        return [...candidates]
          .map((candidate) => ({ candidate, order: rng() }))
          .sort((a, b) => a.order - b.order)
          .map((entry) => entry.candidate)
      }

      function buildPairs(candidates) {
        const pairs = []
        for (let index = 0; index < candidates.length; index += 2) {
          const left = candidates[index]
          const right = candidates[index + 1]
          if (left && right) pairs.push([left, right])
        }
        return pairs
      }

      function currentPair() {
        return state.pairs[state.pairIndex] ?? null
      }

      function vote(decision) {
        const pair = currentPair()
        if (!pair) return
        state.picks.push({
          pairIndex: state.pairIndex,
          decision,
          leftId: pair[0].id,
          rightId: pair[1].id,
        })
        state.pairIndex += 1
        renderCurrent()
      }

      function renderCurrent() {
        const pair = currentPair()
        const scores = computeScores()

        if (!pair) {
          els.resultGrid.classList.add('ready')
          renderScores(scores)
          renderCompletion(scores)
          return
        }

        els.resultGrid.classList.remove('ready')
        els.selectionMeta.textContent = 'Round ' + String(state.pairIndex + 1) + ' of ' + String(state.pairs.length) + ' · 20 candidates across 4 families · arrows work too'
        els.pairGrid.innerHTML = renderPairOption(pair[0], 'left') + renderPairOption(pair[1], 'right')
        els.pairGrid.querySelectorAll('[data-choose-side]').forEach((node) => {
          node.addEventListener('click', () => vote(node.getAttribute('data-choose-side')))
        })
      }

      function renderCompletion(scores) {
        const winner = recommendedFamily(scores)
        const topVariant = topVariantFromScores(scores)
        els.selectionMeta.textContent = winner
          ? 'Done · recommended family: ' + winner.label + ' · based on ' + String(state.picks.length) + ' pairwise picks'
          : 'Done'
        els.pairGrid.innerHTML = topVariant
          ? '<div class="pair-option" style="grid-column:1 / -1;">' + renderCard(topVariant, 'result') + '</div>'
          : '<div class="small">No recommendation yet.</div>'
        els.presetJson.textContent = topVariant ? JSON.stringify(presetFor(topVariant), null, 2) : '{}'
      }

      function renderPairOption(variant, side) {
        return '<div class="pair-option">'
          + '<button class="pair-button" data-choose-side="' + side + '">'
          + renderCard(variant, 'pair')
          + '</button>'
          + '<div class="pair-meta"><span>' + escapeHtml(variant.approachLabel) + '</span><span>' + escapeHtml(variant.label) + '</span></div>'
          + '</div>'
      }

      function computeScores() {
        const variantScores = new Map(state.candidates.map((variant) => [variant.id, 0]))
        for (const pickEntry of state.picks) {
          if (pickEntry.decision === 'left') {
            variantScores.set(pickEntry.leftId, (variantScores.get(pickEntry.leftId) ?? 0) + 2)
            variantScores.set(pickEntry.rightId, (variantScores.get(pickEntry.rightId) ?? 0) - 0.5)
          }
          if (pickEntry.decision === 'right') {
            variantScores.set(pickEntry.rightId, (variantScores.get(pickEntry.rightId) ?? 0) + 2)
            variantScores.set(pickEntry.leftId, (variantScores.get(pickEntry.leftId) ?? 0) - 0.5)
          }
          if (pickEntry.decision === 'good') {
            variantScores.set(pickEntry.leftId, (variantScores.get(pickEntry.leftId) ?? 0) + 1)
            variantScores.set(pickEntry.rightId, (variantScores.get(pickEntry.rightId) ?? 0) + 1)
          }
          if (pickEntry.decision === 'bad') {
            variantScores.set(pickEntry.leftId, (variantScores.get(pickEntry.leftId) ?? 0) - 1)
            variantScores.set(pickEntry.rightId, (variantScores.get(pickEntry.rightId) ?? 0) - 1)
          }
        }

        const familyScores = new Map()
        for (const group of state.groups) {
          let total = 0
          for (const variant of group.variants) {
            total += variantScores.get(variant.id) ?? 0
          }
          familyScores.set(group.id, total)
        }

        return { variantScores, familyScores }
      }

      function renderScores(scores) {
        const families = state.groups
          .map((group) => ({ id: group.id, label: group.label, note: group.note, score: scores.familyScores.get(group.id) ?? 0 }))
          .sort((a, b) => b.score - a.score)
        const maxScore = Math.max(1, ...families.map((family) => family.score + 2))
        const winner = families[0]

        els.recommendationSummary.textContent = winner
          ? 'Current recommended family: ' + winner.label + '. ' + winner.note
          : 'No picks yet.'

        els.scoreList.innerHTML = families.map((family) => {
          const width = Math.max(6, ((family.score + 2) / maxScore) * 100)
          return '<div class="score-row">'
            + '<div class="pair-meta"><span>' + escapeHtml(family.label) + '</span><span>' + String(Number(family.score.toFixed(1))) + '</span></div>'
            + '<div class="score-bar"><div class="score-fill" style="width:' + width + '%;"></div></div>'
            + '</div>'
        }).join('')
      }

      function recommendedFamily(scores) {
        return state.groups
          .map((group) => ({ ...group, score: scores.familyScores.get(group.id) ?? 0 }))
          .sort((a, b) => b.score - a.score)[0] ?? null
      }

      function topVariantFromScores(scores) {
        return [...state.candidates]
          .sort((a, b) => (scores.variantScores.get(b.id) ?? 0) - (scores.variantScores.get(a.id) ?? 0))[0] ?? null
      }

      function fitVariant(variant, mode = 'pair') {
        const next = { ...variant }
        const headlineLength = String(next.headline).length
        const bodyLength = String(next.body).length
        const bulletCount = splitBullets(String(next.body)).length

        if (mode === 'pair') {
          next.headlineScale *= 0.82
          next.padding = Math.max(20, next.padding - 10)
        } else if (mode === 'result') {
          next.headlineScale *= 0.92
          next.padding = Math.max(24, next.padding - 6)
        } else {
          next.headlineScale *= 0.9
          next.padding = Math.max(24, next.padding - 6)
        }

        if (next.platform === 'twitter') {
          next.headlineScale *= 0.94
          next.padding = Math.max(20, next.padding - 4)
        }

        if (headlineLength > 70) {
          next.headlineScale *= 0.88
          next.padding = Math.max(20, next.padding - 4)
        }
        if (headlineLength > 110) {
          next.headlineScale *= 0.8
          next.padding = Math.max(18, next.padding - 4)
          next.density = 'dense'
        }
        if (bodyLength > 180 || bulletCount > 3) {
          next.padding = Math.max(18, next.padding - 4)
          if (next.density === 'quiet') next.density = 'balanced'
        }
        if (bodyLength > 260 || bulletCount > 4) {
          next.density = 'dense'
          next.padding = Math.max(16, next.padding - 4)
        }

        next.headlineScale = Number(next.headlineScale.toFixed(2))
        return next
      }

      function renderCard(variant, mode = 'pair') {
        const fitted = fitVariant(variant, mode)
        const aspect = aspectMap[fitted.platform]
        const density = densitySettings[fitted.density]
        const textureClass = boot.brand.layout === 'signal-grid' ? 'texture-scan' : 'texture-paper'
        const motifClass = boot.brand.layout === 'signal-grid' ? 'motif-bars' : 'motif-rings'
        const layoutClass = fitted.layoutVariant ?? 'layout-footer-band'
        const headlineClass = fitted.cardType === 'hero-stat' ? 'headline stat' : 'headline'
        const mark = boot.brand.logoDataUri
          ? '<img class="brand-logo" alt="' + escapeHtml(boot.brand.name) + ' logo" src="' + boot.brand.logoDataUri + '" />'
          : '<span class="brand-mark"></span>'
        const lockupClass = boot.brand.logoDataUri ? 'brand-lockup has-logo' : 'brand-lockup'
        const style = mode === 'pair'
          ? 'aspect-ratio:' + aspect.width + '/' + aspect.height + '; height:100%; width:auto; max-width:min(100%, 520px);'
          : 'aspect-ratio:' + aspect.width + '/' + aspect.height + '; width:100%; max-width:' + (mode === 'result' ? '920px' : '620px') + ';'

        return '<article class="card" style="' + style + ' --card-bg:' + boot.brand.palette.background + '; --card-fg:' + boot.brand.palette.primary + '; --accent:' + boot.brand.palette.accent + ';">'
          + '<div class="card-inner ' + textureClass + ' ' + motifClass + ' ' + layoutClass + ' align-' + fitted.alignment + ' accent-' + fitted.accentMode + '" style="--headline-scale:' + fitted.headlineScale + '; --texture:' + fitted.texture + '; --motif:' + fitted.motif + '; --pad:' + fitted.padding + 'px; --measure:' + density.measure + '; --body-measure:' + density.bodyMeasure + '; --density-step:' + density.densityStep + ';">'
          + '<div class="card-header">'
          + '<div class="eyebrow">' + escapeHtml(fitted.eyebrow) + '</div>'
          + renderHeadline(fitted, headlineClass)
          + renderBody(fitted)
          + '</div>'
          + renderMediaBlock(fitted)
          + '<div class="card-footer">'
          + '<div class="' + lockupClass + '">' + mark + '<span>' + escapeHtml(boot.brand.name) + '</span></div>'
          + '</div>'
          + '</div>'
          + '</article>'
      }

      function truncateWords(text, count) {
        const words = String(text).split(/\s+/).filter(Boolean)
        return words.length <= count ? words.join(' ') : words.slice(0, count).join(' ') + '…'
      }

      function normalizeBullets(variant) {
        return splitBullets(String(variant.body)).map((item) => truncateWords(item, 12))
      }

      function renderHeadline(variant, headlineClass) {
        const headline = variant.layoutVariant === 'layout-poster'
          ? truncateWords(variant.headline, 8)
          : variant.headline
        return '<h3 class="' + headlineClass + '">' + escapeHtml(headline) + '</h3>'
      }

      function renderBody(variant) {
        const bullets = normalizeBullets(variant)
        if (variant.cardType === 'fact-list') {
          return '<ul class="facts">' + bullets.slice(0, 3).map((item) => '<li><span>' + escapeHtml(item) + '</span></li>').join('') + '</ul>'
        }

        if (variant.cardType === 'hero-stat') {
          const chips = bullets.slice(0, 2).map((item) => '<div class="stat-chip">' + escapeHtml(item) + '</div>').join('')
          return '<div style="display:grid; gap:10px;">'
            + '<p class="body">' + escapeHtml(truncateWords(bullets[0] ?? variant.body, 16)) + '</p>'
            + '<div class="stat-grid">' + chips + '</div>'
            + '</div>'
        }

        if (variant.cardType === 'signal-post') {
          return '<div style="display:grid; gap:10px;">'
            + '<p class="body">' + escapeHtml(truncateWords(bullets.slice(0, 2).join(' '), 22)) + '</p>'
            + '<div class="stat-chip" style="max-width:20ch; justify-self:' + (variant.alignment === 'center' ? 'center' : 'start') + ';">Operator view</div>'
            + '</div>'
        }

        if (variant.cardType === 'photo-text') {
          return '<p class="body">' + escapeHtml(truncateWords(bullets[0] ?? variant.body, 18)) + '</p>'
        }

        return '<p class="body">' + escapeHtml(truncateWords(bullets.slice(0, 2).join(' '), 22)) + '</p>'
      }

      function renderMediaBlock(variant) {
        if (variant.layoutVariant !== 'layout-split') return ''
        return '<div class="media-block" aria-hidden="true"></div>'
      }

      function presetFor(variant) {
        return {
          brand: boot.brand.id,
          series: variant.series,
          approach: variant.approachId,
          template: variant.cardType,
          defaults: {
            platform: variant.platform,
            alignment: variant.alignment,
            density: variant.density,
            accentMode: variant.accentMode,
            headlineScale: variant.headlineScale,
            texture: variant.texture,
            motif: variant.motif,
            padding: variant.padding,
          },
          brief: {
            direction: variant.direction,
            notes: variant.notes,
          },
          content: {
            eyebrow: variant.eyebrow,
            headline: variant.headline,
            body: variant.body,
          },
        }
      }

      function copyPresetJson() {
        const variant = topVariantFromScores(computeScores())
        if (!variant) return
        const payload = JSON.stringify(presetFor(variant), null, 2)
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(payload)
        }
      }

      function splitBullets(text) {
        const parts = text.includes('|') ? text.split('|') : text.split(/\\n+/)
        return parts.map((item) => item.trim()).filter(Boolean)
      }

      function seededRandom(seed) {
        let value = 2166136261
        for (let index = 0; index < seed.length; index += 1) {
          value ^= seed.charCodeAt(index)
          value = Math.imul(value, 16777619)
        }
        return function next() {
          value += 0x6D2B79F5
          let t = value
          t = Math.imul(t ^ (t >>> 15), t | 1)
          t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
          return ((t ^ (t >>> 14)) >>> 0) / 4294967296
        }
      }

      function pick(rng, values) {
        return values[Math.floor(rng() * values.length)]
      }

      function escapeHtml(value) {
        return String(value)
          .replaceAll('&', '&amp;')
          .replaceAll('<', '&lt;')
          .replaceAll('>', '&gt;')
          .replaceAll('"', '&quot;')
          .replaceAll("'", '&#39;')
      }

      function cssFontStack(value) {
        return String(value)
      }
    </script>
  </body>
</html>`
}
