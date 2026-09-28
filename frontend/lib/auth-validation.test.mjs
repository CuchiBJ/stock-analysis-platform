import assert from 'node:assert/strict'
import test from 'node:test'
import { validateDisplayName, validateEmail, validatePassword, validateRegistration } from './auth-validation.ts'

test('registration form validation matches the API contract', () => {
  assert.deepEqual(validateRegistration({ displayName: ' Ada ', email: 'ada@example.com', password: 'correct horse battery' }), {})
  assert.deepEqual(Object.keys(validateRegistration({ displayName: ' ', email: 'invalid', password: 'short' })).sort(), ['displayName', 'email', 'password'])
})

test('profile and password limits are validated before submission', () => {
  assert.ok(validateDisplayName(''))
  assert.ok(validateDisplayName('x'.repeat(81)))
  assert.ok(validatePassword('12345678901'))
  assert.equal(validatePassword('123456789012'), undefined)
  assert.equal(validateEmail('person@example.com'), undefined)
})
