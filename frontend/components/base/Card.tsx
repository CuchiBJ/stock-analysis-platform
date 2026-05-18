import { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface CardProps {
  children: ReactNode
  className?: string
  variant?: 'default' | 'compact' | 'borderless'
  blockType?: 'market-context' | 'live-transitions' | 'actionable' | 'sector' | 'structure'
  hoverable?: boolean
}

export default function Card({
  children,
  className,
  variant = 'default',
  blockType,
  hoverable = false
}: CardProps) {
  const baseStyles = 'rounded-lg'

  const blockTypeStyles = blockType ? {
    'market-context': 'bg-[hsl(var(--block-market-context))] border border-border/50',
    'live-transitions': 'bg-[hsl(var(--block-live-transitions))] border border-border/50',
    'actionable': 'bg-[hsl(var(--block-actionable))] border border-border/50',
    'sector': 'bg-[hsl(var(--block-sector))] border border-border/50',
    'structure': 'bg-[hsl(var(--block-structure))] border border-border/50',
  }[blockType] : 'bg-card'

  const variantStyles = {
    default: 'border border-border p-4',
    compact: 'border border-border p-3',
    borderless: 'p-4'
  }

  const hoverStyles = hoverable ? 'hover:border-border/80 transition-colors cursor-pointer' : ''

  return (
    <div className={cn(baseStyles, blockTypeStyles, variantStyles[variant], hoverStyles, className)}>
      {children}
    </div>
  )
}
