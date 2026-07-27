'use client'

import { useEffect, useRef, useState } from 'react'
import { API_URL } from '@/lib/utils'
import DashboardLayout from '@/components/layout/DashboardLayout'
import Card from '@/components/base/Card'
import { Send, Bot, User, Loader2 } from 'lucide-react'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  toolsUsed?: string[]
}

const SUGGESTIONS = [
  '¿Qué setups accionables hay hoy y cuál tiene mejor score?',
  '¿Qué cambios de estado tuvo ELAN?',
  '¿Qué tan confiable es entering_pullback según la calibración?',
]

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function send(text: string) {
    const q = text.trim()
    if (!q || loading) return

    const history = [...messages, { role: 'user' as const, content: q }]
    setMessages(history)
    setInput('')
    setLoading(true)
    setError(null)

    try {
      const res = await fetch(`${API_URL}/api/v1/chat/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: history.map(m => ({ role: m.role, content: m.content })),
        }),
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => null)
        throw new Error(detail?.detail ?? `HTTP ${res.status}`)
      }
      const data: { answer: string; tools_used: string[] } = await res.json()
      setMessages([
        ...history,
        { role: 'assistant', content: data.answer, toolsUsed: data.tools_used },
      ])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }

  return (
    <DashboardLayout>
      <div className="max-w-3xl mx-auto flex flex-col h-[calc(100vh-9rem)]">
        <div className="mb-3">
          <h1 className="text-xl font-bold text-foreground flex items-center gap-2">
            <Bot className="w-5 h-5 text-cyan-400" /> Chat
          </h1>
          <p className="text-xs text-muted-foreground mt-1">
            Preguntá en lenguaje natural sobre transiciones, calibración, setups e historial por símbolo. Las respuestas se anclan en consultas de solo-lectura a la base.
          </p>
        </div>

        <div className="flex-1 overflow-y-auto space-y-3 pr-1">
          {messages.length === 0 && (
            <Card className="p-4">
              <p className="text-sm text-muted-foreground mb-2">Probá con:</p>
              <div className="flex flex-col gap-2">
                {SUGGESTIONS.map(s => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="text-left text-sm px-3 py-2 rounded border border-white/10 bg-white/5 hover:bg-white/10 text-foreground/90 transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </Card>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`flex gap-2 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {m.role === 'assistant' && <Bot className="w-5 h-5 text-cyan-400 mt-1 shrink-0" />}
              <div
                className={`max-w-[85%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
                  m.role === 'user'
                    ? 'bg-cyan-500/15 border border-cyan-500/30 text-foreground'
                    : 'bg-white/5 border border-white/10 text-foreground/90'
                }`}
              >
                {m.content}
                {m.toolsUsed && m.toolsUsed.length > 0 && (
                  <div className="mt-2 text-[10px] text-white/40 font-mono">
                    consultó: {[...new Set(m.toolsUsed)].join(', ')}
                  </div>
                )}
              </div>
              {m.role === 'user' && <User className="w-5 h-5 text-muted-foreground mt-1 shrink-0" />}
            </div>
          ))}

          {loading && (
            <div className="flex gap-2 items-center text-sm text-muted-foreground">
              <Bot className="w-5 h-5 text-cyan-400 shrink-0" />
              <Loader2 className="w-4 h-4 animate-spin" /> pensando…
            </div>
          )}

          {error && <p className="text-sm text-destructive">Error: {error}</p>}
          <div ref={endRef} />
        </div>

        <form
          onSubmit={e => { e.preventDefault(); send(input) }}
          className="mt-3 flex gap-2"
        >
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Escribí tu pregunta…"
            disabled={loading}
            className="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-cyan-500/40 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-lg bg-cyan-500/20 border border-cyan-500/40 px-4 py-2 text-sm font-medium text-cyan-300 hover:bg-cyan-500/30 disabled:opacity-40 transition-colors flex items-center gap-1.5"
          >
            <Send className="w-4 h-4" /> Enviar
          </button>
        </form>
      </div>
    </DashboardLayout>
  )
}
