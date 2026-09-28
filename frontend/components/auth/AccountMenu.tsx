'use client'

import Link from 'next/link'
import { LogOut, UserRound } from 'lucide-react'
import { useState } from 'react'
import { useAuth } from './AuthProvider'

export default function AccountMenu() {
  const { user, logout } = useAuth()
  const [busy, setBusy] = useState(false)
  if (!user) return null

  const signOut = async () => {
    setBusy(true)
    try {
      await logout()
    } finally {
      setBusy(false)
    }
  }

  return (
    <details className="relative">
      <summary className="flex cursor-pointer list-none items-center gap-2 rounded border border-border px-3 py-2 text-sm hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring">
        <UserRound aria-hidden="true" className="h-4 w-4" />
        <span className="max-w-40 truncate">{user.display_name}</span>
      </summary>
      <div className="absolute right-0 z-50 mt-2 w-56 rounded border border-border bg-card p-2 shadow-xl">
        <p className="truncate px-2 py-1 text-xs text-muted-foreground">{user.email}</p>
        <Link href="/profile" className="block rounded px-2 py-2 text-sm hover:bg-muted">Profile</Link>
        <button
          type="button"
          onClick={signOut}
          disabled={busy}
          className="flex w-full items-center gap-2 rounded px-2 py-2 text-left text-sm hover:bg-muted disabled:opacity-60"
        >
          <LogOut aria-hidden="true" className="h-4 w-4" />
          {busy ? 'Signing out…' : 'Sign out'}
        </button>
      </div>
    </details>
  )
}
