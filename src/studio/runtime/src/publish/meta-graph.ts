import { loadBrandFoundation } from '../brands/load'
import { uploadToR2 } from '../core/r2'
import type { AdapterPostResult } from './base'
import { createCredentialGetter } from './base'

type MetaPlatform = 'instagram' | 'threads'

interface MetaCredentials {
  accessToken: string
  userId: string
}

interface PlatformConfig {
  baseUrl: string
  apiVersion: string
  containerEndpoint: string
  publishEndpoint: string
  statusField: string
}

const CONFIG: Record<MetaPlatform, PlatformConfig> = {
  instagram: {
    baseUrl: 'https://graph.instagram.com',
    apiVersion: 'v21.0',
    containerEndpoint: 'media',
    publishEndpoint: 'media_publish',
    statusField: 'status_code',
  },
  threads: {
    baseUrl: 'https://graph.threads.net',
    apiVersion: 'v1.0',
    containerEndpoint: 'threads',
    publishEndpoint: 'threads_publish',
    statusField: 'status',
  },
}

const getInstagramCredentials = createCredentialGetter<MetaCredentials>('INSTAGRAM', [
  { suffix: 'ACCESS_TOKEN', field: 'accessToken' },
  { suffix: 'USER_ID', field: 'userId' },
])

const getThreadsCredentials = createCredentialGetter<MetaCredentials>('THREADS', [
  { suffix: 'ACCESS_TOKEN', field: 'accessToken' },
  { suffix: 'USER_ID', field: 'userId' },
])

function getCredentials(platform: MetaPlatform, brand: string): MetaCredentials {
  return platform === 'instagram' ? getInstagramCredentials(brand) : getThreadsCredentials(brand)
}

function buildUrl(platform: MetaPlatform, path: string, params?: URLSearchParams): string {
  const config = CONFIG[platform]
  return `${config.baseUrl}/${config.apiVersion}/${path}${params ? `?${params.toString()}` : ''}`
}

async function createContainer(platform: MetaPlatform, credentials: MetaCredentials, text: string, imageUrl?: string): Promise<string> {
  const params = new URLSearchParams({ access_token: credentials.accessToken })

  if (platform === 'instagram') {
    if (!imageUrl) {
      throw new Error('Instagram requires an image')
    }
    params.set('image_url', imageUrl)
    params.set('caption', text)
  } else {
    params.set('text', text)
    if (imageUrl) {
      params.set('media_type', 'IMAGE')
      params.set('image_url', imageUrl)
    } else {
      params.set('media_type', 'TEXT')
    }
  }

  const response = await fetch(buildUrl(platform, `${credentials.userId}/${CONFIG[platform].containerEndpoint}`), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: params,
  })

  if (!response.ok) {
    throw new Error(`${platform} container creation failed: ${response.status} ${await response.text()}`)
  }

  const payload = await response.json() as { id: string }
  return payload.id
}

async function waitForContainer(platform: MetaPlatform, containerId: string, accessToken: string): Promise<void> {
  const config = CONFIG[platform]
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const response = await fetch(buildUrl(platform, containerId, new URLSearchParams({
      fields: config.statusField,
      access_token: accessToken,
    })))

    if (!response.ok) {
      throw new Error(`${platform} status check failed: ${response.status}`)
    }

    const payload = await response.json() as Record<string, string>
    const status = payload[config.statusField]
    if (status === 'FINISHED') {
      return
    }
    if (status === 'ERROR') {
      throw new Error(`${platform} container processing failed`)
    }

    await new Promise((resolve) => setTimeout(resolve, 500))
  }

  throw new Error(`${platform} container processing timed out`)
}

async function publishContainer(platform: MetaPlatform, credentials: MetaCredentials, containerId: string): Promise<string> {
  const response = await fetch(buildUrl(platform, `${credentials.userId}/${CONFIG[platform].publishEndpoint}`), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({
      creation_id: containerId,
      access_token: credentials.accessToken,
    }),
  })

  if (!response.ok) {
    throw new Error(`${platform} publish failed: ${response.status} ${await response.text()}`)
  }

  const payload = await response.json() as { id: string }
  return payload.id
}

async function getInstagramPermalink(mediaId: string, accessToken: string): Promise<string> {
  const response = await fetch(`https://graph.instagram.com/v21.0/${mediaId}?${new URLSearchParams({
    fields: 'permalink',
    access_token: accessToken,
  }).toString()}`)

  if (!response.ok) {
    return `https://www.instagram.com/p/${mediaId}/`
  }

  const payload = await response.json() as { permalink?: string }
  return payload.permalink ?? `https://www.instagram.com/p/${mediaId}/`
}

function getThreadsUrl(brand: string, postId: string, root?: string): string {
  const handle = loadBrandFoundation(brand, { root }).handles?.threads?.replace('@', '') ?? brand
  return `https://www.threads.net/@${handle}/post/${postId}`
}

async function resolvePublicImageUrl(imagePath: string): Promise<string> {
  if (imagePath.startsWith('http')) {
    return imagePath
  }

  return uploadToR2(imagePath)
}

export async function postToInstagram(brand: string, text: string, imagePath: string): Promise<AdapterPostResult> {
  try {
    const credentials = getCredentials('instagram', brand)
    const imageUrl = await resolvePublicImageUrl(imagePath)
    const containerId = await createContainer('instagram', credentials, text, imageUrl)
    await waitForContainer('instagram', containerId, credentials.accessToken)
    const id = await publishContainer('instagram', credentials, containerId)

    return {
      success: true,
      postId: id,
      postUrl: await getInstagramPermalink(id, credentials.accessToken),
    }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : String(error),
    }
  }
}

export async function postToThreads(brand: string, text: string, imagePath?: string, root?: string): Promise<AdapterPostResult> {
  try {
    const credentials = getCredentials('threads', brand)
    const imageUrl = imagePath ? await resolvePublicImageUrl(imagePath) : undefined
    const containerId = await createContainer('threads', credentials, text, imageUrl)
    await waitForContainer('threads', containerId, credentials.accessToken)
    const id = await publishContainer('threads', credentials, containerId)

    return {
      success: true,
      postId: id,
      postUrl: getThreadsUrl(brand, id, root),
    }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : String(error),
    }
  }
}
