from pydantic import BaseModel, Field
from datetime import datetime
from typing import List


class WatchlistBase(BaseModel):
    name: str = Field(..., max_length=100)
    symbols: List[str]


class WatchlistCreate(WatchlistBase):
    pass


class Watchlist(WatchlistBase):
    id: int
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True
