import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import http from 'node:http'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const FRONTEND_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
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


function context() {
  return {
    as_of: '2026-10-20', universe_size: 500, engines_pending: [],
    participation: {
      descriptor: 'STABLE', delta_5d: 0, delta_sample_size_20d: 20,
      metrics: {
        breadth_above_ema21: 0.5, breadth_momentum_5d: 0, highs_lows_ratio: 1.25,
        breadth_above_ema50: 0.5, breadth_above_ema200: 0.5, breadth_momentum_20d: 0,
        near_highs_count: 10, near_lows_count: 8, participation_persistence: 0.5,
      },
      breadth_comparisons: {
        date: '2026-10-20',
        new_session_highs_vs_lows: { up_count: 12, down_count: 3, eligible_symbols: 450, excluded_symbols: 50, up_ratio: 0.8 },
        up_from_open_vs_down: { up_count: 300, down_count: 100, eligible_symbols: 480, excluded_symbols: 20, up_ratio: 0.75 },
        up_4pct_vs_down_4pct: { up_count: 0, down_count: 0, eligible_symbols: 430, excluded_symbols: 70, up_ratio: null },
      },
    },
    leadership: {
      descriptor: 'HEALTHY', delta_5d: 0,
      metrics: {
        leader_count: 20, leader_density_level: 'NORMAL', leader_density_percentile: null,
        leader_density_delta_20d: 0, leader_pullback_quality_avg: 50, leader_climactic_count: 0,
        leader_density: 0.04, leader_count_delta_5d: 0, leader_count_delta_20d: 0,
        leader_density_delta_5d: 0, leader_density_sample_size: 20, leader_tightness_avg: 0,
        leader_vol_contraction_avg: 0, leader_rs_persistence_10d: 0,
        leader_extension_count: 0, leadership_turnover_5d: 0,
      },
    },
  }
}

const USER = { id: 'market-test-user', email: 'market@example.test', role: 'user', display_name: 'Market Test' }
const SESSION = { user: USER, csrf_token: 'synthetic-csrf', expires_at: '2099-01-01T00:00:00Z' }
function json(response, code, value) {
  response.writeHead(code, { 'Content-Type': 'application/json' })
  response.end(JSON.stringify(value))
}
function overviewFixture(empty = false) {
  const ctx = context()
  ctx.posture = { state: 'SELECTIVO', instruction: 'Contexto de prueba', reasons: ['Participación en recuperación'], unlock: null }
  return {
    context: ctx,
    evolution: [
      { date: '2026-10-19', breadth_ratio: 0.48, leader_count: 18 },
      { date: '2026-10-20', breadth_ratio: 0.5, leader_count: 20 },
    ],
    indices: [
      { symbol: 'SPY', price: 586.24, change_pct: 0.84, date: ctx.as_of, metrics_date: ctx.as_of, trend: 'alcista', above_ema50: true, above_ema200: true, new_high_52w: false },
      { symbol: 'QQQ', price: null, change_pct: null, date: null, metrics_date: null, trend: null, above_ema50: null, above_ema200: null, new_high_52w: null },
    ],
    extremes: {
      date: ctx.as_of, up_count: empty ? 0 : 1, down_count: empty ? 0 : 1,
      eligible_symbols: empty ? 0 : 450, excluded_symbols: empty ? 500 : 50,
      up_ratio: empty ? null : 0.5,
      sectors: empty ? [] : [{ sector: 'Tecnología', highs: [{ symbol: 'BOTH', name: 'Both Extreme Test' }], lows: [{ symbol: 'BOTH', name: 'Both Extreme Test' }] }],
    },
  }
}
const VIX = { symbol: 'VIX', price: 19.42, change_points: 0.76, change_pct: 4.07, date: '2026-10-19', source: 'Cboe', source_url: 'https://www.cboe.com/tradable_products/vix/vix_historical_data/', status: 'stale' }

test('market context page isolates evidence failures, discloses sectors and preserves session boundaries', { timeout: 120_000 }, async t => {
  const chromePath = chromeExecutable()
  assert.ok(chromePath, 'Chrome/Chromium is required for this integration test')
  const state = { overview: 'ok', vix: 'unavailable', auth: true, calls: [] }
  const api = http.createServer((request, response) => {
    const url = new URL(request.url, `http://${request.headers.host}`)
    state.calls.push(url.pathname)
    if (url.pathname === '/api/v1/auth/session') return json(response, state.auth ? 200 : 401, state.auth ? SESSION : { detail: 'Session expired' })
    if (url.pathname === '/api/v1/market-context/overview') {
      if (state.overview === 'unauthorized') { state.auth = false; return json(response, 401, { detail: 'Session expired' }) }
      if (state.overview === 'error') return json(response, 503, { detail: 'Synthetic error' })
      if (state.overview === 'missing') return json(response, 404, { detail: 'No market data available' })
      return json(response, 200, overviewFixture(state.overview === 'empty'))
    }
    if (url.pathname === '/api/v1/market-context/volatility') {
      assert.equal(url.searchParams.get('as_of'), '2026-10-20')
      if (state.vix === 'error') return json(response, 503, { detail: 'Synthetic provider error' })
      return json(response, 200, { vix: state.vix === 'ok' ? VIX : null })
    }
    if (url.pathname === '/api/v1/market-context/sector-evolution') return json(response, 200, {
      as_of: '2026-10-20', status: 'available', sessions: [
        { date: '2026-10-19', eligible_symbols: 10, excluded_symbols: 1, high_count: 2, low_count: 1, sectors: [{ sector: 'Tecnología', eligible_symbols: 10, excluded_symbols: 1, high_count: 2, low_count: 1 }] },
        { date: '2026-10-20', eligible_symbols: 10, excluded_symbols: 1, high_count: 3, low_count: 1, sectors: [{ sector: 'Tecnología', eligible_symbols: 10, excluded_symbols: 1, high_count: 3, low_count: 1 }] },
      ],
    })
    if (url.pathname === '/api/v1/health/data-freshness') return json(response, 200, {
      as_of: '2026-10-20T20:00:00Z', is_stale: false, recent_errors_24h: 0, recent_errors: [],
      pipeline_heartbeats: [], coverage: { expected: 500, actual: 500, pct: 100 },
      market_state: { is_open: false, is_warmup: false, minutes_since_open: 0, session_phase: 'closed' }, warnings: [],
    })
    return json(response, 404, { detail: 'Unhandled fixture endpoint' })
  })
  const apiPort = await freePort(), appPort = await freePort(), debugPort = await freePort()
  await new Promise((resolve, reject) => api.listen(apiPort, '127.0.0.1', resolve).once('error', reject))
  const profileDir = await mkdtemp(path.join(os.tmpdir(), 'market-context-browser-'))
  // Already present in tsconfig: avoids Next modifying tracked configuration.
  const nextDistDir = '.next-pipeline-health-e2e'
  const nextLogs = []
  const next = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'dev', '--webpack', '--hostname', '127.0.0.1', '--port', String(appPort)], {
    cwd: FRONTEND_DIR, env: { ...process.env, API_PROXY_TARGET: `http://127.0.0.1:${apiPort}`, NEXT_TELEMETRY_DISABLED: '1', NEXT_DIST_DIR: nextDistDir }, stdio: ['ignore', 'pipe', 'pipe'],
  })
  next.stdout.on('data', chunk => nextLogs.push(String(chunk)))
  next.stderr.on('data', chunk => nextLogs.push(String(chunk)))
  const chrome = spawn(chromePath, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', `--remote-debugging-port=${debugPort}`, `--user-data-dir=${profileDir}`, 'about:blank'], { stdio: 'ignore' })
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
    await waitForHttp(`http://127.0.0.1:${appPort}/market-context`)
    await waitForHttp(`http://127.0.0.1:${debugPort}/json/version`)
    const targets = await fetch(`http://127.0.0.1:${debugPort}/json`).then(r => r.json())
    client = new CdpClient(targets.find(target => target.type === 'page').webSocketDebuggerUrl)
    await client.open()
    await client.send('Page.enable')
    await client.send('Runtime.enable')
    await client.send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 1000, deviceScaleFactor: 1, mobile: false })
    const anonymous = await fetch(`http://127.0.0.1:${appPort}/market-context`, { redirect: 'manual' })
    assert.equal(anonymous.status, 307)
    assert.match(anonymous.headers.get('location'), /login\?returnTo=%2Fmarket-context/)
    const cookie = await client.send('Network.setCookie', { name: '__Host-session', value: 'synthetic-market-session', url: `http://127.0.0.1:${appPort}`, path: '/', secure: true, httpOnly: true, sameSite: 'Lax' })
    assert.equal(cookie.success, true)
    await client.send('Page.navigate', { url: `http://127.0.0.1:${appPort}/market-context` })
    const bodyHas = text => `document.body.innerText.includes(${JSON.stringify(text)})`
    const click = text => client.evaluate(`(() => {const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(text)}); if(!b)throw Error('Button not found'); b.click()})()`)
    await waitForEvaluation(client, bodyHas('VIX no disponible'), 'independent missing VIX')
    const sectionIds = await client.evaluate(`[...document.querySelectorAll('nav[aria-label="Índice de Market Context"] a')].map(a=>a.getAttribute('href'))`)
    assert.deepEqual(sectionIds, ['#lectura-actual', '#cambios-alertas', '#indices-volatilidad', '#participacion-sectores', '#evolucion-continuidad'])
    await client.evaluate(`document.querySelector('a[href="#participacion-sectores"]').focus()`)
    await client.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
    await client.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
    await waitForEvaluation(client, `location.hash==='#participacion-sectores' && document.querySelector('a[href="#participacion-sectores"]').getAttribute('aria-current')==='location'`, 'keyboard section navigation')
    await client.send('Page.navigate', { url: `http://127.0.0.1:${appPort}/market-context#evolucion-continuidad` })
    await waitForEvaluation(client, `document.querySelector('a[href="#evolucion-continuidad"]')?.getAttribute('aria-current')==='location'`, 'direct section link')
    assert.equal(await client.evaluate(`(() => { const title=document.getElementById('evolucion-continuidad-title'); const nav=document.querySelector('nav[aria-label="Índice de Market Context"]'); const box=title.getBoundingClientRect(); return box.top >= nav.getBoundingClientRect().bottom && box.top < window.innerHeight })()`), true, 'deep-link destination title is visible below the sticky index')
    assert.equal(await client.evaluate(`document.querySelectorAll('nav[aria-label="Índice de Market Context"] a[aria-current="location"]').length`), 1)
    await client.evaluate(`(() => { const target=document.getElementById('indices-volatilidad'); const nav=document.querySelector('nav[aria-label="Índice de Market Context"]'); window.scrollTo(0, window.scrollY + target.getBoundingClientRect().top - nav.getBoundingClientRect().bottom - 30) })()`)
    await waitForEvaluation(client, `document.querySelector('a[href="#indices-volatilidad"]')?.getAttribute('aria-current')==='location'`, 'active section follows manual scrolling')
    assert.equal(await client.evaluate(`document.documentElement.scrollWidth <= window.innerWidth`), true)
    assert.equal(await client.evaluate(bodyHas('586.24')), true)
    assert.equal(await client.evaluate(bodyHas('Precio < máximo de cierres (52 semanas)')), true)
    assert.equal(await client.evaluate(bodyHas('Inspeccionar sesión')), true)
    const globalEvidence = await client.evaluate(`({ header: document.querySelector('header').innerText, posture: document.querySelector('#lectura-actual').innerText })`)
    const relevantCallsBefore = state.calls.filter(path => path.startsWith('/api/v1/market-context/')).length
    await client.evaluate(`(() => { const select=document.querySelector('#market-evolution-session'); select.value='2026-10-19'; select.dispatchEvent(new Event('change',{bubbles:true})) })()`)
    await waitForEvaluation(client, `document.querySelector('#market-evolution-session').value==='2026-10-19'`, 'historical series selection')
    assert.deepEqual(await client.evaluate(`({ header: document.querySelector('header').innerText, posture: document.querySelector('#lectura-actual').innerText })`), globalEvidence, 'historical selection remains local to the series')
    assert.equal(state.calls.filter(path => path.startsWith('/api/v1/market-context/')).length, relevantCallsBefore, 'historical selection does not request another global context')
    assert.equal(await client.evaluate(bodyHas('Extremos de la sesión')), true)
    assert.equal(await client.evaluate(`(() => { const root=document.querySelector('[aria-labelledby="sector-evolution-title"]'); return root && root.innerText.indexOf('Sectores con máximos') < root.innerText.indexOf('Tasas y cobertura al') })()`), true)
    await client.evaluate(`[...document.querySelectorAll('button')].find(button=>button.textContent.trim()==='Tecnología').click()`)
    assert.equal(await client.evaluate(bodyHas('Historial de Tecnología')), true)
    assert.equal(await client.evaluate(bodyHas('Sin datos')), true)
    const nav = await client.evaluate(`[...document.querySelectorAll('nav a')].map(a=>a.textContent.trim())`)
    assert.equal(nav[nav.indexOf('Dashboard') + 1], 'Market context')
    assert.equal(state.calls.includes('/api/v1/market-context/current'), false)
    await client.evaluate(`[...document.querySelectorAll('summary')].find(s=>s.textContent.includes('Tecnología')).click()`)
    await waitForEvaluation(client, `document.querySelectorAll('a[href="/stock/BOTH"]').length===2`, 'both sides of a dual extreme')
    assert.equal(await client.evaluate(`document.querySelector('a[href="/stock/BOTH"]').checkVisibility()`), true)
    state.vix = 'ok'
    await click('Actualizar VIX')
    await waitForEvaluation(client, bodyHas('19.42'), 'VIX recovery')
    assert.equal(await client.evaluate(bodyHas('2026-10-19')), true)
    for (const width of [1280, 768]) {
      await client.send('Emulation.setDeviceMetricsOverride', { width, height: 1000, deviceScaleFactor: 1, mobile: false })
      assert.equal(await client.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), true, `No page overflow at ${width}px`)
      assert.equal(await client.evaluate(`(() => { const nav=document.querySelector('nav[aria-label="Índice de Market Context"]'); const links=[...nav.querySelectorAll('a')]; const box=nav.getBoundingClientRect(); return links.length===5 && links.every(link=>{const item=link.getBoundingClientRect(); return item.left>=box.left && item.right<=box.right && item.top>=box.top && item.bottom<=box.bottom}) })()`), true, `All five index links fit within the navigation at ${width}px`)
      await client.evaluate(`document.querySelector('a[href="#participacion-sectores"]').click()`)
      await waitForEvaluation(client, `document.querySelector('a[href="#participacion-sectores"]')?.getAttribute('aria-current')==='location'`, `navigation at ${width}px`)
      assert.equal(await client.evaluate(`(() => { const title=document.getElementById('participacion-sectores-title'); const nav=document.querySelector('nav[aria-label="Índice de Market Context"]'); const box=title.getBoundingClientRect(); return box.top>=nav.getBoundingClientRect().bottom && box.top<window.innerHeight })()`), true, `Destination title is visible at ${width}px`)
    }
    if (process.env.MARKET_CONTEXT_SCREENSHOT) {
      await client.send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 1200, deviceScaleFactor: 1, mobile: false })
      await client.evaluate('window.scrollTo(0, 0)')
      await waitForEvaluation(client, 'window.scrollY===0', 'desktop screenshot at page top')
      const screenshot = await client.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
      await writeFile(process.env.MARKET_CONTEXT_SCREENSHOT, Buffer.from(screenshot.data, 'base64'))
      await client.send('Emulation.setDeviceMetricsOverride', { width: 768, height: 1024, deviceScaleFactor: 1, mobile: false })
      await client.evaluate('window.scrollTo(0, 0)')
      await waitForEvaluation(client, 'window.scrollY===0', 'tablet screenshot at page top')
      const tabletScreenshot = await client.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
      const tabletPath = process.env.MARKET_CONTEXT_SCREENSHOT.replace(/(\.[^.]+)$/, '-tablet$1')
      await writeFile(tabletPath, Buffer.from(tabletScreenshot.data, 'base64'))
    }
    state.overview = 'error'
    await click('Actualizar contexto')
    await waitForEvaluation(client, bodyHas('No se pudo actualizar el contexto'), 'refresh error')
    assert.equal(await client.evaluate(bodyHas('586.24')), true, 'retain dated internal evidence on transient refresh failure')
    state.overview = 'empty'
    await click('Actualizar contexto')
    await waitForEvaluation(client, bodyHas('Sin cobertura suficiente'), 'no annual history')
    state.vix = 'error'
    await click('Actualizar VIX')
    await waitForEvaluation(client, bodyHas('No se pudo actualizar VIX'), 'volatility error independent from overview')
    assert.equal(await client.evaluate(bodyHas('Participación')), true)
    state.overview = 'missing'
    await client.send('Page.reload', { ignoreCache: true })
    await waitForEvaluation(client, bodyHas('Aún no hay contexto'), 'empty context response')
    state.overview = 'ok'
    await click('Actualizar contexto')
    await waitForEvaluation(client, bodyHas('586.24'), 'context retry recovery')
    state.overview = 'unauthorized'
    await click('Actualizar contexto')
    await waitForEvaluation(client, `location.pathname === '/login'`, 'expired session redirect')
    assert.equal(await client.evaluate(bodyHas('586.24')), false, 'private context removed after session loss')
    const errors = client.events.filter(event => event.method === 'Runtime.exceptionThrown')
    assert.deepEqual(errors, [])
  } catch (error) {
    throw new Error(`${error.stack}\nNext logs:\n${nextLogs.join('').slice(-5000)}`)
  }
})
