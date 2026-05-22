#!/usr/bin/env node
import { spawnSync } from 'node:child_process'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const tsxLoader = join(here, '..', 'node_modules', 'tsx', 'dist', 'loader.mjs')
const cli = join(here, '..', 'src', 'cli.ts')
const result = spawnSync(process.execPath, ['--import', tsxLoader, cli, ...process.argv.slice(2)], {
  stdio: 'inherit',
})

if (result.error) {
  throw result.error
}

process.exitCode = result.status ?? 1
