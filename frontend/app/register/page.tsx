'use client'

import Link from 'next/link'
import { FormEvent, useState } from 'react'
import { AuthShell, buttonClassName, FormMessage, inputClassName } from '@/components/auth/AuthShell'
import { apiJson, ApiError } from '@/lib/api-client'
import { AuthFieldErrors, validateRegistration } from '@/lib/auth-validation'

export default function RegisterPage() {
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<AuthFieldErrors>({})
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const nextErrors = validateRegistration({ displayName, email, password })
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length) return
    setBusy(true)
    try {
      const result = await apiJson<{ message: string }>('/api/v1/auth/register', {
        method: 'POST',
        body: JSON.stringify({ display_name: displayName.trim(), email: email.trim(), password }),
      })
      setMessage(result.message)
    } catch (caught) {
      setErrors({ form: caught instanceof ApiError ? caught.message : 'Unable to submit your registration.' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title="Create your account" description="Your journal and profile will remain private to this account." footer={<span>Already registered? <Link className="text-foreground underline" href="/login">Sign in</Link></span>}>
      {message ? (
        <div className="space-y-4"><FormMessage kind="success">{message}</FormMessage><p className="text-sm text-muted-foreground">Check your inbox if an eligible account can be verified.</p><Link className="block text-center text-sm underline" href="/verify-email">Verify or resend email</Link></div>
      ) : (
        <form onSubmit={submit} noValidate className="space-y-4">
          {errors.form && <FormMessage kind="error">{errors.form}</FormMessage>}
          <label className="block text-sm font-medium" htmlFor="display-name">Display name
            <input id="display-name" autoComplete="name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} className={inputClassName} aria-describedby={errors.displayName ? 'display-name-error' : undefined} disabled={busy} />
          </label>
          {errors.displayName && <p id="display-name-error" className="text-sm text-destructive">{errors.displayName}</p>}
          <label className="block text-sm font-medium" htmlFor="email">Email
            <input id="email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} className={inputClassName} aria-describedby={errors.email ? 'email-error' : undefined} disabled={busy} />
          </label>
          {errors.email && <p id="email-error" className="text-sm text-destructive">{errors.email}</p>}
          <label className="block text-sm font-medium" htmlFor="password">Password
            <input id="password" type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} className={inputClassName} aria-describedby="password-help" disabled={busy} />
          </label>
          <p id="password-help" className={errors.password ? 'text-sm text-destructive' : 'text-xs text-muted-foreground'}>{errors.password ?? 'Use at least 12 characters.'}</p>
          <button className={buttonClassName} disabled={busy} type="submit">{busy ? 'Creating account…' : 'Create account'}</button>
        </form>
      )}
    </AuthShell>
  )
}
