/** Shared font registration — call once at startup, idempotent. */

import { registerFont } from 'canvas'
import { existsSync } from 'fs'
import { resolve, join, dirname } from 'path'
import { fileURLToPath } from 'url'

const fontsDir = resolve(dirname(fileURLToPath(import.meta.url)), '../../fonts')

let registered = false

export function ensureFontsRegistered(): void {
  if (registered) return
  registered = true

  for (const [file, family, weight, style] of [
    ['Alegreya-Regular.ttf', 'Alegreya', '400', undefined],
    ['Alegreya-Bold.ttf', 'Alegreya', '700', undefined],
    ['Alegreya-Italic.ttf', 'Alegreya', '400', 'italic'],
    ['Inter-Regular.ttf', 'Inter', '400', undefined],
    ['Inter-Bold.ttf', 'Inter', '700', undefined],
    ['JetBrainsMono-Regular.ttf', 'JetBrains Mono', '400', undefined],
    ['JetBrainsMono-Medium.ttf', 'JetBrains Mono', '500', undefined],
  ] as const) {
    const p = join(fontsDir, file)
    if (existsSync(p)) registerFont(p, { family, weight, style })
  }
}
