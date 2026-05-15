import { cn } from '@/lib/utils'
import { ArrowUp, ArrowDown, Minus } from 'lucide-react'

export type TrendType = 'bullish' | 'bearish' | 'neutral'

interface TrendIndicatorProps {
  trend: TrendType
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
  className?: string
}

const trendConfig = {
  bullish: {
    color: 'text-green-500',
    bgColor: 'bg-green-500/10',
    icon: ArrowUp,
    label: 'Bullish'
  },
  bearish: {
    color: 'text-red-500',
    bgColor: 'bg-red-500/10',
    icon: ArrowDown,
    label: 'Bearish'
  },
  neutral: {
    color: 'text-muted-foreground',
    bgColor: 'bg-muted',
    icon: Minus,
    label: 'Neutral'
  }
}

export default function TrendIndicator({ 
  trend, 
  size = 'md',
  showLabel = false,
  className 
}: TrendIndicatorProps) {
  const config = trendConfig[trend]
  const Icon = config.icon
  
  const sizeStyles = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5'
  }
  
  return (
    <div className={cn('flex items-center gap-1.5', className)}>
      <div className={cn('p-1 rounded', config.bgColor)}>
        <Icon className={cn(sizeStyles[size], config.color)} />
      </div>
      {showLabel && (
        <span className={cn('text-xs font-medium', config.color)}>
          {config.label}
        </span>
      )}
    </div>
  )
}
