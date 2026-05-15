import { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { ArrowUp, ArrowDown, Minus } from 'lucide-react'

interface MetricProps {
  label: string
  value: string | number
  change?: number
  changeLabel?: string
  trend?: 'up' | 'down' | 'neutral'
  size?: 'sm' | 'md' | 'lg'
  className?: string
  icon?: ReactNode
}

export default function Metric({
  label,
  value,
  change,
  changeLabel,
  trend,
  size = 'md',
  className,
  icon
}: MetricProps) {
  const sizeStyles = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-lg'
  }

  const getTrendIcon = () => {
    if (trend === 'up') return <ArrowUp className="w-4 h-4 text-green-500" />
    if (trend === 'down') return <ArrowDown className="w-4 h-4 text-red-500" />
    return <Minus className="w-4 h-4 text-muted-foreground" />
  }

  const getChangeColor = () => {
    if (change === undefined) return 'text-muted-foreground'
    if (change > 0) return 'text-green-500'
    if (change < 0) return 'text-red-500'
    return 'text-muted-foreground'
  }

  const formatChange = (val: number) => {
    const sign = val > 0 ? '+' : ''
    return `${sign}${val.toFixed(2)}%`
  }

  return (
    <div className={cn('flex flex-col', className)}>
      <div className="flex items-center gap-2">
        {icon && <span className="text-muted-foreground">{icon}</span>}
        <span className="text-muted-foreground text-xs uppercase tracking-wide">{label}</span>
      </div>
      <div className="flex items-baseline gap-2 mt-1">
        <span className={cn('font-bold text-foreground', sizeStyles[size])}>{value}</span>
        {change !== undefined && (
          <span className={cn('text-xs font-medium', getChangeColor())}>
            {formatChange(change)}
          </span>
        )}
        {trend && getTrendIcon()}
      </div>
      {changeLabel && (
        <span className="text-xs text-muted-foreground mt-0.5">{changeLabel}</span>
      )}
    </div>
  )
}
