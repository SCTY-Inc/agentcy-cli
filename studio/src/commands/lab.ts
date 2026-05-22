import { existsSync, readFileSync, writeFileSync } from 'fs'
import { extname, join, resolve } from 'path'
import { loadBrandFoundation } from '../brands/load'
import { ensureParentDir, resolveRuntimePaths } from '../core/paths'
import { buildCardLabHtml, CARD_LAB_TYPES, type CardLabType } from '../lab/build'

interface LabInput {
  brand?: string
  type: CardLabType
  headline?: string
  body?: string
  eyebrow?: string
  series: 'weekly-insights' | 'weekly-recap' | 'signal-drop' | 'custom'
  platform: 'twitter' | 'linkedin' | 'instagram'
  seed?: string
  out?: string
}

interface CoverInput {
  brand?: string
  title?: string
  subtitle?: string
  eyebrow?: string
  seed?: string
  source?: string
  background?: string
  out?: string
}

function parseArgs(args: string[]): Record<string, string> {
  const parsed: Record<string, string> = {}
  let index = 0

  while (index < args.length) {
    const arg = args[index]
    if (arg.startsWith('--')) {
      const key = arg.slice(2)
      const value = args[index + 1]
      if (!value || value.startsWith('--')) {
        throw new Error(`Missing value for --${key}`)
      }
      parsed[key] = value
      index += 2
      continue
    }
    index += 1
  }

  return parsed
}

function usage(): string {
  return [
    'Usage:',
    '  lab card --brand <id> [--type quote] [--headline "..."] [--out path]',
    '  lab cover --brand <id> --title "..." [--subtitle "..."] [--eyebrow "..."] [--seed "..."] [--background path.png] [--source post.md] [--out cover.png]',
    '  lab render --brand <id> [--style editorial] [--ground cream] [--platform linkedin] [--headline "..."] [--body "..."] [--out path.png]',
  ].join('\n')
}

function isCardLabType(value: string): value is CardLabType {
  return CARD_LAB_TYPES.includes(value as CardLabType)
}

function normalizeInput(args: string[]): LabInput {
  const parsed = parseArgs(args)
  const type = parsed.type ?? 'quote'
  const platform = parsed.platform ?? 'linkedin'
  const series = parsed.series ?? 'weekly-insights'

  if (!isCardLabType(type)) {
    throw new Error(`Invalid card type: ${type}. Expected one of: ${CARD_LAB_TYPES.join(', ')}`)
  }

  if (!['twitter', 'linkedin', 'instagram'].includes(platform)) {
    throw new Error('Invalid platform: ' + platform + '. Expected one of: twitter, linkedin, instagram')
  }

  if (!['weekly-insights', 'weekly-recap', 'signal-drop', 'custom'].includes(series)) {
    throw new Error('Invalid series: ' + series + '. Expected one of: weekly-insights, weekly-recap, signal-drop, custom')
  }

  return {
    brand: parsed.brand,
    type,
    headline: parsed.headline,
    body: parsed.body,
    eyebrow: parsed.eyebrow,
    series: series as LabInput['series'],
    platform: platform as LabInput['platform'],
    seed: parsed.seed,
    out: parsed.out,
  }
}

function normalizeCoverInput(args: string[]): CoverInput {
  const parsed = parseArgs(args)
  return {
    brand: parsed.brand,
    title: parsed.title,
    subtitle: parsed.subtitle,
    eyebrow: parsed.eyebrow,
    seed: parsed.seed,
    source: parsed.source,
    background: parsed.background,
    out: parsed.out,
  }
}

function slug(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 72) || 'cover'
}

function sidecarPathFor(outputPath: string): string {
  return /\.png$/i.test(outputPath) ? outputPath.replace(/\.png$/i, '.json') : `${outputPath}.json`
}

function backgroundDataUrlFromPath(path: string): string {
  const ext = extname(path).toLowerCase()
  const mime =
    ext === '.png' ? 'image/png' :
    ext === '.jpg' || ext === '.jpeg' ? 'image/jpeg' :
    ''
  if (!mime) {
    throw new Error('Background image must be a PNG or JPEG file')
  }
  return `data:${mime};base64,${readFileSync(path).toString('base64')}`
}

export function runLabCommand(args: string[], root?: string): unknown {
  const [subcommand, ...rest] = args

  if (subcommand === 'render') {
    return runLabRender(rest, root)
  }

  if (subcommand === 'cover') {
    return runLabCover(rest, root)
  }

  if (subcommand !== 'card') {
    throw new Error(usage())
  }

  const input = normalizeInput(rest)
  if (!input.brand) {
    throw new Error(usage())
  }

  const paths = resolveRuntimePaths(root)
  const brand = loadBrandFoundation(input.brand, { root: paths.root })
  const outputPath = input.out
    ? join(paths.root, input.out)
    : join(paths.stateDir, 'lab', `${brand.id}-${input.type}.html`)

  ensureParentDir(outputPath)

  const html = buildCardLabHtml({
    brand,
    brandAssetBasePath: join(paths.brandsDir, brand.id),
    fontHrefPrefix: './fonts',
    initialCardType: input.type,
    initialHeadline: input.headline,
    initialBody: input.body,
    initialEyebrow: input.eyebrow,
    initialPlatform: input.platform,
    initialSeed: input.seed,
    initialSeries: input.series,
  })

  writeFileSync(outputPath, html, 'utf8')

  return {
    brand: brand.id,
    type: input.type,
    path: outputPath,
    next: `Open ${outputPath} in a browser to explore variants and save presets.`,
    series: input.series,
  }
}

async function runLabCover(args: string[], root?: string): Promise<unknown> {
  const { buildOgCoverSidecar, OG_COVER_HEIGHT, OG_COVER_WIDTH, renderOgCover } = await import('../render/og-cover')
  const input = normalizeCoverInput(args)

  if (!input.brand || !input.title) {
    throw new Error(usage())
  }

  const paths = resolveRuntimePaths(root)
  const brand = loadBrandFoundation(input.brand, { root: paths.root })
  const outputPath = input.out
    ? resolve(paths.root, input.out)
    : join(paths.stateDir, 'covers', `${brand.id}-${slug(input.title)}.png`)
  const sidecarPath = sidecarPathFor(outputPath)
  const sourcePath = input.source ? resolve(paths.root, input.source) : undefined
  const backgroundPath = input.background ? resolve(paths.root, input.background) : undefined

  if (sourcePath && !existsSync(sourcePath)) {
    throw new Error(`Source file not found: ${sourcePath}`)
  }
  if (backgroundPath && !existsSync(backgroundPath)) {
    throw new Error(`Background image not found: ${backgroundPath}`)
  }

  ensureParentDir(outputPath)
  ensureParentDir(sidecarPath)

  const renderInput = {
    brand,
    title: input.title,
    subtitle: input.subtitle,
    eyebrow: input.eyebrow,
    seed: input.seed,
    sourcePath,
    outputPath,
    backgroundDataUrl: backgroundPath ? backgroundDataUrlFromPath(backgroundPath) : undefined,
  }
  const png = await renderOgCover(renderInput)
  const sidecar = buildOgCoverSidecar(renderInput)

  writeFileSync(outputPath, png)
  writeFileSync(sidecarPath, `${JSON.stringify(sidecar, null, 2)}\n`, 'utf8')

  return {
    brand: brand.id,
    title: input.title,
    width: OG_COVER_WIDTH,
    height: OG_COVER_HEIGHT,
    path: outputPath,
    sidecarPath,
    sourcePath,
    backgroundPath,
  }
}

async function runLabRender(args: string[], root?: string): Promise<unknown> {
  const { writeFileSync, mkdirSync } = await import('fs')
  const { PLATFORMS } = await import('../render/tokens')
  const { renderCard } = await import('../render/pipeline')
  const parsed = parseArgs(args)

  const groundId = parsed.ground
  const platformId = parsed.platform || 'linkedin'

  if (!(platformId in PLATFORMS))  throw new Error('Invalid platform: ' + platformId + '. Options: ' + Object.keys(PLATFORMS).join(', '))

  const paths    = resolveRuntimePaths(root)
  const brand    = parsed.brand ? loadBrandFoundation(parsed.brand, { root: paths.root }) : undefined
  const styleId  = parsed.style || brand?.visual.defaultStyle
  const style    = brand && styleId ? brand.visual.styles.find((item) => item.id === styleId) : undefined
  if (brand && parsed.style && !style) {
    throw new Error(`Unknown visual style for brand ${brand.id}: ${parsed.style}`)
  }
  const palette = brand ? {
    ...brand.visual.palette,
    ...(style?.palette ?? {}),
  } : undefined
  const ground = palette && !groundId ? {
    bg: palette.background || '#FFFFFF',
    fg: palette.text || palette.primary || '#111111',
    primary: palette.primary,
    secondary: palette.secondary,
    accent: palette.accent,
    dark: /^#?([0-9a-f]{6})$/i.test(palette.background || '') && (() => {
      const value = (palette.background || '#FFFFFF').replace(/^#/, '')
      const [r, g, b] = [0, 2, 4].map((index) => parseInt(value.slice(index, index + 2), 16) / 255)
      return 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.45
    })(),
  } : undefined
  const headline = parsed.headline || 'Care is infrastructure'
  const body     = parsed.body || 'The care economy is valued at $1 trillion in unpaid labor annually.'
  const eyebrow  = parsed.eyebrow || 'CARE ECONOMY'
  const outPath  = parsed.out
    ? resolve(paths.root, parsed.out)
    : join(paths.stateDir, 'cards', `${style?.id ?? groundId ?? 'cream'}-${platformId}.png`)

  const stat = parsed['stat-num']
    ? { num: parsed['stat-num'] as string, label: (parsed['stat-label'] as string) || '' }
    : undefined

  mkdirSync(join(paths.stateDir, 'cards'), { recursive: true })
  const png = await renderCard({
    ground, groundId: groundId || 'cream', platformId,
    topic: eyebrow, eyebrow, headline, body, stat,
    style,
    brandName: brand?.name || 'GiveCare',
  })
  writeFileSync(outPath, png)

  return { ground: groundId || 'brand', style: style?.id ?? null, platform: platformId, path: outPath }
}
