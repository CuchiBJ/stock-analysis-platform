"""Setup Clustering Engine - Detect EMA21 test, reclaim, and tightening clusters"""

from enum import Enum
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from app.models.stock import StockMetrics
import logging

logger = logging.getLogger(__name__)


class ClusterType(Enum):
    """Types of setup clusters"""
    EMA21_TEST = "ema21_test"           # Stocks testing EMA21
    EMA21_RECLAIM = "ema21_reclaim"     # Stocks reclaiming EMA21
    TIGHTENING = "tightening"           # Stocks in tightening phase
    BREAKOUT_ATTEMPT = "breakout_attempt"  # Stocks attempting breakout
    PULLBACK_CONSOLIDATION = "pullback_consolidation"  # Stocks consolidating after pullback


@dataclass
class ClusterMember:
    """Member of a setup cluster"""
    symbol: str
    current_price: float
    distance_to_ema21: float
    pullback_quality_score: float
    weekly_trend_quality: float
    avg_volume_10d: float
    cluster_score: float


@dataclass
class SetupCluster:
    """Cluster of similar setups"""
    cluster_type: ClusterType
    members: List[ClusterMember]
    cluster_size: int
    avg_distance_to_ema21: float
    avg_pullback_quality: float
    avg_weekly_trend: float
    total_volume: float
    cluster_quality_score: float
    sector_distribution: Dict[str, int]
    narrative: str


class ClusteringEngine:
    """
    Setup Clustering Engine - Detect EMA21 test, reclaim, and tightening clusters.
    
    Core philosophy: Stocks don't move in isolation. When institutional players
    are active, they often move multiple stocks in a sector or theme together.
    Clustering detects these patterns to identify sector rotation, theme-based
    setups, and coordinated institutional activity.
    
    Expected outcome:
    - Detect clusters of stocks at similar technical levels (EMA21 test, reclaim)
    - Identify sector rotation patterns
    - Find theme-based setups (e.g., AI, energy, semiconductors)
    - Measure cluster strength and quality
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def detect_ema21_test_cluster(
        self,
        max_distance_pct: float = 2.0,
        min_quality_score: float = 50.0,
        min_volume: int = 700000,
        limit: int = 20
    ) -> Optional[SetupCluster]:
        """
        Detect cluster of stocks testing EMA21.
        
        Stocks within max_distance_pct of EMA21 with minimum quality.
        """
        result = await self.db.execute(
            select(StockMetrics)
            .where(
                and_(
                    StockMetrics.distance_to_ema21.isnot(None),
                    StockMetrics.distance_to_ema21 >= -max_distance_pct,
                    StockMetrics.distance_to_ema21 <= max_distance_pct,
                    StockMetrics.pullback_quality_score >= min_quality_score,
                    StockMetrics.avg_volume_10d >= min_volume
                )
            )
            .order_by(StockMetrics.pullback_quality_score.desc())
            .limit(limit)
        )
        metrics_list = result.scalars().all()
        
        if not metrics_list:
            return None
        
        members = []
        for metrics in metrics_list:
            cluster_score = self._calculate_cluster_score(metrics)
            member = ClusterMember(
                symbol=metrics.symbol,
                current_price=metrics.current_price,
                distance_to_ema21=metrics.distance_to_ema21,
                pullback_quality_score=metrics.pullback_quality_score,
                weekly_trend_quality=metrics.weekly_trend_quality or 0,
                avg_volume_10d=metrics.avg_volume_10d or 0,
                cluster_score=cluster_score
            )
            members.append(member)
        
        cluster = self._create_cluster(
            ClusterType.EMA21_TEST,
            members,
            f"EMA21 Test Cluster ({len(members)} stocks within {max_distance_pct}% of EMA21)"
        )
        
        return cluster
    
    async def detect_ema21_reclaim_cluster(
        self,
        max_distance_pct: float = 1.0,
        min_quality_score: float = 60.0,
        min_volume: int = 700000,
        limit: int = 20
    ) -> Optional[SetupCluster]:
        """
        Detect cluster of stocks reclaiming EMA21.
        
        Stocks that recently lost EMA21 and are reclaiming it.
        """
        result = await self.db.execute(
            select(StockMetrics)
            .where(
                and_(
                    StockMetrics.distance_to_ema21.isnot(None),
                    StockMetrics.distance_to_ema21 >= -max_distance_pct,
                    StockMetrics.distance_to_ema21 <= max_distance_pct,
                    StockMetrics.pullback_quality_score >= min_quality_score,
                    StockMetrics.avg_volume_10d >= min_volume,
                    # Additional condition: recently below EMA21 (simulated by distance range)
                    StockMetrics.distance_to_ema50 >= -10  # Not too far from EMA50
                )
            )
            .order_by(StockMetrics.pullback_quality_score.desc())
            .limit(limit)
        )
        metrics_list = result.scalars().all()
        
        if not metrics_list:
            return None
        
        members = []
        for metrics in metrics_list:
            cluster_score = self._calculate_cluster_score(metrics)
            member = ClusterMember(
                symbol=metrics.symbol,
                current_price=metrics.current_price,
                distance_to_ema21=metrics.distance_to_ema21,
                pullback_quality_score=metrics.pullback_quality_score,
                weekly_trend_quality=metrics.weekly_trend_quality or 0,
                avg_volume_10d=metrics.avg_volume_10d or 0,
                cluster_score=cluster_score
            )
            members.append(member)
        
        cluster = self._create_cluster(
            ClusterType.EMA21_RECLAIM,
            members,
            f"EMA21 Reclaim Cluster ({len(members)} stocks reclaiming EMA21)"
        )
        
        return cluster
    
    async def detect_tightening_cluster(
        self,
        min_weekly_tightness: float = 0.6,
        min_weeks_in_base: int = 4,
        min_volume: int = 700000,
        limit: int = 20
    ) -> Optional[SetupCluster]:
        """
        Detect cluster of stocks in tightening phase.
        
        Stocks showing volume contraction and tight weekly closes.
        """
        result = await self.db.execute(
            select(StockMetrics)
            .where(
                and_(
                    StockMetrics.weekly_tightness.isnot(None),
                    StockMetrics.weekly_tightness >= min_weekly_tightness,
                    StockMetrics.weeks_in_base >= min_weeks_in_base,
                    StockMetrics.avg_volume_10d >= min_volume,
                    StockMetrics.volume_contraction > 0.3  # Significant volume contraction
                )
            )
            .order_by(StockMetrics.weekly_tightness.desc())
            .limit(limit)
        )
        metrics_list = result.scalars().all()
        
        if not metrics_list:
            return None
        
        members = []
        for metrics in metrics_list:
            cluster_score = self._calculate_cluster_score(metrics)
            member = ClusterMember(
                symbol=metrics.symbol,
                current_price=metrics.current_price,
                distance_to_ema21=metrics.distance_to_ema21 or 0,
                pullback_quality_score=metrics.pullback_quality_score or 0,
                weekly_trend_quality=metrics.weekly_trend_quality or 0,
                avg_volume_10d=metrics.avg_volume_10d or 0,
                cluster_score=cluster_score
            )
            members.append(member)
        
        cluster = self._create_cluster(
            ClusterType.TIGHTENING,
            members,
            f"Tightening Cluster ({len(members)} stocks in consolidation phase)"
        )
        
        return cluster
    
    async def detect_sector_rotation_clusters(
        self,
        min_cluster_size: int = 5,
        limit: int = 10
    ) -> List[SetupCluster]:
        """
        Detect sector rotation patterns by clustering stocks by sector.
        
        Returns clusters of stocks in the same sector showing similar technical patterns.
        """
        # This would require sector data in the database
        # For now, return empty list as placeholder
        return []
    
    async def get_all_active_clusters(
        self
    ) -> Dict[ClusterType, Optional[SetupCluster]]:
        """
        Get all active setup clusters.
        
        Returns dictionary mapping cluster types to their clusters.
        """
        clusters = {}
        
        # Detect EMA21 test cluster
        ema21_test = await self.detect_ema21_test_cluster()
        clusters[ClusterType.EMA21_TEST] = ema21_test
        
        # Detect EMA21 reclaim cluster
        ema21_reclaim = await self.detect_ema21_reclaim_cluster()
        clusters[ClusterType.EMA21_RECLAIM] = ema21_reclaim
        
        # Detect tightening cluster
        tightening = await self.detect_tightening_cluster()
        clusters[ClusterType.TIGHTENING] = tightening
        
        return clusters
    
    # --- Helper methods ---
    
    def _calculate_cluster_score(self, metrics: StockMetrics) -> float:
        """
        Calculate cluster score for a stock (0-1).
        
        Based on:
        - Pullback quality score (40%)
        - Weekly trend quality (30%)
        - Volume pattern (20%)
        - Distance to EMA21 (10%)
        """
        score = 0.0
        
        # Pullback quality contribution
        if metrics.pullback_quality_score:
            score += (metrics.pullback_quality_score / 100.0) * 0.4
        
        # Weekly trend contribution
        if metrics.weekly_trend_quality:
            score += metrics.weekly_trend_quality * 0.3
        
        # Volume pattern contribution
        if metrics.volume_contraction:
            score += metrics.volume_contraction * 0.2
        
        # EMA21 distance contribution
        if metrics.distance_to_ema21:
            # Closer to EMA21 = higher score
            distance_score = max(0, 1 - abs(metrics.distance_to_ema21) / 10.0)
            score += distance_score * 0.1
        
        return min(1.0, max(0.0, score))
    
    def _create_cluster(
        self,
        cluster_type: ClusterType,
        members: List[ClusterMember],
        narrative: str
    ) -> SetupCluster:
        """Create a SetupCluster from members"""
        if not members:
            return None
        
        cluster_size = len(members)
        
        # Calculate averages
        avg_distance_to_ema21 = sum(m.distance_to_ema21 for m in members) / cluster_size
        avg_pullback_quality = sum(m.pullback_quality_score for m in members) / cluster_size
        avg_weekly_trend = sum(m.weekly_trend_quality for m in members) / cluster_size
        total_volume = sum(m.avg_volume_10d for m in members)
        
        # Calculate cluster quality score
        cluster_quality_score = sum(m.cluster_score for m in members) / cluster_size
        
        # Sector distribution (placeholder - would need sector data)
        sector_distribution = {}
        
        return SetupCluster(
            cluster_type=cluster_type,
            members=members,
            cluster_size=cluster_size,
            avg_distance_to_ema21=avg_distance_to_ema21,
            avg_pullback_quality=avg_pullback_quality,
            avg_weekly_trend=avg_weekly_trend,
            total_volume=total_volume,
            cluster_quality_score=cluster_quality_score,
            sector_distribution=sector_distribution,
            narrative=narrative
        )
