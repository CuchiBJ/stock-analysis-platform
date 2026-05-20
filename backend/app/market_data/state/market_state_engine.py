"""
Market State Engine

Maintains market state incrementally:
- Current regime
- Leadership quality
- Market forgiveness
- Continuation pressure
- Deterioration pressure
- Breadth state
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from app.market_data.events.event_bus import MarketEvent, MarketEventType, EventPriority
from app.market_data.cache.redis_cache import redis_cache

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime types"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    TRANSITIONING = "transitioning"


class BreadthQuality(Enum):
    """Breadth quality levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


@dataclass
class MarketState:
    """Current market state"""
    regime: MarketRegime = MarketRegime.NEUTRAL
    leadership_quality: float = 0.0  # 0-100
    market_forgiveness: float = 0.0  # 0-100
    continuation_pressure: float = 0.0  # 0-100
    deterioration_pressure: float = 0.0  # 0-100
    breadth_quality: BreadthQuality = BreadthQuality.FAIR
    breadth_score: float = 0.0  # 0-100
    leaders_above_ema21: int = 0
    leaders_above_ema50: int = 0
    total_leaders: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "regime": self.regime.value,
            "leadership_quality": self.leadership_quality,
            "market_forgiveness": self.market_forgiveness,
            "continuation_pressure": self.continuation_pressure,
            "deterioration_pressure": self.deterioration_pressure,
            "breadth_quality": self.breadth_quality.value,
            "breadth_score": self.breadth_score,
            "leaders_above_ema21": self.leaders_above_ema21,
            "leaders_above_ema50": self.leaders_above_ema50,
            "total_leaders": self.total_leaders,
            "last_updated": self.last_updated.isoformat()
        }


class MarketStateEngine:
    """
    Market State Engine
    
    Maintains market state incrementally:
    - Event-driven updates
    - Incremental changes
    - State transitions
    - State persistence
    
    Updates only when relevant events occur, not on every tick.
    """
    
    def __init__(self):
        self._state = MarketState()
        self._subscribers = []
        self._running = False
        self._processor_task = None
    
    async def start(self):
        """Start the market state engine."""
        if self._running:
            return
        
        self._running = True
        logger.info("Starting market state engine")
        
        # Load initial state from cache
        await self._load_state()
        
        # Start background processor
        self._processor_task = asyncio.create_task(self._process_events())
    
    async def stop(self):
        """Stop the market state engine."""
        if not self._running:
            return
        
        self._running = False
        logger.info("Stopping market state engine")
        
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
    
    def subscribe(self, handler):
        """Subscribe to state changes."""
        self._subscribers.append(handler)
    
    def unsubscribe(self, handler):
        """Unsubscribe from state changes."""
        if handler in self._subscribers:
            self._subscribers.remove(handler)
    
    async def handle_event(self, event: MarketEvent):
        """
        Handle market events and update state if relevant.
        
        Args:
            event: Market event
        """
        if not self._running:
            return
        
        # Only certain events affect market state
        if event.event_type in [
            MarketEventType.REGIME_SHIFT,
            MarketEventType.BREADTH_CHANGE,
            MarketEventType.SECTOR_LEADERSHIP_SHIFT,
            MarketEventType.TRANSITION_STRENGTHENING,
            MarketEventType.SETUP_DETERIORATION
        ]:
            await self._update_state_from_event(event)
    
    async def _process_events(self):
        """Process events that affect market state."""
        logger.info("Starting market state event processor")
        
        while self._running:
            await asyncio.sleep(0.1)
    
    async def _update_state_from_event(self, event: MarketEvent):
        """
        Update market state from an event.
        
        Args:
            event: Market event
        """
        old_state = self._state.to_dict()
        
        # Update based on event type
        if event.event_type == MarketEventType.REGIME_SHIFT:
            self._update_regime(event)
        elif event.event_type == MarketEventType.BREADTH_CHANGE:
            self._update_breadth(event)
        elif event.event_type == MarketEventType.SECTOR_LEADERSHIP_SHIFT:
            self._update_leadership(event)
        elif event.event_type == MarketEventType.TRANSITION_STRENGTHENING:
            self._update_continuation_pressure(event)
        elif event.event_type == MarketEventType.SETUP_DETERIORATION:
            self._update_deterioration_pressure(event)
        
        self._state.last_updated = datetime.utcnow()
        
        # Check if state changed
        new_state = self._state.to_dict()
        if old_state != new_state:
            await self._notify_subscribers()
            await self._save_state()
    
    def _update_regime(self, event: MarketEvent):
        """Update regime from event."""
        regime = event.data.get("regime")
        if regime:
            try:
                self._state.regime = MarketRegime(regime)
                logger.info(f"Regime updated to {regime}")
            except ValueError:
                logger.warning(f"Invalid regime: {regime}")
    
    def _update_breadth(self, event: MarketEvent):
        """Update breadth from event."""
        breadth_score = event.data.get("breadth_score")
        if breadth_score is not None:
            self._state.breadth_score = breadth_score
            
            # Determine breadth quality
            if breadth_score >= 80:
                self._state.breadth_quality = BreadthQuality.EXCELLENT
            elif breadth_score >= 60:
                self._state.breadth_quality = BreadthQuality.GOOD
            elif breadth_score >= 40:
                self._state.breadth_quality = BreadthQuality.FAIR
            else:
                self._state.breadth_quality = BreadthQuality.POOR
            
            logger.info(f"Breadth updated: {breadth_score} ({self._state.breadth_quality.value})")
        
        # Update leader counts
        leaders_above_ema21 = event.data.get("leaders_above_ema21")
        leaders_above_ema50 = event.data.get("leaders_above_ema50")
        total_leaders = event.data.get("total_leaders")
        
        if leaders_above_ema21 is not None:
            self._state.leaders_above_ema21 = leaders_above_ema21
        if leaders_above_ema50 is not None:
            self._state.leaders_above_ema50 = leaders_above_ema50
        if total_leaders is not None:
            self._state.total_leaders = total_leaders
    
    def _update_leadership(self, event: MarketEvent):
        """Update leadership quality from event."""
        leadership_quality = event.data.get("leadership_quality")
        if leadership_quality is not None:
            self._state.leadership_quality = leadership_quality
            logger.info(f"Leadership quality updated: {leadership_quality}")
    
    def _update_continuation_pressure(self, event: MarketEvent):
        """Update continuation pressure from event."""
        continuation_pressure = event.data.get("continuation_pressure")
        if continuation_pressure is not None:
            self._state.continuation_pressure = continuation_pressure
            logger.info(f"Continuation pressure updated: {continuation_pressure}")
    
    def _update_deterioration_pressure(self, event: MarketEvent):
        """Update deterioration pressure from event."""
        deterioration_pressure = event.data.get("deterioration_pressure")
        if deterioration_pressure is not None:
            self._state.deterioration_pressure = deterioration_pressure
            logger.info(f"Deterioration pressure updated: {deterioration_pressure}")
    
    async def _notify_subscribers(self):
        """Notify subscribers of state change."""
        for handler in self._subscribers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(self._state)
                else:
                    handler(self._state)
            except Exception as e:
                logger.error(f"Error notifying state subscriber: {e}")
    
    async def _save_state(self):
        """Save state to cache."""
        try:
            state_dict = self._state.to_dict()
            await redis_cache.set_regime_state(state_dict)
        except Exception as e:
            logger.error(f"Error saving state to cache: {e}")
    
    async def _load_state(self):
        """Load state from cache."""
        try:
            state_dict = await redis_cache.get_regime_state()
            if state_dict:
                self._state = MarketState(
                    regime=MarketRegime(state_dict.get("regime", "neutral")),
                    leadership_quality=state_dict.get("leadership_quality", 0.0),
                    market_forgiveness=state_dict.get("market_forgiveness", 0.0),
                    continuation_pressure=state_dict.get("continuation_pressure", 0.0),
                    deterioration_pressure=state_dict.get("deterioration_pressure", 0.0),
                    breadth_quality=BreadthQuality(state_dict.get("breadth_quality", "fair")),
                    breadth_score=state_dict.get("breadth_score", 0.0),
                    leaders_above_ema21=state_dict.get("leaders_above_ema21", 0),
                    leaders_above_ema50=state_dict.get("leaders_above_ema50", 0),
                    total_leaders=state_dict.get("total_leaders", 0),
                    last_updated=datetime.fromisoformat(state_dict.get("last_updated", datetime.utcnow().isoformat()))
                )
                logger.info("Loaded market state from cache")
        except Exception as e:
            logger.error(f"Error loading state from cache: {e}")
    
    def get_state(self) -> MarketState:
        """Get current market state."""
        return self._state
    
    async def update_breadth_metrics(
        self,
        leaders_above_ema21: int,
        leaders_above_ema50: int,
        total_leaders: int,
        breadth_score: float
    ):
        """
        Update breadth metrics.
        
        Args:
            leaders_above_ema21: Number of leaders above EMA21
            leaders_above_ema50: Number of leaders above EMA50
            total_leaders: Total number of leaders
            breadth_score: Overall breadth score (0-100)
        """
        self._state.leaders_above_ema21 = leaders_above_ema21
        self._state.leaders_above_ema50 = leaders_above_ema50
        self._state.total_leaders = total_leaders
        self._state.breadth_score = breadth_score
        
        # Determine breadth quality
        if breadth_score >= 80:
            self._state.breadth_quality = BreadthQuality.EXCELLENT
        elif breadth_score >= 60:
            self._state.breadth_quality = BreadthQuality.GOOD
        elif breadth_score >= 40:
            self._state.breadth_quality = BreadthQuality.FAIR
        else:
            self._state.breadth_quality = BreadthQuality.POOR
        
        self._state.last_updated = datetime.utcnow()
        
        await self._save_state()
        await self._notify_subscribers()
        
        logger.info(f"Breadth metrics updated: {breadth_score} ({self._state.breadth_quality.value})")


# Global market state engine instance
market_state_engine = MarketStateEngine()
