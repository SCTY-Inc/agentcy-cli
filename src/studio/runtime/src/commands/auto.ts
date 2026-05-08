import { isWorkflowName, isSocialPlatform, type SocialPlatform } from '../domain/types'
import { createRuntime } from '../runtime/runtime'

function parseAutoArgs(args: string[]): {
  workflow: string
  brand?: string
  topic?: string
  pillar?: string
  dryRun: boolean
  platforms?: SocialPlatform[]
  input: Record<string, unknown>
} {
  let workflow = 'social.post'
  let brand: string | undefined
  let topic: string | undefined
  let pillar: string | undefined
  let dryRun = false
  let platforms: SocialPlatform[] | undefined
  const input: Record<string, unknown> = {}

  for (let i = 0; i < args.length; i++) {
    const arg = args[i]
    const next = args[i + 1]
    if (arg === '--workflow' && next) { workflow = next; i++ }
    else if (arg === '--brand' && next) { brand = next; i++ }
    else if (arg === '--topic' && next) { topic = next; i++ }
    else if (arg === '--pillar' && next) { pillar = next; i++ }
    else if (arg === '--dry-run') { dryRun = true }
    else if (arg === '--platforms' && next) {
      const requested = next.split(',').map(s => s.trim()).filter(Boolean)
      const invalid = requested.filter(p => !isSocialPlatform(p))
      if (invalid.length > 0) throw new Error(`Invalid platform(s): ${invalid.join(', ')}`)
      platforms = requested as SocialPlatform[]
      i++
    } else if (arg.startsWith('--') && next && !next.startsWith('--')) {
      input[arg.slice(2)] = next
      i++
    } else if (arg.startsWith('--')) {
      input[arg.slice(2)] = true
    }
  }

  if (topic) input.topic = topic
  if (pillar) input.pillar = pillar
  return { workflow, brand, topic, pillar, dryRun, platforms, input }
}

export async function runAutoCommand(args: string[], root?: string): Promise<unknown> {
  const parsed = parseAutoArgs(args)

  if (!parsed.brand) {
    throw new Error('Usage: auto --brand <id> [--workflow social.post] [--topic "..."] [--pillar <id>] [--platforms twitter,linkedin] [--dry-run]')
  }
  if (!isWorkflowName(parsed.workflow)) {
    throw new Error(`Invalid workflow: ${parsed.workflow}`)
  }

  const runtime = createRuntime({ root })

  const run = await runtime.runWorkflow({
    workflow: parsed.workflow,
    brand: parsed.brand,
    input: parsed.input,
    autoApprove: true,
  })

  if (run.status === 'failed') {
    return { run, published: false, error: run.errorMessage }
  }

  const published = await runtime.publishRun(run.id, {
    dryRun: parsed.dryRun,
    platforms: parsed.platforms,
  })

  return {
    run: published,
    runResult: runtime.buildRunResult(published.id),
  }
}
