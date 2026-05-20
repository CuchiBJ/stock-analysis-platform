"""
Smart Recalculation System

Only recalculates what changed instead of full market recalculation.
Implements change detection, dependency tracking, and incremental updates.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any, Set
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict

from app.market_data.events.event_bus import MarketEvent, MarketEventType, EventPriority
from app.market_data.cache.redis_cache import redis_cache

logger = logging.getLogger(__name__)


@dataclass
class DependencyNode:
    """Represents a calculation dependency."""
    symbol: str
    depends_on: Set[str] = field(default_factory=set)
    affects: Set[str] = field(default_factory=set)


@dataclass
class RecalculationTask:
    """Represents a recalculation task."""
    task_id: str
    symbol: str
    task_type: str
    priority: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    completed: bool = False


class SmartRecalculator:
    """
    Smart Recalculation System
    
    Only recalculates what changed:
    - Change detection per symbol
    - Dependency tracking
    - Incremental updates
    - Affected component identification
    
    Example:
    NVDA loses EMA21
    → Only recalculate:
      - NVDA setup state
      - Semis sector leadership
      - Affected rankings
      - Related transitions
    → NOT recalculate:
      - Unchanged symbols
      - Unaffected sectors
      - Unrelated metrics
    """
    
    def __init__(self):
        # Dependency graph
        self._dependency_graph: Dict[str, DependencyNode] = defaultdict(DependencyNode)
        
        # Symbol to sector mapping
        self._symbol_to_sector: Dict[str, str] = {}
        
        # Sector to symbols mapping
        self._sector_to_symbols: Dict[str, Set[str]] = defaultdict(set)
        
        # Recalculation queue
        self._recalc_queue: List[RecalculationTask] = []
        
        # Processing status
        self._processing = False
        self._processor_task: Optional[asyncio.Task] = None
        
        # Statistics
        self._total_recalculations = 0
        self._skipped_recalculations = 0
        self._efficiency_ratio = 0.0
    
    async def start(self):
        """Start the smart recalculation processor."""
        if self._processing:
            return
        
        self._processing = True
        logger.info("Starting smart recalculation processor")
        
        # Start background processor
        self._processor_task = asyncio.create_task(self._process_queue())
    
    async def stop(self):
        """Stop the smart recalculation processor."""
        if not self._processing:
            return
        
        self._processing = False
        logger.info("Stopping smart recalculation processor")
        
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
    
    def build_dependency_graph(self, symbols: List[str], sectors: Dict[str, str]):
        """
        Build dependency graph for symbols and sectors.
        
        Args:
            symbols: List of ticker symbols
            sectors: Dictionary mapping symbol to sector
        """
        self._symbol_to_sector = sectors
        
        # Build sector to symbols mapping
        for symbol, sector in sectors.items():
            self._sector_to_symbols[sector].add(symbol)
        
        # Build dependency nodes
        for symbol in symbols:
            node = self._dependency_graph[symbol]
            node.symbol = symbol
            
            # Add sector dependencies
            sector = sectors.get(symbol)
            if sector:
                sector_symbols = self._sector_to_symbols[sector]
                # This symbol depends on sector leadership
                node.depends_on.add(f"sector:{sector}")
                # This symbol affects sector leadership
                node.affects.update(sector_symbols)
        
        logger.info(f"Built dependency graph for {len(symbols)} symbols")
    
    async def handle_event(self, event: MarketEvent):
        """
        Handle market events and trigger smart recalculation.
        
        Args:
            event: Market event that may trigger recalculation
        """
        # Determine what needs to be recalculated based on event
        affected_symbols = self._determine_affected_symbols(event)
        
        if not affected_symbols:
            logger.debug(f"No recalculation needed for event: {event.event_type}")
            self._skipped_recalculations += 1
            return
        
        # Create recalculation tasks
        tasks = []
        for symbol in affected_symbols:
            task = RecalculationTask(
                task_id=f"{event.event_id}_{symbol}",
                symbol=symbol,
                task_type=event.event_type,
                priority=self._get_task_priority(event)
            )
            tasks.append(task)
        
        # Add to queue
        self._recalc_queue.extend(tasks)
        
        # Update statistics
        self._total_recalculations += len(tasks)
        self._update_efficiency_ratio()
        
        logger.info(f"Queued {len(tasks)} recalculation tasks for event: {event.event_type}")
    
    def _determine_affected_symbols(self, event: MarketEvent) -> Set[str]:
        """
        Determine which symbols need recalculation based on event.
        
        Args:
            event: Market event
            
        Returns:
            Set of symbols that need recalculation
        """
        affected = set()
        
        # Direct symbol affected
        if event.symbol:
            affected.add(event.symbol)
            
            # Add dependencies
            if event.symbol in self._dependency_graph:
                node = self._dependency_graph[event.symbol]
                affected.update(node.affects)
        
        # Sector-wide events
        if event.event_type in [
            MarketEventType.SECTOR_LEADERSHIP_SHIFT,
            MarketEventType.REGIME_SHIFT,
            MarketEventType.BREADTH_CHANGE
        ]:
            # For sector events, get all symbols in that sector
            sector = event.data.get("sector")
            if sector:
                affected.update(self._sector_to_symbols.get(sector, set()))
        
        return affected
    
    def _get_task_priority(self, event: MarketEvent) -> int:
        """
        Get task priority based on event priority.
        
        Args:
            event: Market event
            
        Returns:
            Integer priority (lower = higher priority)
        """
        if event.priority == EventPriority.HIGH:
            return 1
        elif event.priority == EventPriority.MEDIUM:
            return 2
        elif event.priority == EventPriority.LOW:
            return 3
        else:
            return 4
    
    async def _process_queue(self):
        """Process recalculation queue."""
        logger.info("Starting recalculation queue processor")
        
        while self._processing:
            try:
                if not self._recalc_queue:
                    await asyncio.sleep(0.1)
                    continue
                
                # Sort by priority
                self._recalc_queue.sort(key=lambda t: t.priority)
                
                # Process batch of tasks
                batch_size = min(10, len(self._recalc_queue))
                batch = self._recalc_queue[:batch_size]
                self._recalc_queue = self._recalc_queue[batch_size:]
                
                # Process batch
                await self._process_batch(batch)
                
            except Exception as e:
                logger.error(f"Error processing recalculation queue: {e}")
                await asyncio.sleep(0.1)
    
    async def _process_batch(self, tasks: List[RecalculationTask]):
        """
        Process a batch of recalculation tasks.
        
        Args:
            tasks: List of recalculation tasks
        """
        logger.info(f"Processing batch of {len(tasks)} recalculation tasks")
        
        # Process tasks concurrently
        await asyncio.gather(*[self._recalculate_symbol(task) for task in tasks])
        
        # Mark as completed
        for task in tasks:
            task.completed = True
    
    async def _recalculate_symbol(self, task: RecalculationTask):
        """
        Recalculate a single symbol.
        
        Args:
            task: Recalculation task
        """
        try:
            symbol = task.symbol
            logger.debug(f"Recalculating {symbol} (task: {task.task_type})")
            
            # Invalidate cache for this symbol
            await redis_cache.invalidate_symbol(symbol)
            
            # Recalculate setup state
            await self._recalculate_setup_state(symbol)
            
            # Recalculate metrics if needed
            if task.task_type in [
                MarketEventType.AGGREGATE_UPDATE,
                MarketEventType.PRICE_BREAK,
                MarketEventType.EMA21_LOST
            ]:
                await self._recalculate_metrics(symbol)
            
            # Emit recalculation complete event
            # (This would be done via event bus in full implementation)
            
        except Exception as e:
            logger.error(f"Error recalculating {task.symbol}: {e}")
    
    async def _recalculate_setup_state(self, symbol: str):
        """
        Recalculate setup state for a symbol.
        
        Args:
            symbol: Ticker symbol
        """
        # This would integrate with existing setup lifecycle engine
        # For now, just invalidate cache
        await redis_cache.invalidate_symbol(symbol)
    
    async def _recalculate_metrics(self, symbol: str):
        """
        Recalculate metrics for a symbol.
        
        Args:
            symbol: Ticker symbol
        """
        # This would integrate with existing metrics calculator
        # For now, just invalidate cache
        await redis_cache.invalidate_symbol(symbol)
    
    def _update_efficiency_ratio(self):
        """Update efficiency ratio based on statistics."""
        if self._total_recalculations > 0:
            self._efficiency_ratio = (
                self._skipped_recalculations / 
                (self._total_recalculations + self._skipped_recalculations)
            )
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get recalculation statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "total_recalculations": self._total_recalculations,
            "skipped_recalculations": self._skipped_recalculations,
            "efficiency_ratio": self._efficiency_ratio,
            "queue_size": len(self._recalc_queue),
            "dependency_nodes": len(self._dependency_graph),
            "processing": self._processing
        }
    
    async def force_recalculate(self, symbols: List[str]):
        """
        Force recalculation for specific symbols.
        
        Args:
            symbols: List of symbols to recalculate
        """
        logger.info(f"Forcing recalculation for {len(symbols)} symbols")
        
        tasks = []
        for symbol in symbols:
            task = RecalculationTask(
                task_id=f"manual_{symbol}_{datetime.utcnow().timestamp()}",
                symbol=symbol,
                task_type="manual",
                priority=1
            )
            tasks.append(task)
        
        self._recalc_queue.extend(tasks)
        self._total_recalculations += len(tasks)


# Global smart recalculator instance
smart_recalculator = SmartRecalculator()
