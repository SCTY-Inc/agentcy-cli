import { createRuntime } from '../runtime/runtime'

export function runReviewCommand(args: string[], root?: string): unknown {
  const [subcommand, runId, ...rest] = args
  const runtime = createRuntime({ root })

  if (subcommand === 'list') {
    return runtime.listReviewRuns()
  }

  if (subcommand === 'show') {
    if (!runId) throw new Error('Usage: review show <run_id>')
    return runtime.inspectRun(runId)
  }

  if (subcommand === 'approve') {
    if (!runId) throw new Error('Usage: review approve <run_id>')
    const noteIndex = rest.findIndex((arg) => arg === '--note')
    const variantIndex = rest.findIndex((arg) => arg === '--variant')
    return runtime.reviewRun(runId, {
      decision: 'approve',
      note: noteIndex > -1 ? rest[noteIndex + 1] : undefined,
      selectedVariantId: variantIndex > -1 ? rest[variantIndex + 1] : undefined,
    })
  }

  if (subcommand === 'reject') {
    if (!runId) throw new Error('Usage: review reject <run_id>')
    const noteIndex = rest.findIndex((arg) => arg === '--reason')
    return runtime.reviewRun(runId, {
      decision: 'reject',
      note: noteIndex > -1 ? rest[noteIndex + 1] : undefined,
    })
  }

  throw new Error('Usage: review <list|show|approve|reject> ...')
}

