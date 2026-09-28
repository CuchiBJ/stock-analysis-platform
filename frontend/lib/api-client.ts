const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/$/, '')
const MUTATION_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

let csrfToken: string | null = null
const sessionLostListeners = new Set<() => void>()
const sessionCleanupListeners = new Set<() => void | Promise<void>>()

export interface ApiRequestInit extends RequestInit {
  handleUnauthorized?: boolean
}

export class ApiError extends Error {
  readonly status: number
  readonly response: Response

  constructor(
    status: number,
    message: string,
    response: Response,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.response = response
  }
}

function requestUrl(path: string): string {
  // Browser traffic stays on the canonical origin so secure session cookies are
  // never coupled to a JavaScript-visible host configuration.
  if (typeof window !== 'undefined') {
    const target = new URL(path, window.location.origin)
    if (target.origin !== window.location.origin) {
      throw new TypeError('Authenticated API requests must stay on the current origin')
    }
    return `${target.pathname}${target.search}${target.hash}`
  }
  if (/^https?:\/\//i.test(path)) return path
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`
}

export function setSessionCsrfToken(token: string | null): void {
  csrfToken = token
}

export function onSessionLost(listener: () => void): () => void {
  sessionLostListeners.add(listener)
  return () => sessionLostListeners.delete(listener)
}

export function registerSessionCleanup(listener: () => void | Promise<void>): () => void {
  sessionCleanupListeners.add(listener)
  return () => sessionCleanupListeners.delete(listener)
}

export async function runSessionCleanup(): Promise<void> {
  await Promise.allSettled([...sessionCleanupListeners].map((listener) => listener()))
}

export async function apiFetch(path: string, init: ApiRequestInit = {}): Promise<Response> {
  const { handleUnauthorized = true, ...requestInit } = init
  const method = (requestInit.method ?? 'GET').toUpperCase()
  const headers = new Headers(requestInit.headers)

  if (csrfToken && MUTATION_METHODS.has(method) && !headers.has('X-CSRF-Token')) {
    headers.set('X-CSRF-Token', csrfToken)
  }

  const response = await fetch(requestUrl(path), {
    ...requestInit,
    method,
    headers,
    credentials: 'include',
  })

  if (response.status === 401 && handleUnauthorized) {
    setSessionCsrfToken(null)
    await runSessionCleanup()
    sessionLostListeners.forEach((listener) => listener())
  }

  return response
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const payload = await response.clone().json() as { detail?: string; message?: string }
    return payload.detail ?? payload.message ?? `Request failed (${response.status}).`
  } catch {
    return `Request failed (${response.status}).`
  }
}

export async function apiJson<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await apiFetch(path, { ...init, headers })
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response), response)
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
