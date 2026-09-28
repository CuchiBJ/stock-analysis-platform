'use client'

import { FormEvent, useEffect, useState } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { buttonClassName, FormMessage, inputClassName } from '@/components/auth/AuthShell'
import { CurrentUser, useAuth } from '@/components/auth/AuthProvider'
import { apiJson, ApiError } from '@/lib/api-client'
import { validateDisplayName } from '@/lib/auth-validation'

interface ProfileResponse {
  user_id: string
  email: string
  role: 'user' | 'admin'
  display_name: string
  created_at: string
  updated_at: string
}

export default function ProfilePage() {
  const { user, updateCurrentUser } = useAuth()
  const [profile, setProfile] = useState<ProfileResponse | null>(null)
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!user) return
    apiJson<ProfileResponse>('/api/v1/profile')
      .then((value) => { setProfile(value); setDisplayName(value.display_name) })
      .catch((caught) => setError(caught instanceof ApiError ? caught.message : 'Unable to load your profile.'))
  }, [user])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const validationError = validateDisplayName(displayName)
    if (validationError) return setError(validationError)
    setBusy(true); setError(''); setMessage('')
    try {
      const updated = await apiJson<ProfileResponse>('/api/v1/profile', { method: 'PATCH', body: JSON.stringify({ display_name: displayName.trim() }) })
      setProfile(updated)
      const currentUser: CurrentUser = { id: updated.user_id, email: updated.email, role: updated.role, display_name: updated.display_name }
      updateCurrentUser(currentUser)
      setMessage('Profile updated.')
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Unable to update your profile.')
    } finally { setBusy(false) }
  }

  return (
    <DashboardLayout>
      <section className="mx-auto max-w-2xl" aria-labelledby="profile-title">
        <h1 id="profile-title" className="text-2xl font-semibold">Profile</h1>
        <p className="mt-2 text-sm text-muted-foreground">Manage the name shown in your account menu.</p>
        <div className="mt-6 rounded border border-border bg-card p-6">
          {error && <div className="mb-4"><FormMessage kind="error">{error}</FormMessage></div>}
          {message && <div className="mb-4"><FormMessage kind="success">{message}</FormMessage></div>}
          {!profile ? <p role="status" className="text-sm text-muted-foreground">Loading profile…</p> : <form onSubmit={submit} noValidate className="space-y-5">
            <label className="block text-sm font-medium" htmlFor="display-name">Display name<input id="display-name" autoComplete="name" className={inputClassName} value={displayName} onChange={(event) => setDisplayName(event.target.value)} disabled={busy} /></label>
            <div><span className="text-sm font-medium">Email</span><p className="mt-1 text-sm text-muted-foreground">{profile.email}</p></div>
            <div><span className="text-sm font-medium">Role</span><p className="mt-1 text-sm capitalize text-muted-foreground">{profile.role}</p></div>
            <button type="submit" disabled={busy} className={buttonClassName + ' sm:w-auto'}>{busy ? 'Saving…' : 'Save profile'}</button>
          </form>}
        </div>
      </section>
    </DashboardLayout>
  )
}
