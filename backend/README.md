# Stock Analysis Platform - Backend

FastAPI backend for stock momentum and sector rotation analysis.

## Setup

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

4. Run database migrations:
```bash
alembic upgrade head
```

5. Run server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Documentation

Visit http://localhost:8000/docs for interactive API docs.

## Project Structure

- `app/api/` - API endpoints
- `app/core/` - Configuration and dependencies
- `app/models/` - SQLAlchemy models
- `app/schemas/` - Pydantic schemas
- `app/services/` - Business logic
- `app/repositories/` - Data access layer
- `app/data/` - Data ingestion and processing
- `alembic/` - Database migrations
