import assert from 'node:assert/strict'
import { spawn, spawnSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { mkdtemp, rm } from 'node:fs/promises'
import http from 'node:http'
import https from 'node:https'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const FRONTEND_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const EMAIL = 'browser-user@example.test'
const INITIAL_PASSWORD = 'BrowserAuthPass!123'
const RESET_PASSWORD = 'BrowserAuthPass!456'

function json(response, status, payload, headers = {}) {
  response.writeHead(status, { 'Content-Type': 'application/json', ...headers })
  response.end(JSON.stringify(payload))
}

async function requestBody(request) {
  const chunks = []
  for await (const chunk of request) chunks.push(chunk)
  return JSON.parse(Buffer.concat(chunks).toString('utf8') || '{}')
}

function hasSession(request) {
  return /(?:^|;\s*)__Host-session=browser-session(?:;|$)/.test(request.headers.cookie ?? '')
}

function sessionPayload(displayName) {
  return {
    user: { id: 'browser-user-id', email: EMAIL, role: 'user', display_name: displayName },
    csrf_token: 'browser-csrf',
    expires_at: '2099-10-23T00:00:00Z',
  }
}

function createMockApi(state) {
  return http.createServer(async (request, response) => {
    const url = new URL(request.url ?? '/', `http://${request.headers.host}`)
    const body = request.method === 'GET' ? {} : await requestBody(request)

    if (request.method === 'POST' && url.pathname === '/api/v1/auth/register') {
      assert.equal(body.email, EMAIL)
      assert.equal(body.display_name, 'Browser User')
      state.registered = true
      state.password = body.password
      return json(response, 200, { message: 'Check your email to verify your account.' })
    }
    if (request.method === 'POST' && url.pathname === '/api/v1/auth/verify-email') {
      assert.equal(body.token, 'verify-token')
      state.verified = true
      return json(response, 200, { message: 'Email verified.' })
    }
    if (request.method === 'POST' && url.pathname === '/api/v1/auth/forgot-password') {
      assert.equal(body.email, EMAIL)
      state.recoveryRequested = true
      return json(response, 200, { message: 'If the account is eligible, recovery instructions have been sent.' })
    }
    if (request.method === 'POST' && url.pathname === '/api/v1/auth/reset-password') {
      assert.equal(body.token, 'reset-token')
      state.password = body.new_password
      state.sessionExpired = true
      return json(response, 200, { message: 'Password updated.' }, {
        'Set-Cookie': '__Host-session=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0',
      })
    }
    if (request.method === 'POST' && url.pathname === '/api/v1/auth/login') {
      if (!state.verified || body.email !== EMAIL || body.password !== state.password) {
        return json(response, 401, { detail: 'Invalid email or password.' })
      }
      state.sessionExpired = false
      return json(response, 200, sessionPayload(state.displayName), {
        'Set-Cookie': '__Host-session=browser-session; Path=/; HttpOnly; Secure; SameSite=Lax',
      })
    }
    if (request.method === 'POST' && url.pathname === '/api/v1/auth/logout') {
      assert.equal(request.headers['x-csrf-token'], 'browser-csrf')
      return json(response, 200, { ok: true }, {
        'Set-Cookie': '__Host-session=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0',
      })
    }

    if (!hasSession(request) || state.sessionExpired) {
      return json(response, 401, { detail: 'Authentication required.' })
    }
    if (request.method === 'GET' && url.pathname === '/api/v1/auth/session') {
      return json(response, 200, sessionPayload(state.displayName))
    }
    if (request.method === 'GET' && url.pathname === '/api/v1/profile') {
      return json(response, 200, {
        user_id: 'browser-user-id', email: EMAIL, role: 'user', display_name: state.displayName,
        created_at: '2026-09-28T00:00:00Z', updated_at: '2026-09-28T00:00:00Z',
      })
    }
    if (request.method === 'PATCH' && url.pathname === '/api/v1/profile') {
      assert.equal(request.headers['x-csrf-token'], 'browser-csrf')
      state.displayName = body.display_name
      return json(response, 200, {
        user_id: 'browser-user-id', email: EMAIL, role: 'user', display_name: state.displayName,
        created_at: '2026-09-28T00:00:00Z', updated_at: '2026-09-28T00:01:00Z',
      })
    }
    return json(response, 404, { detail: `Unhandled test endpoint: ${request.method} ${url.pathname}` })
  })
}

async function freePort() {
  const server = net.createServer()
  await new Promise((resolve, reject) => server.listen(0, '127.0.0.1', resolve).once('error', reject))
  const { port } = server.address()
  await new Promise(resolve => server.close(resolve))
  return port
}

function chromeExecutable() {
  return [
    process.env.CHROME_PATH,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
  ].filter(Boolean).find(existsSync) ?? null
}

class CdpClient {
  #socket
  #nextId = 1
  #pending = new Map()
  events = []

  constructor(webSocketUrl) {
    this.#socket = new WebSocket(webSocketUrl)
    this.#socket.addEventListener('message', event => {
      const message = JSON.parse(String(event.data))
      if (!message.id) {
        this.events.push(message)
        return
      }
      const pending = this.#pending.get(message.id)
      if (!pending) return
      this.#pending.delete(message.id)
      if (message.error) pending.reject(new Error(message.error.message))
      else pending.resolve(message.result)
    })
  }

  async open() {
    if (this.#socket.readyState === WebSocket.OPEN) return
    await new Promise((resolve, reject) => {
      this.#socket.addEventListener('open', resolve, { once: true })
      this.#socket.addEventListener('error', reject, { once: true })
    })
  }

  send(method, params = {}) {
    const id = this.#nextId++
    return new Promise((resolve, reject) => {
      this.#pending.set(id, { resolve, reject })
      this.#socket.send(JSON.stringify({ id, method, params }))
    })
  }

  async evaluate(expression) {
    const result = await this.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text)
    return result.result.value
  }

  close() { this.#socket.close() }
}

async function waitFor(client, expression, description, timeoutMs = 25_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      if (await client.evaluate(expression)) return
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  const state = await client.evaluate(`({
    url: location.href,
    body: document.body?.innerText?.slice(0, 1500),
    scripts: [...document.scripts].map(script => script.src || 'inline').slice(-20),
    resources: performance.getEntriesByType('resource').map(entry => entry.name).filter(name => name.includes('/_next/')).slice(-20),
  })`)
  const browserEvents = client.events.filter(event => event.method === 'Runtime.exceptionThrown' || event.method === 'Log.entryAdded').slice(-20)
  throw new Error(`Timed out waiting for ${description}: ${JSON.stringify(state)} events=${JSON.stringify(browserEvents)}`)
}

async function setInput(client, selector, value) {
  const focused = await client.evaluate(`(() => {
    const input = document.querySelector(${JSON.stringify(selector)});
    if (!input) return false;
    input.focus();
    input.select();
    return true;
  })()`)
  assert.equal(focused, true, `Expected input ${selector}`)
  await client.send('Input.insertText', { text: value })
  await waitFor(client, `document.querySelector(${JSON.stringify(selector)})?.value === ${JSON.stringify(value)}`, `input value ${selector}`)
}

async function waitForHttp(url) {
  const deadline = Date.now() + 30_000
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url)
      if (response.status < 500) return
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  throw new Error(`Timed out waiting for ${url}`)
}

async function stopChild(child) {
  if (child.exitCode !== null || child.signalCode !== null) return
  child.kill('SIGTERM')
  await new Promise(resolve => {
    const timeout = setTimeout(() => { child.kill('SIGKILL'); resolve() }, 3_000)
    child.once('exit', () => { clearTimeout(timeout); resolve() })
  })
}

test('complete authentication lifecycle works over HTTPS, including expiry', { timeout: 120_000 }, async t => {
  const chromePath = chromeExecutable()
  assert.ok(chromePath, 'Chrome/Chromium is required')
  const tempDir = await mkdtemp(path.join(os.tmpdir(), 'stock-auth-https-'))
  const keyPath = path.join(tempDir, 'key.pem')
  const certPath = path.join(tempDir, 'cert.pem')
  const certificate = spawnSync('openssl', [
    'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
    '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1',
    '-keyout', keyPath, '-out', certPath,
  ], { encoding: 'utf8' })
  assert.equal(certificate.status, 0, certificate.stderr)

  const state = { registered: false, verified: false, recoveryRequested: false, sessionExpired: false, password: '', displayName: 'Browser User' }
  const api = createMockApi(state)
  const apiPort = await freePort()
  const appPort = await freePort()
  const httpsPort = await freePort()
  const debugPort = await freePort()
  await new Promise((resolve, reject) => api.listen(apiPort, '127.0.0.1', resolve).once('error', reject))

  const next = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'dev', '--webpack', '--hostname', '127.0.0.1', '--port', String(appPort)], {
    cwd: FRONTEND_DIR,
    env: { ...process.env, API_PROXY_TARGET: `http://127.0.0.1:${apiPort}`, NEXT_TELEMETRY_DISABLED: '1', NEXT_DIST_DIR: '.next-auth-https' },
    stdio: ['ignore', 'ignore', 'pipe'],
  })
  const proxy = https.createServer({ key: readFileSync(keyPath), cert: readFileSync(certPath) }, (request, response) => {
    const upstream = http.request({
      hostname: '127.0.0.1', port: appPort, path: request.url, method: request.method,
      headers: { ...request.headers, host: `127.0.0.1:${httpsPort}`, 'x-forwarded-proto': 'https' },
    }, upstreamResponse => {
      response.writeHead(upstreamResponse.statusCode ?? 500, upstreamResponse.headers)
      upstreamResponse.pipe(response)
    })
    upstream.on('error', error => response.destroy(error))
    request.pipe(upstream)
  })
  await new Promise((resolve, reject) => proxy.listen(httpsPort, '127.0.0.1', resolve).once('error', reject))

  const chrome = spawn(chromePath, [
    '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--ignore-certificate-errors', `--remote-debugging-port=${debugPort}`, `--user-data-dir=${path.join(tempDir, 'chrome')}`, 'about:blank',
  ], { stdio: ['ignore', 'ignore', 'pipe'] })
  let client
  t.after(async () => {
    client?.close()
    api.closeAllConnections()
    proxy.closeAllConnections()
    await Promise.all([
      new Promise(resolve => api.close(resolve)),
      new Promise(resolve => proxy.close(resolve)),
      stopChild(chrome), stopChild(next),
    ])
    await rm(path.join(FRONTEND_DIR, '.next-auth-https'), { recursive: true, force: true })
    await rm(tempDir, { recursive: true, force: true })
  })

  await waitForHttp(`http://127.0.0.1:${appPort}/login`)
  await waitForHttp(`http://127.0.0.1:${debugPort}/json/version`)
  const targets = await fetch(`http://127.0.0.1:${debugPort}/json`).then(response => response.json())
  const page = targets.find(target => target.type === 'page')
  client = new CdpClient(page.webSocketDebuggerUrl)
  await client.open()
  await client.send('Page.enable')
  await client.send('Runtime.enable')
  await client.send('Log.enable')

  const origin = `https://127.0.0.1:${httpsPort}`
  await client.send('Page.navigate', { url: `${origin}/profile` })
  await waitFor(client, `location.pathname === '/login' && location.search.includes('returnTo')`, 'protected redirect')

  await client.send('Page.navigate', { url: `${origin}/register` })
  await waitFor(client, `!!document.querySelector('#display-name')`, 'registration form')
  await setInput(client, '#display-name', 'Browser User')
  await setInput(client, '#email', EMAIL)
  await setInput(client, '#password', INITIAL_PASSWORD)
  assert.equal(await client.evaluate(`fetch('/api/v1/auth/register', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
    body: JSON.stringify({ display_name: 'Browser User', email: ${JSON.stringify(EMAIL)}, password: ${JSON.stringify(INITIAL_PASSWORD)} }),
  }).then(response => response.ok)`), true)
  assert.equal(state.registered, true)

  await client.send('Page.navigate', { url: `${origin}/verify-email?token=verify-token` })
  await waitFor(client, `document.body.innerText.includes('Verify your email')`, 'email verification page')
  assert.equal(await client.evaluate(`fetch('/api/v1/auth/verify-email', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
    body: JSON.stringify({ token: 'verify-token' }),
  }).then(response => response.ok)`), true)
  assert.equal(state.verified, true)

  await client.send('Page.navigate', { url: `${origin}/login?returnTo=%2Fprofile` })
  await waitFor(client, `!!document.querySelector('#email')`, 'login form')
  await setInput(client, '#email', EMAIL)
  await setInput(client, '#password', INITIAL_PASSWORD)
  assert.equal(await client.evaluate(`fetch('/api/v1/auth/login', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
    body: JSON.stringify({ email: ${JSON.stringify(EMAIL)}, password: ${JSON.stringify(INITIAL_PASSWORD)} }),
  }).then(response => response.ok)`), true)
  await client.send('Page.navigate', { url: `${origin}/profile` })
  await waitFor(client, `location.pathname === '/profile'`, 'authenticated protected navigation')
  assert.equal(await client.evaluate(`fetch('/api/v1/profile', { credentials: 'include' }).then(response => response.json()).then(profile => profile.display_name)`), 'Browser User')
  assert.equal(await client.evaluate(`fetch('/api/v1/profile', {
    method: 'PATCH', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': 'browser-csrf' }, credentials: 'include',
    body: JSON.stringify({ display_name: 'Browser User Updated' }),
  }).then(response => response.ok)`), true)
  assert.equal(await client.evaluate(`fetch('/api/v1/profile', { credentials: 'include' }).then(response => response.json()).then(profile => profile.display_name)`), 'Browser User Updated')
  assert.equal(await client.evaluate(`fetch('/api/v1/auth/logout', {
    method: 'POST', headers: { 'X-CSRF-Token': 'browser-csrf' }, credentials: 'include',
  }).then(response => response.ok)`), true)
  await client.send('Page.navigate', { url: `${origin}/profile` })
  await waitFor(client, `location.pathname === '/login'`, 'logout')

  await client.send('Page.navigate', { url: `${origin}/forgot-password` })
  await waitFor(client, `!!document.querySelector('#email')`, 'recovery form')
  await setInput(client, '#email', EMAIL)
  assert.equal(await client.evaluate(`fetch('/api/v1/auth/forgot-password', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
    body: JSON.stringify({ email: ${JSON.stringify(EMAIL)} }),
  }).then(response => response.ok)`), true)
  assert.equal(state.recoveryRequested, true)

  await client.send('Page.navigate', { url: `${origin}/reset-password?token=reset-token` })
  await waitFor(client, `!!document.querySelector('#confirm-password')`, 'reset form')
  await setInput(client, '#password', RESET_PASSWORD)
  await setInput(client, '#confirm-password', RESET_PASSWORD)
  assert.equal(await client.evaluate(`fetch('/api/v1/auth/reset-password', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
    body: JSON.stringify({ token: 'reset-token', new_password: ${JSON.stringify(RESET_PASSWORD)} }),
  }).then(response => response.ok)`), true)

  await client.send('Page.navigate', { url: `${origin}/login?returnTo=%2Fprofile` })
  await waitFor(client, `!!document.querySelector('#email')`, 'post-reset login')
  await setInput(client, '#email', EMAIL)
  await setInput(client, '#password', RESET_PASSWORD)
  assert.equal(await client.evaluate(`fetch('/api/v1/auth/login', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
    body: JSON.stringify({ email: ${JSON.stringify(EMAIL)}, password: ${JSON.stringify(RESET_PASSWORD)} }),
  }).then(response => response.ok)`), true)
  await client.send('Page.navigate', { url: `${origin}/profile` })
  await waitFor(client, `location.pathname === '/profile'`, 'post-reset protected navigation')
  assert.equal(await client.evaluate(`fetch('/api/v1/profile', { credentials: 'include' }).then(response => response.json()).then(profile => profile.display_name)`), 'Browser User Updated')

  state.sessionExpired = true
  assert.equal(await client.evaluate(`fetch('/api/v1/profile', { credentials: 'include' }).then(response => response.status)`), 401)
  await client.evaluate(`fetch('/api/v1/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': 'browser-csrf' }, credentials: 'include' })`)
  await client.send('Page.navigate', { url: `${origin}/profile` })
  await waitFor(client, `location.pathname === '/login' && location.search.includes('returnTo')`, 'expired-session redirect')
})
