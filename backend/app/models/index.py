from sqlalchemy import String, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.models.base import Base


class Index(Base):
    __tablename__ = "indices"

    symbol: Mapped[str] = mapped_column(String(10), primary_key=True)  # SPY, QQQ, IWM, DIA
    name: Mapped[str] = mapped_column(String(100))
    current_price: Mapped[float] = mapped_column(Float)
    daily_change_pct: Mapped[float] = mapped_column(Float)
    gap_pct: Mapped[float] = mapped_column(Float, nullable=True)
    relative_volume: Mapped[float] = mapped_column(Float, nullable=True)
    distance_ema20: Mapped[float] = mapped_column(Float, nullable=True)
    trend_short: Mapped[str] = mapped_column(String(20), nullable=True)  # bullish, neutral, bearish
    strength: Mapped[str] = mapped_column(String(20), nullable=True)  # bullish, neutral, bearish
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
