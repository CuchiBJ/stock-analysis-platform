# Event-Driven Market Data Architecture

## Architecture Overview

```
Polygon WebSocket
    ↓
WebSocket Ingestion Engine
    ↓
Event Normalization Layer
    ↓
Redis Cache/State Engine
    ↓
Internal Event Bus
    ↓
┌─────────────────────────────────────┐
│  Smart Recalculation System         │
│  - Change detection                 │
│  - Dependency tracking              │
│  - Incremental updates              │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  Setup Lifecycle Engine             │
│  - State transitions                │
│  - Lifecycle events                 │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  Transition Engine                  │
│  - Transition detection             │
│  - Transition events                │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  Market State Engine                 │
│  - Regime tracking                  │
│  - Leadership quality               │
│  - Breadth state                    │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  Event Priority System              │
│  - HIGH/MEDIUM/LOW/BACKGROUND       │
│  - Event routing                    │
└─────────────────────────────────────┘
    ↓
Frontend WebSocket (processed events)
```

## Components

### 1. Market Data Abstraction Layer
**Location**: `app/market_data/interfaces.py`

Provides provider-agnostic interfaces:
- `MarketDataProvider`: REST-based data access
- `WebSocketProvider`: WebSocket-based streaming
- `RateLimitedProvider`: Rate-limit awareness

**Benefits**:
- Provider switching without breaking system
- Clean separation of concerns
- Testable architecture

### 2. PolygonProvider Implementation
**Location**: `app/market_data/providers/polygon_provider.py`

Implements all interfaces using Polygon.io:
- REST endpoints for historical data
- WebSocket for real-time streaming
- Rate-limit awareness with backoff
- Reconnection handling

**Key Features**:
- Provider-agnostic compliance
- Automatic reconnection
- Heartbeat monitoring
- Backpressure handling

### 3. WebSocket Ingestion Engine
**Location**: `app/market_data/ingestion/websocket_engine.py`

Dedicated service for WebSocket management:
- Maintains persistent Polygon connection
- Processes real-time streams
- Normalizes events to internal format
- Detects relevant changes
- Emits internal events

**Key Features**:
- Reconnects automatically
- Handles connection drops
- Throttles message processing
- Batches events for efficiency
- Implements backpressure

**Event Flow**:
```
Polygon WebSocket Message
  → Parse & Validate
  → Normalize to Internal Format
  → Detect Changes (vs cached state)
  → Emit Internal Event (if relevant)
  → Update Redis Cache
```

### 4. Internal Event System
**Location**: `app/market_data/events/event_bus.py`

Event bus for internal communication:
- Event publishing/subscribing
- Event filtering
- Event routing
- Event history tracking

**Event Types**:
```python
PriceBreakEvent          # Price breaks key level
EMA21LostEvent          # Lost EMA21 support
ReclaimAttemptEvent     # Attempting reclaim
RSImprovingEvent        # RS improving
VolumeDryUpEvent        # Volume contraction
SectorLeadershipShiftEvent  # Sector leadership change
SetupDeteriorationEvent    # Setup deteriorating
TransitionStrengtheningEvent  # Transition strengthening
RegimeShiftEvent       # Market regime shift
BreadthChangeEvent     # Breadth quality change
```

**Event Schema**:
```python
@dataclass
class MarketEvent:
    event_id: str
    event_type: str
    symbol: str
    timestamp: datetime
    priority: EventPriority
    data: Dict[str, Any]
    metadata: Dict[str, Any]
```

### 5. Redis Caching Layer
**Location**: `app/market_data/cache/redis_cache.py`

Distributed caching strategy:
- Latest bars per symbol
- Intraday aggregates
- Setup states
- Regime state
- RS calculations
- Sector leadership
- Transition snapshots
- Event history
- Freshness state

**Cache Keys**:
```
market:bars:{symbol}          # Latest bars
market:aggregates:{symbol}    # Intraday aggregates
market:setup:{symbol}         # Setup state
market:regime                 # Current regime
market:rs:{symbol}           # RS calculations
market:sector_leadership:{sector}  # Sector leadership
market:transitions:{symbol}   # Transition snapshots
market:events:recent          # Recent events
market:freshness:{symbol}     # Data freshness
```

**Cache Invalidation**:
- Event-driven invalidation
- TTL-based expiration
- Stale-while-revalidate pattern
- Incremental updates

### 6. Smart Recalculation System
**Location**: `app/market_data/recalculation/smart_recalculator.py`

Only recalculates what changed:
- Change detection per symbol
- Dependency tracking
- Incremental updates
- Affected component identification

**Example Flow**:
```
NVDA loses EMA21
  → Emit EMA21LostEvent(symbol="NVDA")
  → Smart Recalculator:
    - Recalculate NVDA setup state
    - Recalculate semis sector leadership
    - Recalculate affected rankings
    - Recalculate related transitions
  → Emit SetupStateChangeEvent(symbol="NVDA")
  → Emit SectorLeadershipChangeEvent(sector="Technology")
```

**What NOT to recalculate**:
- Unchanged symbols
- Unaffected sectors
- Unrelated metrics
- Static market state

### 7. Market State Engine
**Location**: `app/market_data/state/market_state_engine.py`

Maintains market state incrementally:
- Current regime
- Leadership quality
- Market forgiveness
- Continuation pressure
- Deterioration pressure
- Breadth state

**State Updates**:
- Event-driven updates
- Incremental changes
- State transitions
- State persistence

### 8. Setup Lifecycle Event Flow
**Location**: `app/market_data/lifecycle/setup_lifecycle.py`

Persistent state per ticker:
```python
constructive_pullback
  → reclaim_attempt
  → reclaim_strengthening
  → continuation
  → extended
  → deterioration
```

Each transition emits internal events.

### 9. Event Priority System
**Location**: `app/market_data/events/priority.py`

Event prioritization:
```python
class EventPriority(Enum):
    HIGH = "high"           # Reclaim strengthening, leadership deterioration
    MEDIUM = "medium"       # RS improvement, volume changes
    LOW = "low"             # Minor price movements
    BACKGROUND = "background"  # Data updates, housekeeping
```

**Priority Routing**:
- HIGH: Immediate processing, frontend notification
- MEDIUM: Processed within 1 second
- LOW: Batched processing
- BACKGROUND: Processed when system idle

### 10. Rate-Limit Aware Architecture
**Location**: `app/market_data/rate_limit/rate_limiter.py**

Minimizes REST requests:
- Prioritizes WebSocket streaming
- Request deduplication
- Batching strategy
- Cache-first approach
- Stale-while-revalidate

**Request Strategy**:
```
1. Check Redis cache
2. If fresh (TTL < 5 min): Return cached
3. If stale: Return cached + trigger refresh
4. If missing: Fetch from API + cache
5. Deduplicate concurrent requests
```

### 11. Realtime Frontend Stream
**Location**: `app/api/v1/endpoints/websocket.py`

Frontend WebSocket connection:
- Consumes processed events
- Receives transition updates
- Receives setup updates
- Receives operational signals

**Frontend Responsibilities**:
- Render transitions
- Render setup updates
- Display operational priority
- NO heavy processing
- NO direct API calls

### 12. Architecture Benefits

**vs Current Architecture**:
- **Latency**: 30 min → Realtime (milliseconds)
- **Requests**: 3125/15min → WebSocket (continuous)
- **Recalculation**: Full market → Incremental (only changed)
- **Rate Limiting**: Frequent errors → Minimal (WebSocket)
- **Scalability**: Monolithic → Distributed (Redis + workers)
- **Efficiency**: <5% efficient → >95% efficient

**PRODUCT_BRAIN Alignment**:
- ✅ Transitions > Static States (event-driven transitions)
- ✅ Setup Lifecycle (persistent state tracking)
- ✅ Deterioration Matters (realtime deterioration events)
- ✅ Scarcity is Signal (only relevant events)
- ✅ Institutional Momentum (institutional-grade architecture)

## Implementation Order

1. ✅ Market Data Abstraction Layer (interfaces)
2. ⏳ PolygonProvider Implementation
3. ⏳ WebSocket Ingestion Engine
4. ⏳ Internal Event System
5. ⏳ Redis Caching Layer
6. ⏳ Smart Recalculation System
7. ⏳ Market State Engine
8. ⏳ Setup Lifecycle Event Flow
9. ⏳ Event Priority System
10. ⏳ Rate-Limit Aware Architecture
11. ⏳ Realtime Frontend Stream
12. ⏳ Refactor Existing Components

## Migration Strategy

Phase 1: Foundation
- Implement interfaces
- Implement PolygonProvider
- Set up Redis

Phase 2: Event System
- Implement WebSocket ingestion
- Implement event bus
- Implement event types

Phase 3: Intelligence
- Implement smart recalculation
- Implement market state engine
- Implement setup lifecycle

Phase 4: Frontend
- Implement frontend WebSocket
- Migrate components to event-driven
- Remove polling

Phase 5: Cleanup
- Deprecate old scheduler
- Remove redundant code
- Optimize performance
