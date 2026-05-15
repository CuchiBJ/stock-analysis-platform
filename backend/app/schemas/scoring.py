from pydantic import BaseModel


class ScoreBreakout(BaseModel):
    total: float
    rs: float
    rvol: float
    momentum: float
    sector: float
    trend: float
    proximity: float
    breakout: float
