const PLATFORM_LIMITS: Record<string, { requestsPerWindow: number; windowMs: number }> = {
  twitter: { requestsPerWindow: 15, windowMs: 15 * 60 * 1000 },
  linkedin: { requestsPerWindow: 100, windowMs: 24 * 60 * 60 * 1000 },
  facebook: { requestsPerWindow: 200, windowMs: 60 * 60 * 1000 },
  instagram: { requestsPerWindow: 25, windowMs: 24 * 60 * 60 * 1000 },
  threads: { requestsPerWindow: 250, windowMs: 24 * 60 * 60 * 1000 },
  default: { requestsPerWindow: 10, windowMs: 60 * 1000 },
}

const state = new Map<string, number[]>()

export function checkRateLimit(platform: string, brand: string): {
  allowed: boolean
  waitMs?: number
} {
  const config = PLATFORM_LIMITS[platform] ?? PLATFORM_LIMITS.default
  const key = `${platform}:${brand}`
  const requests = (state.get(key) ?? []).filter((value) => value > Date.now() - config.windowMs)

  if (requests.length >= config.requestsPerWindow) {
    const oldest = Math.min(...requests)
    state.set(key, requests)
    return {
      allowed: false,
      waitMs: Math.max(0, oldest + config.windowMs - Date.now()),
    }
  }

  requests.push(Date.now())
  state.set(key, requests)
  return { allowed: true }
}
