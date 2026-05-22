import { downloadImage } from '../core/http'
import { createCredentialGetter, type AdapterPostResult } from './base'

interface LinkedInCredentials {
  accessToken: string
  orgId: string
}

const getCredentials = createCredentialGetter<LinkedInCredentials>('LINKEDIN', [
  { suffix: 'ACCESS_TOKEN', field: 'accessToken' },
  { suffix: 'ORG_ID', field: 'orgId' },
])

async function uploadImage(imagePath: string, credentials: LinkedInCredentials): Promise<string> {
  const registerResponse = await fetch('https://api.linkedin.com/v2/assets?action=registerUpload', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${credentials.accessToken}`,
      'Content-Type': 'application/json',
      'X-Restli-Protocol-Version': '2.0.0',
    },
    body: JSON.stringify({
      registerUploadRequest: {
        recipes: ['urn:li:digitalmediaRecipe:feedshare-image'],
        owner: `urn:li:organization:${credentials.orgId}`,
        serviceRelationships: [
          {
            relationshipType: 'OWNER',
            identifier: 'urn:li:userGeneratedContent',
          },
        ],
      },
    }),
  })

  if (!registerResponse.ok) {
    throw new Error(`LinkedIn image register failed: ${registerResponse.status} ${await registerResponse.text()}`)
  }

  const registerData = await registerResponse.json() as {
    value: {
      asset: string
      uploadMechanism: {
        'com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest': {
          uploadUrl: string
        }
      }
    }
  }

  const uploadUrl = registerData.value.uploadMechanism['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest'].uploadUrl
  const { data } = await downloadImage(imagePath)
  const uploadResponse = await fetch(uploadUrl, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${credentials.accessToken}`,
      'Content-Type': 'application/octet-stream',
    },
    body: new Uint8Array(data),
  })

  if (!uploadResponse.ok) {
    throw new Error(`LinkedIn image upload failed: ${uploadResponse.status} ${await uploadResponse.text()}`)
  }

  return registerData.value.asset
}

async function createPost(text: string, credentials: LinkedInCredentials, imageAsset?: string): Promise<string> {
  const shareContent: Record<string, unknown> = {
    shareCommentary: { text },
    shareMediaCategory: imageAsset ? 'IMAGE' : 'NONE',
  }

  if (imageAsset) {
    shareContent.media = [{ status: 'READY', media: imageAsset }]
  }

  const response = await fetch('https://api.linkedin.com/v2/ugcPosts', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${credentials.accessToken}`,
      'Content-Type': 'application/json',
      'X-Restli-Protocol-Version': '2.0.0',
    },
    body: JSON.stringify({
      author: `urn:li:organization:${credentials.orgId}`,
      lifecycleState: 'PUBLISHED',
      specificContent: {
        'com.linkedin.ugc.ShareContent': shareContent,
      },
      visibility: {
        'com.linkedin.ugc.MemberNetworkVisibility': 'PUBLIC',
      },
    }),
  })

  if (!response.ok) {
    throw new Error(`LinkedIn post creation failed: ${response.status} ${await response.text()}`)
  }

  const payload = await response.json() as { id: string }
  return payload.id
}

export async function postToLinkedIn(brand: string, text: string, imagePath?: string): Promise<AdapterPostResult> {
  try {
    const credentials = getCredentials(brand)
    const imageAsset = imagePath ? await uploadImage(imagePath, credentials) : undefined
    const id = await createPost(text, credentials, imageAsset)

    return {
      success: true,
      postId: id,
      postUrl: `https://www.linkedin.com/feed/update/${id}`,
    }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : String(error),
    }
  }
}
