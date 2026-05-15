# Stock Analysis Platform

Personal stock analysis platform focused on momentum, sector rotation, and market leadership detection.

## Architecture

### Backend (FastAPI + Python)
- FastAPI with async support
- SQLAlchemy 2.0 with PostgreSQL
- Polygon.io API for stock data
- Repository pattern for data access
- Service layer for business logic

### Frontend (Next.js + React)
- Next.js 14 with App Router
- TypeScript
- TailwindCSS
- TanStack Query for data fetching
- Zustand for state management
- TradingView Lightweight Charts

## Project Structure

```
stock-analysis-platform/
├── backend/           # FastAPI backend
│   ├── app/
│   │   ├── api/       # API endpoints
│   │   ├── core/      # Config, deps
│   │   ├── models/    # SQLAlchemy models
│   │   ├── schemas/   # Pydantic schemas
│   │   ├── services/  # Business logic
│   │   ├── repositories/  # Data access
│   │   ├── data/      # Ingestion, processing
│   │   └── utils/     # Utilities
│   ├── alembic/       # Database migrations
│   └── tests/
└── frontend/          # Next.js frontend
    ├── app/           # App Router pages
    ├── components/    # React components
    ├── lib/           # API client, hooks, store
    └── types/         # TypeScript types
```

## Quick Start

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
cp .env.example .env
# Edit .env with DATABASE_URL and POLYGON_API_KEY
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
cp .env.local.example .env.local
# Edit .env.local with NEXT_PUBLIC_API_URL
npm run dev
```

## Features

- **Dashboard**: Sector heatmap, market breadth, performance metrics
- **Scanner**: Filter stocks by RVOL, breakouts, consolidations, distance to EMAs
- **Relative Strength**: Compare stocks vs SPY/QQQ, detect early leaders
- **Watchlists**: Track strong stocks and recurring leaders
- **Charts**: Candlestick charts with volume and moving averages

## Data Sources

- Polygon.io (US stock data)
- Future: Add more data sources as needed

## Development

### Database Migrations (Backend)
```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Type Checking
```bash
# Backend
cd backend
mypy app/

# Frontend
cd frontend
npx tsc --noEmit
```

## License

Personal use only.
