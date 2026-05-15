from sqlalchemy import String, Float, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.models.base import Base


class Theme(Base):
    __tablename__ = "themes"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))  # AI Infrastructure, Semiconductors, Uranium
    status: Mapped[str] = mapped_column(String(50))  # dominant, accelerating, decelerating, emerging
    strength: Mapped[float] = mapped_column(Float)  # 0-100
    related_sectors: Mapped[str] = mapped_column(String(500), nullable=True)  # comma-separated
    top_stocks: Mapped[str] = mapped_column(String(1000), nullable=True)  # comma-separated symbols
    flow_direction: Mapped[str] = mapped_column(String(20))  # in, out, neutral
    momentum: Mapped[float] = mapped_column(Float, nullable=True)
    correlation: Mapped[float] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
