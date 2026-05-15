from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, date
from app.models.base import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    event_date: Mapped[date] = mapped_column(DateTime)
    event_type: Mapped[str] = mapped_column(String(50))  # earnings, cpi, fomc, speech, unemployment, options_expiry
    title: Mapped[str] = mapped_column(String(255))
    importance: Mapped[str] = mapped_column(String(20))  # high, medium, low
    affected_symbols: Mapped[str] = mapped_column(String(1000), nullable=True)  # comma-separated
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
