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
const USERS = {
  alice: {
    id: 'alice-id',
    email: 'alice@example.test',
    role: 'user',
    display_name: 'Alice Secret Profile',
  },
  bob: {
    id: 'bob-id',
    email: 'bob@example.test',
    role: 'user',
    display_name: 'Bob Clean Profile',
  },
}

const emptyAggregate = {
  n: 0,
  win_rate: null,
  expectancy: null,
  profit_factor: null,
  avg_r: null,
  total_r: null,
  avg_duration_days: null,
  total_pnl: 0,
  wins: 0,
  losses: 0,
  breakeven: 0,
}

function statsFor(userKey) {
  const isAlice = userKey === 'alice'
  return {
    overall: isAlice
      ? { ...emptyAggregate, n: 1, win_rate: 1, total_r: 2.5, total_pnl: 4242, wins: 1 }
      : emptyAggregate,
    by_setup: [],
    by_context: [],
    by_setup_context: [],
    by_entry_reason: [],
    risk_evolution: [],
    by_regime_at_entry: [],
    by_setup_regime_matrix: [],
    decision_overall: {
      n_decisions_total: isAlice ? 1 : 0,
      n_fully_resolved: isAlice ? 1 : 0,
      n_partially_resolved: 0,
      n_fully_open: 0,
      decision_wins: isAlice ? 1 : 0,
      decision_losses: 0,
      decision_breakeven: 0,
      decision_win_rate: isAlice ? 1 : null,
      decision_total_realized_pnl: isAlice ? 4242 : 0,
      decision_total_r: isAlice ? 2.5 : null,
      decision_average_gain: isAlice ? 4242 : null,
      decision_average_loss: null,
      decision_total_gains: isAlice ? 4242 : 0,
      decision_total_losses: 0,
    },
    win_rate_evolution: [],
    rolling_window: 20,
    open_positions: isAlice ? 1 : 0,
    linked_to_observations: 0,
    underpowered_buckets: 0,
  }
}

function tradesFor(userKey) {
  if (userKey !== 'alice') return { trades: [] }
  return {
    trades: [{
      id: 101,
      symbol: 'ALICEONLY',
      direction: 'long',
      setup: 'breakout',
      context: 'bull',
      entry_date: '2026-09-01',
      entry_price: 100,
      qty: 10,
      stop_price: 95,
      exit_date: null,
      exit_price: null,
      duration_days: null,
      pnl_dollars: null,
      pnl_pct: null,
      r_multiple: null,
      error_note: null,
      post_venta: null,
      linked_observation_id: null,
      is_open: true,
      from_queue: false,
      entry_reason: 'discretionary',
      exit_reason: '',
      planned_risk_dollars: 50,
      account_balance_at_entry: 77777,
      effective_risk_dollars: 50,
      risk_pct_of_account: 0.00064,
      regime_at_entry: 'bull',
      system_score_at_entry: 91,
      group_strength_at_entry: 'strong',
      leader_health_at_entry: 0.9,
      initial_stop_price: 95,
      is_risk_free: false,
      parent_trade_id: null,
      decision_id: 101,
      decision_outcome: null,
      decision_result_detail: null,
      is_runner_breakeven_exit: false,
    }],
  }
}

function json(response, status, payload, headers = {}) {
  response.writeHead(status, { 'Content-Type': 'application/json', ...headers })
  response.end(JSON.stringify(payload))
}

async function requestBody(request) {
  const chunks = []
  for await (const chunk of request) chunks.push(chunk)
  return Buffer.concat(chunks).toString('utf8')
}

function sessionFrom(request) {
  const match = /(?:^|;\s*)__Host-session=(alice|bob)(?:;|$)/.exec(request.headers.cookie ?? '')
  return match?.[1] ?? null
}

function createMockApi(reads) {
  return http.createServer(async (request, response) => {
    const url = new URL(request.url ?? '/', `http://${request.headers.host}`)
    const session = sessionFrom(request)

    if (request.method === 'POST' && url.pathname === '/api/v1/auth/login') {
      const body = JSON.parse(await requestBody(request))
      const userKey = body.email === USERS.alice.email ? 'alice' : body.email === USERS.bob.email ? 'bob' : null
      if (!userKey) return json(response, 401, { detail: 'Invalid email or password.' })
      return json(response, 200, {
        user: USERS[userKey],
        csrf_token: `${userKey}-csrf`,
        expires_at: '2026-10-23T00:00:00Z',
      }, { 'Set-Cookie': `__Host-session=${userKey}; Path=/; HttpOnly; Secure; SameSite=Lax` })
    }

    if (request.method === 'POST' && url.pathname === '/api/v1/auth/logout') {
      return json(response, 200, { ok: true }, {
        'Set-Cookie': '__Host-session=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0',
      })
    }

    if (!session) return json(response, 401, { detail: 'Authentication required.' })

    if (request.method === 'GET' && url.pathname === '/api/v1/auth/session') {
      return json(response, 200, {
        user: USERS[session],
        csrf_token: `${session}-csrf`,
        expires_at: '2026-10-23T00:00:00Z',
      })
    }

    if (request.method === 'GET' && url.pathname === '/api/v1/profile') {
      reads.push({ session, resource: 'profile' })
      const user = USERS[session]
      return json(response, 200, {
        user_id: user.id,
        email: user.email,
        role: user.role,
        display_name: user.display_name,
        created_at: '2026-09-01T00:00:00Z',
        updated_at: '2026-09-01T00:00:00Z',
      })
    }

    if (request.method === 'GET' && url.pathname === '/api/v1/journal/stats') {
      reads.push({ session, resource: 'stats' })
      return json(response, 200, statsFor(session))
    }

    if (request.method === 'GET' && url.pathname === '/api/v1/journal/trades') {
      reads.push({ session, resource: 'trades' })
      return json(response, 200, tradesFor(session))
    }

    if (request.method === 'GET' && url.pathname === '/api/v1/journal/vocab') {
      return json(response, 200, {
        setup_options: ['breakout'],
        context_options: ['bull'],
        entry_reason_options: ['discretionary'],
        exit_reason_options: ['target'],
        default_commission: 1,
      })
    }

    if (request.method === 'GET' && url.pathname === '/api/v1/health/data-freshness') {
      return json(response, 200, {
        as_of: '2026-09-23T00:00:00Z',
        stock_metrics_latest: '2026-09-23',
        stock_price_latest: '2026-09-23',
        metrics_lag_days: 0,
        is_stale: false,
        today_et: '2026-09-23',
        is_weekday: true,
        recent_errors_24h: 0,
        recent_errors: [],
        pipeline_heartbeats: [],
        coverage: { expected: 1, actual: 1, pct: 100 },
        market_state: { is_open: false, is_warmup: false, minutes_since_open: null, session_phase: 'closed' },
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
  await new Promise((resolve) => server.close(resolve))
  return address.port
}

async function waitForHttp(url, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      const { status } = await httpGet(url)
      if (status < 500) return
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  throw new Error(`Timed out waiting for ${url}`)
}

function httpGet(url) {
  return new Promise((resolve, reject) => {
    const request = http.get(url, {
      agent: false,
      headers: { Connection: 'close' },
    }, response => {
      const chunks = []
      response.on('data', chunk => chunks.push(chunk))
      response.on('end', () => resolve({
        status: response.statusCode ?? 0,
        body: Buffer.concat(chunks).toString('utf8'),
      }))
    })
    request.once('error', reject)
  })
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
  if (child.exitCode !== null || child.signalCode !== null) return
  child.kill('SIGTERM')
  if (await waitForChildExit(child, 3_000)) return
  child.kill('SIGKILL')
  assert.equal(await waitForChildExit(child, 3_000), true, `${name} did not exit after SIGKILL`)
}

async function waitForEvaluation(client, expression, description, timeoutMs = 20_000) {
  const deadline = Date.now() + timeoutMs
  let lastError
  while (Date.now() < deadline) {
    try {
      if (await client.evaluate(expression)) return
    } catch (error) {
      // Navigation destroys the prior execution context; retry in the new one.
      lastError = error
    }
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  const state = await client.evaluate(`({
    url: location.href,
    body: document.body?.innerText?.slice(0, 2000),
    emailKeys: Reflect.ownKeys(document.querySelector('#email') ?? {}).map(String),
    scripts: [...document.scripts].map(script => script.src || 'inline').slice(-20),
    resources: performance.getEntriesByType('resource').map(entry => entry.name).filter(name => name.includes('/_next/')).slice(-20),
  })`)
  throw new Error(`Timed out waiting for ${description}: ${JSON.stringify(state)}${lastError ? ` (${lastError})` : ''}`)
}

async function clickButton(client, text) {
  const clicked = await client.evaluate(`(() => {
    const button = [...document.querySelectorAll('button')]
      .find(candidate => candidate.textContent.includes(${JSON.stringify(text)}));
    if (!button) return false;
    button.click();
    return true;
  })()`)
  assert.equal(clicked, true, `Expected button containing ${text}`)
}

async function login(client, email) {
  const loggedIn = await client.evaluate(`fetch('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email: ${JSON.stringify(email)}, password: 'SharedBrowserPass!123' }),
  }).then(response => response.ok)`)
  assert.equal(loggedIn, true, `Expected ${email} to establish a browser session`)
  await client.evaluate(`location.assign('/journal')`)
  await waitForEvaluation(client, `location.pathname === '/journal'`, `journal navigation after ${email} login`)
}

test('Bob cannot observe Alice private UI or browser state after logout/login in one Chrome profile', { timeout: 90_000 }, async t => {
  const chromePath = chromeExecutable()
  assert.ok(chromePath, 'Chrome/Chromium is required; set CHROME_PATH when it is not in a standard location')

  const reads = []
  const api = createMockApi(reads)
  const mockApiPort = await freePort()
  const appPort = await freePort()
  const debugPort = await freePort()
  await new Promise((resolve, reject) => api.listen(mockApiPort, '127.0.0.1', resolve).once('error', reject))
  const profileDir = await mkdtemp(path.join(os.tmpdir(), 'stock-shared-browser-'))
  const nextDistDir = '.next-shared-browser'
  const nextLogs = []
  const chromeLogs = []
  const next = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'dev', '--webpack', '--hostname', '127.0.0.1', '--port', String(appPort)], {
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
    api.closeAllConnections()
    await new Promise(resolve => api.close(resolve))
    await Promise.all([
      stopChild(chrome, 'Chrome'),
      stopChild(next, 'Next.js'),
    ])
    await rm(profileDir, { recursive: true, force: true })
    await rm(path.join(FRONTEND_DIR, nextDistDir), { recursive: true, force: true })
  })

  try {
    await waitForHttp(`http://127.0.0.1:${appPort}/login`)
    await waitForHttp(`http://127.0.0.1:${debugPort}/json/version`)
    const targetsResponse = await httpGet(`http://127.0.0.1:${debugPort}/json`)
    assert.equal(targetsResponse.status, 200, 'Chrome debugging target list was unavailable')
    const targets = JSON.parse(targetsResponse.body)
    const page = targets.find(target => target.type === 'page')
    assert.ok(page?.webSocketDebuggerUrl, 'Chrome did not expose a debuggable page')
    client = new CdpClient(page.webSocketDebuggerUrl)
    await client.open()
    await client.send('Page.enable')
    await client.send('Runtime.enable')
    await client.send('Log.enable')

    await client.send('Page.navigate', { url: `http://127.0.0.1:${appPort}/login?returnTo=%2Fjournal` })
    await login(client, USERS.alice.email)
    await waitForEvaluation(client, `document.body.innerText.includes('ALICEONLY') && document.body.innerText.includes('$4242.00')`, 'Alice journal trade and statistics')

    await client.evaluate(`(() => {
      localStorage.setItem('journal:alice-id:account-balance', '77777');
      localStorage.setItem('journal:alice-id:draft', JSON.stringify({ symbol: 'ALICE_DRAFT' }));
    })()`)
    assert.deepEqual(await client.evaluate(`({
      balance: localStorage.getItem('journal:alice-id:account-balance'),
      draft: JSON.parse(localStorage.getItem('journal:alice-id:draft')),
    })`), { balance: '77777', draft: { symbol: 'ALICE_DRAFT' } })
    await clickButton(client, 'Nuevo trade')
    await waitForEvaluation(client, `document.querySelector('input[placeholder="prefilled del último trade"]')?.value === '77777'`, 'Alice account balance in journal form')
    await clickButton(client, 'Cancelar')

    await client.send('Page.navigate', { url: `http://127.0.0.1:${appPort}/profile` })
    await waitForEvaluation(client, `document.querySelector('#display-name')?.value === 'Alice Secret Profile'`, 'Alice profile')
    await client.evaluate(`document.querySelector('summary')?.click()`)
    await clickButton(client, 'Sign out')
    await waitForEvaluation(client, `location.pathname === '/login'`, 'logout navigation')

    const clearedAliceState = await client.evaluate(`({
      balance: localStorage.getItem('journal:alice-id:account-balance'),
      draft: localStorage.getItem('journal:alice-id:draft'),
    })`)
    assert.deepEqual(clearedAliceState, { balance: null, draft: null })

    await client.send('Page.navigate', { url: `http://127.0.0.1:${appPort}/login?returnTo=%2Fjournal` })
    await login(client, USERS.bob.email)
    await waitForEvaluation(client, `document.body.innerText.includes('No hay trades cargados')`, 'Bob empty journal')
    assert.deepEqual(await client.evaluate(`({
      aliceBalance: localStorage.getItem('journal:alice-id:account-balance'),
      aliceDraft: localStorage.getItem('journal:alice-id:draft'),
      bobBalance: localStorage.getItem('journal:bob-id:account-balance'),
      bobDraft: localStorage.getItem('journal:bob-id:draft'),
    })`), { aliceBalance: null, aliceDraft: null, bobBalance: null, bobDraft: null })
    const bobJournalText = await client.evaluate(`document.body.innerText`)
    assert.doesNotMatch(bobJournalText, /ALICEONLY|\$4242\.00|Alice Secret Profile|ALICE_DRAFT|77777/)

    await clickButton(client, 'Nuevo trade')
    await waitForEvaluation(client, `!!document.querySelector('input[placeholder="prefilled del último trade"]')`, 'Bob journal form')
    assert.equal(await client.evaluate(`document.querySelector('input[placeholder="prefilled del último trade"]').value`), '')
    await clickButton(client, 'Cancelar')

    await client.send('Page.navigate', { url: `http://127.0.0.1:${appPort}/profile` })
    await waitForEvaluation(client, `document.querySelector('#display-name')?.value === 'Bob Clean Profile'`, 'Bob profile')
    const bobProfileText = await client.evaluate(`document.body.innerText`)
    assert.doesNotMatch(bobProfileText, /Alice Secret Profile|alice@example\.test/)

    for (const resource of ['trades', 'stats', 'profile']) {
      assert.ok(reads.some(read => read.session === 'alice' && read.resource === resource), `Alice ${resource} was not read`)
      assert.ok(reads.some(read => read.session === 'bob' && read.resource === resource), `Bob ${resource} was not read`)
    }
  } catch (error) {
    const browserErrors = client?.events
      .filter(event => event.method === 'Runtime.exceptionThrown' || event.method === 'Log.entryAdded')
      .slice(-20)
    throw new Error(`${error.message}\nBrowser events:\n${JSON.stringify(browserErrors, null, 2)}\nNext logs:\n${nextLogs.join('').slice(-4000)}\nChrome logs:\n${chromeLogs.join('').slice(-2000)}`)
  }
})
