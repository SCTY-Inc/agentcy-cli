import { existsSync, readFileSync } from 'fs'
import { extname } from 'path'

const ALLOWED_PROTOCOLS = new Set(['http:', 'https:'])
const ALLOWED_IMAGE_TYPES = new Set(['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp'])

function isPrivateIp(hostname: string): boolean {
  const ipv4 = hostname.match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)$/)
  if (ipv4) {
    const [, a, b] = ipv4.map(Number)
    if (a === 10) return true
    if (a === 172 && b >= 16 && b <= 31) return true
    if (a === 192 && b === 168) return true
    if (a === 169 && b === 254) return true
    if (a === 127) return true
    if (a === 0) return true
  }

  const lower = hostname.toLowerCase()
  return lower === '::1' || lower === '[::1]' || lower.startsWith('fc') || lower.startsWith('fd') || lower.startsWith('fe80')
}

export function validateUrl(input: string): URL {
  let url: URL
  try {
    url = new URL(input)
  } catch {
    throw new Error(`Invalid URL: ${input}`)
  }

  if (!ALLOWED_PROTOCOLS.has(url.protocol)) {
    throw new Error(`Invalid protocol: ${url.protocol}`)
  }

  const hostname = url.hostname.toLowerCase()
  if (hostname === 'localhost' || hostname.endsWith('.local') || hostname.endsWith('.internal') || isPrivateIp(hostname)) {
    throw new Error(`Blocked internal URL: ${hostname}`)
  }

  return url
}

export function getMimeType(filePath: string): string {
  const mimeByExt: Record<string, string> = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
  }

  return mimeByExt[extname(filePath).toLowerCase()] ?? 'application/octet-stream'
}

export async function downloadImage(input: string): Promise<{ data: Buffer; mimeType: string }> {
  if (input.startsWith('/') || input.startsWith('./') || input.startsWith('../')) {
    if (!existsSync(input)) {
      throw new Error(`File not found: ${input}`)
    }

    const data = readFileSync(input)
    const mimeType = getMimeType(input)
    if (!ALLOWED_IMAGE_TYPES.has(mimeType)) {
      throw new Error(`Invalid image type: ${mimeType}`)
    }
    return { data, mimeType }
  }

  validateUrl(input)
  const response = await fetch(input)
  if (!response.ok) {
    throw new Error(`Failed to download image: ${response.status} ${response.statusText}`)
  }

  const mimeType = (response.headers.get('content-type') ?? '').split(';')[0].trim().toLowerCase()
  if (!ALLOWED_IMAGE_TYPES.has(mimeType)) {
    throw new Error(`Invalid image type: ${mimeType}`)
  }

  return {
    data: Buffer.from(await response.arrayBuffer()),
    mimeType,
  }
}
