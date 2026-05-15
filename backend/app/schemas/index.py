from pydantic import BaseModel
from datetime import datetime


class IndexBase(BaseModel):
    name: str
    current_price: float
    daily_change_pct: float
    gap_pct: float | None = None
    relative_volume: float | None = None
    distance_ema20: float | None = None
    trend_short: str | None = None
    strength: str | None = None


class Index(IndexBase):
    symbol: str
    updated_at: datetime

    class Config:
        from_attributes = True
