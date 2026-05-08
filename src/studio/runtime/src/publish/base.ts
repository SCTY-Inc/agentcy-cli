export interface AdapterPostResult {
  success: boolean
  postId?: string
  postUrl?: string
  error?: string
}

export function createCredentialGetter<T>(
  platform: string,
  requiredFields: Array<{ suffix: string; field: keyof T }>
): (brand: string) => T {
  return (brand: string): T => {
    const brandUpper = brand.toUpperCase()
    const result = {} as T

    for (const { suffix, field } of requiredFields) {
      const value = process.env[`${platform}_${brandUpper}_${suffix}`]
      if (!value) {
        throw new Error(`${platform}_${brandUpper}_${suffix} not set`)
      }
      result[field] = value as T[keyof T]
    }

    return result
  }
}
