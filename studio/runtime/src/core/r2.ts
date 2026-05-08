import crypto from 'crypto'
import { PutObjectCommand, S3Client } from '@aws-sdk/client-s3'
import { existsSync, readFileSync } from 'fs'
import { extname } from 'path'
import { getMimeType } from './http'

interface R2Config {
  accountId: string
  accessKeyId: string
  secretAccessKey: string
  bucketName: string
  publicUrl: string
}

function getConfig(): R2Config {
  const config = {
    accountId: process.env.R2_ACCOUNT_ID,
    accessKeyId: process.env.R2_ACCESS_KEY_ID,
    secretAccessKey: process.env.R2_SECRET_ACCESS_KEY,
    bucketName: process.env.R2_BUCKET_NAME,
    publicUrl: process.env.R2_PUBLIC_URL,
  }

  const missing = Object.entries(config)
    .filter(([, value]) => !value)
    .map(([key]) => key)

  if (missing.length > 0) {
    throw new Error(`R2 not configured. Missing: ${missing.join(', ')}`)
  }

  return config as R2Config
}

function createClient(config: R2Config): S3Client {
  return new S3Client({
    region: 'auto',
    endpoint: `https://${config.accountId}.r2.cloudflarestorage.com`,
    credentials: {
      accessKeyId: config.accessKeyId,
      secretAccessKey: config.secretAccessKey,
    },
  })
}

export function isR2Configured(): boolean {
  try {
    getConfig()
    return true
  } catch {
    return false
  }
}

export async function uploadToR2(filePath: string): Promise<string> {
  if (!existsSync(filePath)) {
    throw new Error(`File not found: ${filePath}`)
  }

  const config = getConfig()
  const fileData = readFileSync(filePath)
  const hash = crypto.createHash('md5').update(fileData).digest('hex').slice(0, 8)
  const ext = extname(filePath)
  const key = `loom-runtime/${Date.now()}-${hash}${ext}`

  await createClient(config).send(new PutObjectCommand({
    Bucket: config.bucketName,
    Key: key,
    Body: fileData,
    ContentType: getMimeType(filePath),
  }))

  return `${config.publicUrl.replace(/\/$/, '')}/${key}`
}
