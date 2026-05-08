import { SOCIAL_PLATFORMS, type PublishInput, type SocialPlatform } from '../domain/types'
import { isR2Configured } from '../core/r2'
import { postToFacebook } from './facebook-direct'
import { postToLinkedIn } from './linkedin-direct'
import { postToInstagram, postToThreads } from './meta-graph'
import { checkRateLimit } from './rate-limit'
import { postToTwitter } from './twitter-direct'

export interface SocialPlatformAuthStatus {
  platform: SocialPlatform
  supported: boolean
  configured: boolean
  missing: string[]
}

export interface SocialAuthReport {
  brand: string
  available: SocialPlatform[]
  platforms: SocialPlatformAuthStatus[]
  r2Configured: boolean
}

export interface SocialPostResult {
  platform: SocialPlatform
  success: boolean
  postId?: string
  postUrl?: string
  error?: string
}

export interface SocialPublishRequest {
  brand: string
  text: string
  platformAssets: Record<SocialPlatform, string>
  platforms: SocialPlatform[]
  dryRun?: boolean
  root?: string
}

export type SocialPublisher = (request: SocialPublishRequest) => Promise<SocialPostResult[]>

const PLATFORM_REQUIREMENTS: Record<SocialPlatform, string[]> = {
  twitter: ['API_KEY', 'API_SECRET', 'ACCESS_TOKEN', 'ACCESS_SECRET'],
  linkedin: ['ACCESS_TOKEN', 'ORG_ID'],
  facebook: ['PAGE_ACCESS_TOKEN', 'PAGE_ID'],
  instagram: ['ACCESS_TOKEN', 'USER_ID'],
  threads: ['ACCESS_TOKEN', 'USER_ID'],
}

export const ALL_SOCIAL_PLATFORMS: SocialPlatform[] = [...SOCIAL_PLATFORMS]

function resolveValue(platform: SocialPlatform, brand: string, suffix: string): string | undefined {
  const upper = brand.toUpperCase()

  if (platform === 'twitter' && (suffix === 'API_KEY' || suffix === 'API_SECRET')) {
    return process.env[`TWITTER_${upper}_${suffix}`] ?? process.env[`TWITTER_${suffix}`]
  }

  return process.env[`${platform.toUpperCase()}_${upper}_${suffix}`]
}

export function getSocialAuthReport(brand: string): SocialAuthReport {
  const r2Configured = isR2Configured()
  const platforms = ALL_SOCIAL_PLATFORMS.map((platform) => {
    const missing = PLATFORM_REQUIREMENTS[platform].filter((suffix) => !resolveValue(platform, brand, suffix))
    if ((platform === 'instagram' || platform === 'threads') && !r2Configured) {
      missing.push('R2_CONFIG')
    }

    return {
      platform,
      supported: true,
      configured: missing.length === 0,
      missing,
    }
  })

  return {
    brand,
    available: platforms.filter((platform) => platform.configured).map((platform) => platform.platform),
    platforms,
    r2Configured,
  }
}

function selectPlatforms(auth: SocialAuthReport, options: PublishInput = {}): SocialPlatform[] {
  if (options.platforms && options.platforms.length > 0) {
    return options.platforms
  }

  return auth.available
}

async function postToPlatform(platform: SocialPlatform, brand: string, text: string, imagePath: string, root?: string): Promise<SocialPostResult> {
  const rate = checkRateLimit(platform, brand)
  if (!rate.allowed) {
    return {
      platform,
      success: false,
      error: `Rate limited. Try again in ${Math.ceil((rate.waitMs ?? 0) / 1000)} seconds.`,
    }
  }

  switch (platform) {
    case 'twitter':
      return { platform, ...(await postToTwitter(brand, text, imagePath)) }
    case 'linkedin':
      return { platform, ...(await postToLinkedIn(brand, text, imagePath)) }
    case 'facebook':
      return { platform, ...(await postToFacebook(brand, text, imagePath)) }
    case 'instagram':
      return { platform, ...(await postToInstagram(brand, text, imagePath)) }
    case 'threads':
      return { platform, ...(await postToThreads(brand, text, imagePath, root)) }
  }
}

export async function publishSocialPost(request: SocialPublishRequest): Promise<SocialPostResult[]> {
  const platforms = request.platforms.length > 0 ? request.platforms : getSocialAuthReport(request.brand).available
  if (platforms.length === 0) {
    throw new Error(`No configured social platforms for ${request.brand}. Run "loom ops auth check --brand ${request.brand}" first.`)
  }

  if (request.dryRun) {
    return platforms.map((platform) => ({
      platform,
      success: true,
      postUrl: undefined,
    }))
  }

  const results: SocialPostResult[] = []
  for (const platform of platforms) {
    const imagePath = request.platformAssets[platform]
    results.push(await postToPlatform(platform, request.brand, request.text, imagePath, request.root))
  }
  return results
}

export function buildSocialPublishPlan(brand: string, options: PublishInput = {}): { platforms: SocialPlatform[]; auth: SocialAuthReport } {
  const auth = getSocialAuthReport(brand)
  const platforms = selectPlatforms(auth, options)

  if (options.platforms && options.platforms.length > 0 && !options.dryRun) {
    const unavailable = options.platforms.filter((platform) => !auth.available.includes(platform))
    if (unavailable.length > 0) {
      throw new Error(`Requested platforms not configured for ${brand}: ${unavailable.join(', ')}. Run "loom ops auth check --brand ${brand}" first.`)
    }
  }

  if (platforms.length === 0) {
    throw new Error(`No configured social platforms for ${brand}. Run "loom ops auth check --brand ${brand}" first.`)
  }

  return { platforms, auth }
}
