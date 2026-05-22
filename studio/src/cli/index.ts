function print(data: unknown, json: boolean): void {
  if (json) {
    process.stdout.write(`${JSON.stringify(data, null, 2)}\n`)
    return
  }

  if (typeof data === 'string') {
    process.stdout.write(`${data}\n`)
    return
  }

  process.stdout.write(`${JSON.stringify(data, null, 2)}\n`)
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function helpText(): string {
  return [
    'agentcy-studio CLI',
    '',
    'Usage:',
    '  agentcy-studio <command> [options]',
    '  agentcy studio <command> [options]',
    '',
    'Commands:',
    '  auto --brand <id> [--workflow social.post] [--topic "..."] [--dry-run]',
    '  brand <init|show|validate> ...',
    '  run <workflow> --brand <id> [--pillar <id>] [--format <id>] [--brief-file <path>] ...',
    '  review <list|show|approve|reject> ...',
    '  publish <run_id> [--platforms twitter,linkedin] [--dry-run]',
    '  inspect <run|artifact> ...',
    '  retry <run_id> [--from <step>]',
    '  lab <card|cover|render> ...',
    '  ops <health|auth check --brand <id>|auth refresh|migrate>',
    '',
    'Workflows:',
    '  social.post',
    '  blog.post',
    '  outreach.touch',
    '  respond.reply',
    '',
    'Examples:',
    '  agentcy-studio auto --brand givecare',
    '  agentcy-studio auto --brand scty --topic "AI adoption gap" --dry-run',
    '  agentcy-studio ops auth check --brand givecare',
    '  agentcy-studio run social.post --brand givecare --topic "caregiver benefits gap" --style givecare-site-card',
    '  agentcy-studio run social.post --brand givecare --pillar care-economy --topic "$470B unpaid care labor"',
    '  agentcy-studio run social.post --brand givecare --format infographic --topic "caregiver workforce"',
    '  agentcy-studio run blog.post --brand givecare --pillar policy --topic "paid leave"',
    '  agentcy-studio run social.post --brand givecare --brief-file ../protocols/examples/brief.v1.rich.json',
    '  agentcy-studio lab card --brand givecare --type quote --headline "Care is infrastructure"',
    '  agentcy-studio lab cover --brand givecare --title "Care is infrastructure" --subtitle "Make invisible work visible." --json',
    '  agentcy-studio lab render --brand givecare --style givecare-site-card --platform linkedin --headline "Care is infrastructure" --body "63M provide unpaid care."',
    '  agentcy-studio publish run_123 --platforms twitter,linkedin --dry-run',
  ].join('\n')
}

export async function runCli(argv: string[] = process.argv.slice(2)): Promise<number> {
  const json = argv.includes('--json')
  const filtered = argv.filter((arg) => arg !== '--json')
  const [command, ...args] = filtered

  try {
    if (!command || command === 'help' || command === '--help' || command === '-h') {
      if (json) {
        print({ status: 'ok', command: 'help', data: { help: helpText() } }, true)
      } else {
        print(helpText(), false)
      }
      return 0
    }

    let data: unknown
    switch (command) {
      case 'auto': {
        const { runAutoCommand } = await import('../commands/auto')
        data = await runAutoCommand(args)
        break
      }
      case 'brand': {
        const { runBrandCommand } = await import('../commands/brand')
        data = await runBrandCommand(args)
        break
      }
      case 'run': {
        const { runWorkflowCommand } = await import('../commands/run')
        data = await runWorkflowCommand(args)
        break
      }
      case 'review': {
        const { runReviewCommand } = await import('../commands/review')
        data = await runReviewCommand(args)
        break
      }
      case 'publish': {
        const { runPublishCommand } = await import('../commands/publish')
        data = await runPublishCommand(args)
        break
      }
      case 'inspect': {
        const { runInspectCommand } = await import('../commands/inspect')
        data = await runInspectCommand(args)
        break
      }
      case 'retry': {
        const { runRetryCommand } = await import('../commands/retry')
        data = await runRetryCommand(args)
        break
      }
      case 'ops': {
        const { runOpsCommand } = await import('../commands/ops')
        data = await runOpsCommand(args)
        break
      }
      case 'lab': {
        const { runLabCommand } = await import('../commands/lab')
        data = await runLabCommand(args)
        break
      }
      default:
        throw new Error(`Unknown command: ${command}`)
    }

    if (json) {
      print({ status: 'ok', command, data }, true)
    } else {
      print(data, false)
    }
    return 0
  } catch (error) {
    if (json) {
      print({ status: 'error', error: { message: errorMessage(error) } }, true)
    } else {
      process.stderr.write(`${errorMessage(error)}\n`)
    }
    return 1
  }
}
