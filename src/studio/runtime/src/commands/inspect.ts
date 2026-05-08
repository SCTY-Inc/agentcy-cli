import { existsSync, readFileSync, realpathSync } from 'fs'
import { resolve } from 'path'
import { createRuntime } from '../runtime/runtime'
import { resolveRuntimePaths } from '../core/paths'

export function runInspectCommand(args: string[], root?: string): unknown {
  const [subcommand, id] = args
  const runtime = createRuntime({ root })

  if (subcommand === 'run') {
    if (!id) throw new Error('Usage: inspect run <run_id>')
    return runtime.inspectRun(id)
  }

  if (subcommand === 'artifact') {
    if (!id) throw new Error('Usage: inspect artifact <artifact_path>')

    const paths = resolveRuntimePaths(root)
    const artifactsDir = resolve(paths.artifactsDir)
    const artifactPath = resolve(id)
    if (!existsSync(artifactPath)) {
      throw new Error(`Artifact not found: ${id}`)
    }

    const resolvedPath = realpathSync(artifactPath)
    if (!resolvedPath.startsWith(`${artifactsDir}/`)) {
      throw new Error(`Artifact path must be inside ${paths.artifactsDir}`)
    }

    return JSON.parse(readFileSync(resolvedPath, 'utf8')) as Record<string, unknown>
  }

  throw new Error('Usage: inspect <run|artifact> ...')
}

