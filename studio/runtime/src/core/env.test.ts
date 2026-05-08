import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { loadRuntimeEnv } from './env'

const tempPaths: string[] = []
const managedKeys = [
  'GEMINI_API_KEY',
  'GOOGLE_API_KEY',
  'OPENAI_API_KEY',
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
  test('loads missing keys from bash secrets and aliases GOOGLE_API_KEY to GEMINI_API_KEY', () => {
    const root = makeTempDir('loom-env-root-')
    const home = makeTempDir('loom-env-home-')

    mkdirSync(root, { recursive: true })
    writeFileSync(join(root, '.env'), 'OPENAI_API_KEY=openai-token\n', 'utf8')
    writeFileSync(
      join(home, '.bash_secrets'),
      'export GOOGLE_API_KEY="google-key"\n',
      'utf8',
    )

    process.env.HOME = home
    loadRuntimeEnv(root)

    expect(process.env.OPENAI_API_KEY).toBe('openai-token')
    expect(process.env.GOOGLE_API_KEY).toBe('google-key')
    expect(process.env.GEMINI_API_KEY).toBe('google-key')
  })

  test('does not override GEMINI_API_KEY already loaded from .env', () => {
    const root = makeTempDir('loom-env-root-')
    const home = makeTempDir('loom-env-home-')

    writeFileSync(join(root, '.env'), 'GEMINI_API_KEY=env-gemini-key\n', 'utf8')
    writeFileSync(join(home, '.bash_secrets'), 'export GOOGLE_API_KEY="shell-google-key"\n', 'utf8')

    process.env.HOME = home
    loadRuntimeEnv(root)

    expect(process.env.GEMINI_API_KEY).toBe('env-gemini-key')
    expect(process.env.GOOGLE_API_KEY).toBe('shell-google-key')
  })
})
