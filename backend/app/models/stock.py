from sqlalchemy import String, Float, Integer, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Stock(Base):
    __tablename__ = "stocks"

    symbol: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str] = mapped_column(String(100), nullable=True)
    industry: Mapped[str] = mapped_column(String(100), nullable=True)
    market_cap: Mapped[float] = mapped_column(Float, nullable=True)
    float_shares: Mapped[float] = mapped_column(Float, nullable=True)
    is_adr: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        Index('ix_stocks_sector', 'sector'),
        Index('ix_stocks_industry', 'industry'),
    )


class StockPrice(Base):
    __tablename__ = "stock_prices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), index=True)
    date: Mapped[str] = mapped_column(String(10), index=True)
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
    date: Mapped[str] = mapped_column(String(10), index=True)
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

    __table_args__ = (
        Index('ix_stock_metrics_symbol_date', 'symbol', 'date', unique=True),
    )
