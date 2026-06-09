'use client'

import { useState } from 'react'
import { Crosshair } from 'lucide-react'
import { API_URL } from '@/lib/utils'
import { NewTradeModal, type Vocab, type TradeDraftPrefill } from '@/app/journal/TradeForms'

export default function TakeFromQueueButton({
  symbol, setup, onSaved,
}: {
  symbol: string
  setup: string
  onSaved?: () => void
}) {
  const [loading, setLoading] = useState(false)
  const [draft, setDraft] = useState<TradeDraftPrefill | null>(null)
  const [vocab, setVocab] = useState<Vocab | null>(null)

  async function handleClick(e: React.MouseEvent) {
    e.preventDefault()
    e.stopPropagation()
    setLoading(true)
    try {
      // Fetch vocab + draft in parallel — both needed to open the modal
      const [draftRes, vocabRes] = await Promise.all([
        fetch(`${API_URL}/api/v1/journal/trade-draft?symbol=${encodeURIComponent(symbol)}&setup=${encodeURIComponent(setup)}`),
        vocab ? Promise.resolve(null) : fetch(`${API_URL}/api/v1/journal/vocab`),
      ])
      if (!draftRes.ok) {
        const d = await draftRes.json().catch(() => ({}))
        throw new Error(d.detail || `HTTP ${draftRes.status}`)
      }
      const draftData: TradeDraftPrefill = await draftRes.json()
      if (vocabRes) {
        if (!vocabRes.ok) throw new Error(`vocab HTTP ${vocabRes.status}`)
        setVocab(await vocabRes.json())
      }
      setDraft(draftData)
    } catch (e: any) {
      alert(`No se pudo cargar el draft: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={handleClick}
        disabled={loading}
        className="inline-flex items-center gap-1 text-[10px] px-2 py-1 rounded bg-blue-500/15 border border-blue-500/30 text-blue-300 hover:bg-blue-500/25 disabled:opacity-50"
        title={`Tomar trade desde queue ${setup}`}
      >
        <Crosshair className="w-3 h-3" />
        {loading ? '…' : 'Tomar'}
      </button>
      {draft && vocab && (
        <NewTradeModal
          vocab={vocab}
          prefill={draft}
          onClose={() => setDraft(null)}
          onSaved={() => { setDraft(null); onSaved?.() }}
        />
      )}
    </>
  )
}
