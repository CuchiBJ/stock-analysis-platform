from pydantic import BaseModel
from typing import List


class ScoreBreakdown(BaseModel):
    total: float
    rs: float
    rvol: float
    momentum: float
    sector: float
    trend: float
    proximity: float
    breakout: float


class LeaderData(BaseModel):
    symbol: str
    name: str
    sector: str
    price: float
    gain_pct: float
    rvol: float
    rs_rank: float
    volume: int
    market_cap: float
    distance_ath: float
    float: float
    trend_quality: int
    score: float
    badges: List[str]
    mini_chart: List[float]


class ScoredStock(BaseModel):
    symbol: str
    name: str
    sector: str
    score: ScoreBreakdown
    price: float
    change_pct: float
