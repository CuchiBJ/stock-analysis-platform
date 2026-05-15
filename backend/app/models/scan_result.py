from sqlalchemy import String, DateTime, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base
from datetime import datetime


class ScanResult(Base):
    __tablename__ = "scan_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scan_name: Mapped[str] = mapped_column(String(100), index=True)
    symbol: Mapped[str] = mapped_column(String(10), index=True)
    scan_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    metrics: Mapped[dict] = mapped_column(JSON)
    
    __table_args__ = (
        Index('ix_scan_results_scan_date', 'scan_name', 'scan_date'),
    )
