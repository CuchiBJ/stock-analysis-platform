from pydantic import BaseModel
from typing import Optional


class SectorBase(BaseModel):
    name: str
    performance_daily: Optional[float] = None
    performance_weekly: Optional[float] = None
    performance_monthly: Optional[float] = None
    rank: Optional[int] = None


class Sector(SectorBase):
    class Config:
        from_attributes = True
