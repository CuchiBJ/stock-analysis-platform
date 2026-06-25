import math
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text
from typing import List, Dict
from app.models.stock import Stock, StockMetrics, StockPrice
from app.models.sector import Sector
from app.core.cache import cache_sectors
from app.services.sector_mapping import map_sector_to_tradingview


class SectorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @cache_sectors
    async def calculate_sector_performance(self) -> List[Dict]:
        """Groups by market_group (~25 momentum-trading groups) — see market_group_mapping.py.
        The endpoint path /sectors/performance is preserved for compat but the unit of grouping
        changed from GICS L1 to market_group in 2026-05."""
        # Window function avoids a second GROUP BY aggregation pass
        result = await self.db.execute(text("""
            WITH latest AS (
                SELECT *,
                       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
                FROM stock_metrics
            )
            SELECT
                s.market_group,
                l.symbol,
                l.perf_1w,
                l.perf_4w,
                l.relative_volume,
                l.pullback_quality_score,
                l.relative_strength_spy
            FROM latest l
            JOIN stocks s ON s.symbol = l.symbol
            WHERE l.rn = 1
              AND s.market_group IS NOT NULL
              AND l.avg_volume_10d  >= 800000
              AND l.current_price   >= 5.0
              AND l.perf_1w         IS NOT NULL
        """))
        # NB: NO se filtra por ADR aquí. El ADR es un criterio de TRADEO, no de
        # representatividad del sector. Filtrarlo achicaba los grupos de baja
        # volatilidad (Banks/Real Estate/Utilities a ~4 acciones) y sesgaba el
        # agregado. Sin ADR todos los grupos quedan ≥16 → la señal no miente.
        # El filtro de tradeo (ADR≥4%) vive en get_group_constituents.
        rows = result.fetchall()

        groups: dict = defaultdict(list)
        for row in rows:
            groups[row.market_group].append(row)

        spy_perf = await self._get_spy_performance()
        sector_performance = []

        for group_name, stocks in groups.items():
            weekly_perfs  = [r.perf_1w for r in stocks if r.perf_1w  is not None]
            monthly_perfs = [r.perf_4w for r in stocks if r.perf_4w  is not None]

            if not weekly_perfs:
                continue

            avg_weekly  = sum(weekly_perfs)  / len(weekly_perfs)
            avg_monthly = sum(monthly_perfs) / len(monthly_perfs) if monthly_perfs else avg_weekly * 4

            if not (math.isfinite(avg_weekly) and math.isfinite(avg_monthly)):
                continue

            leaders_sorted = sorted(
                [r for r in stocks if r.pullback_quality_score is not None],
                key=lambda r: (r.pullback_quality_score or 0) * 0.6 + (r.relative_strength_spy or 100) * 0.4,
                reverse=True
            )
            leaders = [r.symbol for r in leaders_sorted[:3]]
            avg_rvol = sum(r.relative_volume for r in stocks if r.relative_volume) / max(len(stocks), 1)

            sector_performance.append({
                "name":                group_name,
                "performance_weekly":  round(avg_weekly,  2),
                "performance_monthly": round(avg_monthly, 2),
                "performance_vs_spy":  round(avg_monthly - spy_perf, 2),
                "trend":     "accelerating" if avg_weekly > 1 else "decelerating" if avg_weekly < -1 else "steady",
                "strength":  "strong" if avg_monthly > 2 else "weak" if avg_monthly < -2 else "moderate",
                "volume_trend": "increasing" if avg_rvol > 1.5 else "decreasing" if avg_rvol < 0.8 else "stable",
                "stock_count": len(stocks),
                "leaders":   leaders,
            })

        sector_performance.sort(key=lambda x: x["performance_monthly"], reverse=True)
        return sector_performance

    @cache_sectors
    async def calculate_sector_rotation(self, lookback_sessions: int = 5) -> Dict:
        """Sector rotation by momentum: which market_groups are GAINING leadership.

        Compares each group's average relative strength (RS vs SPY) now vs
        `lookback_sessions` trading days ago, ranks groups at both points, and
        flags groups moving up the ranking as `rotating_in` (and down as
        `rotating_out`). Answers "qué sectores vienen ganando".
        """
        # Trading dates present in stock_metrics (desc). Anchor now + lookback.
        date_rows = (await self.db.execute(
            select(StockMetrics.date).distinct().order_by(StockMetrics.date.desc())
        )).scalars().all()
        if not date_rows:
            return {"as_of": None, "compared_to": None, "lookback_sessions": lookback_sessions,
                    "rotating_in": [], "rotating_out": [], "groups": []}
        date_now = date_rows[0]
        idx = min(lookback_sessions, len(date_rows) - 1)
        date_prev = date_rows[idx]

        # One query for both snapshots. Same liquidity floor as performance, but
        # NO ADR filter — el ADR es criterio de tradeo, no de representatividad; al
        # excluirlo, sectores de baja volatilidad (Banks/Real Estate/Utilities) dejan
        # de aparecer con muestras de ~4 acciones y la rotación deja de mentir.
        rows = (await self.db.execute(text("""
            SELECT s.market_group, l.date, l.relative_strength_spy, l.perf_4w
            FROM stock_metrics l
            JOIN stocks s ON s.symbol = l.symbol
            WHERE l.date IN (:d_now, :d_prev)
              AND s.market_group IS NOT NULL
              AND l.avg_volume_10d >= 800000
              AND l.current_price  >= 5.0
        """), {"d_now": date_now, "d_prev": date_prev})).fetchall()

        # Average RS (fallback perf_4w) per (group, date); count stocks per group at now.
        sums: dict = defaultdict(lambda: defaultdict(float))
        counts: dict = defaultdict(lambda: defaultdict(int))
        for r in rows:
            val = r.relative_strength_spy if r.relative_strength_spy is not None else r.perf_4w
            if val is None or not math.isfinite(val):
                continue
            sums[r.market_group][r.date] += val
            counts[r.market_group][r.date] += 1

        def avg(group, d):
            n = counts[group].get(d, 0)
            return sums[group][d] / n if n else None

        # Eligible groups: ≥5 stocks at the current snapshot and present at both dates.
        eligible = [g for g in sums
                    if counts[g].get(date_now, 0) >= 5
                    and avg(g, date_now) is not None and avg(g, date_prev) is not None]

        rank_now = {g: i + 1 for i, g in enumerate(
            sorted(eligible, key=lambda g: avg(g, date_now), reverse=True))}
        rank_prev = {g: i + 1 for i, g in enumerate(
            sorted(eligible, key=lambda g: avg(g, date_prev), reverse=True))}

        groups = []
        for g in eligible:
            rdelta = rank_prev[g] - rank_now[g]
            rs_delta = round(avg(g, date_now) - avg(g, date_prev), 2)
            direction = "rotating_in" if rdelta >= 2 else "rotating_out" if rdelta <= -2 else "stable"
            groups.append({
                "name": g,
                "rank_now": rank_now[g],
                "rank_prev": rank_prev[g],
                "rank_delta": rdelta,
                "rs_now": round(avg(g, date_now), 2),
                "rs_delta": rs_delta,
                "stock_count": counts[g].get(date_now, 0),
                "direction": direction,
            })

        def _summary(items):
            return [{"name": x["name"], "rank_delta": x["rank_delta"],
                     "rs_delta": x["rs_delta"], "rank_now": x["rank_now"]} for x in items]

        rotating_in = sorted([g for g in groups if g["direction"] == "rotating_in"],
                             key=lambda x: (x["rank_delta"], x["rs_delta"]), reverse=True)
        rotating_out = sorted([g for g in groups if g["direction"] == "rotating_out"],
                              key=lambda x: (x["rank_delta"], x["rs_delta"]))

        return {
            "as_of": date_now.isoformat() if date_now else None,
            "compared_to": date_prev.isoformat() if date_prev else None,
            "lookback_sessions": idx,
            "rotating_in": _summary(rotating_in[:3]),
            "rotating_out": _summary(rotating_out[:3]),
            "groups": sorted(groups, key=lambda x: x["rank_now"]),
        }

    async def get_group_constituents(self, group: str, limit: int = 60) -> Dict:
        """Stocks within a market_group, ranked by score + structure.

        Uses the same composite the heatmap leaders use
        (pullback_quality_score * 0.6 + relative_strength_spy * 0.4), over the
        institutional-quality universe, so the order matches what's surfaced
        elsewhere. Returns puntaje (pullback_quality), structure (weekly trend
        quality) and RS per stock so the UI can show why each ranks where it does.
        """
        latest_date = (await self.db.execute(select(func.max(StockMetrics.date)))).scalar()
        if latest_date is None:
            return {"group": group, "as_of": None, "count": 0, "stocks": []}

        rows = (await self.db.execute(
            select(
                Stock.symbol, Stock.name,
                StockMetrics.current_price,
                StockMetrics.pullback_quality_score,
                StockMetrics.weekly_trend_quality,
                StockMetrics.relative_strength_spy,
                StockMetrics.distance_to_ema21_atr,
                StockMetrics.adr_percent,
                StockMetrics.perf_1w,
            )
            .join(Stock, Stock.symbol == StockMetrics.symbol)
            .where(
                Stock.market_group == group,
                StockMetrics.date == latest_date,
                StockMetrics.avg_volume_10d >= 800000,
                StockMetrics.current_price >= 5.0,
                StockMetrics.adr_percent >= 4.0,
            )
        )).all()

        stocks = []
        for r in rows:
            pq = r.pullback_quality_score or 0.0
            rs = r.relative_strength_spy or 100.0
            structure = (r.weekly_trend_quality or 0) * 100  # 0-100
            # Orden por PUNTAJE + ESTRUCTURA (ambos 0-100, comparables). El RS NO
            # entra en el orden: en escala ~100-300 dominaría el ranking. Puntaje
            # pesa más que estructura porque es la señal principal de calidad.
            composite = pq * 0.7 + structure * 0.3
            stocks.append({
                "symbol": r.symbol,
                "name": r.name,
                "current_price": round(r.current_price, 2) if r.current_price else None,
                "score": round(pq, 1),                # puntaje
                "structure": round(structure, 0),     # estructura 0-100
                "rs": round(rs, 1),
                "dist_ema21_atr": round(r.distance_to_ema21_atr, 2) if r.distance_to_ema21_atr is not None else None,
                "adr_percent": round(r.adr_percent, 1) if r.adr_percent else None,
                "perf_1w": round(r.perf_1w, 1) if r.perf_1w is not None else None,
                "composite": round(composite, 1),
            })

        stocks.sort(key=lambda x: x["composite"], reverse=True)
        return {
            "group": group,
            "as_of": latest_date.isoformat(),
            "count": len(stocks),
            "stocks": stocks[:limit],
        }

    async def _get_spy_performance(self) -> float:
        """Get SPY monthly performance for comparison"""
        try:
            result = await self.db.execute(
                select(StockPrice.date, StockPrice.close)
                .where(StockPrice.symbol == 'SPY')
                .order_by(StockPrice.date.desc())
                .limit(30)
            )
            prices = result.fetchall()
            
            if len(prices) >= 20:
                latest_price = prices[0].close
                month_ago_price = prices[19].close
                return ((latest_price - month_ago_price) / month_ago_price) * 100
            return 0
        except:
            return 0
    
    def _determine_trend(self, distances: List[float]) -> str:
        """Determine trend based on recent performance"""
        if not distances:
            return 'steady'
        
        avg = sum(distances) / len(distances)
        if avg > 1:
            return 'accelerating'
        elif avg < -1:
            return 'decelerating'
        return 'steady'
    
    def _determine_strength(self, avg_performance: float) -> str:
        """Determine strength based on performance"""
        if avg_performance > 2:
            return 'strong'
        elif avg_performance < -2:
            return 'weak'
        return 'moderate'
    
    async def _determine_volume_trend(self, symbols: List[str]) -> str:
        """Determine volume trend based on relative volume"""
        if not symbols:
            return 'stable'
        
        try:
            result = await self.db.execute(
                select(StockMetrics.relative_volume)
                .join(Stock, Stock.symbol == StockMetrics.symbol)
                .where(Stock.symbol.in_(symbols[:50]))  # Limit to 50 stocks for performance
            )
            metrics = result.scalars().all()
            
            if not metrics:
                return 'stable'
            
            avg_rvol = sum([m for m in metrics if m]) / len([m for m in metrics if m])
            
            if avg_rvol > 1.5:
                return 'increasing'
            elif avg_rvol < 0.8:
                return 'decreasing'
            return 'stable'
        except:
            return 'stable'
    
    async def _get_sector_leaders_by_performance(self, symbols: List[str], limit: int) -> List[str]:
        """Get top performing stocks in sector by monthly performance"""
        if not symbols:
            return []
        
        stock_perfs = []
        
        for symbol in symbols[:100]:  # Limit to 100 stocks for performance
            try:
                result = await self.db.execute(
                    select(StockPrice.date, StockPrice.close)
                    .where(StockPrice.symbol == symbol)
                    .order_by(StockPrice.date.desc())
                    .limit(30)
                )
                prices = result.fetchall()
                
                if len(prices) >= 20:
                    latest_price = prices[0].close
                    month_ago_price = prices[19].close
                    monthly_perf = ((latest_price - month_ago_price) / month_ago_price) * 100
                    stock_perfs.append((symbol, monthly_perf))
            except:
                continue
        
        # Sort by monthly performance descending
        stock_perfs.sort(key=lambda x: x[1], reverse=True)
        
        return [symbol for symbol, _ in stock_perfs[:limit]]

    async def get_sector_ranking(self) -> List[Sector]:
        """Get sectors ranked by performance"""
        result = await self.db.execute(
            select(Sector).order_by(Sector.rank.asc().nulls_last())
        )
        return result.scalars().all()
    
    async def get_sector_leaders(self, sector: str, limit: int = 10) -> List[Dict]:
        """Get top leaders in a specific sector"""
        result = await self.db.execute(
            select(Stock, StockMetrics)
            .join(StockMetrics, Stock.symbol == StockMetrics.symbol)
            .where(Stock.sector == sector)
            .where(StockMetrics.distance_to_ema20.isnot(None))
            .order_by(StockMetrics.distance_to_ema20.desc())
            .limit(limit)
        )
        
        leaders = []
        for stock, metrics in result.all():
            leaders.append({
                'symbol': stock.symbol,
                'name': stock.name,
                'sector': stock.sector,
                'distance_to_ema20': metrics.distance_to_ema20,
                'relative_volume': metrics.relative_volume
            })
        
        return leaders
