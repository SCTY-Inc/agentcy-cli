import { downloadImage } from '../core/http'
import { createCredentialGetter, type AdapterPostResult } from './base'

interface FacebookCredentials {
  pageAccessToken: string
  pageId: string
}

const getCredentials = createCredentialGetter<FacebookCredentials>('FACEBOOK', [
  { suffix: 'PAGE_ACCESS_TOKEN', field: 'pageAccessToken' },
  { suffix: 'PAGE_ID', field: 'pageId' },
])

async function createTextPost(text: string, credentials: FacebookCredentials): Promise<string> {
  const response = await fetch(`https://graph.facebook.com/v21.0/${credentials.pageId}/feed`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message: text,
      access_token: credentials.pageAccessToken,
    }),
  })

  if (!response.ok) {
    throw new Error(`Facebook text post failed: ${response.status} ${await response.text()}`)
  }

  const payload = await response.json() as { id: string }
  return payload.id
}

async function uploadAndPublishPhoto(imagePath: string, text: string, credentials: FacebookCredentials): Promise<string> {
  const { data, mimeType } = await downloadImage(imagePath)
  const form = new FormData()
  const extension = mimeType.includes('png') ? 'png' : 'jpg'
  form.append('source', new Blob([new Uint8Array(data)], { type: mimeType }), `image.${extension}`)
  form.append('message', text)
  form.append('published', 'true')
  form.append('access_token', credentials.pageAccessToken)

  const response = await fetch(`https://graph.facebook.com/v21.0/${credentials.pageId}/photos`, {
    method: 'POST',
    body: form,
  })

  if (!response.ok) {
    throw new Error(`Facebook photo upload failed: ${response.status} ${await response.text()}`)
  }

  const payload = await response.json() as { id: string; post_id?: string }
  return payload.post_id ?? payload.id
}

export async function postToFacebook(brand: string, text: string, imagePath?: string): Promise<AdapterPostResult> {
  try {
    const credentials = getCredentials(brand)
    const id = imagePath
      ? await uploadAndPublishPhoto(imagePath, text, credentials)
      : await createTextPost(text, credentials)

    return {
      success: true,
      postId: id,
      postUrl: `https://www.facebook.com/${id}`,
    }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : String(error),
    }
  }
}
