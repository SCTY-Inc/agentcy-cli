import { existsSync, readFileSync } from 'fs'
import { join } from 'path'
import { config } from 'dotenv'

const loadedRoots = new Set<string>()
const SHELL_SECRET_KEYS = new Set([
  'OPENAI_API_KEY',
  'ANTHROPIC_API_KEY',
])

function stripWrappingQuotes(value: string): string {
  const trimmed = value.trim()
  if ((trimmed.startsWith('"') && trimmed.endsWith('"')) || (trimmed.startsWith("'") && trimmed.endsWith("'"))) {
    return trimmed.slice(1, -1)
  }
  return trimmed
}

function loadBashSecrets(homeDir: string): void {
  const secretsPath = join(homeDir, '.bash_secrets')
  if (!existsSync(secretsPath)) {
    return
  }

  const lines = readFileSync(secretsPath, 'utf8').split('\n')
  for (const line of lines) {
    const match = line.match(/^\s*(?:export\s+)?([A-Z0-9_]+)=(.*)\s*$/)
    if (!match) {
      continue
    }

    const [, key, rawValue] = match
    if (!SHELL_SECRET_KEYS.has(key) || process.env[key]) {
      continue
    }

    process.env[key] = stripWrappingQuotes(rawValue)
  }
}

export function loadRuntimeEnv(root: string): void {
  if (loadedRoots.has(root)) {
    return
  }

  const envPath = join(root, '.env')
  if (existsSync(envPath)) {
    config({ path: envPath, override: false })
  }

  loadBashSecrets(process.env.HOME ?? '')

  loadedRoots.add(root)
}
