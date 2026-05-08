import { execFileSync } from 'child_process'
import { downloadImage } from '../core/http'
import type { AdapterPostResult } from './base'
import { writeFileSync, unlinkSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'

function brandToApp(brand: string): string {
  return brand.toLowerCase()
}

async function uploadMedia(imagePath: string, app: string): Promise<string> {
  const { data, mimeType } = await downloadImage(imagePath)
  const ext = mimeType.includes('png') ? 'png' : 'jpg'
  const tmp = join(tmpdir(), `xurl-upload-${Date.now()}.${ext}`)
  writeFileSync(tmp, new Uint8Array(data))
  try {
    const out = execFileSync('xurl', ['--app', app, 'media', 'upload', tmp], {
      encoding: 'utf-8',
      timeout: 60_000,
    })
    const match = out.match(/"media_id_string"\s*:\s*"(\d+)"/) ?? out.match(/media_id_string=(\d+)/) ?? out.match(/"media_id"\s*:\s*(\d+)/)
    if (!match) throw new Error(`Could not parse media ID from xurl output: ${out}`)
    return match[1]
  } finally {
    try { unlinkSync(tmp) } catch {}
  }
}

async function createTweet(text: string, mediaIds: string[], app: string): Promise<string> {
  const body: Record<string, unknown> = { text }
  if (mediaIds.length > 0) {
    body.media = { media_ids: mediaIds }
  }

  const out = execFileSync('xurl', [
    '--app', app,
    '--auth', 'oauth1',
    '-X', 'POST',
    '-d', JSON.stringify(body),
    '/2/tweets',
  ], { encoding: 'utf-8', timeout: 30_000 })

  const parsed = JSON.parse(out) as { data?: { id?: string }; errors?: Array<{ detail?: string }> }
  if (parsed.errors?.[0]) {
    throw new Error(parsed.errors[0].detail ?? 'Unknown Twitter API error')
  }
  if (!parsed.data?.id) {
    throw new Error(`Unexpected response: ${out}`)
  }
  return parsed.data.id
}

export async function postToTwitter(brand: string, text: string, imagePath?: string): Promise<AdapterPostResult> {
  try {
    const app = brandToApp(brand)
    const mediaIds = imagePath ? [await uploadMedia(imagePath, app)] : []
    const id = await createTweet(text, mediaIds, app)

    return {
      success: true,
      postId: id,
      postUrl: `https://x.com/i/status/${id}`,
    }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : String(error),
    }
  }
}
