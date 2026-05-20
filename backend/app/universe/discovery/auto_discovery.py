"""
Auto Discovery Engine

CRITICAL: Automatically discover new leaders.

Discovery Triggers:
- Volume explosion (3x average volume)
- RS acceleration (RS > 2.0 for 5 days)
- Unusual institutional activity (large block trades)
- Sector leadership emergence (top of sector)
- Explosive continuation (breakout with volume)
- Abnormal relative strength (RS > 3.0)
- High-quality reclaim (reclaim with tight structure)
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from app.market_data.events.event_bus import MarketEvent, EventPriority

logger = logging.getLogger(__name__)


class DiscoveryTrigger(Enum):
    """Discovery trigger types"""
    VOLUME_EXPLOSION = "volume_explosion"
    RS_ACCELERATION = "rs_acceleration"
    UNUSUAL_ACTIVITY = "unusual_activity"
    SECTOR_LEADERSHIP = "sector_leadership"
    BREAKOUT = "breakout"
    ABNORMAL_RS = "abnormal_rs"
    RECLAIM_QUALITY = "reclaim_quality"


@dataclass
class DiscoveryCandidate:
    """Candidate discovered by auto discovery"""
    symbol: str
    trigger: DiscoveryTrigger
    timestamp: datetime
    data: Dict[str, Any]
    confidence: float  # 0-100
    priority: int  # 1-10 (1 = highest)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "trigger": self.trigger.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "confidence": self.confidence,
            "priority": self.priority
        }


class AutoDiscoveryEngine:
    """
    Auto Discovery Engine
    
    CRITICAL: Automatically discover new leaders.
    
    Discovery Pipeline:
    Market data stream
      → Detect anomaly (volume explosion, RS acceleration, etc.)
      → Validate ticker (not already in universe, passes validation)
      → Enrich ticker (sector, float, liquidity, etc.)
      → Add to universe
      → Assign tier (based on quality)
      → Emit NewLeaderDiscoveredEvent
      → Start tracking lifecycle
      → If TIER 1: Start realtime tracking
    """
    
    def __init__(self):
        self._discovered_candidates: List[DiscoveryCandidate] = []
        self._discovery_thresholds = self._init_thresholds()
    
    def _init_thresholds(self) -> Dict[DiscoveryTrigger, Dict[str, Any]]:
        """Initialize discovery thresholds"""
        return {
            DiscoveryTrigger.VOLUME_EXPLOSION: {
                "volume_multiplier": 3.0,  # 3x average volume
                "min_volume": 1_000_000,  # 1M shares minimum
                "confidence_boost": 20
            },
            DiscoveryTrigger.RS_ACCELERATION: {
                "rs_threshold": 2.0,  # RS > 2.0
                "consecutive_days": 5,
                "confidence_boost": 30
            },
            DiscoveryTrigger.UNUSUAL_ACTIVITY: {
                "block_trade_threshold": 1_000_000,  # $1M block trade
                "confidence_boost": 15
            },
            DiscoveryTrigger.SECTOR_LEADERSHIP: {
                "sector_rank_threshold": 3,  # Top 3 in sector
                "confidence_boost": 25
            },
            DiscoveryTrigger.BREAKOUT: {
                "price_change_threshold": 0.10,  # 10% price change
                "volume_multiplier": 2.0,
                "confidence_boost": 20
            },
            DiscoveryTrigger.ABNORMAL_RS: {
                "rs_threshold": 3.0,  # RS > 3.0
                "confidence_boost": 35
            },
            DiscoveryTrigger.RECLAIM_QUALITY: {
                "reclaim_ema": "ema21",
                "volume_multiplier": 1.5,
                "tightness_threshold": 0.02,  # 2% tightness
                "confidence_boost": 25
            }
        }
    
    def detect_volume_explosion(
        self,
        symbol: str,
        current_volume: int,
        avg_volume: int,
        current_price: float
    ) -> Optional[DiscoveryCandidate]:
        """
        Detect volume explosion (3x average volume).
        
        Args:
            symbol: Ticker symbol
            current_volume: Current day's volume
            avg_volume: Average volume
            current_price: Current price
            
        Returns:
            DiscoveryCandidate if detected, None otherwise
        """
        threshold = self._discovery_thresholds[DiscoveryTrigger.VOLUME_EXPLOSION]
        
        if avg_volume == 0:
            return None
        
        volume_multiplier = current_volume / avg_volume
        
        if volume_multiplier >= threshold["volume_multiplier"] and current_volume >= threshold["min_volume"]:
            confidence = min(100, 50 + threshold["confidence_boost"])
            
            candidate = DiscoveryCandidate(
                symbol=symbol,
                trigger=DiscoveryTrigger.VOLUME_EXPLOSION,
                timestamp=datetime.utcnow(),
                data={
                    "current_volume": current_volume,
                    "avg_volume": avg_volume,
                    "volume_multiplier": volume_multiplier,
                    "current_price": current_price
                },
                confidence=confidence,
                priority=2
            )
            
            logger.info(f"Volume explosion detected: {symbol} ({volume_multiplier:.2f}x avg)")
            return candidate
        
        return None
    
    def detect_rs_acceleration(
        self,
        symbol: str,
        current_rs: float,
        rs_history: List[float]
    ) -> Optional[DiscoveryCandidate]:
        """
        Detect RS acceleration (RS > 2.0 for 5 consecutive days).
        
        Args:
            symbol: Ticker symbol
            current_rs: Current RS
            rs_history: RS history (last N days)
            
        Returns:
            DiscoveryCandidate if detected, None otherwise
        """
        threshold = self._discovery_thresholds[DiscoveryTrigger.RS_ACCELERATION]
        
        if current_rs < threshold["rs_threshold"]:
            return None
        
        # Check consecutive days above threshold
        consecutive_days = 0
        for rs in reversed(rs_history):
            if rs >= threshold["rs_threshold"]:
                consecutive_days += 1
            else:
                break
        
        if consecutive_days >= threshold["consecutive_days"]:
            confidence = min(100, 50 + threshold["confidence_boost"])
            
            candidate = DiscoveryCandidate(
                symbol=symbol,
                trigger=DiscoveryTrigger.RS_ACCELERATION,
                timestamp=datetime.utcnow(),
                data={
                    "current_rs": current_rs,
                    "consecutive_days": consecutive_days,
                    "rs_history": rs_history[-threshold["consecutive_days"]:]
                },
                confidence=confidence,
                priority=1
            )
            
            logger.info(f"RS acceleration detected: {symbol} (RS: {current_rs:.2f}, {consecutive_days} days)")
            return candidate
        
        return None
    
    def detect_abnormal_rs(
        self,
        symbol: str,
        current_rs: float
    ) -> Optional[DiscoveryCandidate]:
        """
        Detect abnormal relative strength (RS > 3.0).
        
        Args:
            symbol: Ticker symbol
            current_rs: Current RS
            
        Returns:
            DiscoveryCandidate if detected, None otherwise
        """
        threshold = self._discovery_thresholds[DiscoveryTrigger.ABNORMAL_RS]
        
        if current_rs >= threshold["rs_threshold"]:
            confidence = min(100, 50 + threshold["confidence_boost"])
            
            candidate = DiscoveryCandidate(
                symbol=symbol,
                trigger=DiscoveryTrigger.ABNORMAL_RS,
                timestamp=datetime.utcnow(),
                data={
                    "current_rs": current_rs
                },
                confidence=confidence,
                priority=1
            )
            
            logger.info(f"Abnormal RS detected: {symbol} (RS: {current_rs:.2f})")
            return candidate
        
        return None
    
    def detect_breakout(
        self,
        symbol: str,
        price_change: float,
        current_volume: int,
        avg_volume: int
    ) -> Optional[DiscoveryCandidate]:
        """
        Detect explosive continuation (breakout with volume).
        
        Args:
            symbol: Ticker symbol
            price_change: Price change (as percentage)
            current_volume: Current volume
            avg_volume: Average volume
            
        Returns:
            DiscoveryCandidate if detected, None otherwise
        """
        threshold = self._discovery_thresholds[DiscoveryTrigger.BREAKOUT]
        
        if avg_volume == 0:
            return None
        
        volume_multiplier = current_volume / avg_volume
        
        if abs(price_change) >= threshold["price_change_threshold"] and volume_multiplier >= threshold["volume_multiplier"]:
            confidence = min(100, 50 + threshold["confidence_boost"])
            
            candidate = DiscoveryCandidate(
                symbol=symbol,
                trigger=DiscoveryTrigger.BREAKOUT,
                timestamp=datetime.utcnow(),
                data={
                    "price_change": price_change,
                    "current_volume": current_volume,
                    "avg_volume": avg_volume,
                    "volume_multiplier": volume_multiplier
                },
                confidence=confidence,
                priority=2
            )
            
            logger.info(f"Breakout detected: {symbol} ({price_change:.2%}, {volume_multiplier:.2f}x volume)")
            return candidate
        
        return None
    
    def detect_sector_leadership(
        self,
        symbol: str,
        sector: str,
        sector_rank: int,
        sector_total: int
    ) -> Optional[DiscoveryCandidate]:
        """
        Detect sector leadership emergence (top of sector).
        
        Args:
            symbol: Ticker symbol
            sector: Sector
            sector_rank: Rank within sector (1 = top)
            sector_total: Total tickers in sector
            
        Returns:
            DiscoveryCandidate if detected, None otherwise
        """
        threshold = self._discovery_thresholds[DiscoveryTrigger.SECTOR_LEADERSHIP]
        
        if sector_rank <= threshold["sector_rank_threshold"]:
            confidence = min(100, 50 + threshold["confidence_boost"])
            
            candidate = DiscoveryCandidate(
                symbol=symbol,
                trigger=DiscoveryTrigger.SECTOR_LEADERSHIP,
                timestamp=datetime.utcnow(),
                data={
                    "sector": sector,
                    "sector_rank": sector_rank,
                    "sector_total": sector_total
                },
                confidence=confidence,
                priority=1
            )
            
            logger.info(f"Sector leadership detected: {symbol} (Rank: {sector_rank}/{sector_total} in {sector})")
            return candidate
        
        return None
    
    def detect_reclaim_quality(
        self,
        symbol: str,
        reclaimed_ema: str,
        volume_multiplier: float,
        tightness: float
    ) -> Optional[DiscoveryCandidate]:
        """
        Detect high-quality reclaim (reclaim with tight structure).
        
        Args:
            symbol: Ticker symbol
            reclaimed_ema: EMA that was reclaimed
            volume_multiplier: Volume multiplier
            tightness: Price tightness (as percentage)
            
        Returns:
            DiscoveryCandidate if detected, None otherwise
        """
        threshold = self._discovery_thresholds[DiscoveryTrigger.RECLAIM_QUALITY]
        
        if volume_multiplier >= threshold["volume_multiplier"] and tightness <= threshold["tightness_threshold"]:
            confidence = min(100, 50 + threshold["confidence_boost"])
            
            candidate = DiscoveryCandidate(
                symbol=symbol,
                trigger=DiscoveryTrigger.RECLAIM_QUALITY,
                timestamp=datetime.utcnow(),
                data={
                    "reclaimed_ema": reclaimed_ema,
                    "volume_multiplier": volume_multiplier,
                    "tightness": tightness
                },
                confidence=confidence,
                priority=2
            )
            
            logger.info(f"High-quality reclaim detected: {symbol} (Reclaimed {reclaimed_ema}, tightness: {tightness:.2%})")
            return candidate
        
        return None
    
    def add_candidate(self, candidate: DiscoveryCandidate):
        """
        Add discovered candidate to list.
        
        Args:
            candidate: Discovery candidate
        """
        self._discovered_candidates.append(candidate)
        logger.info(f"Added discovery candidate: {candidate.symbol} ({candidate.trigger.value})")
    
    def get_candidates(
        self,
        trigger: Optional[DiscoveryTrigger] = None,
        min_confidence: float = 0,
        limit: int = 100
    ) -> List[DiscoveryCandidate]:
        """
        Get discovered candidates with optional filtering.
        
        Args:
            trigger: Filter by trigger type
            min_confidence: Minimum confidence threshold
            limit: Maximum number of candidates to return
            
        Returns:
            List of discovery candidates
        """
        candidates = self._discovered_candidates
        
        # Filter by trigger
        if trigger:
            candidates = [c for c in candidates if c.trigger == trigger]
        
        # Filter by confidence
        candidates = [c for c in candidates if c.confidence >= min_confidence]
        
        # Sort by priority and confidence
        candidates = sorted(candidates, key=lambda c: (c.priority, -c.confidence))
        
        # Limit
        return candidates[:limit]
    
    def clear_candidates(self):
        """Clear all discovered candidates"""
        self._discovered_candidates.clear()
        logger.info("Cleared all discovery candidates")
    
    def get_discovery_statistics(self) -> Dict[str, Any]:
        """
        Get discovery statistics.
        
        Returns:
            Dictionary with statistics
        """
        total = len(self._discovered_candidates)
        
        # Count by trigger
        trigger_counts = {}
        for candidate in self._discovered_candidates:
            trigger_counts[candidate.trigger.value] = trigger_counts.get(candidate.trigger.value, 0) + 1
        
        # Average confidence
        if total > 0:
            avg_confidence = sum(c.confidence for c in self._discovered_candidates) / total
        else:
            avg_confidence = 0
        
        return {
            "total_candidates": total,
            "trigger_distribution": trigger_counts,
            "average_confidence": avg_confidence,
            "high_confidence_count": sum(1 for c in self._discovered_candidates if c.confidence >= 80)
        }
    
    def emit_discovery_event(self, candidate: DiscoveryCandidate) -> MarketEvent:
        """
        Emit discovery event to event bus.
        
        Args:
            candidate: Discovery candidate
            
        Returns:
            MarketEvent
        """
        event = MarketEvent(
            event_type="new_leader_discovered",
            symbol=candidate.symbol,
            priority=EventPriority.HIGH if candidate.priority == 1 else EventPriority.MEDIUM,
            data={
                "trigger": candidate.trigger.value,
                "confidence": candidate.confidence,
                "discovery_data": candidate.data
            },
            metadata={
                "discovery_timestamp": candidate.timestamp.isoformat()
            }
        )
        
        return event
