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
  id: 'forming-smoke-user',
  email: 'forming-smoke@example.test',
  role: 'user',
  display_name: 'Formation Smoke Test',
}

function json(response, status, payload, headers = {}) {
  response.writeHead(status, { 'Content-Type': 'application/json', ...headers })
  response.end(JSON.stringify(payload))
}

function marketContext() {
  return {
    as_of: '2026-09-28',
    universe_size: 500,
    engines_pending: [],
    participation: {
      descriptor: 'EXPANDING',
      delta_5d: 2.4,
      delta_sample_size_20d: 20,
      metrics: {
        breadth_above_ema21: 0.62,
        breadth_above_ema50: 0.58,
        breadth_above_ema200: 0.54,
        breadth_momentum_5d: 2.4,
        breadth_momentum_20d: 5.1,
        near_highs_count: 90,
        near_lows_count: 12,
        highs_lows_ratio: 7.5,
        participation_persistence: 0.75,
      },
    },
    leadership: {
      descriptor: 'HEALTHY',
      delta_5d: 3.2,
      metrics: {
        leader_count: 41,
        leader_count_delta_5d: 4,
        leader_count_delta_20d: 8,
        leader_density: 0.082,
        leader_density_delta_5d: 3.2,
        leader_density_delta_20d: 6.4,
        leader_density_level: 'STRONG',
        leader_density_percentile: 0.8,
        leader_density_sample_size: 60,
        leader_pullback_quality_avg: 72,
        leader_tightness_avg: 0.78,
        leader_vol_contraction_avg: 0.7,
        leader_rs_persistence_10d: 0.75,
        leader_extension_count: 2,
        leader_climactic_count: 0,
        leadership_turnover_5d: 0.12,
      },
    },
  }
}

function formingSetup() {
  return {
    symbol: 'DOCN',
    current_price: 45.2,
    change_pct: 1.4,
    formation_state: 'ORDERLY_PULLBACK',
    formation_score: 78,
    formation_narrative: 'Pullback ordenado con contracción; todavía espera confirmación en EMA9.',
    primary_risk: 'La trayectoria de fuerza relativa aún es neutral.',
    next_trigger: 'EMA9',
    distance_to_trigger_atr: -0.42,
    structure_evidence: 'Precio sobre EMA50 y SMA150; SMA150 sobre SMA200.',
    contraction_evidence: 'Rango y volumen contrayéndose.',
    rs_direction: 'IMPROVING',
    group_strength: { group: 'Software - Infrastructure', badge: 'leader' },
  }
}

function promotedDiagnostic() {
  return {
    header: {
      symbol: 'PROMO',
      name: 'Synthetic Promoted Setup',
      sector: 'Technology',
      industry: 'Software',
      market_group: 'Software - Infrastructure',
      current_price: 50,
      has_metrics: true,
      metrics_date: '2026-09-28',
      is_latest: true,
      is_benchmark: false,
    },
    lists: [{
      key: 'forming',
      name: 'Setups Forming',
      passes: true,
      criteria: [],
      status: 'promoted_to_feed',
      rank: null,
      eligible_count: 1,
      cutoff_gap: null,
      structural_age_days: 24,
    }],
    transition_history: [],
    market_context_applied: null,
    group_strength: { group: 'Software - Infrastructure', badge: 'neutral', multiplier: 1 },
    minervini_status: null,
    assessment: null,
    benchmark_context: null,
  }
}

function createMockApi(state) {
  return http.createServer((request, response) => {
    const url = new URL(request.url ?? '/', `http://${request.headers.host}`)

    if (request.method === 'POST' && url.pathname === '/api/v1/auth/login') {
      return json(response, 200, {
        user: USER,
        csrf_token: 'forming-smoke-csrf',
        expires_at: '2026-10-28T00:00:00Z',
      }, { 'Set-Cookie': '__Host-session=forming-smoke; Path=/; HttpOnly; Secure; SameSite=Lax' })
    }
    if (request.method === 'GET' && url.pathname === '/api/v1/auth/session') {
      return json(response, 200, {
        user: USER,
        csrf_token: 'forming-smoke-csrf',
        expires_at: '2026-10-28T00:00:00Z',
      })
    }
    if (request.method === 'GET' && url.pathname === '/api/v1/market-context/current') {
      return json(response, 200, marketContext())
    }
    if (request.method === 'GET' && url.pathname === '/api/v1/transitions/forming') {
      const setups = state.empty ? [] : [formingSetup()]
      return json(response, 200, { setups, total_eligible: setups.length, context: {} })
    }
    if (request.method === 'GET' && url.pathname === '/api/v1/transitions/live') {
      return json(response, 200, [{
        symbol: 'PROMO',
        transition: 'entering_pullback',
        direction: 'bullish',
        strength: 0.82,
        observation_priority: 84,
        pullback_quality_score: 79,
        setup_score: null,
        is_pre_reclaim: true,
        timestamp: '2026-09-28T15:00:00Z',
        narrative: 'Pullback de calidad entrando en zona operable.',
        severity: 'positive',
        rs_change: -0.4,
        volume_change_pct: -31,
        current_price: 50,
        change_pct: -1.2,
        dist_to_setup_pct: 0.3,
        dist_ema_label: 'EMA9',
      }])
    }
    if (request.method === 'GET' && url.pathname === '/api/v1/stocks/PROMO/diagnostic') {
      return json(response, 200, promotedDiagnostic())
    }
    if (request.method === 'GET' && url.pathname === '/api/v1/health/data-freshness') {
      return json(response, 200, {
        as_of: '2026-09-28T15:00:00Z',
        stock_metrics_latest: '2026-09-28',
        stock_price_latest: '2026-09-28',
        metrics_lag_days: 0,
        is_stale: false,
        today_et: '2026-09-28',
        is_weekday: true,
        recent_errors_24h: 0,
        recent_errors: [],
        pipeline_heartbeats: [],
        coverage: { expected: 500, actual: 500, pct: 100 },
        market_state: { is_open: true, is_warmup: false, minutes_since_open: 120, session_phase: 'regular' },
        warnings: [],
      })
    }
    return json(response, 404, { detail: `Unhandled test endpoint: ${request.method} ${url.pathname}` })
  })
}

async function freePort() {
  const server = net.createServer()
  await new Promise((resolve, reject) => server.listen(0, '127.0.0.1', resolve).once('error', reject))
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
  return [
    process.env.CHROME_PATH,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
  ].filter(Boolean).find(candidate => existsSync(candidate)) ?? null
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
      if (!message.id) return this.events.push(message)
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

  async close() {
    if (this.#socket.readyState === WebSocket.CLOSED) return
    await new Promise(resolve => {
      const timeout = setTimeout(resolve, 2_000)
      this.#socket.addEventListener('close', () => { clearTimeout(timeout); resolve() }, { once: true })
      this.#socket.close()
    })
  }
}

async function waitForEvaluation(client, expression, description, timeoutMs = 20_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      if (await client.evaluate(expression)) return
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  const state = await client.evaluate(`({ url: location.href, body: document.body?.innerText?.slice(0, 3000) })`)
  throw new Error(`Timed out waiting for ${description}: ${JSON.stringify(state)}`)
}

async function stopChild(child) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return
  child.kill('SIGTERM')
  await new Promise(resolve => {
    const timeout = setTimeout(() => { child.kill('SIGKILL'); resolve() }, 3_000)
    child.once('exit', () => { clearTimeout(timeout); resolve() })
  })
}

test('authenticated formation workflow covers preparation, promotion, and scarcity', { timeout: 120_000 }, async t => {
  const chromePath = chromeExecutable()
  assert.ok(chromePath, 'Chrome/Chromium is required for this smoke test')

  const state = { empty: false }
  const api = createMockApi(state)
  const mockApiPort = await freePort()
  const appPort = await freePort()
  const debugPort = await freePort()
  await new Promise((resolve, reject) => api.listen(mockApiPort, '127.0.0.1', resolve).once('error', reject))

  const profileDir = await mkdtemp(path.join(os.tmpdir(), 'stock-forming-smoke-'))
  const nextDistDir = '.next-forming-e2e'
  const nextLogs = []
  const chromeLogs = []
  const next = spawn(process.execPath, [
    'node_modules/next/dist/bin/next', 'dev', '--webpack', '--hostname', '127.0.0.1', '--port', String(appPort),
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
    '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    `--remote-debugging-port=${debugPort}`, `--user-data-dir=${profileDir}`, 'about:blank',
  ], { stdio: ['ignore', 'ignore', 'pipe'] })
  chrome.stderr.on('data', chunk => chromeLogs.push(String(chunk)))

  let client
  t.after(async () => {
    await client?.close()
    await stopChild(chrome)
    await stopChild(next)
    api.closeAllConnections()
    await new Promise(resolve => api.close(resolve))
    await rm(profileDir, { recursive: true, force: true })
    await rm(path.join(FRONTEND_DIR, nextDistDir), { recursive: true, force: true })
  })

  try {
    await waitForHttp(`http://127.0.0.1:${appPort}/login`)
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
      method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
      body: JSON.stringify({ email: ${JSON.stringify(USER.email)}, password: 'test-password' }),
    }).then(response => response.ok)`)
    assert.equal(loggedIn, true)

    await client.send('Page.navigate', { url: `http://127.0.0.1:${appPort}/dashboard` })
    await waitForEvaluation(client, `document.body.innerText.includes('DOCN') && document.body.innerText.includes('PROMO')`, 'formation and feed symbols')
    await waitForEvaluation(client, `document.body.innerText.includes('PARTICIPATION') && document.body.innerText.includes('LEADERSHIP')`, 'market context')
    const dashboard = await client.evaluate(`(() => {
      const headings = [...document.querySelectorAll('h2,h3')];
      const forming = headings.find(node => node.textContent.includes('Setups Forming'));
      const feed = headings.find(node => node.textContent.includes('Setup Feed'));
      return {
        market: document.body.innerText.includes('PARTICIPATION') && document.body.innerText.includes('LEADERSHIP'),
        formingBeforeFeed: !!forming && !!feed && Boolean(forming.compareDocumentPosition(feed) & Node.DOCUMENT_POSITION_FOLLOWING),
        formingText: document.querySelector('#setups')?.innerText,
        feedText: document.querySelector('#transitions')?.innerText,
      };
    })()`)
    assert.equal(dashboard.market, true, JSON.stringify(dashboard))
    assert.equal(dashboard.formingBeforeFeed, true, JSON.stringify(dashboard))
    assert.match(dashboard.formingText, /DOCN/)
    assert.doesNotMatch(dashboard.formingText, /PROMO/)
    assert.match(dashboard.feedText, /PROMO/)

    await client.send('Page.navigate', { url: `http://127.0.0.1:${appPort}/stock/PROMO` })
    await waitForEvaluation(client, `document.body.innerText.includes('PROMOVIDO AL SETUP FEED')`, 'promoted symbol diagnostic')

    state.empty = true
    await client.send('Page.navigate', { url: `http://127.0.0.1:${appPort}/dashboard` })
    await waitForEvaluation(
      client,
      `document.body.innerText.includes('No hay estructuras suficientemente preparadas en este snapshot')`,
      'honest empty formation panel',
    )
  } catch (error) {
    const browserErrors = client?.events.filter(event => event.method === 'Runtime.exceptionThrown' || event.method === 'Log.entryAdded').slice(-20)
    throw new Error(
      `${error.message}\nBrowser events:\n${JSON.stringify(browserErrors, null, 2)}` +
      `\nNext logs:\n${nextLogs.join('').slice(-5000)}` +
      `\nChrome logs:\n${chromeLogs.join('').slice(-2000)}`,
    )
  }
})
