import { existsSync, mkdirSync, readdirSync, realpathSync } from 'fs'
import { dirname, join, resolve } from 'path'

export interface RuntimePaths {
  root: string
  brandsDir: string
  stateDir: string
  artifactsDir: string
  exportsDir: string
  dbPath: string
}

function normalizePath(path: string): string {
  return existsSync(path) ? realpathSync(path) : resolve(path)
}

function hasBrandFoundations(root: string): boolean {
  const brandsDir = join(root, 'brands')
  if (!existsSync(brandsDir)) return false

  const entries = readdirSync(brandsDir, { withFileTypes: true })
  return entries.some((entry) => entry.isDirectory() && existsSync(join(brandsDir, entry.name, 'brand.md')))
}

function detectWorkspaceRoot(start: string): string {
  let current = normalizePath(start)

  while (true) {
    if (hasBrandFoundations(current)) {
      return current
    }

    const parent = dirname(current)
    if (parent === current) {
      return normalizePath(start)
    }
    current = parent
  }
}

export function resolveRuntimePaths(root?: string): RuntimePaths {
  const resolvedRoot = detectWorkspaceRoot(root ?? process.env.LOOM_ROOT ?? process.cwd())
  const stateDir = join(resolvedRoot, 'state')
  const artifactsDir = join(stateDir, 'artifacts')
  const exportsDir = join(stateDir, 'exports')

  return {
    root: resolvedRoot,
    brandsDir: join(resolvedRoot, 'brands'),
    stateDir,
    artifactsDir,
    exportsDir,
    dbPath: join(stateDir, 'loom.sqlite'),
  }
}

export function ensureRuntimePaths(paths: RuntimePaths): void {
  for (const target of [paths.brandsDir, paths.stateDir, paths.artifactsDir, paths.exportsDir]) {
    if (!existsSync(target)) {
      mkdirSync(target, { recursive: true })
    }
  }
}

export function ensureParentDir(filePath: string): void {
  const parent = dirname(filePath)
  if (!existsSync(parent)) {
    mkdirSync(parent, { recursive: true })
  }
}
