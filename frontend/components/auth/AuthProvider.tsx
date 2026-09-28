'use client'

import { useQueryClient } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { apiFetch, apiJson, onSessionLost, registerSessionCleanup, runSessionCleanup, setSessionCsrfToken } from '@/lib/api-client'
import { isPublicAuthPath, loginPathFor, sanitizeReturnPath } from '@/lib/auth-navigation'
import { clearUserPrivateStorage } from '@/lib/private-state'

export interface CurrentUser {
  id: string
  email: string
  role: 'user' | 'admin'
  display_name: string
}

export interface Session {
  user: CurrentUser
  csrf_token: string
  expires_at: string
}

type SessionStatus = 'loading' | 'authenticated' | 'unauthenticated'

interface AuthContextValue {
  session: Session | null
  user: CurrentUser | null
  status: SessionStatus
  refreshSession: () => Promise<Session | null>
  login: (email: string, password: string) => Promise<Session>
  logout: () => Promise<void>
  updateCurrentUser: (user: CurrentUser) => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient()
  const router = useRouter()
  const [session, setSession] = useState<Session | null>(null)
  const [status, setStatus] = useState<SessionStatus>('loading')
  const userIdRef = useRef<string | null>(null)

  const clearIdentity = useCallback(() => {
    userIdRef.current = null
    setSessionCsrfToken(null)
    setSession(null)
    setStatus('unauthenticated')
  }, [])

  useEffect(() => registerSessionCleanup(async () => {
    const userId = userIdRef.current
    if (!userId) return
    await queryClient.cancelQueries({ queryKey: ['private', userId] })
    queryClient.removeQueries({ queryKey: ['private', userId] })
    clearUserPrivateStorage(userId)
  }), [queryClient])

  useEffect(() => onSessionLost(() => {
    clearIdentity()
    const pathname = window.location.pathname
    if (!isPublicAuthPath(pathname)) {
      router.replace(loginPathFor(pathname, window.location.search))
    }
  }), [clearIdentity, router])

  const establishSession = useCallback((nextSession: Session) => {
    userIdRef.current = nextSession.user.id
    setSessionCsrfToken(nextSession.csrf_token)
    setSession(nextSession)
    setStatus('authenticated')
    return nextSession
  }, [])

  const refreshSession = useCallback(async () => {
    try {
      const nextSession = await apiJson<Session>('/api/v1/auth/session')
      return establishSession(nextSession)
    } catch {
      clearIdentity()
      return null
    }
  }, [clearIdentity, establishSession])

  useEffect(() => {
    queueMicrotask(() => void refreshSession())
  }, [refreshSession])

  const login = useCallback(async (email: string, password: string) => {
    const nextSession = await apiJson<Session>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
      handleUnauthorized: false,
    })
    return establishSession(nextSession)
  }, [establishSession])

  const logout = useCallback(async () => {
    try {
      await apiFetch('/api/v1/auth/logout', { method: 'POST', handleUnauthorized: false })
    } finally {
      await runSessionCleanup()
      clearIdentity()
      router.replace('/login')
      router.refresh()
    }
  }, [clearIdentity, router])

  const updateCurrentUser = useCallback((user: CurrentUser) => {
    userIdRef.current = user.id
    setSession((current) => current ? { ...current, user } : current)
  }, [])

  const value = useMemo<AuthContextValue>(() => ({
    session,
    user: session?.user ?? null,
    status,
    refreshSession,
    login,
    logout,
    updateCurrentUser,
  }), [session, status, refreshSession, login, logout, updateCurrentUser])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}

export function ProtectedContent({ children }: { children: React.ReactNode }) {
  const { status } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (status !== 'unauthenticated') return
    router.replace(loginPathFor(window.location.pathname, window.location.search))
  }, [router, status])

  if (status === 'loading') {
    return <div className="min-h-screen grid place-items-center text-sm text-muted-foreground" role="status">Loading your account…</div>
  }
  if (status === 'unauthenticated') return null
  return children
}

export function safePostLoginPath(value: string | null): string {
  return sanitizeReturnPath(value)
}
