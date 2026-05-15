'use client'

import { useState, useEffect } from 'react'
import Link from "next/link"

export default function WatchlistsPage() {
  const [watchlists, setWatchlists] = useState<any[]>([])
  const [newWatchlistName, setNewWatchlistName] = useState('')
  const [newWatchlistSymbols, setNewWatchlistSymbols] = useState('')

  useEffect(() => {
    fetchWatchlists()
  }, [])

  const fetchWatchlists = async () => {
    try {
      const response = await fetch('/api/v1/watchlists')
      const data = await response.json()
      setWatchlists(data)
    } catch (error) {
      console.error('Error fetching watchlists:', error)
    }
  }

  const createWatchlist = async () => {
    if (!newWatchlistName || !newWatchlistSymbols) return

    try {
      const symbols = newWatchlistSymbols.split(',').map(s => s.trim().toUpperCase())
      await fetch('/api/v1/watchlists', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newWatchlistName, symbols })
      })
      setNewWatchlistName('')
      setNewWatchlistSymbols('')
      fetchWatchlists()
    } catch (error) {
      console.error('Error creating watchlist:', error)
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <nav className="border-b border-border">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <Link href="/" className="text-xl font-bold">Stock Analysis</Link>
            <div className="flex gap-4">
              <Link href="/dashboard" className="text-muted-foreground hover:text-foreground">
                Dashboard
              </Link>
              <Link href="/scanner" className="text-muted-foreground hover:text-foreground">
                Scanner
              </Link>
              <Link href="/watchlists" className="text-foreground">Watchlists</Link>
            </div>
          </div>
        </div>
      </nav>

      <main className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-8">Watchlists</h1>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <div className="bg-card border border-border rounded-lg p-6">
            <h2 className="text-lg font-bold mb-4">Create Watchlist</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-muted-foreground mb-2">Name</label>
                <input
                  type="text"
                  value={newWatchlistName}
                  onChange={(e) => setNewWatchlistName(e.target.value)}
                  className="w-full px-3 py-2 bg-muted border border-border rounded"
                  placeholder="My Watchlist"
                />
              </div>
              <div>
                <label className="block text-sm text-muted-foreground mb-2">Symbols (comma separated)</label>
                <textarea
                  value={newWatchlistSymbols}
                  onChange={(e) => setNewWatchlistSymbols(e.target.value)}
                  className="w-full px-3 py-2 bg-muted border border-border rounded h-24"
                  placeholder="AAPL, MSFT, GOOGL"
                />
              </div>
              <button
                onClick={createWatchlist}
                className="w-full px-4 py-2 bg-primary text-primary-foreground rounded hover:opacity-90"
              >
                Create Watchlist
              </button>
            </div>
          </div>

          <div className="lg:col-span-2">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {watchlists.map((watchlist) => (
                <div key={watchlist.id} className="bg-card border border-border rounded-lg p-6">
                  <h3 className="text-lg font-bold mb-2">{watchlist.name}</h3>
                  <div className="text-sm text-muted-foreground mb-4">
                    {watchlist.symbols.length} symbols
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {watchlist.symbols.slice(0, 5).map((symbol: string) => (
                      <span key={symbol} className="px-2 py-1 bg-muted rounded text-sm">
                        {symbol}
                      </span>
                    ))}
                    {watchlist.symbols.length > 5 && (
                      <span className="px-2 py-1 bg-muted rounded text-sm">
                        +{watchlist.symbols.length - 5} more
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
