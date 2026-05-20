'use client';

import { useEffect, useState } from 'react';

interface MarketRegimeData {
  regime: string;
  breadth_quality: number;
  leadership_health: number;
  speculative_appetite: number;
  sector_expansion: number;
  pullback_environment_quality: number;
  confidence: number;
  summary: string;
}

export default function MarketRegimePanel() {
  const [regimeData, setRegimeData] = useState<MarketRegimeData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchRegimeData = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const response = await fetch(`${apiUrl}/api/v1/market-regime/current`);
        if (!response.ok) {
          throw new Error('Failed to fetch market regime data');
        }
        const data = await response.json();
        setRegimeData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        console.error('Error fetching market regime:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchRegimeData();
  }, []);

  if (isLoading) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-2">Market Regime</h3>
        <p className="text-xs text-muted-foreground">Loading market regime data...</p>
      </div>
    );
  }

  if (error || !regimeData) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-2">Market Regime</h3>
        <p className="text-xs text-red-400">{error || 'No data available'}</p>
      </div>
    );
  }

  return (
    <div className="bg-white/5 border border-white/10 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-2">Market Regime</h3>
      <div className="space-y-3">
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-muted-foreground">Regime</span>
            <span className="font-semibold text-white">{regimeData.regime}</span>
          </div>
        </div>
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-muted-foreground">Breadth Quality</span>
            <span className="font-semibold text-white">{(regimeData.breadth_quality * 100).toFixed(0)}%</span>
          </div>
          <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 transition-all"
              style={{ width: `${regimeData.breadth_quality * 100}%` }}
            />
          </div>
        </div>
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-muted-foreground">Leadership Health</span>
            <span className="font-semibold text-white">{(regimeData.leadership_health * 100).toFixed(0)}%</span>
          </div>
          <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 transition-all"
              style={{ width: `${regimeData.leadership_health * 100}%` }}
            />
          </div>
        </div>
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-muted-foreground">Speculative Appetite</span>
            <span className="font-semibold text-white">{(regimeData.speculative_appetite * 100).toFixed(0)}%</span>
          </div>
          <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full bg-yellow-500 transition-all"
              style={{ width: `${regimeData.speculative_appetite * 100}%` }}
            />
          </div>
        </div>
        <div className="pt-2 border-t border-white/10">
          <p className="text-xs text-muted-foreground">{regimeData.summary}</p>
        </div>
      </div>
    </div>
  );
}
