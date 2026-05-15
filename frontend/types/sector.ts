export interface Sector {
  name: string;
  performance_daily: number;
  performance_weekly: number;
  performance_monthly: number;
  stock_count: number;
}

export interface SectorPerformance {
  name: string;
  performance_daily: number;
  performance_weekly: number;
  performance_monthly: number;
  performance_vs_spy: number;
  trend: 'accelerating' | 'steady' | 'decelerating';
  strength: 'strong' | 'moderate' | 'weak';
  volume_trend: 'increasing' | 'stable' | 'decreasing';
  stock_count: number;
  leaders: string[];  // symbols
}
