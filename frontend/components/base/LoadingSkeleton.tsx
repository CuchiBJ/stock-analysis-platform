import { cn } from '@/lib/utils'

interface LoadingSkeletonProps {
  className?: string
  variant?: 'text' | 'card' | 'metric' | 'table-row'
}

export default function LoadingSkeleton({ className, variant = 'text' }: LoadingSkeletonProps) {
  const baseStyles = 'animate-pulse bg-muted'
  
  const variantStyles = {
    text: 'h-4 w-full rounded',
    card: 'h-32 w-full rounded-lg',
    metric: 'h-16 w-full rounded-lg',
    'table-row': 'h-12 w-full rounded'
  }
  
  return (
    <div className={cn(baseStyles, variantStyles[variant], className)} />
  )
}
