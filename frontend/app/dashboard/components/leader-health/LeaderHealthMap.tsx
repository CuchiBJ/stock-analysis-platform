"use client";

import { useEffect, useState } from "react";
import Card from "@/components/base/Card";

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchLeaderHealth();
    const interval = setInterval(fetchLeaderHealth, 60000); // Refresh every 60s
    return () => clearInterval(interval);
  }, []);

  const fetchLeaderHealth = async () => {
    try {
      setLoading(true);
      const response = await fetch("http://localhost:8000/api/v1/leader-health/current");
      if (!response.ok) throw new Error("Failed to fetch leader health");
      const data: LeaderHealthData = await response.json();
      setHealthData(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error fetching leader health");
      console.error("Error fetching leader health:", err);
    } finally {
      setLoading(false);
    }
  };

  const getHealthColor = (score: number) => {
    if (score >= 0.8) return "text-green-600";
    if (score >= 0.6) return "text-blue-600";
    if (score >= 0.4) return "text-yellow-600";
    return "text-red-600";
  };

  const getHealthBadge = (score: number) => {
    if (score >= 0.8) return "bg-green-100 text-green-800";
    if (score >= 0.6) return "bg-blue-100 text-blue-800";
    if (score >= 0.4) return "bg-yellow-100 text-yellow-800";
    return "bg-red-100 text-red-800";
  };

  if (loading) {
    return (
      <Card blockType="market-context">
        <h2 className="text-lg font-bold mb-2">Leader Health Map</h2>
        <div className="text-center py-8 text-gray-500">Loading leader health...</div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card blockType="market-context">
        <h2 className="text-lg font-bold mb-2">Leader Health Map</h2>
        <div className="text-center py-8 text-red-500">Error: {error}</div>
      </Card>
    );
  }

  if (!healthData) {
    return null;
  }

  return (
    <Card blockType="market-context">
      <h2 className="text-lg font-bold mb-2">Leader Health Map</h2>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-foreground">Overall Health Score:</span>
          <span
            className={`inline-block px-3 py-1 rounded-full text-sm font-bold ${getHealthBadge(
              healthData.overall_health_score
            )}`}
          >
            {(healthData.overall_health_score * 100).toFixed(0)}%
          </span>
        </div>

        <div className="border-t pt-4">
          <p className="text-sm text-foreground mb-4">{healthData.summary}</p>
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-foreground/80">Leaders Above EMA21:</span>
            <div className="flex items-center mt-1">
              <div className="flex-1 bg-gray-200 rounded-full h-2 mr-2">
                <div
                  className="bg-green-600 h-2 rounded-full"
                  style={{ width: `${healthData.leaders_above_ema21 * 100}%` }}
                />
              </div>
              <span className="text-xs font-medium">
                {(healthData.leaders_above_ema21 * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          <div>
            <span className="text-foreground/80">Pullback Quality Index:</span>
            <div className="flex items-center mt-1">
              <div className="flex-1 bg-gray-200 rounded-full h-2 mr-2">
                <div
                  className="bg-blue-600 h-2 rounded-full"
                  style={{ width: `${healthData.pullback_quality_index}%` }}
                />
              </div>
              <span className="text-xs font-medium">
                {healthData.pullback_quality_index.toFixed(0)}
              </span>
            </div>
          </div>

          <div>
            <span className="text-foreground/80">Reclaim Quality:</span>
            <div className="flex items-center mt-1">
              <div className="flex-1 bg-gray-200 rounded-full h-2 mr-2">
                <div
                  className="bg-purple-600 h-2 rounded-full"
                  style={{ width: `${healthData.reclaim_quality * 100}%` }}
                />
              </div>
              <span className="text-xs font-medium">
                {(healthData.reclaim_quality * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          <div>
            <span className="text-foreground/80">Continuation Quality:</span>
            <div className="flex items-center mt-1">
              <div className="flex-1 bg-gray-200 rounded-full h-2 mr-2">
                <div
                  className="bg-teal-600 h-2 rounded-full"
                  style={{ width: `${healthData.continuation_quality * 100}%` }}
                />
              </div>
              <span className="text-xs font-medium">
                {(healthData.continuation_quality * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          <div className="col-span-2 grid grid-cols-4 gap-2 text-xs">
            <div className="text-center">
              <div className="text-red-600 font-bold">
                {healthData.failed_breakouts}
              </div>
              <div className="text-foreground/70">Failed Breakouts</div>
            </div>
            <div className="text-center">
              <div className="text-orange-600 font-bold">
                {healthData.distribution_count}
              </div>
              <div className="text-foreground/70">Distribution</div>
            </div>
            <div className="text-center">
              <div className="text-red-600 font-bold">
                {healthData.breakdown_count}
              </div>
              <div className="text-foreground/70">Breakdowns</div>
            </div>
            <div className="text-center">
              <div className="text-yellow-600 font-bold">
                {healthData.rs_deterioration}
              </div>
              <div className="text-foreground/70">RS Deterioration</div>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}
