'use client'

import { useState } from 'react'
import Link from "next/link"

export default function ScannerPage() {
  const [scanType, setScanType] = useState('breakout')
  const [results, setResults] = useState<any[]>([])

  const runScan = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/scanners/${scanType}?limit=50`)
      const data = await response.json()
      // Handle both array response and object with results property
      setResults(Array.isArray(data) ? data : (data.results || []))
    } catch (error) {
      console.error('Error running scan:', error)
      setResults([])
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
              <Link href="/scanner" className="text-foreground">Scanner</Link>
              <Link href="/watchlists" className="text-muted-foreground hover:text-foreground">
                Watchlists
              </Link>
            </div>
          </div>
        </div>
      </nav>

      <main className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-8">Stock Scanner</h1>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="bg-card border border-border rounded-lg p-6">
            <h2 className="text-lg font-bold mb-4">Scan Type</h2>
            <div className="space-y-2">
              {['custom', 'breakout', 'near-high', 'oversold'].map((type) => (
                <button
                  key={type}
                  onClick={() => setScanType(type)}
                  className={`w-full text-left px-3 py-2 rounded ${scanType === type
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted hover:bg-muted/80'
                    }`}
                >
                  {type === 'custom' ? 'Custom Screener' : type.charAt(0).toUpperCase() + type.slice(1).replace('-', ' ')}
                </button>
              ))}
            </div>
            <button
              onClick={runScan}
              className="w-full mt-4 px-4 py-2 bg-primary text-primary-foreground rounded hover:opacity-90"
            >
              Run Scan
            </button>
          </div>

          <div className="lg:col-span-3 bg-card border border-border rounded-lg p-6">
            <h2 className="text-lg font-bold mb-4">Results ({results.length})</h2>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 px-4">Symbol</th>
                    <th className="text-left py-2 px-4">Name</th>
                    <th className="text-left py-2 px-4">Sector</th>
                    <th className="text-right py-2 px-4">Price</th>
                    {scanType === 'custom' && (
                      <>
                        <th className="text-right py-2 px-4">Perf 1Y</th>
                        <th className="text-right py-2 px-4">Perf 1W</th>
                        <th className="text-right py-2 px-4">ADR %</th>
                        <th className="text-right py-2 px-4">52W Range</th>
                      </>
                    )}
                    {scanType !== 'custom' && (
                      <>
                        <th className="text-right py-2 px-4">RVOL</th>
                        <th className="text-right py-2 px-4">RSI</th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {results.map((stock, index) => (
                    <tr key={index} className="border-b border-border hover:bg-muted/50">
                      <td className="py-2 px-4 font-bold">{stock.symbol}</td>
                      <td className="py-2 px-4">{stock.name}</td>
                      <td className="py-2 px-4">{stock.sector || '-'}</td>
                      <td className="py-2 px-4 text-right">${stock.price?.toFixed(2)}</td>
                      {scanType === 'custom' && (
                        <>
                          <td className="py-2 px-4 text-right">{stock.perf_1y?.toFixed(1)}%</td>
                          <td className="py-2 px-4 text-right">{stock.perf_1w?.toFixed(1)}%</td>
                          <td className="py-2 px-4 text-right">{stock.adr_percent?.toFixed(1)}%</td>
                          <td className="py-2 px-4 text-right">{(stock.range_52w * 100)?.toFixed(1)}%</td>
                        </>
                      )}
                      {scanType !== 'custom' && (
                        <>
                          <td className="py-2 px-4 text-right">{stock.relative_volume?.toFixed(2)}x</td>
                          <td className="py-2 px-4 text-right">{stock.rsi?.toFixed(1)}</td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
              {results.length === 0 && (
                <div className="text-center py-8 text-muted-foreground">
                  Run a scan to see results
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
