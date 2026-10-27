from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MarketPostureRecord(Base):
    __tablename__ = "market_posture_records"
    __table_args__ = (
        CheckConstraint(
            "state IN ('FUERA', 'DEFENSIVO', 'SELECTIVO', 'NORMAL', 'AGRESIVO')",
            name="ck_market_posture_records_known_state",
        ),
    )

    session_date: Mapped[date] = mapped_column(Date, primary_key=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
