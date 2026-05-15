from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ScannerFilter(BaseModel):
    min_relative_volume: Optional[float] = Field(None, ge=0)
    max_distance_to_ema20: Optional[float] = Field(None, ge=0)
    min_distance_to_ema50: Optional[float] = Field(None, ge=0)
    sector: Optional[str] = None
    industry: Optional[str] = None
    min_market_cap: Optional[float] = Field(None, ge=0)
    max_market_cap: Optional[float] = Field(None, ge=0)
    is_adr: Optional[bool] = None
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    breakout: Optional[bool] = None


class ScanResult(BaseModel):
    id: int
    scan_name: str
    symbol: str
    scan_date: datetime
    metrics: dict

    class Config:
        from_attributes = True


class ScannerResponse(BaseModel):
    results: List[ScanResult]
    total: int
