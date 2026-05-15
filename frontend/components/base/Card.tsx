import { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface CardProps {
  children: ReactNode
  className?: string
  variant?: 'default' | 'compact' | 'borderless'
  hoverable?: boolean
}

export default function Card({ 
  children, 
  className, 
  variant = 'default',
  hoverable = false 
}: CardProps) {
  const baseStyles = 'bg-card rounded-lg'
  
  const variantStyles = {
    default: 'border border-border p-4',
    compact: 'border border-border p-3',
    borderless: 'p-4'
  }
  
  const hoverStyles = hoverable ? 'hover:border-border/80 transition-colors cursor-pointer' : ''
  
  return (
    <div className={cn(baseStyles, variantStyles[variant], hoverStyles, className)}>
      {children}
    </div>
  )
}
