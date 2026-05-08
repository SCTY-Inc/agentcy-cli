import { isWorkflowName } from '../domain/types'
import { loadBriefV1 } from '../domain/brief-v1'
import { createRuntime } from '../runtime/runtime'

function parseWorkflowInput(args: string[]): Record<string, unknown> {
  const input: Record<string, unknown> = {}
  let i = 0

  while (i < args.length) {
    const arg = args[i]
    if (arg.startsWith('--')) {
      const key = arg.slice(2)
      const next = args[i + 1]
      if (next && !next.startsWith('--')) {
        input[key] = next
        i += 2
      } else {
        input[key] = true
        i += 1
      }
      continue
    }

    i += 1
  }

  return input
}

export async function runWorkflowCommand(args: string[], root?: string): Promise<unknown> {
  const [workflow, ...rest] = args
  if (!workflow) {
    throw new Error('Usage: run <workflow> --brand <id> [--pillar <id>] [--topic "..."] [--brief-file path/to/brief.v1.json]')
  }

  if (!isWorkflowName(workflow)) {
    throw new Error(`Invalid workflow: ${workflow}. Expected one of: social.post, blog.post, outreach.touch, respond.reply`)
  }

  const input = parseWorkflowInput(rest)
  const brand = typeof input.brand === 'string' ? input.brand : undefined
  if (!brand) {
    throw new Error('Usage: run <workflow> --brand <id> [--pillar <id>] [--topic "..."] [--brief-file path/to/brief.v1.json]')
  }

  if (typeof input['brief-file'] === 'string') {
    input.importedBrief = {
      path: input['brief-file'],
      payload: loadBriefV1(input['brief-file']),
    }
  }

  const autoApprove = input['auto-approve'] === true
  delete input.brand
  delete input['auto-approve']
  delete input['brief-file']
  const runtime = createRuntime({ root })
  return await runtime.runWorkflow({
    workflow,
    brand,
    input,
    autoApprove,
  })
}

