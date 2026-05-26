from __future__ import annotations

from sqlalchemy import String, Float, Integer, Boolean, Index, DateTime, Date
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, date
from typing import Optional
from app.models.base import Base


class Stock(Base):
    __tablename__ = "stocks"

    symbol: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str] = mapped_column(String(100), nullable=True)
    industry: Mapped[str] = mapped_column(String(100), nullable=True)
    market_group: Mapped[str] = mapped_column(String(50), nullable=True)
    market_cap: Mapped[float] = mapped_column(Float, nullable=True)
    float_shares: Mapped[float] = mapped_column(Float, nullable=True)
    is_adr: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        Index('ix_stocks_sector', 'sector'),
        Index('ix_stocks_industry', 'industry'),
        Index('ix_stocks_market_group', 'market_group'),
    )


class StockPrice(Base):
    __tablename__ = "stock_prices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer)
    vwap: Mapped[float] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index('ix_stock_prices_symbol_date', 'symbol', 'date', unique=True),
    )


class StockMetrics(Base):
    __tablename__ = "stock_metrics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    # Fast EMAs for pullback quality
    ema9: Mapped[float] = mapped_column(Float, nullable=True)
    ema21: Mapped[float] = mapped_column(Float, nullable=True)
    # Standard EMAs
    ema20: Mapped[float] = mapped_column(Float, nullable=True)
    ema50: Mapped[float] = mapped_column(Float, nullable=True)
    ema200: Mapped[float] = mapped_column(Float, nullable=True)
    rsi: Mapped[float] = mapped_column(Float, nullable=True)
    relative_strength_spy: Mapped[float] = mapped_column(Float, nullable=True)
    relative_strength_qqq: Mapped[float] = mapped_column(Float, nullable=True)
    distance_to_ema9: Mapped[float] = mapped_column(Float, nullable=True)
    distance_to_ema21: Mapped[float] = mapped_column(Float, nullable=True)
    distance_to_ema20: Mapped[float] = mapped_column(Float, nullable=True)
    distance_to_ema50: Mapped[float] = mapped_column(Float, nullable=True)
    distance_to_high_52w: Mapped[float] = mapped_column(Float, nullable=True)
    high_52w: Mapped[float] = mapped_column(Float, nullable=True)
    avg_volume_20d: Mapped[int] = mapped_column(Integer, nullable=True)
    relative_volume: Mapped[float] = mapped_column(Float, nullable=True)
    # Additional indicators for custom screener
    sma50: Mapped[float] = mapped_column(Float, nullable=True)
    sma150: Mapped[float] = mapped_column(Float, nullable=True)
    sma200: Mapped[float] = mapped_column(Float, nullable=True)
    perf_1y: Mapped[float] = mapped_column(Float, nullable=True)
    perf_1w: Mapped[float] = mapped_column(Float, nullable=True)
    low_52w: Mapped[float] = mapped_column(Float, nullable=True)
    adr_percent: Mapped[float] = mapped_column(Float, nullable=True)
    avg_volume_10d: Mapped[int] = mapped_column(Integer, nullable=True)
    current_price: Mapped[float] = mapped_column(Float, nullable=True)
    # Performance metrics for multiple timeframes
    perf_4w: Mapped[float] = mapped_column(Float, nullable=True)
    perf_13w: Mapped[float] = mapped_column(Float, nullable=True)
    # Weekly structure metrics
    weekly_tightness: Mapped[float] = mapped_column(Float, nullable=True)
    weekly_volatility_contraction: Mapped[float] = mapped_column(Float, nullable=True)
    weekly_trend_quality: Mapped[float] = mapped_column(Float, nullable=True)
    weeks_in_base: Mapped[int] = mapped_column(Integer, nullable=True)
    # Pullback quality metrics
    pullback_quality_score: Mapped[float] = mapped_column(Float, nullable=True)
    volume_contraction: Mapped[float] = mapped_column(Float, nullable=True)
    setup_quality: Mapped[str] = mapped_column(String(50), nullable=True)
    # Volatility metrics
    atr: Mapped[float] = mapped_column(Float, nullable=True)
    atr_percent: Mapped[float] = mapped_column(Float, nullable=True)
    # ATR-normalized positioning (contextual, volatility-aware)
    distance_to_ema9_atr: Mapped[float] = mapped_column(Float, nullable=True)
    distance_to_ema21_atr: Mapped[float] = mapped_column(Float, nullable=True)
    distance_to_ema50_atr: Mapped[float] = mapped_column(Float, nullable=True)
    distance_to_high_52w_atr: Mapped[float] = mapped_column(Float, nullable=True)
    # VCP pattern detection
    vcp_contractions_count: Mapped[int] = mapped_column(Integer, nullable=True)
    vcp_latest_depth_pct: Mapped[float] = mapped_column(Float, nullable=True)
    vcp_score: Mapped[float] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index('ix_stock_metrics_symbol_date', 'symbol', 'date', unique=True),
        Index('ix_stock_metrics_vcp_score', 'vcp_score'),
    )


class SetupStateLog(Base):
    """Tracks when each symbol enters and exits a setup state.

    Populated by the scheduler after each fast-metrics cycle.
    Enables real days_in_state and freshness scoring in the transitions engine.
    """
    __tablename__ = "setup_state_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), index=True)
    state: Mapped[str] = mapped_column(String(50))
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    exited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('ix_setup_state_log_symbol_entered', 'symbol', 'entered_at'),
    )


class TransitionObservation(Base):
    """Persists each non-STABLE transition detection with context snapshot and async outcome fields."""
    __tablename__ = "transition_observations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    transition_type: Mapped[str] = mapped_column(String(40), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_detected: Mapped[date] = mapped_column(Date, nullable=False)
    # context snapshot
    regime_at_detection: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    price_at_detection: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ema9_at_detection: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ema21_at_detection: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ema50_at_detection: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    atr_at_detection: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rs_spy_at_detection: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    adr_percent_at_detection: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vcp_score_at_detection: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    relative_volume_at_detection: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weekly_tightness_at_detection: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # outcome fields (filled async)
    price_1d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_5d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_20d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pct_1d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pct_5d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pct_20d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_gain_within_10d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_drawdown_within_10d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_gain_atr_within_10d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_drawdown_atr_within_10d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reached_ema21_within_10d: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    broke_ema50_within_10d: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    outcome_status: Mapped[str] = mapped_column(String(20), nullable=False, default='PENDING')
    outcome_evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('ix_obs_symbol_type_date', 'symbol', 'transition_type', 'date_detected', unique=True),
        Index('ix_obs_aggregation', 'transition_type', 'regime_at_detection', 'outcome_status'),
    )


class SchedulerError(Base):
    __tablename__ = "scheduler_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_name: Mapped[str] = mapped_column(String(100), nullable=False)
    exception_type: Mapped[str] = mapped_column(String(100), nullable=False)
    exception_message: Mapped[str] = mapped_column(String, nullable=False)
    traceback: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_scheduler_errors_occurred_at", "occurred_at"),
        Index("ix_scheduler_errors_task_name", "task_name"),
    )

