import assert from 'node:assert/strict'
import test from 'node:test'
import { isPublicAuthPath, loginPathFor, sanitizeReturnPath } from './auth-navigation.ts'

test('protected navigation preserves safe local return paths', () => {
  assert.equal(sanitizeReturnPath('/journal?closed=true#latest'), '/journal?closed=true#latest')
  assert.equal(loginPathFor('/stock/AAPL', '?tab=journal'), '/login?returnTo=%2Fstock%2FAAPL%3Ftab%3Djournal')
})

test('protected navigation rejects unsafe return URLs', () => {
  for (const unsafe of ['https://evil.test/x', '//evil.test/x', '/\\evil.test', '/%2F%2Fevil.test', '/login']) {
    assert.equal(sanitizeReturnPath(unsafe), '/dashboard')
  }
})

test('only explicit authentication pages are public', () => {
  assert.equal(isPublicAuthPath('/register'), true)
  assert.equal(isPublicAuthPath('/reset-password'), true)
  assert.equal(isPublicAuthPath('/journal'), false)
})

test('admin-only build exposes login as the sole public account page', async () => {
  const previous = process.env.NEXT_PUBLIC_PUBLIC_ACCOUNT_FLOWS_ENABLED
  process.env.NEXT_PUBLIC_PUBLIC_ACCOUNT_FLOWS_ENABLED = 'false'
  try {
    const adminOnly = await import(`./auth-navigation.ts?admin-only=${Date.now()}`)
    assert.deepEqual(adminOnly.PUBLIC_AUTH_PATHS, ['/login'])
    assert.equal(adminOnly.isPublicAuthPath('/register'), false)
    assert.equal(adminOnly.isPublicAuthPath('/forgot-password'), false)
  } finally {
    if (previous === undefined) delete process.env.NEXT_PUBLIC_PUBLIC_ACCOUNT_FLOWS_ENABLED
    else process.env.NEXT_PUBLIC_PUBLIC_ACCOUNT_FLOWS_ENABLED = previous
  }
})
