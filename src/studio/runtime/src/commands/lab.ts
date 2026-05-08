import { writeFileSync } from 'fs'
import { join, resolve } from 'path'
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
    '  lab render --brand <id> --figure statement --gravity center --ground cream [--platform linkedin] [--image topography] [--headline "..."] [--body "..."] [--out path.png]',
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

export function runLabCommand(args: string[], root?: string): unknown {
  const [subcommand, ...rest] = args

  if (subcommand === 'render') {
    return runLabRender(rest, root)
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

async function runLabRender(args: string[], root?: string): Promise<unknown> {
  const parsed = parseArgs(args)
  const { FIGURES, GRAVITIES, GROUNDS, PLATFORMS, renderCardToFile } = await import('../render/card')

  const figure = parsed.figure || 'statement'
  const gravity = parsed.gravity || 'center'
  const groundId = parsed.ground || 'cream'
  const platform = parsed.platform || 'linkedin'
  const image = parsed.image || 'topography'

  if (!FIGURES.includes(figure as (typeof FIGURES)[number])) {
    throw new Error('Invalid figure: ' + figure + '. Options: ' + FIGURES.join(', '))
  }
  if (!GRAVITIES.includes(gravity as (typeof GRAVITIES)[number])) {
    throw new Error('Invalid gravity: ' + gravity + '. Options: ' + GRAVITIES.join(', '))
  }
  if (!GROUNDS.find((ground) => ground.id === groundId)) {
    throw new Error('Invalid ground: ' + groundId + '. Options: ' + GROUNDS.map((ground) => ground.id).join(', '))
  }
  if (!(platform in PLATFORMS)) {
    throw new Error('Invalid platform: ' + platform + '. Options: ' + Object.keys(PLATFORMS).join(', '))
  }

  const paths = resolveRuntimePaths(root)

  const brand = parsed.brand ? loadBrandFoundation(parsed.brand, { root: paths.root }) : undefined
  const brandName = brand?.name || 'GiveCare'
  const logoPath = brand?.visual.logo
    ? join(paths.root, 'brands', brand.id, brand.visual.logo)
    : undefined

  const headline = parsed.headline || 'Care is infrastructure'
  const body = parsed.body || 'The care economy is valued at $1 trillion in unpaid labor annually.'
  const eyebrow = parsed.eyebrow || 'CARE ECONOMY'
  const seed = parsed.seed || groundId + '|' + figure + '|' + Date.now()

  const outPath = parsed.out
    ? resolve(paths.root, parsed.out)
    : join(paths.stateDir, 'cards', `${figure}-${gravity}-${groundId}-${platform}.png`)

  const result = renderCardToFile({
    figure: figure as (typeof FIGURES)[number],
    gravity: gravity as (typeof GRAVITIES)[number],
    ground: groundId,
    platform,
    eyebrow,
    headline,
    body,
    statNum: parsed['stat-num'],
    statLabel: parsed['stat-label'],
    image,
    brandName,
    logoPath,
    seed,
    out: outPath,
  })

  return {
    figure,
    gravity,
    ground: groundId,
    platform,
    image,
    path: result.path,
  }
}
