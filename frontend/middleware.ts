import { NextRequest, NextResponse } from 'next/server'
import { isPublicAuthPath, loginPathFor } from './lib/auth-navigation'

const SESSION_COOKIE = '__Host-session'

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl
  if (isPublicAuthPath(pathname)) return NextResponse.next()
  if (request.cookies.has(SESSION_COOKIE)) return NextResponse.next()

  const loginUrl = request.nextUrl.clone()
  loginUrl.pathname = '/login'
  loginUrl.search = new URL(loginPathFor(pathname, search), request.url).search
  return NextResponse.redirect(loginUrl)
}

export const config = {
  matcher: ['/dashboard/:path*', '/queue/:path*', '/calibration/:path*', '/journal/:path*', '/chat/:path*', '/guide/:path*', '/stock/:path*', '/profile/:path*'],
}
