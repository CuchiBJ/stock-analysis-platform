# Realtime Fallback Architecture

## Overview

Provider-agnostic real-time price architecture with automatic fallback. The system works both with WebSocket streaming (primary) and smart polling (fallback), without blocking the architecture on Polygon WebSocket availability.

## Architecture Components

### 1. DataSourceStrategy Abstraction
**Location:** `app/market_data/strategies/data_source_strategy.py`

**Purpose:** Abstract interface for all data sources, ensuring provider-agnostic internal event flow.

**Components:**
- `DataSourceStrategy` - Abstract base class
- `WebSocketDataSource` - Polygon WebSocket implementation
- `SmartPollingDataSource` - REST API polling with tier-based intervals

**Key Features:**
- Provider-agnostic interface
- Normalized event flow
- Health monitoring
- Error tracking

### 2. DataSourceManager
**Location:** `app/market_data/strategies/data_source_manager.py`

**Purpose:** Manages multiple data sources with automatic fallback and graceful degradation.

**Modes:**
- `WEBSOCKET` - Primary mode (low latency, real-time)
- `POLLING` - Fallback mode (tier-based intervals)
- `DEGRADED` - Extended polling on repeated failures

**Features:**
- Automatic fallback on WebSocket failure
- Graceful degradation
- Health monitoring
- Mode change notifications
- Statistics tracking

### 3. NormalizedEventBus
**Location:** `app/market_data/events/normalized_event_bus.py`

**Purpose:** Internal event bus for normalized price events. Consumers don't know data origin.

**Event Types:**
- `PRICE_UPDATE` - Individual price updates
- `PRICE_SNAPSHOT` - Bulk price snapshots
- `DATA_SOURCE_CHANGE` - Mode changes
- `HEALTH_UPDATE` - Health status

**Features:**
- Subscription-based delivery
- Event filtering
- Event history
- Statistics

### 4. SmartPollingDataSource
**Location:** `app/market_data/strategies/data_source_strategy.py`

**Purpose:** Fallback data source with tier-based polling intervals.

**Polling Intervals:**
- Tier 1: 15 seconds
- Tier 2: 1 minute
- Tier 3: 5 minutes
- Tier 4: 5 minutes

**Features:**
- Universe Engine integration (tier-based intervals)
- Redis caching
- Request deduplication
- Stale-while-revalidate

### 5. Redis Caching Layer
**Location:** `app/market_data/cache/redis_cache.py`

**Purpose:** Distributed caching for market data with intelligent cache invalidation.

**Features:**
- TTL-based expiration
- Event-driven invalidation
- Stale-while-revalidate pattern
- Request deduplication
- Freshness tracking

### 6. RealtimePriceService (Updated)
**Location:** `app/services/realtime_price_service.py`

**Purpose:** Orchestrates real-time price ingestion using DataSourceManager + NormalizedEventBus.

**Changes:**
- Uses DataSourceManager instead of direct WebSocket
- Emits to NormalizedEventBus
- Works without POLYGON_API_KEY
- Tracks mode changes
- Graceful degradation

## Data Flow

### WebSocket Mode (Primary)
```
Polygon WebSocket → WebSocketDataSource → DataSourceManager → NormalizedEventBus → Frontend
```

### Polling Mode (Fallback)
```
Polygon REST API → SmartPollingDataSource → DataSourceManager → NormalizedEventBus → Frontend
```

### Degraded Mode
```
Extended polling intervals with reduced symbol set
```

## Key Design Decisions

### Provider-Agnostic
- Frontend doesn't know data origin (WebSocket vs Polling)
- Internal systems consume normalized events
- Same event flow regardless of source

### Graceful Degradation
- Automatic fallback on WebSocket failure
- Tier-based polling intervals
- Extended intervals on repeated failures
- No blocking on WebSocket availability

### Performance Optimization
- Redis caching reduces API calls
- Request deduplication prevents duplicate requests
- Stale-while-revalidate improves cache hit rate
- Tier-based intervals optimize resource usage

### Universe Engine Integration
- Tier-based polling intervals
- Dynamic symbol prioritization
- Smart resource allocation

## Configuration

### Environment Variables
- `POLYGON_API_KEY` - Optional (uses polling fallback if not set)
- `REDIS_URL` - Redis connection string

### Startup Behavior
```python
# Works with or without POLYGON_API_KEY
realtime_service = get_realtime_price_service(os.getenv("POLYGON_API_KEY"))
await realtime_service.start()
```

### Mode Selection
- If `POLYGON_API_KEY` is set → Tries WebSocket first
- If WebSocket fails → Falls back to polling
- If no `POLYGON_API_KEY` → Uses polling directly

## API Endpoints

### Realtime Service
- `POST /api/v1/realtime/start` - Start service
- `POST /api/v1/realtime/stop` - Stop service
- `GET /api/v1/realtime/status` - Get status (includes mode)
- `POST /api/v1/realtime/symbols/add` - Add symbols
- `POST /api/v1/realtime/symbols/remove` - Remove symbols
- `POST /api/v1/realtime/symbols/update` - Update symbols

### Status Response
```json
{
  "running": true,
  "mode": "polling",
  "active_source": "SmartPollingDataSource",
  "symbols_count": 500,
  "messages_received": 1000,
  "messages_broadcast": 1000,
  "last_update": "2026-05-19T12:00:00Z",
  "mode_change_count": 1,
  "data_source_health": { ... },
  "connected_clients": 5
}
```

## Frontend Integration

### WebSocket Events
- `realtime_status` - Service status changes
- `price_update` - Price updates (provider-agnostic)
- `realtime_mode_change` - Mode changes

### Price Update Format
```json
{
  "symbol": "AAPL",
  "timestamp": "2026-05-19T12:00:00Z",
  "open": 150.0,
  "high": 152.0,
  "low": 149.5,
  "close": 151.5,
  "volume": 1000000,
  "vwap": 151.0,
  "source_type": "polling",
  "metadata": { ... }
}
```

### Frontend Behavior
- Connect to WebSocket regardless of backend mode
- Display connection status
- Handle mode changes gracefully
- No UI changes based on data source

## Monitoring

### Health Checks
```python
health = await data_source_manager.health_check()
```

### Statistics
```python
stats = event_bus.get_statistics()
```

### Mode Changes
- Track mode change count
- Monitor fallback frequency
- Alert on excessive degradation

## Testing

### Graceful Degradation
1. Start with WebSocket mode
2. Simulate WebSocket failure
3. Verify automatic fallback to polling
4. Verify data continues to flow
5. Verify frontend receives updates

### Performance
1. Measure latency in WebSocket mode
2. Measure latency in polling mode
3. Verify tier-based intervals
4. Monitor cache hit rate
5. Verify request deduplication

## Benefits

### No Blocking on WebSocket
- System works without Polygon WebSocket
- No API key requirement
- Graceful degradation

### Provider-Agnostic
- Easy to switch providers
- Same internal event flow
- Frontend doesn't know origin

### Performance Optimized
- Redis caching reduces load
- Tier-based intervals optimize resources
- Request deduplication prevents waste

### Resilient
- Automatic fallback
- Health monitoring
- Graceful degradation

## Future Enhancements

1. Additional data sources (Yahoo Finance, Alpha Vantage)
2. Hybrid mode (WebSocket + polling)
3. Predictive caching
4. Machine learning for interval optimization
5. Multi-region failover
