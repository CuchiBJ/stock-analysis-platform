from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class ThemeBase(BaseModel):
    name: str
    status: str
    strength: float
    flow_direction: str
    momentum: Optional[float] = None
    correlation: Optional[float] = None


class Theme(ThemeBase):
    id: str
    related_sectors: List[str]
    top_stocks: List[str]
    updated_at: datetime

    class Config:
        from_attributes = True
