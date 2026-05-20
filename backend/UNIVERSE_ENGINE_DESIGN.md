# Universe Engine Design

## Architecture Overview

```
Universe Source Layer (Polygon, NASDAQ, NYSE, ETFs, IPO feeds)
    ↓
Universe Normalization Layer (symbol, canonical, exchange, asset type)
    ↓
Canonical Identity System (UUID, current symbol, historical symbols, lifecycle)
    ↓
Universe Validation Layer (quality filters, liquidity, tradability)
    ↓
Universe Enrichment Layer (sector, float, ATR, institutional quality)
    ↓
Universe Lifecycle System (IPOs, delistings, ticker changes, sector migrations)
    ↓
Universe Tiers (TIER 1-4: institutional → passive)
    ↓
Auto Discovery Engine (volume explosion, RS acceleration, unusual activity)
    ↓
Discovery Scans (nightly scans for new leaders, emerging structure)
    ↓
Universe Health Monitoring (coverage gaps, stale tickers, universe freshness)
    ↓
Universe Event System (NewLeaderDiscoveredEvent, SymbolChangedEvent, etc.)
    ↓
Smart Universe Prioritization (what deserves realtime, websocket, deep analysis)
```

## Component Design

### 1. Universe Source Layer
**Location**: `app/universe/sources/universe_source.py`

Provider abstraction for multiple ticker sources:
- Polygon tickers endpoint
- NASDAQ listings
- NYSE listings
- ETFs universe
- IPO feeds
- Active listings
- Delisted listings

**Interfaces**:
```python
class UniverseSource(ABC):
    async def get_active_listings() -> List[TickerInfo]
    async def get_delisted_listings() -> List[TickerInfo]
    async def get_ipo_feed() -> List[IPOInfo]
    async def get_etf_universe() -> List[ETFInfo]
```

**Benefits**:
- Provider-agnostic
- Can switch/add sources easily
- No coupling to single source

### 2. Universe Normalization Layer
**Location**: `app/universe/normalization/normalizer.py`

Normalize data from all sources:
- Symbol standardization (uppercase, remove suffixes)
- Canonical symbol resolution
- Exchange normalization (NASDAQ → "NASDAQ", not "XNAS")
- Asset type classification (ETF, common stock, ADR, warrant, preferred)
- Market cap normalization
- Sector/industry normalization

**Key Functions**:
- Resolve symbol inconsistencies
- Deduplicate listings across exchanges
- Standardize sector/industry classifications
- Normalize market cap formats

### 3. Canonical Identity System
**Location**: `app/universe/identity/canonical_identity.py`

**CRITICAL**: Handle symbol changes (FB → META, mergers, relistings)

**Data Model**:
```python
@dataclass
class InstrumentIdentity:
    internal_id: UUID  # Internal UUID (never changes)
    current_symbol: str  # Current active symbol
    historical_symbols: List[str]  # All historical symbols
    lifecycle_state: LifecycleState  # ACTIVE, DELISTED, MERGED, CHANGED
    listing_history: List[ListingEvent]  # IPO, delisting, symbol changes
    company_name: str  # Company name (may change)
    primary_exchange: str  # Primary exchange
    asset_type: AssetType  # ETF, COMMON_STOCK, ADR, WARRANT, PREFERRED
```

**Key Features**:
- Internal UUID never changes
- Track all historical symbols
- Map historical symbols to current symbol
- Track company identity across symbol changes
- Resolve duplicate listings

**Benefits**:
- Symbol changes don't break historical data
- Can track company across mergers/acquisitions
- Maintain data continuity

### 4. Universe Validation Layer
**Location**: `app/universe/validation/validator.py`

Quality filters to remove garbage:
- **Liquidity filter**: Average volume > 500K
- **Price filter**: Price > $5 (avoid penny stocks)
- **Float filter**: Float > $50M
- **Volatility filter**: ATR < 20% (avoid hyper-volatile garbage)
- **Tradability filter**: Spread < 1%
- **Exchange filter**: Only major exchanges (NASDAQ, NYSE, AMEX)
- **Asset type filter**: Exclude ETFs, warrants, preferreds (for setup analysis)

**Validation Pipeline**:
```
Raw ticker
  → Exchange validation
  → Asset type validation
  → Liquidity validation
  → Price validation
  → Float validation
  → Volatility validation
  → Tradability validation
  → Valid ticker
```

### 5. Universe Enrichment Layer
**Location**: `app/universe/enrichment/enricher.py`

Enrich each ticker with:
- Sector (GICS classification)
- Industry (GICS sub-industry)
- Float (shares outstanding)
- Liquidity (average volume, average dollar volume)
- ATR (Average True Range)
- Volatility profile
- Institutional quality (institutional ownership)
- RS baseline (relative strength vs SPY/QQQ)
- Tradability metrics (spread, depth)
- Market cap tier (mega/large/mid/small/micro)

**Enrichment Pipeline**:
```
Valid ticker
  → Fetch sector/industry (Polygon/Yahoo)
  → Fetch float (Polygon)
  → Calculate liquidity metrics (price history)
  → Calculate ATR (price history)
  → Calculate volatility profile (price history)
  → Fetch institutional ownership (optional)
  → Calculate RS baseline (vs SPY/QQQ)
  → Calculate tradability metrics (optional)
  → Enriched ticker
```

### 6. Universe Lifecycle System
**Location**: `app/universe/lifecycle/lifecycle_tracker.py`

Track instrument lifecycle:
- IPOs (new listings)
- Delistings (removed from exchange)
- Ticker changes (FB → META)
- Sector migrations (company changes sector)
- Exchange changes (NASDAQ → NYSE)
- Emerging leaders (new institutional leaders)
- Dormant leaders (leaders that deteriorated)

**Lifecycle States**:
```python
class LifecycleState(Enum):
    IPO = "ipo"  # Recently listed
    ACTIVE = "active"  # Normal active listing
    DELISTED = "delisted"  # Removed from exchange
    MERGED = "merged"  # Acquired/merged
    SYMBOL_CHANGED = "symbol_changed"  # Symbol changed
    EMERGING_LEADER = "emerging_leader"  # New institutional leader
    DORMANT_LEADER = "dormant_leader"  # Former leader that deteriorated
```

**Event Emission**:
- NewIPOEvent
- DelistedEvent
- SymbolChangedEvent
- SectorMigrationEvent
- ExchangeChangedEvent
- EmergingLeaderEvent
- DormantLeaderEvent

### 7. Auto Discovery Engine
**Location**: `app/universe/discovery/auto_discovery.py`

**CRITICAL**: Automatically discover new leaders

**Discovery Triggers**:
- Volume explosion (3x average volume)
- RS acceleration (RS > 2.0 for 5 days)
- Unusual institutional activity (large block trades)
- Sector leadership emergence (top of sector)
- Explosive continuation (breakout with volume)
- Abnormal relative strength (RS > 3.0)
- High-quality reclaim (reclaim with tight structure)

**Discovery Pipeline**:
```
Market data stream
  → Detect anomaly (volume explosion, RS acceleration, etc.)
  → Validate ticker (not already in universe, passes validation)
  → Enrich ticker (sector, float, liquidity, etc.)
  → Add to universe
  → Assign tier (based on quality)
  → Emit NewLeaderDiscoveredEvent
  → Start tracking lifecycle
  → If TIER 1: Start realtime tracking
```

### 8. Universe Tiers
**Location**: `app/universe/tiers/tier_manager.py`

**TIER 1 - Institutional Leaders** (Full realtime lifecycle tracking)
- Criteria: Market cap > $10B, volume > 5M/day, RS > 1.5
- Processing: Full WebSocket streaming, deep analysis, realtime tracking
- Count: ~200-500 tickers
- Examples: NVDA, AAPL, MSFT, GOOGL, AMZN

**TIER 2 - Active Watchlist** (Partial realtime)
- Criteria: Market cap > $2B, volume > 1M/day, RS > 1.2
- Processing: Daily intraday updates, setup analysis
- Count: ~1000-2000 tickers
- Examples: Mid-cap leaders, emerging leaders

**TIER 3 - Passive Market Universe** (Daily recalculation)
- Criteria: Market cap > $500M, volume > 500K/day
- Processing: Daily recalculation, no realtime
- Count: ~3000-5000 tickers
- Examples: Small caps, less active tickers

**TIER 4 - Dormant/Inactive** (Minimal maintenance)
- Criteria: Market cap < $500M or volume < 500K/day
- Processing: Weekly refresh, minimal analysis
- Count: ~1000-2000 tickers
- Examples: Micro caps, illiquid tickers

**Dynamic Tier Movement**:
- Promote: TIER 4 → TIER 3 → TIER 2 → TIER 1 (based on quality improvement)
- Demote: TIER 1 → TIER 2 → TIER 3 → TIER 4 (based on quality deterioration)
- Weekly tier re-evaluation

### 9. Discovery Scans
**Location**: `app/universe/scans/discovery_scanner.py`

Nightly scans to detect:
- New RS leaders (RS > 2.0 for 5 consecutive days)
- Emerging structure (tight base, volume contraction)
- Volume anomalies (3x average volume)
- Unusual tightness (ATR < 2%)
- New sector leadership (top 3 in sector)
- Breakout pressure (price near highs with volume)
- Reclaim quality (reclaim of EMA21 with volume)
- Continuation quality (extension with volume)

**Scan Schedule**:
- Run nightly after market close
- Scan entire market universe (TIER 2-4)
- Detect new candidates
- Validate and enrich
- Add to universe if valid
- Emit discovery events

### 10. Universe Health Monitoring
**Location**: `app/universe/monitoring/health_monitor.py`

Monitor universe health:
- Missing sectors (sectors with no tickers)
- Stale tickers (tickers not updated in > 7 days)
- Dead listings (tickers with no price data)
- Symbol inconsistencies (duplicate symbols, invalid symbols)
- Universe freshness (last update time)
- Coverage gaps (sectors with < 10 tickers)
- Ingestion failures (failed enrichments, validation failures)

**Health Metrics**:
- Universe size (total tickers, by tier)
- Coverage (by sector, by asset type)
- Freshness (average age of data)
- Quality (percentage passing validation)
- Discovery rate (new tickers discovered per day)
- Delist rate (tickers delisted per day)

**Alerts**:
- Coverage gap alert (sector with < 10 tickers)
- Stale data alert (tickers not updated > 7 days)
- Ingestion failure alert (high failure rate)
- Universe shrinkage alert (universe size decreasing)

### 11. Universe Event System
**Location**: `app/universe/events/universe_event_bus.py`

Internal events for universe changes:
- NewLeaderDiscoveredEvent
- NewIPOEvent
- SymbolChangedEvent
- LiquidityDeteriorationEvent
- SectorMigrationEvent
- NewHighRSEvent
- UniverseCoverageGapEvent
- TierPromotionEvent
- TierDemotionEvent
- DelistedEvent

**Event Schema**:
```python
@dataclass
class UniverseEvent:
    event_id: str
    event_type: str
    instrument_id: UUID
    symbol: str
    timestamp: datetime
    priority: EventPriority
    data: Dict[str, Any]
    metadata: Dict[str, Any]
```

### 12. Smart Universe Prioritization
**Location**: `app/universe/prioritization/prioritizer.py**

Decide what tickers deserve:
- Realtime WebSocket tracking
- Deep analysis
- Lifecycle tracking
- Setup analysis

**Prioritization Factors**:
- Institutional quality (market cap, volume, float)
- Leadership (RS, sector leadership)
- Setup quality (pullback quality, tightness)
- Sector relevance (sector in current regime)
- Regime alignment (setup aligned with current regime)

**Prioritization Logic**:
```
Ticker
  → Calculate institutional quality score (0-100)
  → Calculate leadership score (0-100)
  → Calculate setup quality score (0-100)
  → Calculate sector relevance score (0-100)
  → Calculate regime alignment score (0-100)
  → Overall priority score (weighted average)
  → If score > 80: TIER 1 (full realtime)
  → If score > 60: TIER 2 (partial realtime)
  → If score > 40: TIER 3 (daily)
  → Else: TIER 4 (minimal)
```

## Data Model

### InstrumentIdentity Table
```sql
CREATE TABLE instrument_identities (
    internal_id UUID PRIMARY KEY,
    current_symbol VARCHAR(10) NOT NULL,
    historical_symbols JSONB,
    lifecycle_state VARCHAR(50),
    company_name VARCHAR(255),
    primary_exchange VARCHAR(50),
    asset_type VARCHAR(50),
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    
    INDEX idx_current_symbol (current_symbol),
    INDEX idx_lifecycle_state (lifecycle_state),
    INDEX idx_asset_type (asset_type)
);
```

### ListingEvents Table
```sql
CREATE TABLE listing_events (
    id SERIAL PRIMARY KEY,
    instrument_id UUID REFERENCES instrument_identities(internal_id),
    event_type VARCHAR(50),
    event_date DATE,
    old_symbol VARCHAR(10),
    new_symbol VARCHAR(10),
    old_exchange VARCHAR(50),
    new_exchange VARCHAR(50),
    metadata JSONB,
    
    INDEX idx_instrument_id (instrument_id),
    INDEX idx_event_date (event_date)
);
```

### UniverseEnrichment Table
```sql
CREATE TABLE universe_enrichment (
    instrument_id UUID PRIMARY KEY REFERENCES instrument_idencies(internal_id),
    sector VARCHAR(100),
    industry VARCHAR(100),
    float_shares BIGINT,
    avg_volume_20d BIGINT,
    avg_dollar_volume_20d DECIMAL,
    atr DECIMAL,
    volatility_profile VARCHAR(50),
    institutional_quality_score DECIMAL,
    rs_baseline_spy DECIMAL,
    rs_baseline_qqq DECIMAL,
    tradability_score DECIMAL,
    market_cap_tier VARCHAR(50),
    tier VARCHAR(10),
    last_enriched_at TIMESTAMP,
    
    INDEX idx_sector (sector),
    INDEX idx_tier (tier),
    INDEX idx_market_cap_tier (market_cap_tier)
);
```

## Implementation Order

Phase 1: Foundation
1. Canonical Identity System (CRITICAL)
2. Universe Source Layer
3. Universe Normalization Layer

Phase 2: Quality
4. Universe Validation Layer
5. Universe Enrichment Layer
6. Universe Lifecycle System

Phase 3: Intelligence
7. Universe Tiers
8. Auto Discovery Engine
9. Discovery Scans

Phase 4: Monitoring
10. Universe Health Monitoring
11. Universe Event System
12. Smart Universe Prioritization

Phase 5: Integration
13. Migrate existing Stock model to InstrumentIdentity
14. Update StockIngestor to use Universe Engine
15. Update setup detection to use canonical identity
16. Update sector leadership to use canonical identity

## Benefits vs Current System

### Identity
- **Current**: Symbol-only (breaks on FB → META)
- **New**: UUID-based (handles symbol changes)

### Discovery
- **Current**: Static universe (no auto discovery)
- **New**: Adaptive universe (auto discovers new leaders)

### Quality
- **Current**: No validation (garbage in universe)
- **New**: Quality filters (only quality tickers)

### Enrichment
- **Current**: Minimal enrichment (sector, market cap)
- **New**: Full enrichment (float, liquidity, institutional quality)

### Lifecycle
- **Current**: No lifecycle tracking (cannot track IPOs, delistings)
- **New**: Full lifecycle tracking (IPOs, delistings, symbol changes)

### Tiers
- **Current**: All tickers equal (no prioritization)
- **New**: Tier-based (prioritize institutional leaders)

### Coverage
- **Current**: 3125 tickers (static, incomplete)
- **New**: 10,000+ tickers (adaptive, complete)

### Efficiency
- **Current**: Process all tickers equally (wasteful)
- **New**: Process by tier (efficient resource allocation)

## PRODUCT_BRAIN Alignment

✅ **Institutional Momentum**: Universe focused on institutional quality
✅ **Leadership Awareness**: Auto discovery of new leaders
✅ **Adaptive Universe**: Self-updating ecosystem
✅ **Scarcity is Signal**: Tier-based prioritization (only process what matters)
✅ **Institutional Context**: Full enrichment with institutional metrics
