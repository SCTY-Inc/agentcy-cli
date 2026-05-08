import { runCli } from './cli/index'

runCli()
  .then((exitCode) => {
    process.exitCode = exitCode
  })
  .catch((error) => {
    console.error(error instanceof Error ? error.message : String(error))
    process.exitCode = 1
  })

