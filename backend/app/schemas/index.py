from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class IndexBase(BaseModel):
    name: str
    current_price: float
    daily_change_pct: float
    gap_pct: Optional[float] = None
    relative_volume: Optional[float] = None
    distance_ema20: Optional[float] = None
    trend_short: Optional[str] = None
    strength: Optional[str] = None


class Index(IndexBase):
    symbol: str
    updated_at: datetime

    class Config:
        from_attributes = True
