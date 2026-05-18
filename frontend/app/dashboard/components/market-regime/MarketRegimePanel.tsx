"use client";

import { useQuery } from "@tanstack/react-query";
import Card from "@/components/base/Card";

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

interface MarketRegimeResponse {
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
  const { data: regimeData, isLoading, error } = useQuery<MarketRegimeResponse>({
    queryKey: ['market-regime'],
    queryFn: async () => {
      const response = await fetch("http://localhost:8000/api/v1/market-regime/current");
      if (!response.ok) throw new Error("Failed to fetch market regime");
      return response.json();
    },
    refetchInterval: 60000, // Refresh every 60s
  });

  const getRegimeColor = (regime: string) => {
    const colors: Record<string, string> = {
      risk_on: "text-green-600",
      risk_off: "text-red-600",
      transition: "text-yellow-600",
      choppy: "text-gray-600",
    };
    return colors[regime] || "text-gray-600";
  };

  const getRegimeBadge = (regime: string) => {
    const badges: Record<string, string> = {
      risk_on: "bg-green-100 text-green-800",
      risk_off: "bg-red-100 text-red-800",
      transition: "bg-yellow-100 text-yellow-800",
      choppy: "bg-gray-100 text-gray-800",
    };
    return badges[regime] || "bg-gray-100 text-gray-800";
  };

  if (isLoading) {
    return (
      <Card blockType="market-context">
        <h2 className="text-lg font-bold mb-2">Market Regime</h2>
        <div className="text-center py-8 text-gray-500">Loading market regime...</div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card blockType="market-context">
        <h2 className="text-lg font-bold mb-2">Market Regime</h2>
        <div className="text-center py-8 text-red-500">
          Error: {error instanceof Error ? error.message : 'Failed to load'}
        </div>
      </Card>
    );
  }

  if (!regimeData) {
    return null;
  }

  return (
    <Card blockType="market-context">
      <h2 className="text-lg font-bold mb-2">Market Regime</h2>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-foreground">Current Regime:</span>
          <span
            className={`inline-block px-3 py-1 rounded-full text-sm font-bold ${getRegimeBadge(
              regimeData.regime
            )}`}
          >
            {regimeData.regime.replace("_", " ").toUpperCase()}
          </span>
        </div>

        <div className="border-t pt-4">
          <p className="text-sm text-foreground mb-4">{regimeData.summary}</p>
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-foreground/80">Breadth Quality:</span>
            <div className="flex items-center mt-1">
              <div className="flex-1 bg-gray-200 rounded-full h-2 mr-2">
                <div
                  className="bg-blue-600 h-2 rounded-full"
                  style={{ width: `${regimeData.breadth_quality * 100}%` }}
                />
              </div>
              <span className="text-xs font-medium">
                {(regimeData.breadth_quality * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          <div>
            <span className="text-foreground/80">Leadership Health:</span>
            <div className="flex items-center mt-1">
              <div className="flex-1 bg-gray-200 rounded-full h-2 mr-2">
                <div
                  className="bg-green-600 h-2 rounded-full"
                  style={{ width: `${regimeData.leadership_health * 100}%` }}
                />
              </div>
              <span className="text-xs font-medium">
                {(regimeData.leadership_health * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          <div>
            <span className="text-foreground/80">Speculative Appetite:</span>
            <div className="flex items-center mt-1">
              <div className="flex-1 bg-gray-200 rounded-full h-2 mr-2">
                <div
                  className="bg-purple-600 h-2 rounded-full"
                  style={{ width: `${regimeData.speculative_appetite * 100}%` }}
                />
              </div>
              <span className="text-xs font-medium">
                {(regimeData.speculative_appetite * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          <div>
            <span className="text-foreground/80">Sector Expansion:</span>
            <div className="flex items-center mt-1">
              <div className="flex-1 bg-gray-200 rounded-full h-2 mr-2">
                <div
                  className="bg-orange-600 h-2 rounded-full"
                  style={{ width: `${regimeData.sector_expansion * 100}%` }}
                />
              </div>
              <span className="text-xs font-medium">
                {(regimeData.sector_expansion * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          <div className="col-span-2">
            <span className="text-foreground/80">Pullback Environment Quality:</span>
            <div className="flex items-center mt-1">
              <div className="flex-1 bg-gray-200 rounded-full h-2 mr-2">
                <div
                  className="bg-teal-600 h-2 rounded-full"
                  style={{ width: `${regimeData.pullback_environment_quality * 100}%` }}
                />
              </div>
              <span className="text-xs font-medium">
                {(regimeData.pullback_environment_quality * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        </div>

        <div className="border-t pt-4 text-xs text-foreground/70">
          Confidence: {(regimeData.confidence * 100).toFixed(0)}%
        </div>
      </div>
    </Card>
  );
}
