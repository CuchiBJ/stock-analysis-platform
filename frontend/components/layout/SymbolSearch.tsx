'use client'

import { useState, FormEvent } from 'react'
import { useRouter } from 'next/navigation'
import { Search } from 'lucide-react'

export default function SymbolSearch() {
  const [value, setValue] = useState('')
  const router = useRouter()

  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    e.stopPropagation()
    const t = value.trim().toUpperCase()
    if (!t) return
    router.push(`/stock/${t}`)
    setValue('')
  }

  return (
    <form
      onSubmit={onSubmit}
      role="search"
      className="flex items-center gap-1.5 px-2 py-1 rounded border border-border bg-card/50 focus-within:border-foreground/30 transition-colors"
    >
      <Search className="w-3.5 h-3.5 text-muted-foreground" />
      <input
        type="text"
        name="symbol-search"
        value={value}
        onChange={e => setValue(e.target.value)}
        placeholder="Symbol…"
        className="bg-transparent border-0 outline-none text-xs w-24 placeholder:text-muted-foreground/50 uppercase tracking-wide"
        spellCheck={false}
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="characters"
      />
    </form>
  )
}
