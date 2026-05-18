"""Setup Replay Engine - Track state history and transition logs"""

from enum import Enum
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.setup_lifecycle_engine import SetupState, StateTransition
import logging

logger = logging.getLogger(__name__)


class ReplayEventType(Enum):
    """Types of replay events"""
    STATE_TRANSITION = "state_transition"
    SETUP_ENTRY = "setup_entry"
    SETUP_EXIT = "setup_exit"
    INVALIDATION = "invalidation"
    RANKING_CHANGE = "ranking_change"
    QUALITY_UPDATE = "quality_update"


@dataclass
class ReplayEvent:
    """Single event in setup replay"""
    event_type: ReplayEventType
    timestamp: datetime
    symbol: str
    from_state: Optional[SetupState]
    to_state: Optional[SetupState]
    quality_score: float
    priority_score: float
    market_regime: str
    metadata: Dict


@dataclass
class SetupReplay:
    """Complete replay of a setup's lifecycle"""
    symbol: str
    events: List[ReplayEvent]
    start_time: datetime
    end_time: datetime
    total_duration_hours: float
    state_transitions: int
    final_state: SetupState
    peak_quality_score: float
    peak_priority_score: float
    avg_quality_score: float
    avg_priority_score: float
    setup_success: bool


class ReplayEngine:
    """
    Setup Replay Engine - Track state history and transition logs.
    
    Core philosophy: Understanding how setups evolve over time is crucial
    for improving detection algorithms and understanding market patterns.
    The replay engine maintains a complete history of setup states, transitions,
    and quality metrics for post-mortem analysis and learning.
    
    Expected outcome:
    - Complete audit trail of setup lifecycle
    - Ability to replay setup evolution for analysis
    - Identify patterns in successful vs failed setups
    - Improve detection algorithms through historical analysis
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.active_replays: Dict[str, List[ReplayEvent]] = {}
    
    def start_replay(self, symbol: str, initial_state: SetupState) -> None:
        """
        Start a new replay for a setup.
        
        Args:
            symbol: Stock symbol
            initial_state: Initial setup state
        """
        event = ReplayEvent(
            event_type=ReplayEventType.SETUP_ENTRY,
            timestamp=datetime.now(),
            symbol=symbol,
            from_state=None,
            to_state=initial_state,
            quality_score=0.0,
            priority_score=0.0,
            market_regime="unknown",
            metadata={}
        )
        
        if symbol not in self.active_replays:
            self.active_replays[symbol] = []
        
        self.active_replays[symbol].append(event)
        logger.info(f"Started replay for {symbol} with initial state {initial_state.value}")
    
    def record_state_transition(
        self,
        symbol: str,
        from_state: SetupState,
        to_state: SetupState,
        quality_score: float,
        priority_score: float,
        market_regime: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Record a state transition in the replay.
        
        Args:
            symbol: Stock symbol
            from_state: Previous state
            to_state: New state
            quality_score: Current quality score
            priority_score: Current priority score
            market_regime: Current market regime
            metadata: Additional metadata
        """
        if symbol not in self.active_replays:
            self.active_replays[symbol] = []
        
        event = ReplayEvent(
            event_type=ReplayEventType.STATE_TRANSITION,
            timestamp=datetime.now(),
            symbol=symbol,
            from_state=from_state,
            to_state=to_state,
            quality_score=quality_score,
            priority_score=priority_score,
            market_regime=market_regime,
            metadata=metadata or {}
        )
        
        self.active_replays[symbol].append(event)
        logger.info(
            f"Recorded transition for {symbol}: {from_state.value} -> {to_state.value}"
        )
    
    def record_invalidation(
        self,
        symbol: str,
        invalidation_reason: str,
        quality_score: float,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Record a setup invalidation.
        
        Args:
            symbol: Stock symbol
            invalidation_reason: Reason for invalidation
            quality_score: Quality score at invalidation
            metadata: Additional metadata
        """
        if symbol not in self.active_replays:
            self.active_replays[symbol] = []
        
        event = ReplayEvent(
            event_type=ReplayEventType.INVALIDATION,
            timestamp=datetime.now(),
            symbol=symbol,
            from_state=None,
            to_state=None,
            quality_score=quality_score,
            priority_score=0.0,
            market_regime="unknown",
            metadata={"invalidation_reason": invalidation_reason, **(metadata or {})}
        )
        
        self.active_replays[symbol].append(event)
        logger.info(f"Recorded invalidation for {symbol}: {invalidation_reason}")
    
    def record_ranking_change(
        self,
        symbol: str,
        old_rank: int,
        new_rank: int,
        priority_score: float,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Record a ranking change.
        
        Args:
            symbol: Stock symbol
            old_rank: Previous rank
            new_rank: New rank
            priority_score: Current priority score
            metadata: Additional metadata
        """
        if symbol not in self.active_replays:
            self.active_replays[symbol] = []
        
        event = ReplayEvent(
            event_type=ReplayEventType.RANKING_CHANGE,
            timestamp=datetime.now(),
            symbol=symbol,
            from_state=None,
            to_state=None,
            quality_score=0.0,
            priority_score=priority_score,
            market_regime="unknown",
            metadata={"old_rank": old_rank, "new_rank": new_rank, **(metadata or {})}
        )
        
        self.active_replays[symbol].append(event)
    
    def record_quality_update(
        self,
        symbol: str,
        old_quality: float,
        new_quality: float,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Record a quality score update.
        
        Args:
            symbol: Stock symbol
            old_quality: Previous quality score
            new_quality: New quality score
            metadata: Additional metadata
        """
        if symbol not in self.active_replays:
            self.active_replays[symbol] = []
        
        event = ReplayEvent(
            event_type=ReplayEventType.QUALITY_UPDATE,
            timestamp=datetime.now(),
            symbol=symbol,
            from_state=None,
            to_state=None,
            quality_score=new_quality,
            priority_score=0.0,
            market_regime="unknown",
            metadata={"old_quality": old_quality, "new_quality": new_quality, **(metadata or {})}
        )
        
        self.active_replays[symbol].append(event)
    
    def end_replay(
        self,
        symbol: str,
        final_state: SetupState,
        setup_success: bool
    ) -> Optional[SetupReplay]:
        """
        End a replay and generate summary.
        
        Args:
            symbol: Stock symbol
            final_state: Final setup state
            setup_success: Whether setup was successful
        
        Returns:
            SetupReplay summary
        """
        if symbol not in self.active_replays:
            logger.warning(f"No active replay found for {symbol}")
            return None
        
        events = self.active_replays[symbol]
        
        # Add exit event
        exit_event = ReplayEvent(
            event_type=ReplayEventType.SETUP_EXIT,
            timestamp=datetime.now(),
            symbol=symbol,
            from_state=final_state,
            to_state=None,
            quality_score=0.0,
            priority_score=0.0,
            market_regime="unknown",
            metadata={"setup_success": setup_success}
        )
        events.append(exit_event)
        
        # Calculate summary metrics
        start_time = events[0].timestamp
        end_time = events[-1].timestamp
        total_duration_hours = (end_time - start_time).total_seconds() / 3600
        
        state_transitions = sum(
            1 for e in events if e.event_type == ReplayEventType.STATE_TRANSITION
        )
        
        quality_scores = [e.quality_score for e in events if e.quality_score > 0]
        priority_scores = [e.priority_score for e in events if e.priority_score > 0]
        
        peak_quality = max(quality_scores) if quality_scores else 0.0
        peak_priority = max(priority_scores) if priority_scores else 0.0
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        avg_priority = sum(priority_scores) / len(priority_scores) if priority_scores else 0.0
        
        replay = SetupReplay(
            symbol=symbol,
            events=events,
            start_time=start_time,
            end_time=end_time,
            total_duration_hours=total_duration_hours,
            state_transitions=state_transitions,
            final_state=final_state,
            peak_quality_score=peak_quality,
            peak_priority_score=peak_priority,
            avg_quality_score=avg_quality,
            avg_priority_score=avg_priority,
            setup_success=setup_success
        )
        
        # Remove from active replays
        del self.active_replays[symbol]
        
        logger.info(
            f"Ended replay for {symbol}. Success: {setup_success}, "
            f"Duration: {total_duration_hours:.2f}h, "
            f"Transitions: {state_transitions}"
        )
        
        return replay
    
    def get_active_replay(self, symbol: str) -> Optional[List[ReplayEvent]]:
        """
        Get active replay for a symbol.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            List of replay events or None if no active replay
        """
        return self.active_replays.get(symbol)
    
    def get_all_active_replays(self) -> Dict[str, List[ReplayEvent]]:
        """Get all active replays."""
        return self.active_replays.copy()
    
    def analyze_replay_patterns(
        self,
        replays: List[SetupReplay]
    ) -> Dict:
        """
        Analyze patterns across multiple replays.
        
        Args:
            replays: List of SetupReplay objects
        
        Returns:
            Dictionary with pattern analysis
        """
        if not replays:
            return {}
        
        # Calculate success rate
        successful = sum(1 for r in replays if r.setup_success)
        success_rate = successful / len(replays)
        
        # Calculate average duration
        avg_duration = sum(r.total_duration_hours for r in replays) / len(replays)
        
        # Calculate average transitions
        avg_transitions = sum(r.state_transitions for r in replays) / len(replays)
        
        # Calculate average peak quality
        avg_peak_quality = sum(r.peak_quality_score for r in replays) / len(replays)
        
        # Most common final states
        final_states = [r.final_state.value for r in replays]
        from collections import Counter
        most_common_states = Counter(final_states).most_common(3)
        
        return {
            "total_replays": len(replays),
            "success_rate": success_rate,
            "avg_duration_hours": avg_duration,
            "avg_state_transitions": avg_transitions,
            "avg_peak_quality_score": avg_peak_quality,
            "most_common_final_states": most_common_states
        }
