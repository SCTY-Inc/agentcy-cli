import { readFileSync } from 'fs'
import { dirname, join } from 'path'
import { fileURLToPath } from 'url'

const FONTS_DIR = join(dirname(fileURLToPath(import.meta.url)), '../../fonts')

export type FontEntry = {
  name: string
  data: ArrayBuffer
  weight: 100|200|300|400|500|600|700|800|900
  style: 'normal'|'italic'
}

let fonts: FontEntry[] | null = null

function loadFont(file: string): ArrayBuffer {
  const buf = readFileSync(join(FONTS_DIR, file))
  return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer
}

export function getFonts(): FontEntry[] {
  if (fonts) return fonts
  fonts = [
    { name: 'Alegreya',       data: loadFont('Alegreya-Regular.ttf'),      weight: 400, style: 'normal' },
    { name: 'Alegreya',       data: loadFont('Alegreya-Bold.ttf'),         weight: 700, style: 'normal' },
    { name: 'JetBrains Mono', data: loadFont('JetBrainsMono-Regular.ttf'), weight: 400, style: 'normal' },
    { name: 'JetBrains Mono', data: loadFont('JetBrainsMono-Medium.ttf'),  weight: 500, style: 'normal' },
    { name: 'Inter',          data: loadFont('Inter-Regular.ttf'),         weight: 400, style: 'normal' },
    { name: 'Inter',          data: loadFont('Inter-Bold.ttf'),            weight: 700, style: 'normal' },
  ]
  return fonts
}
