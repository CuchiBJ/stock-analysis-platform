'use client'

import Link from 'next/link'
import { FormEvent, useEffect, useRef, useState } from 'react'
import { AuthShell, buttonClassName, FormMessage, inputClassName } from '@/components/auth/AuthShell'
import { apiJson, ApiError } from '@/lib/api-client'
import { validateEmail } from '@/lib/auth-validation'

export default function VerifyEmailPage() {
  const attemptedToken = useRef<string | null>(null)
  const [email, setEmail] = useState('')
  const [state, setState] = useState<'idle' | 'verifying' | 'verified' | 'invalid' | 'resent'>('idle')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get('token')
    if (!token || attemptedToken.current === token) return
    attemptedToken.current = token
    setState('verifying')
    apiJson<{ message: string }>('/api/v1/auth/verify-email', { method: 'POST', body: JSON.stringify({ token }) })
      .then(() => setState('verified'))
      .catch(() => setState('invalid'))
  }, [])

  const resend = async (event: FormEvent) => {
    event.preventDefault()
    const validationError = validateEmail(email)
    if (validationError) return setError(validationError)
    setBusy(true); setError('')
    try {
      await apiJson('/api/v1/auth/resend-verification', { method: 'POST', body: JSON.stringify({ email: email.trim() }) })
      setState('resent')
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Unable to submit the request.')
    } finally { setBusy(false) }
  }

  return (
    <AuthShell title="Verify your email" description="Verification is required before signing in." footer={<Link className="underline" href="/login">Back to sign in</Link>}>
      {state === 'verifying' && <p role="status" className="text-sm text-muted-foreground">Verifying your link…</p>}
      {state === 'verified' && <div className="space-y-4"><FormMessage kind="success">Email verified. You can now sign in.</FormMessage><Link href="/login" className={buttonClassName + ' block text-center'}>Sign in</Link></div>}
      {state === 'resent' && <FormMessage kind="success">If the account is eligible, an email has been sent.</FormMessage>}
      {(state === 'idle' || state === 'invalid') && <form onSubmit={resend} noValidate className="space-y-4">
        {state === 'invalid' && <FormMessage kind="error">This verification link is invalid or expired. You can request another.</FormMessage>}
        {error && <FormMessage kind="error">{error}</FormMessage>}
        <label className="block text-sm font-medium" htmlFor="email">Email<input id="email" type="email" autoComplete="email" className={inputClassName} value={email} onChange={(event) => setEmail(event.target.value)} disabled={busy} /></label>
        <button className={buttonClassName} type="submit" disabled={busy}>{busy ? 'Sending…' : 'Resend verification email'}</button>
      </form>}
    </AuthShell>
  )
}
