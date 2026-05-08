/**
 * Explore grid — 3x3 mood board of visual directions via Gemini.
 */

import { writeFileSync } from 'fs'
import { join } from 'path'
import type { BrandFoundation } from '../domain/types'
import { ensureParentDir, type RuntimePaths } from '../core/paths'
import { generateImage } from '../render/gemini'

interface ExploreGridOptions {
  brand: BrandFoundation
  paths: RuntimePaths
  runId: string
  topic: string
}

interface ExploreGridResult {
  gridImagePath: string
  prompt: string
  provider: string
}

function buildPrompt(brand: BrandFoundation, topic: string): string {
  if (brand.visual.imagePrompt) {
    const basePrompt = brand.visual.imagePrompt.replace(/\[SUBJECT\]/gi, topic)
    return [
      'Generate a 3x3 mood board grid (3:4 aspect ratio) with nine panels separated by clean visible grid lines.',
      'Each panel should be a distinct variation using this visual system:',
      '',
      basePrompt,
      '',
      `Each panel explores a different angle on "${topic}" within this system.`,
      'Vary composition, density, and specific visual elements across panels while maintaining the same grammar.',
    ].join('\n')
  }

  const lines: string[] = []
  lines.push(`A 3x3 mood board grid (3:4 aspect ratio) exploring visual directions for "${topic}" by ${brand.name}.`)
  lines.push('Nine panels separated by clean visible grid lines. Each panel is a distinct composition.')
  if (brand.visual.style) lines.push('', brand.visual.style)
  if (brand.visual.texture) lines.push(`Texture: ${brand.visual.texture}`)
  lines.push(`Palette: ${brand.visual.palette.background}, ${brand.visual.palette.primary}, ${brand.visual.palette.accent}.`)
  if (brand.visual.negative) lines.push(`Avoid: ${brand.visual.negative}`)
  return lines.join('\n')
}

export async function generateExploreGrid(options: ExploreGridOptions): Promise<ExploreGridResult> {
  const prompt = buildPrompt(options.brand, options.topic)
  const outputPath = join(options.paths.artifactsDir, options.runId, 'explore-grid.png')

  const imageBytes = await generateImage(prompt)
  if (!imageBytes) throw new Error('Gemini returned no image for explore grid')

  ensureParentDir(outputPath)
  writeFileSync(outputPath, imageBytes)

  return { gridImagePath: outputPath, prompt, provider: 'gemini-3.1-flash-image-preview' }
}
