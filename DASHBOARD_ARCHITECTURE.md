# Dashboard Architecture - Trading Momentum Platform

## Executive Summary

Professional trading dashboard for momentum traders with focus on:
- Market breadth and rotation detection
- Sector flow analysis
- Real-time strength identification
- High-density information display
- Sub-20 second market assessment

---

## Current Architecture Analysis

### Frontend Stack
- Next.js 14 (App Router)
- React 18
- TanStack Query (data fetching)
- Zustand (state management)
- Lightweight Charts (charting)
- Tailwind CSS (styling)
- TypeScript

### Backend Stack
- FastAPI
- SQLAlchemy (async)
- PostgreSQL
- Polygon.io + Yahoo Finance (data sources)

### Current Gaps
1. No major indices tracking (SPY, QQQ, IWM, DIA)
2. No scoring system
3. No theme/flow detection
4. No event calendar
5. No smart watchlists
6. No badge system
7. No inline mini-charts
8. No quick scanner
9. Basic state management
10. No table virtualization
11. No advanced caching
12. Limited component reusability

---

## Proposed Architecture

### 1. Frontend Folder Structure

```
frontend/
├── app/
│   ├── dashboard/
│   │   ├── components/
│   │   │   ├── market-overview/
│   │   │   │   ├── IndexCard.tsx
│   │   │   │   ├── IndexGrid.tsx
│   │   │   │   └── types.ts
│   │   │   ├── market-breadth/
│   │   │   │   ├── BreadthPanel.tsx
│   │   │   │   ├── BreadthGauge.tsx
│   │   │   │   ├── SectorBreadth.tsx
│   │   │   │   └── types.ts
│   │   │   ├── sector-rotation/
│   │   │   │   ├── SectorHeatmap.tsx (enhanced)
│   │   │   │   ├── SectorRanking.tsx
│   │   │   │   ├── SectorPerformance.tsx
│   │   │   │   ├── RelativeStrengthChart.tsx
│   │   │   │   └── types.ts
│   │   │   ├── leaders-table/
│   │   │   │   ├── LeadersTable.tsx
│   │   │   │   ├── StockRow.tsx
│   │   │   │   ├── MiniChart.tsx
│   │   │   │   ├── BadgeSystem.tsx
│   │   │   │   └── types.ts
│   │   │   ├── quick-scanner/
│   │   │   │   ├── ScannerBar.tsx
│   │   │   │   ├── FilterControls.tsx
│   │   │   │   └── types.ts
│   │   │   ├── smart-watchlists/
│   │   │   │   ├── SmartWatchlist.tsx
│   │   │   │   ├── PersistentWatchlist.tsx
│   │   │   │   └── types.ts
│   │   │   ├── theme-flow/
│   │   │   │   ├── ThemeDetector.tsx
│   │   │   │   ├── FlowPanel.tsx
│   │   │   │   └── types.ts
│   │   │   ├── calendar/
│   │   │   │   ├── EventCalendar.tsx
│   │   │   │   └── types.ts
│   │   │   ├── relative-strength/
│   │   │   │   ├── RSChart.tsx
│   │   │   │   ├── RSLeaderboard.tsx
│   │   │   │   └── types.ts
│   │   │   └── score-system/
│   │   │       ├── ScoreCard.tsx
│   │   │       ├── TopLeaders.tsx
│   │   │       └── types.ts
│   │   ├── layout.tsx
│   │   └── page.tsx
│   └── ...
├── components/
│   ├── base/
│   │   ├── Card.tsx
│   │   ├── Badge.tsx
│   │   ├── Metric.tsx
│   │   ├── TrendIndicator.tsx
│   │   ├── LoadingSkeleton.tsx
│   │   └── ErrorBoundary.tsx
│   ├── tables/
│   │   ├── VirtualizedTable.tsx
│   │   ├── SortableTable.tsx
│   │   └── FilterableTable.tsx
│   ├── charts/
│   │   ├── Sparkline.tsx
│   │   ├── MiniChart.tsx
│   │   ├── ComparisonChart.tsx
│   │   └── Heatmap.tsx
│   └── layout/
│       ├── DashboardLayout.tsx
│       ├── Sidebar.tsx
│       └── Header.tsx
├── lib/
│   ├── api/
│   │   ├── client.ts (enhanced with caching)
│   │   ├── endpoints.ts (expanded)
│   │   └── hooks.ts (custom hooks)
│   ├── store/
│   │   ├── dashboardStore.ts
│   │   ├── marketStore.ts
│   │   ├── scannerStore.ts
│   │   ├── watchlistStore.ts
│   │   └── index.ts
│   ├── hooks/
│   │   ├── useMarketData.ts
│   │   ├── useSectorData.ts
│   │   ├── useLeaders.ts
│   │   ├── useScanner.ts
│   │   └── useRealtime.ts
│   ├── utils/
│   │   ├── formatters.ts
│   │   ├── calculators.ts
│   │   ├── validators.ts
│   │   └── constants.ts
│   └── config/
│       ├── theme.ts
│       └── breakpoints.ts
└── types/
    ├── dashboard.ts
    ├── market.ts
    ├── sector.ts
    ├── stock.ts (enhanced)
    ├── scanner.ts (enhanced)
    └── watchlist.ts (enhanced)
```

### 2. Backend Folder Structure

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── indices.py (NEW)
│   │       │   ├── breadth.py (NEW)
│   │       │   ├── sectors.py (enhanced)
│   │       │   ├── leaders.py (NEW)
│   │       │   ├── themes.py (NEW)
│   │       │   ├── calendar.py (NEW)
│   │       │   ├── scoring.py (NEW)
│   │       │   ├── stocks.py (enhanced)
│   │       │   ├── scanners.py (enhanced)
│   │       │   └── watchlists.py (enhanced)
│   │       └── api.py
│   ├── models/
│   │   ├── base.py
│   │   ├── stock.py (enhanced)
│   │   ├── sector.py (enhanced)
│   │   ├── index.py (NEW)
│   │   ├── event.py (NEW)
│     │   ├── theme.py (NEW)
│   │   └── watchlist.py (enhanced)
│   ├── schemas/
│   │   ├── stock.py (enhanced)
│   │   ├── sector.py (enhanced)
│   │   ├── index.py (NEW)
│   │   ├── breadth.py (NEW)
│   │   ├── leader.py (NEW)
│   │   ├── theme.py (NEW)
│   │   ├── calendar.py (NEW)
│   │   └── scoring.py (NEW)
│   ├── services/
│   │   ├── index_service.py (NEW)
│   │   ├── breadth_service.py (NEW)
│   │   ├── sector_service.py (enhanced)
│   │   ├── leader_service.py (NEW)
│   │   ├── theme_service.py (NEW)
│   │   ├── calendar_service.py (NEW)
│   │   ├── scoring_service.py (NEW)
│   │   ├── stock_service.py (enhanced)
│   │   ├── scanner_service.py (enhanced)
│   │   └── watchlist_service.py (enhanced)
│   ├── repositories/
│   │   ├── base.py
│   │   ├── stock_repository.py (enhanced)
│   │   ├── index_repository.py (NEW)
│   │   ├── event_repository.py (NEW)
│   │   └── watchlist_repository.py (enhanced)
│   └── core/
│       ├── deps.py
│       ├── config.py
│       └── cache.py (NEW)
```

---

## Component Architecture

### Base Components

#### Card.tsx
- Reusable card container
- Dark theme optimized
- Compact variants
- Loading states

#### Badge.tsx
- Badge system for stocks
- Types: breakout, near_ath, earnings, squeeze, ema20_reclaim, unusual_volume
- Color coding
- Tooltip support

#### Metric.tsx
- Standardized metric display
- Format: value + change + indicator
- Color coding based on trend
- Compact and expanded variants

#### TrendIndicator.tsx
- Visual trend indicators
- Arrows, colors, sparklines
- Bullish/neutral/bearish states

#### MiniChart.tsx
- Inline sparkline charts
- Lightweight rendering
- Configurable periods
- Performance optimized

### Table Components

#### VirtualizedTable.tsx
- React Virtual or TanStack Virtual
- Handle 1000+ rows
- Lazy loading
- Sticky headers

#### SortableTable.tsx
- Multi-column sorting
- Custom comparators
- Sort indicators
- Persist sort state

#### FilterableTable.tsx
- Column filters
- Global search
- Filter persistence
- Quick filter presets

---

## State Management (Zustand)

### dashboardStore.ts
```typescript
interface DashboardState {
  // Layout
  activeSection: string
  sidebarCollapsed: boolean
  
  // Filters
  marketFilter: 'all' | 'large_cap' | 'mid_cap' | 'small_cap'
  sectorFilter: string | null
  timeframeFilter: '1d' | '1w' | '1m'
  
  // View preferences
  tableView: 'compact' | 'detailed'
  showCharts: boolean
  showBadges: boolean
  
  // Actions
  setActiveSection: (section: string) => void
  setMarketFilter: (filter: string) => void
  setSectorFilter: (sector: string | null) => void
  setTimeframeFilter: (timeframe: string) => void
  toggleSidebar: () => void
}
```

### marketStore.ts
```typescript
interface MarketState {
  // Indices
  indices: IndexData[]
  indicesLoading: boolean
  
  // Breadth
  breadth: BreadthData
  breadthLoading: boolean
  
  // Themes
  activeThemes: Theme[]
  themesLoading: boolean
  
  // Calendar
  upcomingEvents: Event[]
  eventsLoading: boolean
  
  // Actions
  fetchIndices: () => Promise<void>
  fetchBreadth: () => Promise<void>
  fetchThemes: () => Promise<void>
  fetchEvents: () => Promise<void>
}
```

### scannerStore.ts
```typescript
interface ScannerState {
  // Quick filters
  quickFilters: QuickFilter[]
  activeFilters: ScannerFilter
  
  // Results
  scanResults: ScanResult[]
  scanLoading: boolean
  
  // History
  scanHistory: ScanResult[]
  
  // Actions
  setQuickFilter: (filter: QuickFilter) => void
  setActiveFilter: (filter: ScannerFilter) => void
  runScan: () => Promise<void>
  clearResults: () => void
}
```

### watchlistStore.ts
```typescript
interface WatchlistState {
  // Smart watchlists
  smartWatchlists: SmartWatchlist[]
  customWatchlists: CustomWatchlist[]
  
  // Persistence
  appearanceHistory: Map<string, number[]>
  
  // Actions
  fetchSmartWatchlists: () => Promise<void>
  fetchCustomWatchlists: () => Promise<void>
  addToWatchlist: (symbol: string, listId: string) => Promise<void>
  removeFromWatchlist: (symbol: string, listId: string) => Promise<void>
  trackAppearance: (symbol: string, listType: string) => void
}
```

---

## Data Models & API Contracts

### 1. Market Overview (NEW)

#### Backend Model
```python
class Index(Base):
    __tablename__ = "indices"
    
    symbol: Mapped[str] = mapped_column(String(10), primary_key=True)  # SPY, QQQ, IWM, DIA
    name: Mapped[str] = mapped_column(String(100))
    current_price: Mapped[float] = mapped_column(Float)
    daily_change_pct: Mapped[float] = mapped_column(Float)
    gap_pct: Mapped[float] = mapped_column(Float, nullable=True)
    relative_volume: Mapped[float] = mapped_column(Float, nullable=True)
    distance_ema20: Mapped[float] = mapped_column(Float, nullable=True)
    trend_short: Mapped[str] = mapped_column(String(20), nullable=True)  # bullish, neutral, bearish
    strength: Mapped[str] = mapped_column(String(20), nullable=True)  # bullish, neutral, bearish
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

#### API Endpoint
```
GET /api/v1/indices
Response: IndexData[]
```

#### Frontend Type
```typescript
interface IndexData {
  symbol: string
  name: string
  current_price: number
  daily_change_pct: number
  gap_pct: number | null
  relative_volume: number | null
  distance_ema20: number | null
  trend_short: 'bullish' | 'neutral' | 'bearish'
  strength: 'bullish' | 'neutral' | 'bearish'
  updated_at: string
}
```

### 2. Market Breadth (NEW)

#### API Endpoint
```
GET /api/v1/breadth
Response: BreadthData
```

#### Frontend Type
```typescript
interface BreadthData {
  advance_decline: {
    advancers: number
    decliners: number
    ratio: number
  }
  new_highs_lows: {
    new_highs: number
    new_lows: number
  }
  above_ema: {
    above_ema20: number  // percentage
    above_ema50: number  // percentage
  }
  color_breakdown: {
    green_stocks: number
    red_stocks: number
    neutral_stocks: number
  }
  sector_breadth: SectorBreadth[]
}

interface SectorBreadth {
  sector: string
  advancers: number
  decliners: number
  strength: 'strong' | 'moderate' | 'weak'
}
```

### 3. Sector Rotation (ENHANCED)

#### API Endpoint
```
GET /api/v1/sectors/performance?timeframe=daily
Response: SectorPerformance[]

GET /api/v1/sectors/leaders?sector=Technology
Response: Stock[]
```

#### Frontend Type
```typescript
interface SectorPerformance {
  name: string
  performance_daily: number
  performance_weekly: number
  performance_monthly: number
  performance_vs_spy: number
  trend: 'accelerating' | 'steady' | 'decelerating'
  strength: 'strong' | 'moderate' | 'weak'
  volume_trend: 'increasing' | 'stable' | 'decreasing'
  stock_count: number
  leaders: Stock[]
}
```

### 4. Leaders Table (NEW)

#### API Endpoint
```
GET /api/v1/leaders?limit=50&sort=score
Response: LeaderData[]
```

#### Frontend Type
```typescript
interface LeaderData {
  symbol: string
  name: string
  sector: string
  price: number
  gain_pct: number
  rvol: number
  rs_rank: number
  volume: number
  market_cap: number
  distance_ath: number
  float: number
  trend_quality: number  // 0-100
  score: number  // 0-100
  badges: Badge[]
  mini_chart: number[]  // last 30 closes
}

type Badge = 
  | 'breakout'
  | 'near_ath'
  | 'earnings'
  | 'squeeze'
  | 'ema20_reclaim'
  | 'unusual_volume'
  | 'tight_consolidation'
  | 'strong_rs'
```

### 5. Quick Scanner (ENHANCED)

#### API Endpoint
```
POST /api/v1/scanners/quick
Body: QuickScannerFilter
Response: ScanResult[]
```

#### Frontend Type
```typescript
interface QuickScannerFilter {
  min_rvol?: number
  market_cap_range?: [number, number]
  price_range?: [number, number]
  sector?: string
  min_distance_high?: number
  min_rs?: number
  min_volume?: number
  max_adr?: number
  gap_pct_range?: [number, number]
  consolidation_days?: number
  upcoming_earnings_days?: number
}
```

### 6. Smart Watchlists (NEW)

#### API Endpoint
```
GET /api/v1/watchlists/smart
Response: SmartWatchlist[]

GET /api/v1/watchlists/smart/:type
Response: Stock[]
```

#### Frontend Type
```typescript
interface SmartWatchlist {
  id: string
  name: string
  type: 'persistent_leaders' | 'strongest_pullbacks' | 'ema20_defenders' | 
        'scanner_repeaters' | 'tight_consolidations' | 'strongest_rs' | 'unusual_strength'
  stocks: Stock[]
  appearance_count: number  // days appeared consecutively
  last_updated: string
}
```

### 7. Theme/Flow Detection (NEW)

#### API Endpoint
```
GET /api/v1/themes
Response: Theme[]
```

#### Frontend Type
```typescript
interface Theme {
  id: string
  name: string  // "AI Infrastructure", "Semiconductors", "Uranium"
  status: 'dominant' | 'accelerating' | 'decelerating' | 'emerging'
  strength: number  // 0-100
  related_sectors: string[]
  top_stocks: Stock[]
  flow_direction: 'in' | 'out' | 'neutral'
  momentum: number
  correlation: number
}
```

### 8. Calendar (NEW)

#### API Endpoint
```
GET /api/v1/calendar?days=30
Response: Event[]
```

#### Frontend Type
```typescript
interface Event {
  id: string
  date: string
  type: 'earnings' | 'cpi' | 'fomc' | 'speech' | 'unemployment' | 'options_expiry'
  title: string
  importance: 'high' | 'medium' | 'low'
  affected_symbols?: string[]
  description?: string
}
```

### 9. Relative Strength (ENHANCED)

#### API Endpoint
```
GET /api/v1/relative-strength/:symbol
Response: RSData

GET /api/v1/relative-strength/ranking
Response: RSLeaderboard[]
```

#### Frontend Type
```typescript
interface RSData {
  symbol: string
  vs_spy: {
    current: number
    trend: 'strengthening' | 'weakening' | 'neutral'
    history: number[]
  }
  vs_qqq: {
    current: number
    trend: 'strengthening' | 'weakening' | 'neutral'
    history: number[]
  }
  vs_sector: {
    current: number
    trend: 'strengthening' | 'weakening' | 'neutral'
    history: number[]
  }
  rank: number
  percentile: number
}

interface RSLeaderboard {
  symbol: string
  rs_score: number
  rank: number
  vs_spy: number
  vs_qqq: number
  vs_sector: number
}
```

### 10. Score System (NEW)

#### Backend Service
```python
class ScoringService:
    def calculate_score(self, stock: Stock, metrics: StockMetrics) -> Score:
        # RS contribution: 25%
        rs_score = self._calculate_rs_score(metrics)
        
        # RVOL contribution: 20%
        rvol_score = self._calculate_rvol_score(metrics)
        
        # Momentum contribution: 20%
        momentum_score = self._calculate_momentum_score(metrics)
        
        # Sector strength contribution: 15%
        sector_score = self._calculate_sector_score(stock.sector)
        
        # Trend quality contribution: 10%
        trend_score = self._calculate_trend_score(metrics)
        
        # Proximity to highs contribution: 5%
        proximity_score = self._calculate_proximity_score(metrics)
        
        # Breakout quality contribution: 5%
        breakout_score = self._calculate_breakout_score(metrics)
        
        total_score = (
            rs_score * 0.25 +
            rvol_score * 0.20 +
            momentum_score * 0.20 +
            sector_score * 0.15 +
            trend_score * 0.10 +
            proximity_score * 0.05 +
            breakout_score * 0.05
        )
        
        return Score(
            total=round(total_score, 2),
            rs=rs_score,
            rvol=rvol_score,
            momentum=momentum_score,
            sector=sector_score,
            trend=trend_score,
            proximity=proximity_score,
            breakout=breakout_score
        )
```

#### API Endpoint
```
GET /api/v1/scoring/top?limit=50
Response: ScoredStock[]
```

#### Frontend Type
```typescript
interface ScoredStock {
  symbol: string
  name: string
  sector: string
  score: {
    total: number
    rs: number
    rvol: number
    momentum: number
    sector: number
    trend: number
    proximity: number
    breakout: number
  }
  price: number
  change_pct: number
}
```

---

## Performance Strategy

### 1. Caching Layer
```python
# backend/app/core/cache.py
from functools import lru_cache
from datetime import timedelta

# Cache market data for 1 minute
@lru_cache(maxsize=100)
def get_indices_data() -> IndexData:
    ...

# Cache sector performance for 5 minutes
@lru_cache(maxsize=50)
def get_sector_performance() -> SectorPerformance:
    ...

# Cache breadth data for 2 minutes
@lru_cache(maxsize=50)
def get_breadth_data() -> BreadthData:
    ...
```

### 2. Frontend Caching (TanStack Query)
```typescript
// lib/api/hooks.ts
export const useMarketData = () => {
  return useQuery({
    queryKey: ['market'],
    queryFn: () => marketApi.getAll(),
    staleTime: 60000,  // 1 minute
    refetchInterval: 60000,
  })
}

export const useSectorData = (timeframe: string) => {
  return useQuery({
    queryKey: ['sectors', timeframe],
    queryFn: () => sectorApi.getPerformance(timeframe),
    staleTime: 300000,  // 5 minutes
  })
}
```

### 3. Virtualization
```typescript
// components/tables/VirtualizedTable.tsx
import { useVirtualizer } from '@tanstack/react-virtual'

export const VirtualizedTable = ({ data }: { data: any[] }) => {
  const parentRef = useRef<HTMLDivElement>(null)
  
  const virtualizer = useVirtualizer({
    count: data.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 50,
    overscan: 10,
  })
  
  return (
    <div ref={parentRef} style={{ height: '600px', overflow: 'auto' }}>
      <div style={{ height: `${virtualizer.getTotalSize()}px` }}>
        {virtualizer.getVirtualItems().map(item => (
          <StockRow key={item.key} data={data[item.index]} />
        ))}
      </div>
    </div>
  )
}
```

### 4. Lazy Loading
```typescript
// app/dashboard/components/leaders-table/LeadersTable.tsx
const MiniChart = dynamic(() => import('./MiniChart'), {
  loading: () => <ChartSkeleton />,
  ssr: false,
})
```

### 5. Optimistic Updates
```typescript
// lib/store/scannerStore.ts
const runScan: () => Promise<void> = async () => {
  set({ scanLoading: true })
  
  try {
    const results = await scannerApi.run(get().activeFilters)
    set({ scanResults: results, scanLoading: false })
  } catch (error) {
    set({ scanLoading: false, scanResults: [] })
  }
}
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
**Goal**: Establish core architecture and base components

**Frontend**:
- [ ] Create folder structure
- [ ] Implement base components (Card, Badge, Metric, TrendIndicator)
- [ ] Set up Zustand stores (dashboard, market, scanner, watchlist)
- [ ] Create type definitions for all data models
- [ ] Set up API client with caching
- [ ] Create custom hooks (useMarketData, useSectorData, etc.)
- [ ] Implement dashboard layout

**Backend**:
- [ ] Create new models (Index, Event, Theme)
- [ ] Create new schemas
- [ ] Set up base repositories
- [ ] Create service layer structure
- [ ] Implement caching layer
- [ ] Create API endpoints skeleton

### Phase 2: Market Overview & Breadth (Week 3)
**Goal**: Display market context

**Frontend**:
- [ ] Implement IndexCard component
- [ ] Implement IndexGrid component
- [ ] Implement BreadthPanel component
- [ ] Implement BreadthGauge component
- [ ] Implement SectorBreadth component
- [ ] Integrate with marketStore

**Backend**:
- [ ] Implement index_service.py
- [ ] Implement breadth_service.py
- [ ] Create indices API endpoint
- [ ] Create breadth API endpoint
- [ ] Set up data ingestion for indices
- [ ] Calculate breadth metrics

### Phase 3: Sector Rotation (Week 4)
**Goal**: Track sector flow

**Frontend**:
- [ ] Enhance SectorHeatmap with more data
- [ ] Implement SectorRanking component
- [ ] Implement SectorPerformance component
- [ ] Implement RelativeStrengthChart component
- [ ] Add sector filtering

**Backend**:
- [ ] Enhance sector_service.py
- [ ] Add sector vs SPY relative strength
- [ ] Calculate sector momentum
- [ ] Identify sector leaders
- [ ] Add sector performance API

### Phase 4: Leaders Table (Week 5-6)
**Goal**: Show top stocks with inline data

**Frontend**:
- [ ] Implement VirtualizedTable component
- [ ] Implement StockRow component
- [ ] Implement MiniChart component
- [ ] Implement BadgeSystem component
- [ ] Add sorting and filtering
- [ ] Implement sticky headers

**Backend**:
- [ ] Implement leader_service.py
- [ ] Implement scoring_service.py
- [ ] Calculate stock scores
- [ ] Detect badges (breakout, near ATH, etc.)
- [ ] Create leaders API endpoint
- [ ] Optimize query performance

### Phase 5: Quick Scanner (Week 7)
**Goal**: Fast filtering

**Frontend**:
- [ ] Implement ScannerBar component
- [ ] Implement FilterControls component
- [ ] Add filter presets
- [ ] Implement instant feedback
- [ ] Add keyboard shortcuts

**Backend**:
- [ ] Enhance scanner_service.py
- [ ] Add quick scanner endpoint
- [ ] Optimize scanner queries
- [ ] Add filter validation

### Phase 6: Smart Watchlists (Week 8)
**Goal**: Automated watchlists

**Frontend**:
- [ ] Implement SmartWatchlist component
- [ ] Implement PersistentWatchlist component
- [ ] Add appearance history
- [ ] Implement watchlist persistence

**Backend**:
- [ ] Enhance watchlist_service.py
- [ ] Implement smart watchlist logic
- [ ] Track appearance history
- [ ] Create smart watchlist API endpoints

### Phase 7: Theme/Flow Detection (Week 9)
**Goal**: Identify market themes

**Frontend**:
- [ ] Implement ThemeDetector component
- [ ] Implement FlowPanel component
- [ ] Add theme visualization

**Backend**:
- [ ] Implement theme_service.py
- [ ] Create theme detection algorithm
- [ ] Calculate theme strength
- [ ] Create theme API endpoint

### Phase 8: Calendar (Week 10)
**Goal**: Show upcoming events

**Frontend**:
- [ ] Implement EventCalendar component
- [ ] Add event filtering
- [ ] Show event importance

**Backend**:
- [ ] Implement calendar_service.py
- [ ] Create event model
- [ ] Set up event data source
- [ ] Create calendar API endpoint

### Phase 9: Relative Strength (Week 11)
**Goal**: Real RS analysis

**Frontend**:
- [ ] Enhance RSChart component
- [ ] Implement RSLeaderboard component
- [ ] Add comparison charts

**Backend**:
- [ ] Enhance rs_service.py
- [ ] Add RS ranking
- [ ] Calculate RS trends
- [ ] Create RS API endpoints

### Phase 10: Score System (Week 12)
**Goal**: Comprehensive scoring

**Frontend**:
- [ ] Implement ScoreCard component
- [ ] Implement TopLeaders component
- [ ] Add score breakdown view

**Backend**:
- [ ] Finalize scoring_service.py
- [ ] Optimize score calculation
- [ ] Add score history
- [ ] Create scoring API endpoint

### Phase 11: UI/UX Polish (Week 13-14)
**Goal**: Professional trading aesthetic

**Frontend**:
- [ ] Apply dark theme consistently
- [ ] Optimize spacing and density
- [ ] Add hover states
- [ ] Implement keyboard shortcuts
- [ ] Add sticky filters
- [ ] Optimize animations
- [ ] Remove unnecessary whitespace
- [ ] Ensure high contrast

### Phase 12: Performance Optimization (Week 15-16)
**Goal**: Sub-second load times

**Frontend**:
- [ ] Implement virtualization everywhere
- [ ] Add lazy loading for charts
- [ ] Optimize bundle size
- [ ] Add code splitting
- [ ] Implement service worker for caching

**Backend**:
- [ ] Add database indexes
- [ ] Optimize queries
- [ ] Implement Redis caching
- [ ] Add query result caching
- [ ] Optimize data ingestion

---

## Technical Decisions

### 1. Chart Library
- **Choice**: Lightweight Charts (already in use)
- **Why**: Fast, lightweight, designed for financial data
- **Alternative**: TradingView Lightweight Charts (same)

### 2. Table Virtualization
- **Choice**: TanStack Virtual
- **Why**: Excellent performance, TypeScript support, React Query integration
- **Alternative**: react-virtualized

### 3. State Management
- **Choice**: Zustand (already in use)
- **Why**: Simple, TypeScript-first, no boilerplate
- **Alternative**: Redux Toolkit (more complex)

### 4. Data Fetching
- **Choice**: TanStack Query (already in use)
- **Why**: Caching, deduplication, background updates
- **Alternative**: SWR (similar, less features)

### 5. Caching Strategy
- **Frontend**: TanStack Query with staleTime
- **Backend**: Python lru_cache + Redis (future)
- **Database**: Query result caching

### 6. Real-time Updates
- **Choice**: Polling (1-5 min intervals)
- **Why**: Simple, reliable, sufficient for this use case
- **Alternative**: WebSockets (more complex, overkill)

### 7. Styling
- **Choice**: Tailwind CSS (already in use)
- **Why**: Utility-first, dark mode support, small bundle
- **Alternative**: CSS Modules (more verbose)

---

## Design System

### Color Palette (Dark Theme)
```typescript
const colors = {
  // Backgrounds
  background: '#0a0a0a',
  card: '#141414',
  cardHover: '#1a1a1a',
  
  // Text
  text: '#e5e5e5',
  textMuted: '#737373',
  
  // Accents
  primary: '#3b82f6',
  success: '#22c55e',
  warning: '#eab308',
  danger: '#ef4444',
  
  // Trading specific
  bullish: '#22c55e',
  bearish: '#ef4444',
  neutral: '#737373',
  
  // Heatmap gradients
  heatmapGreen: ['#22c55e', '#16a34a', '#15803d'],
  heatmapRed: ['#ef4444', '#dc2626', '#b91c1c'],
}
```

### Typography
```typescript
const typography = {
  font: 'Inter, system-ui, sans-serif',
  fontMono: 'JetBrains Mono, monospace',
  
  sizes: {
    xs: '0.75rem',
    sm: '0.875rem',
    base: '1rem',
    lg: '1.125rem',
    xl: '1.25rem',
    '2xl': '1.5rem',
  },
  
  weights: {
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },
}
```

### Spacing
```typescript
const spacing = {
  xs: '0.25rem',
  sm: '0.5rem',
  md: '1rem',
  lg: '1.5rem',
  xl: '2rem',
  '2xl': '3rem',
}
```

### Border Radius
```typescript
const radius = {
  sm: '0.25rem',
  md: '0.375rem',
  lg: '0.5rem',
  xl: '0.75rem',
}
```

---

## Summary

This architecture provides:

1. **Scalability**: Modular structure allows easy addition of features
2. **Performance**: Caching, virtualization, lazy loading
3. **Maintainability**: Clear separation of concerns
4. **Type Safety**: TypeScript throughout
5. **Developer Experience**: Consistent patterns, reusable components
6. **User Experience**: Fast, responsive, professional trading aesthetic

The phased approach ensures:
- Early validation of architecture
- Incremental value delivery
- Risk mitigation
- Ability to adjust based on feedback

**Next Steps**: Review architecture, approve phases, begin Phase 1 implementation.
