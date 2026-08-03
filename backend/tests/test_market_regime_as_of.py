"""Regression coverage for snapshot-anchored market regime detection."""
import asyncio
from datetime import date

from sqlalchemy.dialects import postgresql

from app.services.market_regime_engine import MarketRegime, MarketRegimeEngine


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class RecordingDb:
    def __init__(self, values):
        self.values = iter(values)
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return ScalarResult(next(self.values))


class ProbeEngine(MarketRegimeEngine):
    def __init__(self, resolved):
        super().__init__(db=object())
        self.resolved = resolved
        self.factor_dates = []

    async def _resolve_as_of(self, target=None):
        self.target = target
        return self.resolved

    async def _factor(self, as_of, value):
        self.factor_dates.append(as_of)
        return value

    async def _calculate_breadth_quality(self, as_of=None):
        return await self._factor(as_of, 0.30)

    async def _calculate_leadership_health(self, as_of=None):
        return await self._factor(as_of, 0.50)

    async def _calculate_speculative_appetite(self, as_of=None):
        return await self._factor(as_of, 0.60)

    async def _calculate_sector_expansion(self, as_of=None):
        return await self._factor(as_of, 0.40)

    async def _calculate_pullback_environment_quality(self, as_of=None):
        return await self._factor(as_of, 0.55)


def test_detect_regime_passes_one_resolved_date_to_every_factor():
    resolved = date(2026, 7, 24)
    target = date(2026, 7, 26)
    engine = ProbeEngine(resolved)
    result = asyncio.run(engine.detect_regime(target))

    assert engine.target == target
    assert engine.factor_dates == [resolved] * 5
    assert result.as_of == resolved
    assert result.regime == MarketRegime.RISK_OFF


def test_empty_history_returns_neutral_choppy_context():
    engine = ProbeEngine(None)
    result = asyncio.run(engine.detect_regime(date(2020, 1, 1)))
    assert result.regime == MarketRegime.CHOPPY
    assert result.as_of is None
    assert result.breadth_quality == 0.5
    assert result.leadership_health == 0.5
    assert result.speculative_appetite == 0.5


def test_breadth_queries_include_exact_snapshot_date():
    snapshot = date(2026, 7, 27)
    db = RecordingDb([40, 100, 20])
    engine = MarketRegimeEngine(db)
    value = asyncio.run(engine._calculate_breadth_quality(snapshot))
    assert round(value, 4) == 0.34

    sql = "\n".join(
        str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        for statement in db.statements
    )
    assert sql.count("stock_metrics.date = '2026-07-27'") == 3
