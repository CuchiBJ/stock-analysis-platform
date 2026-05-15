import { cn } from '@/lib/utils'

export type BadgeType = 
  | 'breakout'
  | 'near_ath'
  | 'earnings'
  | 'squeeze'
  | 'ema20_reclaim'
  | 'unusual_volume'
  | 'tight_consolidation'
  | 'strong_rs'

interface BadgeProps {
  type: BadgeType
  className?: string
  size?: 'sm' | 'md'
}

const badgeConfig: Record<BadgeType, { label: string; color: string }> = {
  breakout: { label: 'BRK', color: 'bg-green-600' },
  near_ath: { label: 'ATH', color: 'bg-blue-600' },
  earnings: { label: 'E', color: 'bg-yellow-600' },
  squeeze: { label: 'SQZ', color: 'bg-purple-600' },
  ema20_reclaim: { label: 'EMA20', color: 'bg-cyan-600' },
  unusual_volume: { label: 'UVOL', color: 'bg-orange-600' },
  tight_consolidation: { label: 'TIGHT', color: 'bg-pink-600' },
  strong_rs: { label: 'RS', color: 'bg-red-600' },
}

export default function Badge({ type, className, size = 'sm' }: BadgeProps) {
  const config = badgeConfig[type]
  const sizeStyles = size === 'sm' ? 'text-xs px-1.5 py-0.5' : 'text-sm px-2 py-1'
  
  return (
    <span 
      className={cn(
        'inline-flex items-center font-bold text-white rounded',
        config.color,
        sizeStyles,
        className
      )}
      title={config.label}
    >
      {config.label}
    </span>
  )
}
