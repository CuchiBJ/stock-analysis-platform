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


class JournalTrade(Base):
    """One real round-trip executed in the broker, as recorded in the user's journal.

    Source of truth for what actually happened with capital at risk. Pairs Compra+Venta
    rows from the journal CSV into single records; partial fills become separate trades
    via FIFO matching against open Compras of the same symbol.
    """
    __tablename__ = "journal_trades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    setup: Mapped[str] = mapped_column(String(32), nullable=False, default='unknown')
    # DEPRECATED — manual operator label. New trades default to 'unknown'; the
    # canonical context dimension is `regime_at_entry` from system snapshots.
    # Column preserved for historical CSV-imported trades.
    context: Mapped[str] = mapped_column(String(32), nullable=False, default='unknown')

    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    stop_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Snapshot of the FIRST non-null stop_price ever set on this trade.
    # Immutable after first set — preserves planned risk for honest R-multiple
    # computation across the trade's lifetime (R = (exit-entry) / (entry-initial_stop)
    # stays comparable even after operator moves stop to BE or trails).
    initial_stop_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Decision grouping: NULL means this row IS the representative of its decision;
    # non-NULL means it's a partial execution child of the decision whose
    # representative has id = parent_trade_id. decision_id = COALESCE(parent_trade_id, id).
    parent_trade_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # DEPRECATED — derived field. New trades leave this NULL; `_trade_to_dict`
    # computes entry_price * qty on-demand. Historical rows retain cached values.
    cost_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    exit_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # DEPRECATED — derived field. New trades leave this NULL; `_trade_to_dict`
    # computes (exit_date - entry_date).days on-demand. Historical rows cached.
    duration_days: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    pnl_dollars: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # DEPRECATED — derived field. New trades leave this NULL; `_trade_to_dict`
    # computes exit/entry - 1 on-demand. Historical rows cached.
    pnl_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    r_multiple: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    error_note: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # DEPRECATED — low-signal free-text. Removed from NewTradeModal; only
    # editable via EditTradeModal. Re-evaluate for full removal in 6 months
    # based on usage.
    post_venta: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Decision provenance — separates queue-driven trades from discretionary.
    # `from_queue`: null=unmarked, true=came from take-from-queue workflow,
    # false=operator explicitly marked as off-system.
    from_queue: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # Categorized origin of the entry decision. Vocabulary kept short on
    # purpose — operators don't honestly self-label fomo/revenge in the moment.
    entry_reason: Mapped[str] = mapped_column(String(20), nullable=False, default='other')
    # Categorized reason for the exit. `partial_take` is auto-inferred when
    # qty<trade.qty on close unless operator overrides.
    exit_reason: Mapped[str] = mapped_column(String(20), nullable=False, default='unknown')

    # Operator-supplied risk plan at entry. Nullable for backward compatibility
    # with historical CSV-imported trades. When `planned_risk_dollars` is set,
    # it takes precedence over stop-derived inference for risk exposure metrics.
    # `account_balance_at_entry` enables normalization to % of account.
    planned_risk_dollars: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    account_balance_at_entry: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # System engine snapshots taken at entry time. Immutable after first save.
    # `regime_at_entry`: composite "<participation>/<leadership>" from MarketContextEngine.
    # `system_score_at_entry`: priority_score (0-1) from SetupPriorityEngine if metrics available.
    # `group_strength_at_entry`: badge "leader"|"neutral"|"weak" from GroupStrengthService.
    # `leader_health_at_entry`: overall_health_score (0-1) from LeaderHealthCalculator (market-wide).
    regime_at_entry: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    system_score_at_entry: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    group_strength_at_entry: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    leader_health_at_entry: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Optional link to the closest transition_observation detected for this symbol
    # near entry_date (±3 days). Populated on import when a match exists; null otherwise.
    # This is how the journal closes the loop with empirical calibration.
    linked_observation_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Broker auto-sync provenance (IBKR Flex). `broker_exec_id` is the stable
    # idempotency key — the closing execution's tradeID for a closed leg, or
    # "<buyExecId>:open" for an open remainder. NULL for manual/CSV trades.
    # `broker_open_exec_id` is the opening (buy) execution's tradeID, used to
    # carry manual annotations across the open→closed transition on re-sync.
    broker_exec_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    broker_open_exec_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index('ix_journal_symbol_entry', 'symbol', 'entry_date'),
        Index('ix_journal_setup_context', 'setup', 'context'),
        Index('ix_journal_parent_trade_id', 'parent_trade_id'),
        Index('ix_journal_broker_exec_id', 'broker_exec_id', unique=True),
    )


class JournalStopEvent(Base):
    """Append-only audit log of stop_price changes per JournalTrade.

    Auto-classified by the PATCH/POST handlers; operator never types the kind.
    Used to (a) preserve the operator's risk-management actions for review and
    (b) enable analytics like "% of winners that reached BE before exit".
    """
    __tablename__ = "journal_stop_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_id: Mapped[int] = mapped_column(Integer, nullable=False)
    old_stop_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    new_stop_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # One of: 'initial', 'moved_to_be', 'trailed_up', 'widened', 'removed'.
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    auto_classified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index('ix_journal_stop_events_trade', 'trade_id', 'occurred_at'),
    )


class PipelineHeartbeat(Base):
    __tablename__ = "pipeline_heartbeats"

    cycle_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    last_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    symbols_processed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    symbols_expected: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ok")
    last_error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

