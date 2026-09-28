'use client'

import Link from 'next/link'
import { FormEvent, useState } from 'react'
import { AuthShell, buttonClassName, FormMessage, inputClassName } from '@/components/auth/AuthShell'
import { apiJson, ApiError } from '@/lib/api-client'
import { validateEmail } from '@/lib/auth-validation'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const validationError = validateEmail(email)
    if (validationError) return setError(validationError)
    setBusy(true); setError('')
    try {
      const result = await apiJson<{ message: string }>('/api/v1/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email: email.trim() }) })
      setMessage(result.message)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Unable to submit the request.')
    } finally { setBusy(false) }
  }

  return (
    <AuthShell title="Reset your password" description="We will send recovery instructions when the account is eligible." footer={<Link className="underline" href="/login">Back to sign in</Link>}>
      {message ? <FormMessage kind="success">{message}</FormMessage> : <form onSubmit={submit} noValidate className="space-y-4">
        {error && <FormMessage kind="error">{error}</FormMessage>}
        <label className="block text-sm font-medium" htmlFor="email">Email<input id="email" type="email" autoComplete="email" className={inputClassName} value={email} onChange={(event) => setEmail(event.target.value)} disabled={busy} /></label>
        <button className={buttonClassName} type="submit" disabled={busy}>{busy ? 'Sending…' : 'Send recovery instructions'}</button>
      </form>}
    </AuthShell>
  )
}
