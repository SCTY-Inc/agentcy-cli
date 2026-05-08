import { isStepName } from '../domain/types'
import { createRuntime } from '../runtime/runtime'

export async function runRetryCommand(args: string[], root?: string): Promise<unknown> {
  const [runId, ...rest] = args
  if (!runId) {
    throw new Error('Usage: retry <run_id> [--from <step>]')
  }

  const fromIndex = rest.findIndex((arg) => arg === '--from')
  const fromStep = fromIndex > -1 ? rest[fromIndex + 1] : 'draft'
  if (!isStepName(fromStep)) {
    throw new Error(`Invalid step: ${fromStep}. Expected one of: signal, brief, draft, explore, image, render, outline, publish, review`)
  }

  const runtime = createRuntime({ root })
  return await runtime.retryRun(runId, { fromStep })
}

