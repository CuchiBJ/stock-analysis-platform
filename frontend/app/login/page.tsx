'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { FormEvent, useEffect, useState } from 'react'
import { AuthShell, buttonClassName, FormMessage, inputClassName } from '@/components/auth/AuthShell'
import { safePostLoginPath, useAuth } from '@/components/auth/AuthProvider'
import { ApiError } from '@/lib/api-client'
import { validateEmail } from '@/lib/auth-validation'

export default function LoginPage() {
  const router = useRouter()
  const { login, status } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (status !== 'authenticated') return
    const returnTo = new URLSearchParams(window.location.search).get('returnTo')
    router.replace(safePostLoginPath(returnTo))
  }, [router, status])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const emailError = validateEmail(email)
    if (emailError) return setError(emailError)
    setBusy(true)
    setError('')
    try {
      await login(email, password)
      const returnTo = new URLSearchParams(window.location.search).get('returnTo')
      router.replace(safePostLoginPath(returnTo))
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Unable to sign in. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell
      title="Sign in"
      description="Access your private trading workspace."
      footer={<span>New here? <Link className="text-foreground underline" href="/register">Create an account</Link></span>}
    >
      <form onSubmit={submit} noValidate className="space-y-4">
        {error && <FormMessage kind="error">{error}</FormMessage>}
        <label className="block text-sm font-medium" htmlFor="email">Email
          <input id="email" name="email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} className={inputClassName} disabled={busy} />
        </label>
        <label className="block text-sm font-medium" htmlFor="password">Password
          <input id="password" name="password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} className={inputClassName} disabled={busy} />
        </label>
        <div className="text-right"><Link href="/forgot-password" className="text-sm underline">Forgot password?</Link></div>
        <button className={buttonClassName} disabled={busy} type="submit">{busy ? 'Signing in…' : 'Sign in'}</button>
      </form>
    </AuthShell>
  )
}
