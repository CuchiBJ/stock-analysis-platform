"""Exercise the pullback data migration on a disposable in-memory database."""
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


DERIVED_FIELDS = (
    "price_1d", "price_5d", "price_20d", "pct_1d", "pct_5d", "pct_20d",
    "max_gain_within_10d", "max_drawdown_within_10d",
    "max_gain_atr_within_10d", "max_drawdown_atr_within_10d",
    "reached_ema21_within_10d", "broke_ema50_within_10d",
)


@pytest.mark.parametrize("direction", ["upgrade", "downgrade"])
def test_migration_resets_only_terminal_pullbacks_preserving_detection(monkeypatch, direction):
    path = Path(__file__).resolve().parents[1] / "alembic/versions/e5f6a7b8c9d0_reset_entering_pullback_outcomes.py"
    spec = importlib.util.spec_from_file_location("pullback_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    observations = sa.Table(
        "transition_observations", metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("transition_type", sa.String),
        sa.Column("outcome_status", sa.String),
        sa.Column("outcome_evaluated_at", sa.String),
        sa.Column("price_at_detection", sa.Float),
        sa.Column("ema9_at_detection", sa.Float),
        sa.Column("ema21_at_detection", sa.Float),
        sa.Column("ema50_at_detection", sa.Float),
        sa.Column("atr_at_detection", sa.Float),
        sa.Column("date_detected", sa.String),
        sa.Column("regime_at_detection", sa.String),
        *(sa.Column(field, sa.Float) for field in DERIVED_FIELDS),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        records = []
        for i, status in enumerate(("SUCCESS", "FAILURE", "NEUTRAL", "INSUFFICIENT_DATA", "PENDING"), 1):
            records.append(dict(
                id=i, transition_type="entering_pullback", outcome_status=status,
                outcome_evaluated_at="2026-06-20", price_at_detection=100.0,
                ema9_at_detection=99.0, ema21_at_detection=97.0, ema50_at_detection=90.0,
                atr_at_detection=2.0, date_detected="2026-06-01", regime_at_detection="risk_on",
                **{field: 1.0 for field in DERIVED_FIELDS},
            ))
        records.append(dict(records[0], id=6, transition_type="support_holding"))
        connection.execute(observations.insert(), records)
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        getattr(migration, direction)()
        rows = connection.execute(sa.select(observations).order_by(observations.c.id)).mappings().all()
        for row in rows[:4]:
            assert row["outcome_status"] == "PENDING"
            assert row["outcome_evaluated_at"] is None
            assert all(row[field] is None for field in DERIVED_FIELDS)
            for field in ("price_at_detection", "ema9_at_detection", "ema21_at_detection",
                          "ema50_at_detection", "atr_at_detection", "date_detected", "regime_at_detection"):
                assert row[field] == records[row["id"] - 1][field]
        assert dict(rows[4]) == records[4]
        assert dict(rows[5]) == records[5]
    engine.dispose()
