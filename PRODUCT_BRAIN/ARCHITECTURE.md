# ARCHITECTURE
## Technical Architecture Overview

**Purpose**: Provide a high-level overview of the technical architecture. For detailed architectural philosophy, see ARCHITECTURAL_PHILOSOPHY.md.

---

## ARCHITECTURE OVERVIEW

**Architecture Type**: Modular Monolith

**Philosophy**: Simple, modular, future-proof. Microservices when needed, not before.

**Key Characteristics**:
- Single deployable unit
- Clear module boundaries
- Event-driven internal communication
- Rule-based logic (no ML for core)
- Time-series data focus
- Interpretable systems

---

## SYSTEM COMPONENTS

### Backend Components

#### 1. Data Ingestion Module
**Purpose**: Fetch and store market data

**Responsibilities**:
- Fetch daily market data (price, volume)
- Fetch institutional data (ownership, flows)
- Fetch technical indicators
- Store in time-series database
- Emit data update events

**Technologies**:
- Python
- Celery for async tasks
- TimescaleDB for storage
- Event bus for communication

#### 2. Calculation Engine Module
**Purpose**: Calculate metrics and indicators

**Responsibilities**:
- Calculate technical indicators (RSI, MACD, etc.)
- Calculate sponsorship metrics
- Calculate volume metrics
- Calculate momentum metrics
- Calculate transition metrics
- Emit calculation complete events

**Technologies**:
- Python
- Pandas for calculations
- NumPy for numerical operations
- Event bus for communication

#### 3. Setup Detection Module
**Purpose**: Detect and track setups

**Responsibilities**:
- Apply setup detection rules
- Manage setup lifecycle state machine
- Detect setup transitions
- Detect deterioration
- Emit setup state change events

**Technologies**:
- Python
- State machine library
- Event bus for communication
- PostgreSQL for state storage

#### 4. Regime Engine Module
**Purpose**: Detect market regime

**Responsibilities**:
- Calculate regime indicators
- Detect regime transitions
- Apply regime-aware rules
- Emit regime change events

**Technologies**:
- Python
- Event bus for communication
- PostgreSQL for regime storage

#### 5. Narrative Engine Module
**Purpose**: Generate setup narratives

**Responsibilities**:
- Synthesize metrics into narratives
- Include transition context
- Include regime context
- Generate action-oriented text
- Emit narrative generation events

**Technologies**:
- Python
- Template-based generation
- Event bus for communication

#### 6. Priority Engine Module
**Purpose**: Rank and filter setups

**Responsibilities**:
- Calculate setup quality scores
- Apply regime-aware filtering
- Apply scarcity rules
- Rank setups by quality
- Emit ranking complete events

**Technologies**:
- Python
- Event bus for communication
- PostgreSQL for ranking storage

#### 7. API Module
**Purpose**: Expose REST API for frontend

**Responsibilities**:
- Setup CRUD endpoints
- Market data endpoints
- Regime information endpoints
- Alert management endpoints
- Authentication and authorization

**Technologies**:
- FastAPI
- Pydantic for validation
- JWT for authentication
- PostgreSQL for data

### Frontend Components

#### 1. Setup Display Module
**Purpose**: Display setups to users

**Responsibilities**:
- Display setup cards
- Show narratives
- Show transitions
- Show deterioration alerts
- Handle user interactions

**Technologies**:
- Next.js (React)
- TypeScript
- Tailwind CSS
- React Query for server state

#### 2. Dashboard Module
**Purpose**: Main user interface

**Responsibilities**:
- Layout and navigation
- Setup list view
- Setup detail view
- Regime indicator
- Alert display

**Technologies**:
- Next.js (React)
- TypeScript
- Tailwind CSS
- Zustand for client state

#### 3. Alert Module
**Purpose**: Display and manage alerts

**Responsibilities**:
- Display alert notifications
- Handle alert actions
- Alert history
- Alert preferences

**Technologies**:
- Next.js (React)
- TypeScript
- Tailwind CSS
- React Query for server state

---

## DATA ARCHITECTURE

### Data Stores

#### PostgreSQL
**Purpose**: Relational data and state storage

**Data**:
- Setup state and lifecycle
- User accounts and preferences
- Regime state and history
- Alert history
- Audit logs

#### TimescaleDB
**Purpose**: Time-series market data

**Data**:
- Daily price data
- Daily volume data
- Institutional ownership data
- Technical indicator history
- Metric history

#### Redis
**Purpose**: Caching and ephemeral state

**Data**:
- Cached API responses
- Session data
- Real-time state
- Rate limiting

### Data Flow

```
Data Ingestion → TimescaleDB (store)
              → Calculation Engine (calculate)
              → Setup Detection (detect)
              → Regime Engine (detect regime)
              → Narrative Engine (generate narrative)
              → Priority Engine (rank)
              → PostgreSQL (store state)
              → API Module (expose)
              → Frontend (display)
```

---

## EVENT ARCHITECTURE

### Event Types

**Data Events**:
- `market_data_updated`: Market data fetched and stored
- `institutional_data_updated`: Institutional data fetched and stored

**Calculation Events**:
- `calculation_complete`: Metrics calculated
- `indicators_updated`: Technical indicators updated

**Setup Events**:
- `setup_detected`: New setup detected
- `setup_state_changed`: Setup lifecycle state changed
- `setup_deteriorating`: Setup deterioration detected
- `setup_invalidated`: Setup invalidated
- `setup_completed`: Setup completed

**Regime Events**:
- `regime_changed`: Market regime changed
- `regime_assessed`: Regime assessment complete

**Narrative Events**:
- `narrative_generated`: Narrative generated for setup

**Priority Events**:
- `ranking_complete`: Setup ranking complete

### Event Bus

**Technology**: Redis Pub/Sub or message queue (RabbitMQ/Kafka)

**Purpose**: Decouple modules, enable event-driven architecture

**Event Handlers**:
- Each module subscribes to relevant events
- Events trigger module processing
- Events are logged for observability

---

## API ARCHITECTURE

### API Endpoints

**Setup Endpoints**:
- `GET /api/v1/setups` - List setups
- `GET /api/v1/setups/{id}` - Get setup detail
- `GET /api/v1/setups/{id}/history` - Get setup history
- `POST /api/v1/setups/{id}/state` - Manual state change

**Market Data Endpoints**:
- `GET /api/v1/market-data/{ticker}` - Get market data
- `GET /api/v1/market-data/{ticker}/history` - Get historical data

**Regime Endpoints**:
- `GET /api/v1/regime` - Get current regime
- `GET /api/v1/regime/history` - Get regime history

**Alert Endpoints**:
- `GET /api/v1/alerts` - List alerts
- `POST /api/v1/alerts/{id}/dismiss` - Dismiss alert
- `GET /api/v1/alerts/preferences` - Get alert preferences
- `PUT /api/v1/alerts/preferences` - Update alert preferences

### API Design Principles

- RESTful design
- Versioned URLs (/api/v1/)
- JSON request/response
- OpenAPI documentation
- JWT authentication
- Rate limiting

---

## DEPLOYMENT ARCHITECTURE

### Deployment Strategy

**Containerization**: Docker
**Orchestration**: Kubernetes
**Deployment**: Blue-green deployments
**Rollback**: Automated rollback on failure

### Infrastructure

**Development**: Local Docker Compose
**Staging**: Kubernetes cluster
**Production**: Kubernetes cluster

### Monitoring

**Metrics**: Prometheus
**Logs**: ELK Stack
**Tracing**: OpenTelemetry
**Error Tracking**: Sentry

---

## SECURITY ARCHITECTURE

### Authentication

**Method**: JWT tokens
**Storage**: HTTP-only cookies
**Expiration**: 24 hours
**Refresh**: Token refresh endpoint

### Authorization

**Method**: Role-based access control (RBAC)
**Roles**: Admin, User, Read-only
**Permissions**: Endpoint-level permissions

### Data Security

**Encryption**: TLS in transit, at rest encryption
**Secrets**: Environment variables, secret management
**Backup**: Daily backups, point-in-time recovery

---

## PERFORMANCE ARCHITECTURE

### Performance Targets

- API response time: < 100ms (p95)
- Page load time: < 1s
- Setup calculation: < 5s
- Data ingestion: < 10min for full market

### Optimization Strategies

- Database indexing
- Query optimization
- Caching (Redis)
- CDN for static assets
- Lazy loading

---

## SCALABILITY ARCHITECTURE

### Horizontal Scaling

**Backend**: Kubernetes pod scaling
**Database**: Read replicas for PostgreSQL
**Cache**: Redis cluster

### Vertical Scaling

**Backend**: Increase CPU/memory
**Database**: Increase instance size
**Cache**: Increase memory

### Scaling Triggers

- CPU > 70%
- Memory > 80%
- API response time > 200ms
- Database connection pool > 80%

---

## ARCHITECTURE DIAGRAM

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                    │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTPS
┌──────────────────────▼──────────────────────────────────┐
│                    API Gateway (FastAPI)                  │
└──────┬─────────┬─────────┬─────────┬─────────┬──────────┘
       │         │         │         │         │
┌──────▼──┐ ┌───▼────┐ ┌──▼──────┐ ┌▼────────┐ ┌▼─────────┐
│ Setup   │ │ Market │ │ Regime  │ │ Alert   │ │ Auth     │
│ Service │ │ Data   │ │ Service │ │ Service │ │ Service  │
└──────┬──┘ └───┬────┘ └──┬──────┘ └┬────────┘ └┬─────────┘
       │        │        │         │          │
┌──────▼────────▼────────▼─────────▼──────────▼──────────┐
│                   Event Bus (Redis)                     │
└──────┬─────────┬─────────┬─────────┬─────────┬──────────┘
       │         │         │         │         │
┌──────▼──┐ ┌───▼────┐ ┌──▼──────┐ ┌▼────────┐ ┌▼─────────┐
│ Setup   │ │ Market │ │ Regime  │ │ Alert   │ │ Data     │
│ Detection│ │ Calc   │ │ Engine  │ │ Engine  │ │ Ingestion│
└──────┬──┘ └───┬────┘ └──┬──────┘ └┬────────┘ └┬─────────┘
       │        │        │         │          │
┌──────▼────────▼────────▼─────────▼──────────▼──────────┐
│              PostgreSQL + TimescaleDB                    │
└─────────────────────────────────────────────────────────┘
```

---

## ARCHITECTURE SUMMARY

**Type**: Modular Monolith
**Backend**: Python (FastAPI)
**Frontend**: Next.js (React)
**Database**: PostgreSQL + TimescaleDB
**Cache**: Redis
**Event Bus**: Redis Pub/Sub
**Deployment**: Docker + Kubernetes
**Monitoring**: Prometheus + Grafana

**Key principles**:
- Modular monolith
- Event-driven
- Rule-based
- Interpretable
- Observable

**This document provides the technical architecture overview. For philosophical guidance, see ARCHITECTURAL_PHILOSOPHY.md.**
