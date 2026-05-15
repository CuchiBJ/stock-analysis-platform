from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class StockBase(BaseModel):
    symbol: str = Field(..., max_length=10)
    name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[float] = None
    float_shares: Optional[float] = None
    is_adr: bool = False


class StockCreate(StockBase):
    pass


class Stock(StockBase):
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StockPriceBase(BaseModel):
    symbol: str = Field(..., max_length=10)
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None


class StockPrice(StockPriceBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class StockMetricsBase(BaseModel):
    symbol: str = Field(..., max_length=10)
    date: str
    ema20: Optional[float] = None
    ema50: Optional[float] = None
    ema200: Optional[float] = None
    rsi: Optional[float] = None
    relative_strength_spy: Optional[float] = None
    relative_strength_qqq: Optional[float] = None
    distance_to_ema20: Optional[float] = None
    distance_to_ema50: Optional[float] = None
    distance_to_high_52w: Optional[float] = None
    avg_volume_20d: Optional[int] = None
    relative_volume: Optional[float] = None


class StockMetrics(StockMetricsBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
