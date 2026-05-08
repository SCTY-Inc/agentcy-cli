import { randomUUID } from 'crypto'

export function createId(prefix: string): string {
  return `${prefix}_${randomUUID()}`
}

export function nowIso(): string {
  return new Date().toISOString()
}

