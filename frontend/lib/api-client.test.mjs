import assert from 'node:assert/strict'
import test from 'node:test'
import { apiFetch, onSessionLost, registerSessionCleanup, setSessionCsrfToken } from './api-client.ts'

test('credentialed mutations attach the current CSRF proof', async (context) => {
  const originalFetch = globalThis.fetch
  context.after(() => { globalThis.fetch = originalFetch; setSessionCsrfToken(null) })
  let request
  globalThis.fetch = async (url, init) => {
    request = { url, init }
    return new Response('{}', { status: 200 })
  }
  setSessionCsrfToken('csrf-proof')

  await apiFetch('/api/v1/profile', { method: 'PATCH', body: '{}' })

  assert.equal(request.url, '/api/v1/profile')
  assert.equal(request.init.credentials, 'include')
  assert.equal(request.init.headers.get('X-CSRF-Token'), 'csrf-proof')
})

test('401 runs cleanup before broadcasting session loss', async (context) => {
  const originalFetch = globalThis.fetch
  context.after(() => { globalThis.fetch = originalFetch })
  const events = []
  const removeCleanup = registerSessionCleanup(async () => events.push('cleanup'))
  const removeListener = onSessionLost(() => events.push('lost'))
  context.after(() => { removeCleanup(); removeListener() })
  globalThis.fetch = async () => new Response('{}', { status: 401 })

  await apiFetch('/api/v1/private')

  assert.deepEqual(events, ['cleanup', 'lost'])
})

test('expected login failures do not broadcast session loss', async (context) => {
  const originalFetch = globalThis.fetch
  context.after(() => { globalThis.fetch = originalFetch })
  let called = false
  const removeListener = onSessionLost(() => { called = true })
  context.after(removeListener)
  globalThis.fetch = async () => new Response('{}', { status: 401 })

  await apiFetch('/api/v1/auth/login', { method: 'POST', handleUnauthorized: false })

  assert.equal(called, false)
})

test('browser requests reject cross-origin credential and CSRF disclosure', async (context) => {
  const originalWindow = globalThis.window
  const originalFetch = globalThis.fetch
  context.after(() => {
    globalThis.window = originalWindow
    globalThis.fetch = originalFetch
    setSessionCsrfToken(null)
  })
  globalThis.window = { location: { origin: 'https://app.example.test' } }
  let called = false
  globalThis.fetch = async () => {
    called = true
    return new Response('{}', { status: 200 })
  }
  setSessionCsrfToken('must-not-leak')

  await assert.rejects(
    apiFetch('https://evil.example.test/collect', { method: 'POST' }),
    /current origin/,
  )
  assert.equal(called, false)
})
