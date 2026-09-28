export const PUBLIC_AUTH_PATHS = [
  '/login',
  '/register',
  '/verify-email',
  '/forgot-password',
  '/reset-password',
] as const

const CONTROL_CHARACTERS = /[\u0000-\u001f\u007f]/

export function sanitizeReturnPath(value: string | null | undefined, fallback = '/dashboard'): string {
  if (!value || CONTROL_CHARACTERS.test(value) || value.includes('\\')) return fallback
  if (!value.startsWith('/') || value.startsWith('//')) return fallback

  try {
    const decoded = decodeURIComponent(value)
    if (!decoded.startsWith('/') || decoded.startsWith('//') || decoded.includes('\\')) return fallback
    const parsed = new URL(value, 'https://local.invalid')
    if (parsed.origin !== 'https://local.invalid') return fallback
    if (PUBLIC_AUTH_PATHS.some((path) => parsed.pathname === path)) return fallback
    return `${parsed.pathname}${parsed.search}${parsed.hash}`
  } catch {
    return fallback
  }
}

export function loginPathFor(pathname: string, search = ''): string {
  const returnPath = sanitizeReturnPath(`${pathname}${search}`)
  return `/login?returnTo=${encodeURIComponent(returnPath)}`
}

export function isPublicAuthPath(pathname: string): boolean {
  return PUBLIC_AUTH_PATHS.some((path) => pathname === path || pathname.startsWith(`${path}/`))
}
