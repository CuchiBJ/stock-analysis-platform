import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const dashboardUrl = new URL('../app/dashboard/page.tsx', import.meta.url)
const componentUrl = new URL('../components/dashboard/SetupsForming.tsx', import.meta.url)
const canonicalWebSocketUrl = new URL('../hooks/useWebSocket.ts', import.meta.url)
const legacyWebSocketUrl = new URL('../app/hooks/useWebSocket.ts', import.meta.url)

test('dashboard places Setups Forming before the Setup Feed', async () => {
  const source = await readFile(dashboardUrl, 'utf8')
  assert.ok(source.indexOf('<SetupsForming />') < source.indexOf('<LiveTransitionFeed />'))
  assert.doesNotMatch(source, /TopActionableSetups/)
})

test('formation panel uses the protected contract and enforces six-card scarcity', async () => {
  const source = await readFile(componentUrl, 'utf8')
  assert.match(source, /transitions\/forming\?limit=6/)
  assert.match(source, /setups\.slice\(0, 6\)/)
  assert.match(source, /No hay estructuras suficientemente preparadas/)
  assert.doesNotMatch(source, /continuation_prob|confidence|freshness|buy/i)
})

test('dashboard websocket imports resolve to one canonical hook', async () => {
  const component = await readFile(componentUrl, 'utf8')
  const canonicalHook = await readFile(canonicalWebSocketUrl, 'utf8')

  assert.match(component, /from '@\/hooks\/useWebSocket'/)
  assert.match(canonicalHook, /channel: string/)
  await assert.rejects(readFile(legacyWebSocketUrl, 'utf8'), { code: 'ENOENT' })
})
