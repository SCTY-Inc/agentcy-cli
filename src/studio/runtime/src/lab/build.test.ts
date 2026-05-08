import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'
import { afterEach, describe, expect, test } from 'vitest'
import { loadBrandFoundation } from '../brands/load'
import { buildCardLabHtml } from './build'
import { writeBrandFixture } from '../test-fixtures'

const roots: string[] = []

function createWorkspace(): string {
  const root = mkdtempSync(join(tmpdir(), 'loom-lab-'))
  roots.push(root)
  writeBrandFixture(root)
  writeFileSync(
    join(root, 'brands', 'givecare', 'logo.png'),
    Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wn7n6cAAAAASUVORK5CYII=', 'base64'),
  )
  return root
}

afterEach(() => {
  while (roots.length > 0) {
    rmSync(roots.pop()!, { recursive: true, force: true })
  }
})

describe('buildCardLabHtml', () => {
  test('builds a self-contained interactive card lab document', () => {
    const root = createWorkspace()
    const brand = loadBrandFoundation('givecare', { root })

    const html = buildCardLabHtml({
      brand,
      brandAssetBasePath: join(root, 'brands', 'givecare'),
      initialCardType: 'quote',
      initialHeadline: 'Care is infrastructure',
      initialBody: 'Invisible labor should be visible labor.',
      initialPlatform: 'linkedin',
    })

    expect(html).toContain('<title>GiveCare Card Lab</title>')
    expect(html).toContain('Generate 20 Variations')
    expect(html).toContain('Head to head')
    expect(html).toContain('Choose between two directions')
    expect(html).toContain('Prefer left')
    expect(html).toContain('Current leaning')
    expect(html).toContain('Care is infrastructure')
    expect(html).toContain('data:image/png;base64,')
    expect(html).toContain('Copy top preset JSON')
  })
})
