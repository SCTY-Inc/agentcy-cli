import crypto from 'crypto'
import { downloadImage } from '../core/http'
import type { AdapterPostResult } from './base'

interface TwitterCredentials {
  apiKey: string
  apiSecret: string
  accessToken: string
  accessSecret: string
}

function getCredentials(brand: string): TwitterCredentials {
  const brandUpper = brand.toUpperCase()
  const apiKey = process.env[`TWITTER_${brandUpper}_API_KEY`] ?? process.env.TWITTER_API_KEY
  const apiSecret = process.env[`TWITTER_${brandUpper}_API_SECRET`] ?? process.env.TWITTER_API_SECRET
  const accessToken = process.env[`TWITTER_${brandUpper}_ACCESS_TOKEN`]
  const accessSecret = process.env[`TWITTER_${brandUpper}_ACCESS_SECRET`]

  if (!apiKey || !apiSecret) {
    throw new Error(`TWITTER_${brandUpper}_API_KEY/API_SECRET or shared TWITTER_API_KEY/TWITTER_API_SECRET required`)
  }
  if (!accessToken || !accessSecret) {
    throw new Error(`TWITTER_${brandUpper}_ACCESS_TOKEN and TWITTER_${brandUpper}_ACCESS_SECRET required`)
  }

  return { apiKey, apiSecret, accessToken, accessSecret }
}

function generateOAuthSignature(
  method: string,
  url: string,
  params: Record<string, string>,
  credentials: TwitterCredentials,
): string {
  const normalized = Object.keys(params)
    .sort()
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(params[key] ?? '')}`)
    .join('&')

  const base = [method.toUpperCase(), encodeURIComponent(url), encodeURIComponent(normalized)].join('&')
  const signingKey = `${encodeURIComponent(credentials.apiSecret)}&${encodeURIComponent(credentials.accessSecret)}`
  return crypto.createHmac('sha1', signingKey).update(base).digest('base64')
}

function generateOAuthHeader(
  method: string,
  url: string,
  credentials: TwitterCredentials,
  extraParams: Record<string, string> = {},
): string {
  const params: Record<string, string> = {
    oauth_consumer_key: credentials.apiKey,
    oauth_nonce: crypto.randomBytes(16).toString('hex'),
    oauth_signature_method: 'HMAC-SHA1',
    oauth_timestamp: Math.floor(Date.now() / 1000).toString(),
    oauth_token: credentials.accessToken,
    oauth_version: '1.0',
    ...extraParams,
  }
  params.oauth_signature = generateOAuthSignature(method, url, params, credentials)

  return `OAuth ${Object.keys(params)
    .sort()
    .map((key) => `${encodeURIComponent(key)}="${encodeURIComponent(params[key] ?? '')}"`)
    .join(', ')}`
}

async function uploadMedia(imagePath: string, credentials: TwitterCredentials): Promise<string> {
  const { data, mimeType } = await downloadImage(imagePath)
  const url = 'https://upload.twitter.com/1.1/media/upload.json'
  const form = new FormData()
  const extension = mimeType.includes('png') ? 'png' : 'jpg'
  form.append('media', new Blob([new Uint8Array(data)], { type: mimeType }), `image.${extension}`)

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: generateOAuthHeader('POST', url, credentials),
    },
    body: form,
  })

  if (!response.ok) {
    throw new Error(`Twitter media upload failed: ${response.status} ${await response.text()}`)
  }

  const payload = await response.json() as { media_id_string: string }
  return payload.media_id_string
}

async function createTweet(text: string, mediaIds: string[], credentials: TwitterCredentials): Promise<string> {
  const url = 'https://api.twitter.com/2/tweets'
  const body: Record<string, unknown> = { text }
  if (mediaIds.length > 0) {
    body.media = { media_ids: mediaIds }
  }

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: generateOAuthHeader('POST', url, credentials),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    throw new Error(`Twitter tweet creation failed: ${response.status} ${await response.text()}`)
  }

  const payload = await response.json() as { data: { id: string } }
  return payload.data.id
}

export async function postToTwitter(brand: string, text: string, imagePath?: string): Promise<AdapterPostResult> {
  try {
    const credentials = getCredentials(brand)
    const mediaIds = imagePath ? [await uploadMedia(imagePath, credentials)] : []
    const id = await createTweet(text, mediaIds, credentials)

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
