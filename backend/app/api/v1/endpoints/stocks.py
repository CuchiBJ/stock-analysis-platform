from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.core.deps import get_db
from app.models.stock import Stock, StockPrice, StockMetrics
from app.schemas.stock import Stock as StockSchema, StockPrice as StockPriceSchema, StockMetrics as StockMetricsSchema

router = APIRouter()


@router.get("/", response_model=List[StockSchema])
async def get_stocks(
    skip: int = 0,
    limit: int = 100,
    sector: str = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Stock).where(Stock.is_active == True)
    if sector:
        query = query.where(Stock.sector == sector)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{symbol}", response_model=StockSchema)
async def get_stock(symbol: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Stock).where(Stock.symbol == symbol.upper()))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return stock


@router.get("/{symbol}/prices", response_model=List[StockPriceSchema])
async def get_stock_prices(
    symbol: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    query = select(StockPrice).where(
        StockPrice.symbol == symbol.upper()
    ).order_by(StockPrice.date.desc()).limit(days)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{symbol}/metrics", response_model=StockMetricsSchema)
async def get_stock_metrics(symbol: str, db: AsyncSession = Depends(get_db)):
    query = select(StockMetrics).where(
        StockMetrics.symbol == symbol.upper()
    ).order_by(StockMetrics.date.desc()).limit(1)
    result = await db.execute(query)
    metrics = result.scalar_one_or_none()
    if not metrics:
        raise HTTPException(status_code=404, detail="Metrics not found")
    return metrics
