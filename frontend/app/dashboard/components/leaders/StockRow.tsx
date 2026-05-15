import { StockRowProps } from './types'
import MiniChart from '@/components/charts/MiniChart'
import Badge from '@/components/base/Badge'
import { TrendingUp, TrendingDown, Minus, Flame, Zap, Activity, ArrowUp } from 'lucide-react'

export default function StockRow({ stock, index }: StockRowProps) {
  const getChangeColor = (value: number) => {
    if (value > 0) return 'text-green-400'
    if (value < 0) return 'text-red-400'
    return 'text-muted-foreground'
  }

  const formatNumber = (num: number) => {
    if (num >= 1e9) return `${(num / 1e9).toFixed(1)}B`
    if (num >= 1e6) return `${(num / 1e6).toFixed(1)}M`
    if (num >= 1e3) return `${(num / 1e3).toFixed(1)}K`
    return num.toFixed(0)
  }

  const getChartColor = (): 'green' | 'red' | 'neutral' => {
    if (stock.gain_pct > 0) return 'green'
    if (stock.gain_pct < 0) return 'red'
    return 'neutral'
  }

  const getBadgeColor = (badge: string) => {
    const badgeColors: Record<string, string> = {
      'breakout': 'bg-green-500/20 text-green-400 border-green-500/30',
      'near ATH': 'bg-blue-500/20 text-blue-400 border-blue-500/30',
      'EMA20 reclaim': 'bg-purple-500/20 text-purple-400 border-purple-500/30',
      'squeeze': 'bg-orange-500/20 text-orange-400 border-orange-500/30',
      'unusual volume': 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
      'earnings': 'bg-pink-500/20 text-pink-400 border-pink-500/30',
      'accelerating RS': 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
      'high RS': 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
      'strong volume': 'bg-amber-500/20 text-amber-400 border-amber-500/30'
    }
    return badgeColors[badge] || 'bg-muted text-muted-foreground border-border'
  }

  const getBadgeIcon = (badge: string) => {
    if (badge === 'breakout') return <TrendingUp className="w-3 h-3" />
    if (badge === 'near ATH') return <Flame className="w-3 h-3" />
    if (badge === 'accelerating RS') return <Zap className="w-3 h-3" />
    if (badge === 'unusual volume' || badge === 'strong volume') return <Activity className="w-3 h-3" />
    if (badge === 'high RS') return <ArrowUp className="w-3 h-3" />
    return null
  }

  const getRVOLColor = (rvol: number) => {
    if (rvol >= 3) return 'text-green-400 font-semibold'
    if (rvol >= 2) return 'text-green-400'
    if (rvol >= 1.5) return 'text-yellow-400'
    return 'text-muted-foreground'
  }

  const getRSColor = (rank: number) => {
    if (rank >= 90) return 'text-green-400 font-semibold'
    if (rank >= 80) return 'text-green-400'
    if (rank >= 70) return 'text-yellow-400'
    return 'text-muted-foreground'
  }

  return (
    <div className="grid grid-cols-12 gap-2 px-2 py-2 text-[11px] border-b border-border/50 hover:bg-muted/50 transition-colors group">
      {/* Ticker */}
      <div className="col-span-1 font-bold text-white group-hover:text-primary transition-colors">
        {stock.symbol}
      </div>

      {/* Sector */}
      <div className="col-span-2 text-muted-foreground truncate text-[10px]">
        {stock.sector}
      </div>

      {/* % Gain */}
      <div className={`col-span-1 font-mono text-right ${getChangeColor(stock.gain_pct || 0)}`}>
        {stock.gain_pct ? (stock.gain_pct > 0 ? '+' : '') + stock.gain_pct.toFixed(2) + '%' : 'N/A'}
      </div>

      {/* RVOL */}
      <div className={`col-span-1 font-mono text-right ${getRVOLColor(stock.rvol || 0)}`}>
        {stock.rvol ? stock.rvol.toFixed(2) + 'x' : 'N/A'}
      </div>

      {/* RS Rank */}
      <div className={`col-span-1 font-mono text-right ${getRSColor(stock.rs_rank || 0)}`}>
        {stock.rs_rank ? '#' + stock.rs_rank : 'N/A'}
      </div>

      {/* Score */}
      <div className={`col-span-1 font-mono text-right ${stock.score >= 8 ? 'text-green-400 font-semibold' : stock.score >= 6 ? 'text-yellow-400' : 'text-muted-foreground'}`}>
        {stock.score ? stock.score.toFixed(1) : 'N/A'}
      </div>

      {/* Volume */}
      <div className="col-span-2 font-mono text-right text-muted-foreground text-[10px]">
        {stock.volume ? formatNumber(stock.volume) : 'N/A'}
      </div>

      {/* Distance to ATH */}
      <div className={`col-span-1 font-mono text-right ${getChangeColor(stock.distance_ath || 0)}`}>
        {stock.distance_ath ? (stock.distance_ath > 0 ? '+' : '') + stock.distance_ath.toFixed(1) + '%' : 'N/A'}
      </div>

      {/* Float */}
      <div className="col-span-1 font-mono text-right text-muted-foreground text-[10px]">
        {stock.float ? formatNumber(stock.float) : 'N/A'}
      </div>

      {/* Badges */}
      <div className="col-span-2 flex items-center gap-1 flex-wrap justify-center">
        {stock.badges?.slice(0, 3).map((badge: string, i: number) => (
          <span
            key={i}
            className={`px-1.5 py-0.5 rounded text-[9px] font-medium border flex items-center gap-0.5 ${getBadgeColor(badge)}`}
          >
            {getBadgeIcon(badge)}
            {badge}
          </span>
        ))}
      </div>
    </div>
  )
}
