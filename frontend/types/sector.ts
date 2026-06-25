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

export interface SectorRotationEntry {
  name: string;
  rank_delta: number;   // positive = subió en el ranking (rota hacia adentro)
  rs_delta: number;
  rank_now: number;
}

export interface SectorRotationGroup extends SectorRotationEntry {
  rank_prev: number;
  rs_now: number;
  stock_count: number;
  direction: 'rotating_in' | 'rotating_out' | 'stable';
}

export interface SectorRotation {
  as_of: string | null;
  compared_to: string | null;
  lookback_sessions: number;
  rotating_in: SectorRotationEntry[];
  rotating_out: SectorRotationEntry[];
  groups: SectorRotationGroup[];
}
