"""
Universe Engine API Endpoints

Endpoints for:
- Universe refresh
- Discovery candidates
- Tier management
- Health monitoring
- Universe statistics
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.deps import get_db
from app.universe.universe_engine import get_universe_engine
from app.universe.monitoring.health_monitor import UniverseHealthReport
from pydantic import BaseModel

router = APIRouter()


class UniverseRefreshResponse(BaseModel):
    """Response for universe refresh"""
    total_tickers: int
    new_tickers: int
    tier_distribution: Dict[str, Any]


class HealthReportResponse(BaseModel):
    """Response for health report"""
    timestamp: str
    total_tickers: int
    active_tickers: int
    stale_tickers: int
    dead_listings: int
    universe_freshness: Optional[float]
    alerts: List[Dict[str, Any]]


class UniverseStatisticsResponse(BaseModel):
    """Response for universe statistics"""
    identity_statistics: Dict[str, Any]
    tier_statistics: Dict[str, Any]
    discovery_statistics: Dict[str, Any]
    scan_statistics: Dict[str, Any]
    health_statistics: Dict[str, Any]
    event_statistics: Dict[str, Any]


@router.post("/refresh", response_model=UniverseRefreshResponse)
async def refresh_universe(db: AsyncSession = Depends(get_db)):
    """
    Refresh universe from all sources.
    
    Fetches tickers from all configured sources, normalizes, validates,
    assigns identities, enriches, and assigns tiers.
    """
    try:
        universe_engine = get_universe_engine()
        stats = await universe_engine.refresh_universe(db)
        return UniverseRefreshResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=HealthReportResponse)
async def get_health_report(db: AsyncSession = Depends(get_db)):
    """
    Get universe health report.
    
    Returns comprehensive health metrics including freshness,
    coverage gaps, stale tickers, and alerts.
    """
    try:
        universe_engine = get_universe_engine()
        report = await universe_engine.generate_health_report(db)
        return HealthReportResponse(
            timestamp=report.timestamp.isoformat(),
            total_tickers=report.total_tickers,
            active_tickers=report.active_tickers,
            stale_tickers=report.stale_tickers,
            dead_listings=report.dead_listings,
            universe_freshness=report.universe_freshness,
            alerts=[a.to_dict() for a in report.alerts]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", response_model=UniverseStatisticsResponse)
async def get_universe_statistics():
    """
    Get universe statistics.
    
    Returns aggregated statistics from all Universe Engine components.
    """
    try:
        universe_engine = get_universe_engine()
        stats = await universe_engine.get_universe_statistics()
        return UniverseStatisticsResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # Agregado paréntesis de cierre


@router.post("/scans")
async def run_nightly_scans(db: AsyncSession = Depends(get_db)):
    """
    Run nightly discovery scans.
    
    Runs all discovery scans to detect new leaders, emerging structure,
    volume anomalies, and other market patterns.
    """
    try:
        universe_engine = get_universe_engine()
        results = await universe_engine.run_nightly_scans(db)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tiers")
async def get_tier_distribution():
    """
    Get tier distribution.
    
    Returns the distribution of tickers across all tiers.
    """
    try:
        universe_engine = get_universe_engine()
        stats = universe_engine.tier_manager.get_tier_statistics()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/identities")
async def get_all_identities():
    """
    Get all instrument identities.
    
    Returns all canonical instrument identities in the universe.
    """
    try:
        universe_engine = get_universe_engine()
        identities = universe_engine.identity_manager.get_all_identities()
        return {
            "total": len(identities),
            "identities": [i.to_dict() for i in identities]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/identities/{symbol}")
async def get_identity_by_symbol(symbol: str):
    """
    Get instrument identity by symbol.
    
    Returns the canonical identity for a given symbol,
    including historical symbols and lifecycle state.
    """
    try:
        universe_engine = get_universe_engine()
        identity = universe_engine.identity_manager.get_identity_by_symbol(symbol)
        if not identity:
            raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
        return identity.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/discovery/candidates")
async def get_discovery_candidates(
    trigger: Optional[str] = None,
    min_confidence: Optional[float] = None,
    limit: int = 100
):
    """
    Get discovery candidates.
    
    Returns candidates from auto discovery with optional filtering.
    """
    try:
        universe_engine = get_universe_engine()
        from app.universe.discovery.auto_discovery import DiscoveryTrigger
        
        trigger_filter = DiscoveryTrigger(trigger) if trigger else None
        candidates = universe_engine.discovery_engine.get_candidates(
            trigger=trigger_filter,
            min_confidence=min_confidence or 0,
            limit=limit
        )
        return {
            "total": len(candidates),
            "candidates": [c.to_dict() for c in candidates]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
