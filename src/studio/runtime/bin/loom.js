#!/usr/bin/env node

import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const binDir = path.dirname(fileURLToPath(import.meta.url))
const cliPath = path.resolve(binDir, '../src/cli.ts')

const result = spawnSync(
  process.execPath,
  ['--import', 'tsx', cliPath, ...process.argv.slice(2)],
  {
    cwd: path.resolve(binDir, '..'),
    stdio: 'inherit',
  },
)

if (result.error) {
  console.error(result.error instanceof Error ? result.error.message : String(result.error))
  process.exit(1)
}

process.exit(result.status ?? 1)
