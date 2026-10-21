"""Exercise formation history loading against a disposable database."""

import asyncio
from datetime import date, timedelta
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.stock import StockMetrics
from app.models.user import User  # noqa: F401 — register the shared ORM ownership relationships
from app.services.forming_setup_service import FormationSetupService


def test_previous_metrics_loads_one_row_per_symbol_without_loading_full_history():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    StockMetrics.__table__.create(engine)
    snapshot = date(2026, 10, 1)
    try:
        with Session(engine) as session:
            session.add_all([
                StockMetrics(symbol=symbol, date=snapshot - timedelta(days=offset))
                for symbol in ("CORT", "PEER", "OUTSIDE")
                for offset in range(1000)
            ])
            # A symbol with no earlier row must retain neutral missing history.
            session.add(StockMetrics(symbol="NEW", date=snapshot))
            session.commit()

            class AsyncDatabase:
                loaded_count = None

                async def execute(self, statement):
                    # Count the actual rows selected, not just the returned dict:
                    # Python deduplication of an unbounded query must fail here.
                    rows = session.execute(statement).scalars().all()
                    self.loaded_count = len(rows)
                    return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: rows))

            db = AsyncDatabase()
            previous = asyncio.run(FormationSetupService(db)._previous_metrics(
                ["CORT", "PEER", "NEW", "MISSING"], snapshot,
            ))
            assert db.loaded_count == 2
            assert set(previous) == {"CORT", "PEER"}
            assert all(row.date == snapshot - timedelta(days=1) for row in previous.values())

            # Preserve the existing global-snapshot cutoff even for a stale symbol.
            session.add(StockMetrics(symbol="STALE", date=snapshot - timedelta(days=10)))
            session.commit()
            stale = asyncio.run(FormationSetupService(db)._previous_metrics(["STALE"], snapshot))
            assert stale["STALE"].date == snapshot - timedelta(days=10)
            assert asyncio.run(FormationSetupService(db)._previous_metrics([], snapshot)) == {}
    finally:
        engine.dispose()
