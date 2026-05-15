import { FilterPresetProps } from './types'
import Card from '@/components/base/Card'
import Badge from '@/components/base/Badge'

export default function FilterPreset({ name, description, count, isActive, onClick }: FilterPresetProps) {
  return (
    <div onClick={onClick}>
      <Card
        variant="compact"
        className={`cursor-pointer transition-all hover:border-primary ${isActive ? 'border-primary bg-primary/5' : 'hover:border-border/80'
          }`}
      >
        <div className="flex items-start justify-between mb-2">
          <h3 className="font-bold text-sm text-foreground">{name}</h3>
          {isActive && <Badge type="strong_rs" size="sm" />}
        </div>
        <p className="text-xs text-muted-foreground mb-3 line-clamp-2">{description}</p>
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono text-muted-foreground">{count} stocks</span>
          <span className="text-xs text-muted-foreground">→</span>
        </div>
      </Card>
    </div>
  )
}
