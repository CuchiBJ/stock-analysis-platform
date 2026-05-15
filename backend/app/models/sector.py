from sqlalchemy import String, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Sector(Base):
    __tablename__ = "sectors"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    performance_daily: Mapped[float] = mapped_column(Float, nullable=True)
    performance_weekly: Mapped[float] = mapped_column(Float, nullable=True)
    performance_monthly: Mapped[float] = mapped_column(Float, nullable=True)
    rank: Mapped[int] = mapped_column(Float, nullable=True)
