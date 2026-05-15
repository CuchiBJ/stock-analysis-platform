from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base
from datetime import datetime


class Watchlist(Base):
    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    symbols: Mapped[str] = mapped_column(String)  # Comma-separated symbols
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(default=True)
