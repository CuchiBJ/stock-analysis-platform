interface BreadthGaugeProps {
  label: string
  value: number
  advancers: number
  decliners: number
}

export default function BreadthGauge({ label, value, advancers, decliners }: BreadthGaugeProps) {
  const getHealthColor = (ratio: number) => {
    if (ratio >= 2) return 'text-green-500'
    if (ratio >= 1.5) return 'text-green-400'
    if (ratio >= 1) return 'text-yellow-500'
    if (ratio >= 0.5) return 'text-orange-500'
    return 'text-red-500'
  }

  const getHealthLabel = (ratio: number) => {
    if (ratio >= 2) return 'Strong'
    if (ratio >= 1.5) return 'Healthy'
    if (ratio >= 1) return 'Neutral'
    if (ratio >= 0.5) return 'Weak'
    return 'Bearish'
  }

  const getBarWidth = () => {
    const total = advancers + decliners
    if (total === 0) return 50
    return (advancers / total) * 100
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-muted-foreground">{label}</span>
        <span className={`text-sm font-bold ${getHealthColor(value)}`}>
          {getHealthLabel(value)}
        </span>
      </div>
      
      {/* Bar visualization */}
      <div className="h-3 bg-muted rounded-full overflow-hidden">
        <div 
          className="h-full bg-gradient-to-r from-red-500 via-yellow-500 to-green-500 transition-all duration-300"
          style={{ width: `${getBarWidth()}%` }}
        />
      </div>
      
      {/* Stats */}
      <div className="flex justify-between mt-2 text-xs">
        <span className="text-green-500 font-medium">{advancers} advancers</span>
        <span className="text-red-500 font-medium">{decliners} decliners</span>
      </div>
    </div>
  )
}
