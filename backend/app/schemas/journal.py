"""Validated request contracts for journal mutations."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


DEFAULT_COMMISSION = 1.0


class OpenTradeIn(BaseModel):
    symbol: str
    entry_date: date
    entry_price: float = Field(gt=0)
    qty: float = Field(gt=0)
    stop_price: Optional[float] = Field(default=None, gt=0)
    setup: str = "unknown"
    context: str = "unknown"
    from_queue: Optional[bool] = None
    entry_reason: str = "other"
    planned_risk_dollars: Optional[float] = Field(default=None, gt=0)
    account_balance_at_entry: Optional[float] = Field(default=None, gt=0)
    commission: float = DEFAULT_COMMISSION


class CloseTradeIn(BaseModel):
    exit_date: date
    exit_price: float = Field(gt=0)
    qty: Optional[float] = Field(
        default=None,
        gt=0,
        description="If < trade.qty, performs a partial close (splits the trade).",
    )
    exit_reason: Optional[str] = None
    error_note: Optional[str] = None
    post_venta: Optional[str] = None
    commission: float = DEFAULT_COMMISSION


class PatchTradeIn(BaseModel):
    symbol: Optional[str] = None
    setup: Optional[str] = None
    context: Optional[str] = None
    entry_date: Optional[date] = None
    entry_price: Optional[float] = Field(default=None, gt=0)
    qty: Optional[float] = Field(default=None, gt=0)
    stop_price: Optional[float] = Field(default=None, gt=0)
    exit_date: Optional[date] = None
    exit_price: Optional[float] = Field(default=None, gt=0)
    error_note: Optional[str] = None
    post_venta: Optional[str] = None
    from_queue: Optional[bool] = None
    entry_reason: Optional[str] = None
    exit_reason: Optional[str] = None
    planned_risk_dollars: Optional[float] = Field(default=None, gt=0)
    account_balance_at_entry: Optional[float] = Field(default=None, gt=0)


__all__ = ["CloseTradeIn", "OpenTradeIn", "PatchTradeIn"]
