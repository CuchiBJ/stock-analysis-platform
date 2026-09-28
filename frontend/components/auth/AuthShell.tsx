import Link from 'next/link'

export function AuthShell({
  title,
  description,
  children,
  footer,
}: {
  title: string
  description: string
  children: React.ReactNode
  footer?: React.ReactNode
}) {
  return (
    <main className="min-h-screen bg-background px-4 py-12">
      <section className="mx-auto w-full max-w-md rounded border border-border bg-card p-6 shadow-xl" aria-labelledby="auth-title">
        <Link href="/" className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Stock Analysis</Link>
        <h1 id="auth-title" className="mt-4 text-2xl font-semibold">{title}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{description}</p>
        <div className="mt-6">{children}</div>
        {footer && <div className="mt-6 border-t border-border pt-4 text-sm text-muted-foreground">{footer}</div>}
      </section>
    </main>
  )
}

export const inputClassName = 'mt-1 w-full rounded border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring disabled:opacity-60'
export const buttonClassName = 'w-full rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60'

export function FormMessage({ kind, children }: { kind: 'error' | 'success'; children: React.ReactNode }) {
  return (
    <div role={kind === 'error' ? 'alert' : 'status'} className={`rounded border px-3 py-2 text-sm ${kind === 'error' ? 'border-destructive/50 text-destructive' : 'border-emerald-700/50 text-emerald-500'}`}>
      {children}
    </div>
  )
}
