"""
Setup Lifecycle Event Flow

Persistent state per ticker with lifecycle transitions.
Each transition emits internal events.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Set
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from app.market_data.events.event_bus import MarketEvent, MarketEventType, EventPriority
from app.market_data.cache.redis_cache import redis_cache

logger = logging.getLogger(__name__)


class SetupLifecycleState(Enum):
    """Setup lifecycle states"""
    CONSTRUCTIVE_PULLBACK = "constructive_pullback"
    RECLAIM_ATTEMPT = "reclaim_attempt"
    RECLAIM_STRENGTHENING = "reclaim_strengthening"
    CONTINUATION = "continuation"
    EXTENDED = "extended"
    DETERIORATION = "deterioration"
    UNKNOWN = "unknown"


@dataclass
class SetupState:
    """Persistent setup state for a ticker"""
    symbol: str
    current_state: SetupLifecycleState = SetupLifecycleState.UNKNOWN
    previous_state: SetupLifecycleState = SetupLifecycleState.UNKNOWN
    state_entered_at: datetime = field(default_factory=datetime.utcnow)
    last_transition: datetime = field(default_factory=datetime.utcnow)
    transition_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "current_state": self.current_state.value,
            "previous_state": self.previous_state.value,
            "state_entered_at": self.state_entered_at.isoformat(),
            "last_transition": self.last_transition.isoformat(),
            "transition_count": self.transition_count,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SetupState':
        """Create from dictionary"""
        return cls(
            symbol=data["symbol"],
            current_state=SetupLifecycleState(data["current_state"]),
            previous_state=SetupLifecycleState(data["previous_state"]),
            state_entered_at=datetime.fromisoformat(data["state_entered_at"]),
            last_transition=datetime.fromisoformat(data["last_transition"]),
            transition_count=data["transition_count"],
            metadata=data.get("metadata", {})
        )


class SetupLifecycleEngine:
    """
    Setup Lifecycle Engine
    
    Maintains persistent state per ticker:
    - constructive_pullback → reclaim_attempt → reclaim_strengthening → continuation → extended → deterioration
    
    Each transition emits internal events.
    """
    
    def __init__(self):
        self._setup_states: Dict[str, SetupState] = {}
        self._subscribers = []
        self._running = False
        self._processor_task = None
    
    async def start(self):
        """Start the setup lifecycle engine."""
        if self._running:
            return
        
        self._running = True
        logger.info("Starting setup lifecycle engine")
        
        # Load initial states from cache
        await self._load_states()
        
        # Start background processor
        self._processor_task = asyncio.create_task(self._process_events())
    
    async def stop(self):
        """Stop the setup lifecycle engine."""
        if not self._running:
            return
        
        self._running = False
        logger.info("Stopping setup lifecycle engine")
        
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
        Handle market events and update setup state if relevant.
        
        Args:
            event: Market event
        """
        if not self._running:
            return
        
        symbol = event.symbol
        if not symbol:
            return
        
        # Determine if this event affects setup state
        if event.event_type in [
            MarketEventType.PRICE_BREAK,
            MarketEventType.EMA21_LOST,
            MarketEventType.RECLAIM_ATTEMPT,
            MarketEventType.RS_IMPROVING,
            MarketEventType.SETUP_DETERIORATION,
            MarketEventType.TRANSITION_STRENGTHENING
        ]:
            await self._update_setup_state(symbol, event)
    
    async def _process_events(self):
        """Process events that affect setup state."""
        logger.info("Starting setup lifecycle event processor")
        
        while self._running:
            await asyncio.sleep(0.1)
    
    async def _update_setup_state(self, symbol: str, event: MarketEvent):
        """
        Update setup state based on event.
        
        Args:
            symbol: Ticker symbol
            event: Market event
        """
        # Get or create state
        if symbol not in self._setup_states:
            self._setup_states[symbol] = SetupState(symbol=symbol)
        
        old_state = self._setup_states[symbol].current_state
        new_state = self._determine_new_state(symbol, event, old_state)
        
        if new_state != old_state:
            # State transition
            await self._transition_state(symbol, old_state, new_state, event)
    
    def _determine_new_state(
        self,
        symbol: str,
        event: MarketEvent,
        current_state: SetupLifecycleState
    ) -> SetupLifecycleState:
        """
        Determine new state based on event.
        
        Args:
            symbol: Ticker symbol
            event: Market event
            current_state: Current setup state
            
        Returns:
            New setup state
        """
        # State transition logic
        if event.event_type == MarketEventType.RECLAIM_ATTEMPT:
            if current_state in [SetupLifecycleState.CONSTRUCTIVE_PULLBACK, SetupLifecycleState.DETERIORATION]:
                return SetupLifecycleState.RECLAIM_ATTEMPT
        
        elif event.event_type == MarketEventType.TRANSITION_STRENGTHENING:
            if current_state == SetupLifecycleState.RECLAIM_ATTEMPT:
                return SetupLifecycleState.RECLAIM_STRENGTHENING
            elif current_state == SetupLifecycleState.RECLAIM_STRENGTHENING:
                return SetupLifecycleState.CONTINUATION
        
        elif event.event_type == MarketEventType.SETUP_DETERIORATION:
            if current_state in [
                SetupLifecycleState.CONTINUATION,
                SetupLifecycleState.EXTENDED,
                SetupLifecycleState.RECLAIM_STRENGTHENING
            ]:
                return SetupLifecycleState.DETERIORATION
        
        elif event.event_type == MarketEventType.PRICE_BREAK:
            if current_state == SetupLifecycleState.CONTINUATION:
                return SetupLifecycleState.EXTENDED
        
        # No state change
        return current_state
    
    async def _transition_state(
        self,
        symbol: str,
        old_state: SetupLifecycleState,
        new_state: SetupLifecycleState,
        event: MarketEvent
    ):
        """
        Execute state transition and emit event.
        
        Args:
            symbol: Ticker symbol
            old_state: Previous state
            new_state: New state
            event: Triggering event
        """
        state = self._setup_states[symbol]
        
        # Update state
        state.previous_state = old_state
        state.current_state = new_state
        state.state_entered_at = datetime.utcnow()
        state.last_transition = datetime.utcnow()
        state.transition_count += 1
        
        # Update metadata
        state.metadata.update({
            "triggering_event": event.event_type,
            "triggering_event_id": event.event_id
        })
        
        logger.info(f"Setup state transition for {symbol}: {old_state.value} → {new_state.value}")
        
        # Save to cache
        await self._save_state(symbol)
        
        # Emit state change event
        await self._emit_state_change_event(symbol, old_state, new_state, event)
        
        # Notify subscribers
        await self._notify_subscribers(symbol, state)
    
    async def _emit_state_change_event(
        self,
        symbol: str,
        old_state: SetupLifecycleState,
        new_state: SetupLifecycleState,
        triggering_event: MarketEvent
    ):
        """
        Emit setup state change event.
        
        Args:
            symbol: Ticker symbol
            old_state: Previous state
            new_state: New state
            triggering_event: Event that triggered transition
        """
        from app.market_data.events.event_bus import event_bus
        
        state_change_event = MarketEvent(
            event_type=MarketEventType.SETUP_STATE_CHANGE,
            symbol=symbol,
            priority=EventPriority.MEDIUM,
            data={
                "old_state": old_state.value,
                "new_state": new_state.value,
                "triggering_event": triggering_event.event_type,
                "transition_count": self._setup_states[symbol].transition_count
            },
            metadata={
                "triggering_event_id": triggering_event.event_id
            }
        )
        
        await event_bus.publish(state_change_event)
    
    async def _notify_subscribers(self, symbol: str, state: SetupState):
        """Notify subscribers of state change."""
        for handler in self._subscribers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(symbol, state)
                else:
                    handler(symbol, state)
            except Exception as e:
                logger.error(f"Error notifying setup lifecycle subscriber: {e}")
    
    async def _save_state(self, symbol: str):
        """Save state to cache."""
        try:
            state = self._setup_states[symbol]
            state_dict = state.to_dict()
            await redis_cache.set_setup_state(symbol, state_dict)
        except Exception as e:
            logger.error(f"Error saving setup state for {symbol}: {e}")
    
    async def _load_states(self):
        """Load states from cache."""
        # In a full implementation, this would load states for all tracked symbols
        # For now, we'll load states on-demand
        pass
    
    def get_setup_state(self, symbol: str) -> Optional[SetupState]:
        """
        Get setup state for a symbol.
        
        Args:
            symbol: Ticker symbol
            
        Returns:
            Setup state or None if not tracked
        """
        return self._setup_states.get(symbol)
    
    async def initialize_state(self, symbol: str, initial_state: SetupLifecycleState):
        """
        Initialize setup state for a symbol.
        
        Args:
            symbol: Ticker symbol
            initial_state: Initial setup state
        """
        if symbol not in self._setup_states:
            self._setup_states[symbol] = SetupState(
                symbol=symbol,
                current_state=initial_state,
                previous_state=SetupLifecycleState.UNKNOWN
            )
            await self._save_state(symbol)
            logger.info(f"Initialized setup state for {symbol}: {initial_state.value}")
    
    async def force_transition(self, symbol: str, new_state: SetupLifecycleState, reason: str):
        """
        Force a state transition.
        
        Args:
            symbol: Ticker symbol
            new_state: New state to transition to
            reason: Reason for transition
        """
        if symbol not in self._setup_states:
            await self.initialize_state(symbol, SetupLifecycleState.UNKNOWN)
        
        old_state = self._setup_states[symbol].current_state
        
        # Create dummy event
        dummy_event = MarketEvent(
            event_type="manual_transition",
            symbol=symbol,
            priority=EventPriority.MEDIUM,
            data={"reason": reason}
        )
        
        await self._transition_state(symbol, old_state, new_state, dummy_event)


# Global setup lifecycle engine instance
setup_lifecycle_engine = SetupLifecycleEngine()
