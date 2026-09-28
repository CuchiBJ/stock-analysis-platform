'use client'

import Link from 'next/link'
import { FormEvent, useState } from 'react'
import { AuthShell, buttonClassName, FormMessage, inputClassName } from '@/components/auth/AuthShell'
import { apiJson, ApiError } from '@/lib/api-client'
import { validatePassword } from '@/lib/auth-validation'

export default function ResetPasswordPage() {
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const token = new URLSearchParams(window.location.search).get('token') ?? ''
    const passwordError = validatePassword(password)
    if (!token) return setError('This reset link is missing its token.')
    if (passwordError) return setError(passwordError)
    if (password !== confirmPassword) return setError('Passwords do not match.')
    setBusy(true); setError('')
    try {
      const result = await apiJson<{ message: string }>('/api/v1/auth/reset-password', { method: 'POST', body: JSON.stringify({ token, new_password: password }) })
      setMessage(result.message)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Unable to reset the password.')
    } finally { setBusy(false) }
  }

  return (
    <AuthShell title="Choose a new password" description="Your existing sessions will be revoked after a successful reset." footer={<Link className="underline" href="/login">Back to sign in</Link>}>
      {message ? <div className="space-y-4"><FormMessage kind="success">{message}</FormMessage><Link href="/login" className={buttonClassName + ' block text-center'}>Sign in</Link></div> : <form onSubmit={submit} noValidate className="space-y-4">
        {error && <FormMessage kind="error">{error}</FormMessage>}
        <label className="block text-sm font-medium" htmlFor="password">New password<input id="password" type="password" autoComplete="new-password" className={inputClassName} value={password} onChange={(event) => setPassword(event.target.value)} disabled={busy} /></label>
        <label className="block text-sm font-medium" htmlFor="confirm-password">Confirm password<input id="confirm-password" type="password" autoComplete="new-password" className={inputClassName} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} disabled={busy} /></label>
        <button className={buttonClassName} type="submit" disabled={busy}>{busy ? 'Updating…' : 'Update password'}</button>
      </form>}
    </AuthShell>
  )
}
