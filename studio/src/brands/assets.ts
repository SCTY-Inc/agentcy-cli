import { existsSync, readFileSync } from 'fs'
import { join } from 'path'
import type { BrandFoundation } from '../domain/types'

function mimeType(path: string): string {
  const lower = path.toLowerCase()
  if (lower.endsWith('.svg')) return 'image/svg+xml'
  if (lower.endsWith('.png')) return 'image/png'
  if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'image/jpeg'
  if (lower.endsWith('.webp')) return 'image/webp'
  return 'application/octet-stream'
}

export function brandAssetPath(
  brand: BrandFoundation,
  brandsDir: string,
  assetPath: string,
): string {
  return join(brandsDir, brand.id, assetPath)
}

export function brandLogoDataUri(
  brand: BrandFoundation,
  brandsDir: string,
): string | undefined {
  const logo = brand.visual.logo
  if (!logo) return undefined

  const filePath = brandAssetPath(brand, brandsDir, logo)
  if (!existsSync(filePath)) return undefined

  return `data:${mimeType(filePath)};base64,${readFileSync(filePath).toString('base64')}`
}
