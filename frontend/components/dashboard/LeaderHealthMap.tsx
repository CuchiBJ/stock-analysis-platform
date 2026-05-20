'use client';

import { useEffect, useState } from 'react';

interface LeaderHealthData {
  leaders_above_ema21: number;
  failed_breakouts: number;
  distribution_count: number;
  pullback_quality_index: number;
  breakdown_count: number;
  reclaim_quality: number;
  continuation_quality: number;
  rs_deterioration: number;
  overall_health_score: number;
  summary: string;
}

export default function LeaderHealthMap() {
  const [healthData, setHealthData] = useState<LeaderHealthData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchHealthData = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const response = await fetch(`${apiUrl}/api/v1/leader-health/current`);
        if (!response.ok) {
          throw new Error('Failed to fetch leader health data');
        }
        const data = await response.json();
        setHealthData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        console.error('Error fetching leader health:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchHealthData();
  }, []);

  if (isLoading) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-2">Leader Health</h3>
        <p className="text-xs text-muted-foreground">Loading leader health data...</p>
      </div>
    );
  }

  if (error || !healthData) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-2">Leader Health</h3>
        <p className="text-xs text-red-400">{error || 'No data available'}</p>
      </div>
    );
  }

  return (
    <div className="bg-white/5 border border-white/10 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-2">Leader Health</h3>
      <div className="space-y-3">
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-muted-foreground">Overall Health Score</span>
            <span className={`font-semibold ${healthData.overall_health_score >= 0.6 ? 'text-green-400' : healthData.overall_health_score >= 0.4 ? 'text-yellow-400' : 'text-red-400'}`}>
              {(healthData.overall_health_score * 100).toFixed(0)}%
            </span>
          </div>
          <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all ${healthData.overall_health_score >= 0.6 ? 'bg-green-500' : healthData.overall_health_score >= 0.4 ? 'bg-yellow-500' : 'bg-red-500'}`}
              style={{ width: `${healthData.overall_health_score * 100}%` }}
            />
          </div>
        </div>
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-muted-foreground">Leaders Above EMA21</span>
            <span className="font-semibold text-white">{healthData.leaders_above_ema21}</span>
          </div>
        </div>
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-muted-foreground">Failed Breakouts</span>
            <span className="font-semibold text-white">{healthData.failed_breakouts}</span>
          </div>
        </div>
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-muted-foreground">Distribution Count</span>
            <span className="font-semibold text-white">{healthData.distribution_count}</span>
          </div>
        </div>
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-muted-foreground">Pullback Quality Index</span>
            <span className="font-semibold text-white">{healthData.pullback_quality_index.toFixed(2)}</span>
          </div>
        </div>
        <div className="pt-2 border-t border-white/10">
          <p className="text-xs text-muted-foreground">{healthData.summary}</p>
        </div>
      </div>
    </div>
  );
}
