# Market Data Architecture Audit

## Current Architecture Analysis

### Data Flow (POLLING-DRIVEN)
```
Scheduler (polling every 15/30 min)
  → PriceIngestor.ingest_intraday_prices() (REST requests to ALL symbols)
  → PolygonClient.get_intraday_bars() (HTTP requests to Polygon/yfinance)
  → Database (PostgreSQL)
  → MetricsCalculator.calculate_metrics_batch() (recalculates ALL 3125 symbols)
  → Frontend (polls APIs for updates)
```

### Problems Identified

#### 1. POLLING-DRIVEN ARCHITECTURE
- **Scheduler polling**: Every 15 minutes for prices, 30 minutes for metrics
- **No event-driven**: System doesn't react to market changes in realtime
- **Constant recalculation**: Recalculates ALL 3125 symbols every 30 minutes
- **Inefficient**: Most symbols don't change significantly between updates

#### 2. RATE LIMITING ISSUES
- **Massive REST requests**: Attempts to fetch intraday for ALL symbols simultaneously
- **No rate-limit awareness**: Doesn't respect API limits proactively
- **Sequential processing**: Processes symbols one by one with delays
- **Provider coupling**: Tightly coupled to Polygon/yfinance APIs

#### 3. DATA REDUNDANCY
- **Duplicate requests**: No intelligent caching strategy
- **Repeated calculations**: Recalculates metrics for unchanged symbols
- **No incremental updates**: Full refresh instead of delta updates
- **Stale data**: Data becomes stale between polling intervals

#### 4. SCALABILITY ISSUES
- **Monolithic scheduler**: Single process handles all data ingestion
- **No horizontal scaling**: Can't distribute load across workers
- **Synchronous processing**: Blocks on each request
- **No backpressure**: Doesn't handle rate limiting gracefully

#### 5. FRONTEND POLLING
- **Direct API calls**: Frontend polls backend APIs constantly
- **No realtime**: No WebSocket connection for live updates
- **Heavy processing**: Frontend does calculations that should be backend
- **No event consumption**: Frontend doesn't consume processed events

#### 6. NO EVENT SYSTEM
- **No internal events**: System doesn't emit events for state changes
- **No reactivity**: Components don't react to market changes
- **No event priority**: All updates treated equally
- **No event history**: No tracking of important transitions

#### 7. NO CACHING STRATEGY
- **No Redis**: No distributed caching layer
- **No cache invalidation**: No intelligent cache management
- **No stale-while-revalidate**: No cache refresh strategy
- **No request deduplication**: Duplicate requests not prevented

#### 8. NO SMART RECALCULATION
- **Full recalculation**: Recalculates entire market every update
- **No change detection**: Doesn't detect which symbols actually changed
- **No incremental updates**: Doesn't update only affected components
- **No dependency tracking**: Doesn't track which calculations depend on which data

### Current Components

#### Data Ingestion
- **PriceIngestor**: Polls Polygon/yfinance for intraday data
- **StockIngestor**: Fetches stock metadata
- **MetricsCalculator**: Recalculates all metrics for all symbols
- **Scheduler**: Polling-based scheduler (15/30 min intervals)

#### Data Sources
- **PolygonClient**: REST client for Polygon API
- **yfinance**: Fallback for intraday data (rate-limited)
- **MultiAPIClient**: Attempted multi-API fallback (not configured)

#### Data Storage
- **PostgreSQL**: Primary database for prices, metrics, stocks
- **No Redis**: No distributed caching layer
- **No message queue**: No event streaming

### Current Data Flow Problems

1. **Scheduler** triggers every 15 minutes
2. **PriceIngestor** fetches intraday for ALL symbols sequentially
3. **PolygonClient** makes HTTP requests with rate limiting delays
4. **Database** stores all data (no caching)
5. **MetricsCalculator** recalculates ALL metrics for ALL symbols
6. **Frontend** polls APIs to get latest data
7. **No events**: System doesn't emit events for state changes
8. **No realtime**: Data is stale between polling intervals

### Key Metrics

- **Symbols**: 3125 symbols
- **Update frequency**: 15 min (prices), 30 min (metrics)
- **Requests per update**: 3125 REST requests
- **Recalculation**: Full market recalculation every 30 min
- **Latency**: Up to 30 minutes stale data
- **Rate limiting**: Frequent rate limit errors
- **Efficiency**: <5% of symbols actually change significantly

### Architecture Violations

1. **Not event-driven**: Polling instead of event-driven
2. **Not rate-limit aware**: Doesn't respect API limits
3. **Not scalable**: Monolithic, no horizontal scaling
4. **Not realtime**: Up to 30 minute latency
5. **Not efficient**: Full recalculation instead of incremental
6. **Not reactive**: Doesn't react to market changes
7. **Not cached**: No distributed caching layer
8. **Not smart**: Doesn't detect actual changes

### PRODUCT_BRAIN Alignment Issues

1. **Transitions > Static States**: Current architecture is static-state oriented
2. **Setup Lifecycle**: No event-driven setup lifecycle tracking
3. **Deterioration Matters**: No realtime deterioration detection
4. **Scarcity is Signal**: Polling floods system with irrelevant data
5. **Institutional Momentum**: Not designed for institutional-grade realtime

### Conclusion

Current architecture is fundamentally polling-driven and not suitable for:
- Realtime market data
- Event-driven transitions
- Efficient setup lifecycle tracking
- Rate-limit aware operation
- Scalable operation

Needs complete redesign to event-driven architecture with:
- WebSocket streaming
- Internal event system
- Redis caching
- Smart recalculation
- Rate-limit awareness
