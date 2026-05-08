/**
 * Source image generation via Gemini. Returns null when no API key is set.
 */

import { writeFileSync } from 'fs'
import { join } from 'path'
import type { BrandFoundation } from '../domain/types'
import { ensureParentDir, type RuntimePaths } from '../core/paths'
import { generateImage } from '../render/gemini'

interface SourceImageOptions {
  brand: BrandFoundation
  paths: RuntimePaths
  runId: string
  topic: string
}

function buildPrompt(brand: BrandFoundation, topic: string): string {
  if (brand.visual.imagePrompt) {
    return brand.visual.imagePrompt.replace(/\[SUBJECT\]/gi, topic)
  }
  return [
    `A warm, abstract visual about ${topic}.`,
    `Color palette: ${brand.visual.palette.background}, ${brand.visual.palette.primary}, ${brand.visual.palette.accent}.`,
    'No text, no logos, no watermarks.',
  ].join(' ')
}

export async function generateSourceImage(options: SourceImageOptions): Promise<{ imagePath: string; provider: string } | null> {
  const prompt = buildPrompt(options.brand, options.topic)
  const outputPath = join(options.paths.artifactsDir, options.runId, 'source-image.png')

  const imageBytes = await generateImage(prompt)
  if (!imageBytes) return null

  ensureParentDir(outputPath)
  writeFileSync(outputPath, imageBytes)

  return { imagePath: outputPath, provider: 'gemini-3.1-flash-image-preview' }
}
