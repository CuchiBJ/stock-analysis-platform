"use client";

import { useQuery } from "@tanstack/react-query";
import Card from "@/components/base/Card";

interface Setup {
  symbol: string;
  current_state: string;
  priority_score: number;
  continuation_probability: number;
  weekly_structure_score: number;
  narrative: string;
  metrics: {
    pullback_quality_score: number;
    distance_to_ema21: number;
    distance_to_ema50: number;
    distance_to_high_52w: number;
    weekly_trend_quality: number;
    relative_strength_spy: number | null;
    current_price: number;
    avg_volume_10d: number | null;
  };
}

interface SetupLifecycleResponse {
  total_analyzed: number;
  total_passed_invalidation: number;
  total_ranked: number;
  setups: Setup[];
}

export default function SetupLifecyclePanel() {
  const { data: response, isLoading, error } = useQuery<SetupLifecycleResponse>({
    queryKey: ['setup-lifecycle-active'],
    queryFn: async () => {
      const response = await fetch("http://localhost:8000/api/v1/setup-lifecycle/active-setups?limit=6&min_score=55");
      if (!response.ok) throw new Error("Failed to fetch setups");
      return response.json();
    },
    refetchInterval: 60000, // Refresh every 60s
  });

  const setups = response?.setups || [];

  const formatVolume = (volume: number): string => {
    if (volume >= 1000000) {
      return `${(volume / 1000000).toFixed(1)}M`;
    } else if (volume >= 1000) {
      return `${(volume / 1000).toFixed(0)}K`;
    }
    return volume.toString();
  };

  const getStateColor = (state: string) => {
    const colors: Record<string, string> = {
      trigger_ready: "text-green-600",
      continuation: "text-blue-600",
      constructive_pullback: "text-yellow-600",
      tightening: "text-orange-600",
      emerging: "text-gray-600",
      weakening: "text-red-600",
      broken: "text-red-800",
    };
    return colors[state] || "text-gray-600";
  };

  const getStateBadge = (state: string) => {
    const badges: Record<string, string> = {
      trigger_ready: "bg-green-100 text-green-800",
      continuation: "bg-blue-100 text-blue-800",
      constructive_pullback: "bg-yellow-100 text-yellow-800",
      tightening: "bg-orange-100 text-orange-800",
      emerging: "bg-gray-100 text-gray-800",
      weakening: "bg-red-100 text-red-800",
      broken: "bg-red-900 text-red-100",
    };
    return badges[state] || "bg-gray-100 text-gray-800";
  };

  if (isLoading) {
    return (
      <Card>
        <h2 className="text-lg font-bold mb-2">Setup Lifecycle Feed</h2>
        <div className="text-center py-8 text-gray-500">Loading setups...</div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <h2 className="text-lg font-bold mb-2">Setup Lifecycle Feed</h2>
        <div className="text-center py-8 text-red-500">
          Error: {error instanceof Error ? error.message : 'Failed to load'}
        </div>
      </Card>
    );
  }

  if (setups.length === 0) {
    return (
      <Card>
        <h2 className="text-lg font-bold mb-2">Setup Lifecycle Feed</h2>
        <div className="text-center py-8 text-gray-500">
          No active setups found. Invalidation filter eliminated all candidates.
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <h2 className="text-lg font-bold mb-2">Setup Lifecycle Feed</h2>
      <p className="text-sm text-gray-500 mb-4">
        Top {setups.length} ranked setups • SCARCITY IS SIGNAL
      </p>
      <div className="space-y-4">
        {setups.map((setup) => (
          <div
            key={setup.symbol}
            className="border rounded-lg p-4 hover:bg-gray-50 transition-all duration-200 hover:shadow-md cursor-pointer group"
          >
            <div className="flex justify-between items-start mb-2">
              <div>
                <h3 className="font-bold text-lg group-hover:text-blue-600 transition-colors duration-200">{setup.symbol}</h3>
                <span
                  className={`inline-block px-2 py-1 rounded text-xs font-medium transition-all duration-200 ${getStateBadge(
                    setup.current_state
                  )}`}
                >
                  {setup.current_state.replace("_", " ").toUpperCase()}
                </span>
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold text-blue-600">
                  {setup.priority_score.toFixed(0)}
                </div>
                <div className="text-xs text-gray-500">Priority Score</div>
              </div>
            </div>

            <p className="text-sm text-gray-700 mb-3">{setup.narrative}</p>

            <div className="grid grid-cols-3 gap-2 text-xs">
              <div>
                <span className="text-gray-500">Pullback Quality:</span>
                <span className="ml-1 font-medium">
                  {setup.metrics.pullback_quality_score.toFixed(0)}
                </span>
              </div>
              <div>
                <span className="text-gray-500">Cont Prob:</span>
                <span className="ml-1 font-medium">
                  {(setup.continuation_probability * 100).toFixed(0)}%
                </span>
              </div>
              <div>
                <span className="text-gray-500">Weekly Score:</span>
                <span className="ml-1 font-medium">
                  {setup.weekly_structure_score.toFixed(0)}
                </span>
              </div>
              <div>
                <span className="text-gray-500">EMA21:</span>
                <span className="ml-1 font-medium">
                  {setup.metrics.distance_to_ema21.toFixed(1)}%
                </span>
              </div>
              <div>
                <span className="text-gray-500">RS vs SPY:</span>
                <span className="ml-1 font-medium">
                  {setup.metrics.relative_strength_spy ? setup.metrics.relative_strength_spy.toFixed(0) : 'N/A'}
                </span>
              </div>
              <div>
                <span className="text-gray-500">Avg Volume:</span>
                <span className="ml-1 font-medium">
                  {setup.metrics.avg_volume_10d ? formatVolume(setup.metrics.avg_volume_10d) : 'N/A'}
                </span>
              </div>
              <div>
                <span className="text-gray-500">Price:</span>
                <span className="ml-1 font-medium">
                  ${setup.metrics.current_price.toFixed(2)}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
