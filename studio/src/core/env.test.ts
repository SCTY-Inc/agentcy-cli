import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { loadRuntimeEnv } from './env'

const tempPaths: string[] = []
const managedKeys = [
  'OPENAI_API_KEY',
  'ANTHROPIC_API_KEY',
]

function makeTempDir(prefix: string): string {
  const path = mkdtempSync(join(tmpdir(), prefix))
  tempPaths.push(path)
  return path
}

function clearManagedKeys(): void {
  for (const key of managedKeys) {
    delete process.env[key]
  }
}

beforeEach(() => {
  clearManagedKeys()
})

afterEach(() => {
  while (tempPaths.length > 0) {
    rmSync(tempPaths.pop()!, { recursive: true, force: true })
  }

  clearManagedKeys()
  delete process.env.HOME
})

describe('loadRuntimeEnv', () => {
  test('loads dotenv and supported shell secrets', () => {
    const root = makeTempDir('studio-env-root-')
    const home = makeTempDir('studio-env-home-')

    mkdirSync(root, { recursive: true })
    writeFileSync(join(root, '.env'), 'OPENAI_API_KEY=openai-token\n', 'utf8')
    writeFileSync(
      join(home, '.bash_secrets'),
      'export ANTHROPIC_API_KEY="anthropic-key"\nexport UNSUPPORTED_API_KEY="ignored"\n',
      'utf8',
    )

    process.env.HOME = home
    loadRuntimeEnv(root)

    expect(process.env.OPENAI_API_KEY).toBe('openai-token')
    expect(process.env.ANTHROPIC_API_KEY).toBe('anthropic-key')
    expect(process.env.UNSUPPORTED_API_KEY).toBeUndefined()
  })

  test('does not override keys already loaded from .env', () => {
    const root = makeTempDir('studio-env-root-')
    const home = makeTempDir('studio-env-home-')

    writeFileSync(join(root, '.env'), 'ANTHROPIC_API_KEY=env-anthropic-key\n', 'utf8')
    writeFileSync(join(home, '.bash_secrets'), 'export ANTHROPIC_API_KEY="shell-anthropic-key"\n', 'utf8')

    process.env.HOME = home
    loadRuntimeEnv(root)

    expect(process.env.ANTHROPIC_API_KEY).toBe('env-anthropic-key')
  })
})
