import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { mkdtemp, rm } from 'node:fs/promises'
import http from 'node:http'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const FRONTEND_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const USER = {
  id: 'pipeline-health-user',
  email: 'pipeline-health@example.test',
  role: 'user',
  display_name: 'Pipeline Health Test',
}

function json(response, status, payload, headers = {}) {
  response.writeHead(status, { 'Content-Type': 'application/json', ...headers })
  response.end(JSON.stringify(payload))
}

function snapshotFor(state) {
  const now = new Date()
  const lastRun = new Date(now.getTime() - 15_000).toISOString()
  const base = {
    as_of: now.toISOString(),
    stock_metrics_latest: '2026-09-25',
    stock_price_latest: '2026-09-25',
    metrics_lag_days: 0,
    is_stale: false,
    today_et: '2026-09-25',
    is_weekday: true,
    recent_errors_24h: 0,
    recent_errors: [],
    pipeline_heartbeats: [{
      cycle_name: 'fast_metrics',
      last_run_at: lastRun,
      last_success_at: lastRun,
      last_duration_seconds: 2.5,
      symbols_processed: 100,
      symbols_expected: 100,
      status: 'ok',
      last_error_message: null,
      age_seconds: 15,
    }],
    coverage: { expected: 100, actual: 100, pct: 100 },
    market_state: {
      is_open: true,
      is_warmup: false,
      minutes_since_open: 120,
      session_phase: 'regular',
    },
    warnings: [],
  }

  if (state === 'partial') {
    base.coverage = { expected: 100, actual: 80, pct: 80 }
    base.pipeline_heartbeats[0] = {
      ...base.pipeline_heartbeats[0],
      last_success_at: new Date(now.getTime() - 300_000).toISOString(),
      symbols_processed: 80,
      status: 'partial',
      last_error_message: 'Polygon 429 on batch 12',
    }
  }

  if (state === 'failed') {
    base.pipeline_heartbeats[0] = {
      ...base.pipeline_heartbeats[0],
      last_success_at: new Date(now.getTime() - 300_000).toISOString(),
      symbols_processed: 0,
      status: 'failed',
      last_error_message: 'connection refused',
    }
    base.recent_errors_24h = 1
    base.recent_errors = [{
      task_name: 'fast_metrics',
      exception_type: 'RuntimeError',
      exception_message: 'connection refused',
      occurred_at: lastRun,
    }]
  }

  return base
}

function createMockApi(currentState) {
  return http.createServer((request, response) => {
    const url = new URL(request.url ?? '/', `http://${request.headers.host}`)

    if (request.method === 'POST' && url.pathname === '/api/v1/auth/login') {
      return json(response, 200, {
        user: USER,
        csrf_token: 'pipeline-health-csrf',
        expires_at: '2026-10-25T00:00:00Z',
      }, {
        'Set-Cookie': '__Host-session=pipeline-health; Path=/; HttpOnly; Secure; SameSite=Lax',
      })
    }

    if (request.method === 'GET' && url.pathname === '/api/v1/auth/session') {
      return json(response, 200, {
        user: USER,
        csrf_token: 'pipeline-health-csrf',
        expires_at: '2026-10-25T00:00:00Z',
      })
    }

    if (request.method === 'GET' && url.pathname === '/api/v1/health/data-freshness') {
      return json(response, 200, snapshotFor(currentState.value))
    }

    return json(response, 404, {
      detail: `Unhandled test endpoint: ${request.method} ${url.pathname}`,
    })
  })
}

async function freePort() {
  const server = net.createServer()
  await new Promise((resolve, reject) => {
    server.listen(0, '127.0.0.1', resolve).once('error', reject)
  })
  const address = server.address()
  await new Promise(resolve => server.close(resolve))
  return address.port
}

async function waitForHttp(url, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url)
      if (response.status < 500) return
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  throw new Error(`Timed out waiting for ${url}`)
}

function chromeExecutable() {
  const candidates = [
    process.env.CHROME_PATH,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
  ].filter(Boolean)
  return candidates.find(candidate => existsSync(candidate)) ?? null
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
    const result = await this.send('Runtime.evaluate', {
      expression,
      awaitPromise: true,
      returnByValue: true,
    })
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text)
    return result.result.value
  }

  async close() {
    if (this.#socket.readyState === WebSocket.CLOSED) return
    await new Promise(resolve => {
      const timeout = setTimeout(resolve, 2_000)
      this.#socket.addEventListener('close', () => {
        clearTimeout(timeout)
        resolve()
      }, { once: true })
      this.#socket.close()
    })
  }
}

async function waitForChildExit(child, timeoutMs) {
  if (child.exitCode !== null || child.signalCode !== null) return true
  return new Promise(resolve => {
    const onExit = () => {
      clearTimeout(timeout)
      resolve(true)
    }
    const timeout = setTimeout(() => {
      child.off('exit', onExit)
      resolve(false)
    }, timeoutMs)
    child.once('exit', onExit)
  })
}

async function stopChild(child, name) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return
  child.kill('SIGTERM')
  if (await waitForChildExit(child, 3_000)) return
  child.kill('SIGKILL')
  assert.equal(await waitForChildExit(child, 3_000), true, `${name} did not exit`)
}

async function waitForEvaluation(client, expression, description, timeoutMs = 20_000) {
  const deadline = Date.now() + timeoutMs
  let lastError
  while (Date.now() < deadline) {
    try {
      if (await client.evaluate(expression)) return
    } catch (error) {
      lastError = error
    }
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  const state = await client.evaluate(`({
    url: location.href,
    body: document.body?.innerText?.slice(0, 2000),
  })`)
  throw new Error(
    `Timed out waiting for ${description}: ${JSON.stringify(state)}` +
    `${lastError ? ` (${lastError})` : ''}`,
  )
}

async function loadState(client, appPort, currentState, state, expectedColor) {
  currentState.value = state
  await client.send('Page.navigate', { url: `http://127.0.0.1:${appPort}/guide` })
  await waitForEvaluation(
    client,
    `document.querySelector('[aria-label="Open pipeline health detail"] > span')` +
      `?.classList.contains(${JSON.stringify(`bg-${expectedColor}-500`)})`,
    `${state} pipeline chip`,
  )

  const clicked = await client.evaluate(`(() => {
    const button = document.querySelector('[aria-label="Open pipeline health detail"]');
    if (!button) return false;
    button.click();
    return true;
  })()`)
  assert.equal(clicked, true, `Expected ${state} health chip to be clickable`)
  await waitForEvaluation(
    client,
    `document.querySelector('[role="dialog"][aria-label="Pipeline health detail"]') !== null`,
    `${state} pipeline drawer`,
  )
}

async function closeDrawer(client) {
  await client.evaluate(
    `window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))`,
  )
  await waitForEvaluation(
    client,
    `document.querySelector('[role="dialog"][aria-label="Pipeline health detail"]') === null`,
    'pipeline drawer close',
  )
}

test('pipeline health chip and drawer render healthy, partial, and failed states', {
  timeout: 120_000,
}, async t => {
  const chromePath = chromeExecutable()
  assert.ok(
    chromePath,
    'Chrome/Chromium is required; set CHROME_PATH when it is not in a standard location',
  )

  const currentState = { value: 'healthy' }
  const api = createMockApi(currentState)
  const mockApiPort = await freePort()
  const appPort = await freePort()
  const debugPort = await freePort()
  await new Promise((resolve, reject) => {
    api.listen(mockApiPort, '127.0.0.1', resolve).once('error', reject)
  })
  const profileDir = await mkdtemp(path.join(os.tmpdir(), 'stock-pipeline-health-'))
  const nextDistDir = '.next-pipeline-health-e2e'
  const nextLogs = []
  const chromeLogs = []
  const next = spawn(process.execPath, [
    'node_modules/next/dist/bin/next',
    'dev',
    '--webpack',
    '--hostname',
    '127.0.0.1',
    '--port',
    String(appPort),
  ], {
    cwd: FRONTEND_DIR,
    env: {
      ...process.env,
      API_PROXY_TARGET: `http://127.0.0.1:${mockApiPort}`,
      NEXT_TELEMETRY_DISABLED: '1',
      NEXT_DIST_DIR: nextDistDir,
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  next.stdout.on('data', chunk => nextLogs.push(String(chunk)))
  next.stderr.on('data', chunk => nextLogs.push(String(chunk)))

  const chrome = spawn(chromePath, [
    '--headless=new',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    `--remote-debugging-port=${debugPort}`,
    `--user-data-dir=${profileDir}`,
    'about:blank',
  ], { stdio: ['ignore', 'ignore', 'pipe'] })
  chrome.stderr.on('data', chunk => chromeLogs.push(String(chunk)))

  let client
  t.after(async () => {
    await client?.close()
    await stopChild(chrome, 'Chrome')
    await stopChild(next, 'Next.js')
    api.closeAllConnections()
    await new Promise(resolve => api.close(resolve))
    await rm(profileDir, { recursive: true, force: true })
    await rm(path.join(FRONTEND_DIR, nextDistDir), { recursive: true, force: true })
  })

  try {
    await waitForHttp(`http://127.0.0.1:${appPort}/guide`)
    await waitForHttp(`http://127.0.0.1:${debugPort}/json/version`)
    const targets = await fetch(`http://127.0.0.1:${debugPort}/json`).then(response => response.json())
    const page = targets.find(target => target.type === 'page')
    assert.ok(page?.webSocketDebuggerUrl, 'Chrome did not expose a debuggable page')
    client = new CdpClient(page.webSocketDebuggerUrl)
    await client.open()
    await client.send('Page.enable')
    await client.send('Runtime.enable')
    await client.send('Log.enable')

    await client.send('Page.navigate', { url: `http://127.0.0.1:${appPort}/login` })
    await waitForEvaluation(client, `location.pathname === '/login'`, 'login page')
    const loggedIn = await client.evaluate(`fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email: ${JSON.stringify(USER.email)}, password: 'test-password' }),
    }).then(response => response.ok)`)
    assert.equal(loggedIn, true, 'Expected browser session to be established')

    await loadState(client, appPort, currentState, 'healthy', 'emerald')
    const healthy = await client.evaluate(`(() => {
      const dialog = document.querySelector('[role="dialog"]');
      const coverage = [...dialog.querySelectorAll('section')]
        .find(section => section.textContent.includes('Universe coverage'));
      const cycle = [...dialog.querySelectorAll('li')]
        .find(item => item.textContent.includes('fast_metrics'));
      return {
        chipText: document.querySelector('[aria-label="Open pipeline health detail"]').textContent,
        coverageText: coverage.textContent,
        coverageBar: coverage.querySelector('.bg-emerald-500')?.getAttribute('style'),
        cycleGreen: !!cycle?.querySelector('.bg-emerald-500'),
      };
    })()`)
    assert.match(healthy.chipText, /100%/)
    assert.match(healthy.coverageText, /100\/100 \(100%\)/)
    assert.match(healthy.coverageBar, /width:\s*100%/)
    assert.equal(healthy.cycleGreen, true)
    await closeDrawer(client)

    await loadState(client, appPort, currentState, 'partial', 'amber')
    const partial = await client.evaluate(`(() => {
      const dialog = document.querySelector('[role="dialog"]');
      const coverage = [...dialog.querySelectorAll('section')]
        .find(section => section.textContent.includes('Universe coverage'));
      const cycle = [...dialog.querySelectorAll('li')]
        .find(item => item.textContent.includes('fast_metrics'));
      return {
        chipText: document.querySelector('[aria-label="Open pipeline health detail"]').textContent,
        coverageText: coverage.textContent,
        coverageBar: coverage.querySelector('.bg-amber-500')?.getAttribute('style'),
        cycleText: cycle?.textContent,
        cycleAmber: !!cycle?.querySelector('.bg-amber-500'),
      };
    })()`)
    assert.match(partial.chipText, /80%/)
    assert.match(partial.coverageText, /80\/100 \(80%\)/)
    assert.match(partial.coverageBar, /width:\s*80%/)
    assert.match(partial.cycleText, /80\/100/)
    assert.match(partial.cycleText, /Polygon 429 on batch 12/)
    assert.equal(partial.cycleAmber, true)
    await closeDrawer(client)

    await loadState(client, appPort, currentState, 'failed', 'red')
    const failed = await client.evaluate(`(() => {
      const dialog = document.querySelector('[role="dialog"]');
      const cycle = [...dialog.querySelectorAll('li')]
        .find(item => item.textContent.includes('fast_metrics'));
      const errors = [...dialog.querySelectorAll('section')]
        .find(section => section.textContent.includes('Recent errors (24h)'));
      return {
        cycleRed: !!cycle?.querySelector('.bg-red-500'),
        cycleText: cycle?.textContent,
        errorsText: errors?.textContent,
      };
    })()`)
    assert.equal(failed.cycleRed, true)
    assert.match(failed.cycleText, /connection refused/)
    assert.match(failed.errorsText, /fast_metrics/)
    assert.match(failed.errorsText, /RuntimeError/)
    assert.match(failed.errorsText, /connection refused/)
  } catch (error) {
    const browserErrors = client?.events
      .filter(event => event.method === 'Runtime.exceptionThrown' || event.method === 'Log.entryAdded')
      .slice(-20)
    throw new Error(
      `${error.message}\nBrowser events:\n${JSON.stringify(browserErrors, null, 2)}` +
      `\nNext logs:\n${nextLogs.join('').slice(-4000)}` +
      `\nChrome logs:\n${chromeLogs.join('').slice(-2000)}`,
    )
  }
})
