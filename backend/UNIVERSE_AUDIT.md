# Universe Audit - Current Ticker System

## Critical Problems Identified

### 1. INCOMPLETE DATA MODEL
**File**: `app/models/stock.py`

**Problems**:
- **Symbol-only identity**: Primary key is symbol string, no internal UUID
- **No canonical identity**: Cannot handle symbol changes (FB → META)
- **No lifecycle tracking**: No IPOs, delistings, ticker changes
- **No exchange tracking**: Cannot differentiate NASDAQ vs NYSE vs other exchanges
- **No asset type classification**: Cannot distinguish ETFs, common stocks, ADRs, warrants, preferreds
- **No listing history**: Cannot track historical symbols
- **No tier classification**: All tickers treated equally
- **No quality metrics**: No liquidity, tradability, institutional quality tracking

**Impact**:
- Symbol changes break all historical data references
- Cannot track instrument lifecycle
- Cannot prioritize by asset type
- Cannot filter by exchange
- Cannot handle mergers/acquisitions
- Cannot track IPOs
- Cannot handle delistings

### 2. STATIC INGESTION PROCESS
**File**: `app/data/ingestors/stock_ingestor.py`

**Problems**:
- **Hardcoded limit**: `limit=1000` from Polygon (misses many tickers)
- **No auto discovery**: Does not discover new leaders automatically
- **Static sources**: Only Polygon, Wikipedia, TradingView (no dynamic discovery)
- **No validation**: No quality filters for liquidity, tradability
- **No enrichment**: No float, ATR, volatility profile, institutional quality
- **No lifecycle tracking**: No IPO detection, delisting detection
- **No universe tiers**: All tickers treated equally
- **No priority system**: Cannot prioritize institutional leaders

**Impact**:
- Missing tickers constantly appear in analysis
- New leaders never discovered automatically
- Universe is incomplete and static
- Low-quality tickers pollute analysis
- No institutional context
- No adaptive universe

### 3. NO UNIVERSE MANAGEMENT
**Problems**:
- **No universe engine**: No dedicated system for universe management
- **No auto discovery**: Cannot detect emerging leaders
- **No validation layer**: Cannot filter broken/low-liquidity tickers
- **No normalization**: Cannot resolve symbol inconsistencies
- **No enrichment**: Cannot enrich with sector, float, liquidity metrics
- **No lifecycle tracking**: Cannot track IPOs, delistings, symbol changes
- **No tiers**: Cannot prioritize by institutional quality
- **No health monitoring**: Cannot detect universe gaps, stale data

**Impact**:
- Setup detection breaks for missing tickers
- Sector leadership calculations incomplete
- Market regime calculations inaccurate
- RS rankings missing key players
- Emerging leaders never discovered
- Continuation analysis incomplete
- Breadth quality calculations wrong
- Institutional context missing

### 4. SYMBOL-ONLY ARCHITECTURE
**Problems**:
- **No canonical identity**: System depends entirely on symbol string
- **No historical tracking**: Cannot track symbol changes (FB → META)
- **No instrument identity**: Cannot distinguish same company with different symbols
- **No mapping**: Cannot map historical symbols to current symbols
- **No deduplication**: Cannot detect duplicate listings across exchanges

**Impact**:
- Historical data breaks on symbol changes
- Mergers/acquisitions break data continuity
- Cannot track company identity across symbol changes
- Cannot resolve duplicate listings
- Cannot maintain accurate historical analysis

### 5. NO ASSET TYPE CLASSIFICATION
**Problems**:
- **No ETF filtering**: Cannot exclude ETFs from setup analysis
- **No ADR detection**: Incomplete ADR detection (only checks primary_exchange)
- **No preferred stock filtering**: Cannot exclude preferred stocks
- **No warrant filtering**: Cannot exclude warrants
- **No common stock filtering**: Cannot filter to only common stocks

**Impact**:
- Setup analysis polluted by ETFs
- Preferred stocks included in analysis
- Warrants included in analysis
- Cannot filter by asset type
- Cannot maintain institutional context

### 6. NO EXCHANGE TRACKING
**Problems**:
- **No exchange field**: Cannot differentiate NASDAQ vs NYSE vs other exchanges
- **No exchange filtering**: Cannot filter by exchange
- **No exchange-specific logic**: Cannot apply exchange-specific rules

**Impact**:
- Cannot apply exchange-specific filters
- Cannot track exchange leadership
- Cannot detect exchange rotation
- Cannot maintain institutional context

### 7. NO QUALITY FILTERING
**Problems**:
- **No liquidity filter**: Cannot filter by average volume
- **No float filter**: Cannot filter by float size
- **No price filter**: Cannot filter by price range
- **No volatility filter**: Cannot filter by volatility profile
- **No tradability filter**: Cannot filter by tradability metrics

**Impact**:
- Low-liquidity tickers pollute analysis
- Illiquid tickers cause setup detection errors
- Penny stocks included in analysis
- Cannot maintain institutional quality
- Cannot filter by tradability

### 8. NO AUTO DISCOVERY
**Problems**:
- **No volume explosion detection**: Cannot detect volume anomalies
- **No RS acceleration detection**: Cannot detect emerging RS leaders
- **No unusual activity detection**: Cannot detect unusual institutional activity
- **No sector leadership emergence**: Cannot detect new sector leaders
- **No breakout detection**: Cannot detect explosive continuation
- **No reclaim quality detection**: Cannot detect high-quality reclaims

**Impact**:
- New leaders never discovered automatically
- Emerging setups missed
- Sector rotation not detected
- Universe remains static
- No adaptive universe

### 9. NO UNIVERSE TIERS
**Problems**:
- **All tickers equal**: Cannot prioritize institutional leaders
- **No tier classification**: Cannot classify by institutional quality
- **No tier movement**: Cannot move tickers between tiers
- **No tier-specific logic**: Cannot apply tier-specific processing

**Impact**:
- Cannot prioritize institutional leaders
- Cannot allocate resources efficiently
- Cannot scale universe management
- Cannot maintain institutional context

### 10. NO LIFECYCLE TRACKING
**Problems**:
- **No IPO detection**: Cannot detect new IPOs
- **No delisting detection**: Cannot detect delistings
- **No symbol change detection**: Cannot detect symbol changes (FB → META)
- **No sector migration detection**: Cannot detect sector changes
- **No exchange change detection**: Cannot detect exchange changes
- **No emerging leader detection**: Cannot detect new leaders
- **No dormant leader detection**: Cannot detect deteriorating leaders

**Impact**:
- Universe becomes stale
- Delisted tickers remain in analysis
- Symbol changes break data continuity
- Cannot track company lifecycle
- Cannot maintain accurate universe

## Current Architecture Summary

### Data Flow (Static Universe)
```
Polygon API (limit=1000)
  → StockIngestor.ingest_stock_list()
  → Stock model (symbol-only)
  → Static database
  → No auto discovery
  → No validation
  → No enrichment
  → No lifecycle tracking
  → No tiers
```

### Problems Summary
1. **Symbol-only identity**: No canonical identity system
2. **Static universe**: No auto discovery, no adaptive universe
3. **No validation**: No quality filters, no deduplication
4. **No enrichment**: No float, liquidity, institutional quality
5. **No lifecycle**: No IPOs, delistings, symbol changes
6. **No tiers**: All tickers treated equally
7. **No asset type**: Cannot filter ETFs, ADRs, preferreds
8. **No exchange**: Cannot track exchange
9. **No quality**: No liquidity, tradability filters
10. **No discovery**: Cannot detect emerging leaders

## Impact on Product

### Setup Detection
- **Missing tickers**: New leaders not in universe
- **False negatives**: Valid setups missed due to missing tickers
- **Inaccurate quality**: Low-quality tickers pollute analysis

### Sector Leadership
- **Incomplete sectors**: Missing leaders skew sector calculations
- **Wrong leaders**: Stale universe shows outdated leaders
- **No emergence**: Cannot detect new sector leaders

### Market Regime
- **Inaccurate breadth**: Missing tickers skew breadth calculations
- **Wrong regime**: Stale universe produces wrong regime signals
- **No adaptation**: Cannot adapt to market structure changes

### RS Rankings
- **Missing leaders**: New RS leaders not in universe
- **Stale rankings**: Rankings don't reflect current reality
- **No emergence**: Cannot detect emerging RS leaders

### Institutional Context
- **No institutional quality**: Cannot filter by institutional quality
- **No liquidity context**: Cannot assess tradability
- **No exchange context**: Cannot track exchange leadership

## Conclusion

Current ticker system is fundamentally broken:
- **Symbol-only architecture** breaks on symbol changes
- **Static universe** cannot adapt to market changes
- **No canonical identity** cannot track instrument lifecycle
- **No auto discovery** cannot detect emerging leaders
- **No validation** cannot filter low-quality tickers
- **No enrichment** cannot provide institutional context
- **No lifecycle** cannot track IPOs, delistings, symbol changes
- **No tiers** cannot prioritize institutional leaders

**Urgency**: CRITICAL - This breaks core product functionality.

**Solution**: Implement complete Universe Engine with:
- Canonical identity system
- Auto discovery
- Universe validation
- Enrichment pipeline
- Lifecycle tracking
- Universe tiers
- Health monitoring
