from pydantic import BaseModel


class AdvanceDecline(BaseModel):
    advancers: int
    decliners: int
    ratio: float


class NewHighsLows(BaseModel):
    new_highs: int
    new_lows: int


class AboveEMA(BaseModel):
    above_ema20: float
    above_ema50: float


class ColorBreakdown(BaseModel):
    green_stocks: int
    red_stocks: int
    neutral_stocks: int


class SectorBreadth(BaseModel):
    sector: str
    advancers: int
    decliners: int
    strength: str


class BreadthData(BaseModel):
    advance_decline: AdvanceDecline
    new_highs_lows: NewHighsLows
    above_ema: AboveEMA
    color_breakdown: ColorBreakdown
    sector_breadth: list[SectorBreadth]
