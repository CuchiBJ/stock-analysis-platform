import assert from 'node:assert/strict'
import test from 'node:test'
import { QueryClient } from '@tanstack/react-query'

import {
  clearUserPrivateStorage,
  privateQueryKey,
  readJournalStorage,
  writeJournalStorage,
} from './private-state.ts'

class MemoryStorage {
  #values = new Map()

  get length() { return this.#values.size }
  getItem(key) { return this.#values.get(key) ?? null }
  setItem(key, value) { this.#values.set(key, String(value)) }
  removeItem(key) { this.#values.delete(key) }
  key(index) { return [...this.#values.keys()][index] ?? null }
}

test('two users sharing one browser receive isolated journal state and query keys', () => {
  const storage = new MemoryStorage()

  writeJournalStorage('alice-id', 'account-balance', '12500', storage)
  writeJournalStorage('bob-id', 'account-balance', '900', storage)
  writeJournalStorage('alice-id', 'draft', '{"symbol":"AAPL"}', storage)

  assert.equal(readJournalStorage('alice-id', 'account-balance', storage), '12500')
  assert.equal(readJournalStorage('bob-id', 'account-balance', storage), '900')
  assert.notDeepEqual(
    privateQueryKey('alice-id', 'journal', 'trades'),
    privateQueryKey('bob-id', 'journal', 'trades'),
  )

  clearUserPrivateStorage('alice-id', storage)

  assert.equal(readJournalStorage('alice-id', 'account-balance', storage), null)
  assert.equal(readJournalStorage('alice-id', 'draft', storage), null)
  assert.equal(readJournalStorage('bob-id', 'account-balance', storage), '900')
})

test('logout cleanup cannot expose Alice cached journal, stats, or profile to Bob', async () => {
  const queryClient = new QueryClient()
  const alicePrefix = privateQueryKey('alice-id')
  const aliceTrades = privateQueryKey('alice-id', 'journal', 'trades')
  const aliceStats = privateQueryKey('alice-id', 'journal', 'stats')
  const aliceProfile = privateQueryKey('alice-id', 'profile')
  const bobTrades = privateQueryKey('bob-id', 'journal', 'trades')

  queryClient.setQueryData(aliceTrades, [{ symbol: 'SECRET' }])
  queryClient.setQueryData(aliceStats, { totalPnl: 1234 })
  queryClient.setQueryData(aliceProfile, { displayName: 'Alice' })
  queryClient.setQueryData(bobTrades, [])

  await queryClient.cancelQueries({ queryKey: alicePrefix })
  queryClient.removeQueries({ queryKey: alicePrefix })

  assert.equal(queryClient.getQueryData(aliceTrades), undefined)
  assert.equal(queryClient.getQueryData(aliceStats), undefined)
  assert.equal(queryClient.getQueryData(aliceProfile), undefined)
  assert.deepEqual(queryClient.getQueryData(bobTrades), [])
})

test('private state cannot be written without an authenticated user id', () => {
  const storage = new MemoryStorage()
  assert.throws(
    () => writeJournalStorage('  ', 'account-balance', 'secret', storage),
    /user id is required/,
  )
  assert.equal(storage.length, 0)
})
