from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List
from app.core.deps import get_db
from app.models.stock import Stock, StockPrice, StockMetrics, TransitionObservation
from app.schemas.stock import Stock as StockSchema, StockPrice as StockPriceSchema, StockMetrics as StockMetricsSchema
from app.services.quality_leader_gate import evaluate_minervini_criteria
from app.services.symbol_diagnostic import (
    diagnose_actionable,
    diagnose_live,
    diagnose_u_and_r,
    diagnose_emerging_leaders,
    diagnose_building_bases,
    list_check_to_dict,
)
from app.services.group_strength_service import (
    fetch_current_group_strengths,
    compute_group_multiplier,
)
from app.services.context_decision_filter import (
    fetch_current_context,
    compute_context_multiplier,
)

router = APIRouter()


@router.get("/", response_model=List[StockSchema])
async def get_stocks(
    skip: int = 0,
    limit: int = 100,
    sector: str = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Stock).where(Stock.is_active == True)
    if sector:
        query = query.where(Stock.sector == sector)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{symbol}", response_model=StockSchema)
async def get_stock(symbol: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Stock).where(Stock.symbol == symbol.upper()))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return stock


@router.get("/{symbol}/prices", response_model=List[StockPriceSchema])
async def get_stock_prices(
    symbol: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    query = select(StockPrice).where(
        StockPrice.symbol == symbol.upper()
    ).order_by(StockPrice.date.desc()).limit(days)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{symbol}/metrics", response_model=StockMetricsSchema)
async def get_stock_metrics(symbol: str, db: AsyncSession = Depends(get_db)):
    query = select(StockMetrics).where(
        StockMetrics.symbol == symbol.upper()
    ).order_by(StockMetrics.date.desc()).limit(1)
    result = await db.execute(query)
    metrics = result.scalar_one_or_none()
    if not metrics:
        raise HTTPException(status_code=404, detail="Metrics not found")
    return metrics


@router.get("/{symbol}/diagnostic")
async def get_symbol_diagnostic(symbol: str, db: AsyncSession = Depends(get_db)):
    """Explain pass/fail per system list for any active ticker."""
    sym = symbol.upper()
    stock = (await db.execute(select(Stock).where(Stock.symbol == sym))).scalar_one_or_none()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Symbol {sym} not found")

    latest_date = (await db.execute(select(func.max(StockMetrics.date)))).scalar()
    metrics = (await db.execute(
        select(StockMetrics)
        .where(StockMetrics.symbol == sym)
        .order_by(StockMetrics.date.desc())
        .limit(1)
    )).scalar_one_or_none()

    header = {
        "symbol": stock.symbol,
        "name": stock.name,
        "sector": stock.sector,
        "industry": stock.industry,
        "market_group": stock.market_group,
        "current_price": metrics.current_price if metrics else None,
        "has_metrics": metrics is not None,
        "metrics_date": metrics.date.isoformat() if metrics and metrics.date else None,
        "is_latest": (metrics is not None and latest_date is not None and metrics.date == latest_date),
    }

    if not metrics:
        return {
            "header": header,
            "note": f"No stock_metrics row found for {sym}. Stock may be delisted or outside the universe.",
            "lists": [],
            "transition_history": [],
            "market_context_applied": None,
            "group_strength": None,
            "minervini_status": None,
        }

    # 25-day metrics history for stateful checks (U&R, building bases)
    today = date.today()
    hist_start = today - timedelta(days=25)
    history_rows = (await db.execute(
        select(
            StockMetrics.date,
            StockMetrics.distance_to_ema21_atr,
            StockMetrics.distance_to_ema50_atr,
        )
        .where(StockMetrics.symbol == sym, StockMetrics.date >= hist_start)
        .order_by(StockMetrics.date)
    )).all()
    history_25d = [
        {"date": d, "d21": d21, "d50": d50}
        for d, d21, d50 in history_rows
    ]
    d21_history_nonnull = [h["d21"] for h in history_25d if h["d21"] is not None]

    # Recent observations (last 30d) for transition_history + boolean checks
    obs_cutoff = today - timedelta(days=30)
    obs_rows = (await db.execute(
        select(TransitionObservation)
        .where(TransitionObservation.symbol == sym, TransitionObservation.date_detected >= obs_cutoff)
        .order_by(desc(TransitionObservation.date_detected))
        .limit(10)
    )).scalars().all()
    transition_history = [
        {
            "transition_type": o.transition_type,
            "date_detected": o.date_detected.isoformat() if o.date_detected else None,
            "outcome_status": o.outcome_status,
        }
        for o in obs_rows
    ]
    # Booleans for /live (recent non-stable) and /u_and_r (last 2d non-stable)
    cutoff_2d = today - timedelta(days=2)
    has_recent_non_stable = any(o.transition_type != 'stable' for o in obs_rows)
    has_recent_2d_obs = any(
        o.transition_type != 'stable' and o.date_detected >= cutoff_2d
        for o in obs_rows
    )

    # Group strength + market context (for applied-multiplier reporting)
    group_perfs = await fetch_current_group_strengths(db)
    group_mult = compute_group_multiplier(stock.market_group, group_perfs)
    participation, leadership = await fetch_current_context(db)
    ctx_mult = compute_context_multiplier(participation, leadership)

    group_strength_payload = {
        "group": stock.market_group,
        "badge": group_mult.badge,
        "multiplier": group_mult.score_multiplier,
    }
    market_context_applied = {
        "participation": participation,
        "leadership": leadership,
        "score_multiplier": ctx_mult.score_multiplier,
        "suppress_lenses": list(ctx_mult.suppress_lenses),
        "surface_warnings": list(ctx_mult.surface_warnings),
    }

    # Run the diagnostics
    lists = [
        list_check_to_dict(diagnose_actionable(metrics)),
        list_check_to_dict(diagnose_live(metrics, has_recent_non_stable)),
        list_check_to_dict(diagnose_u_and_r(metrics, history_25d, has_recent_2d_obs)),
        list_check_to_dict(diagnose_emerging_leaders(metrics)),
        list_check_to_dict(diagnose_building_bases(metrics, d21_history_nonnull)),
    ]

    # Compute actual inclusion + rank by hitting the same endpoints/services the UI uses.
    # This makes "passes criteria + cutoff" answers truthful: passing filter ≠ appearing.
    import logging as _logging
    _log = _logging.getLogger(__name__)

    async def _augment_with_rank(list_key: str, fetch_symbols):
        try:
            symbols_in_order = await fetch_symbols()
            in_list = sym in symbols_in_order
            for lst in lists:
                if lst["key"] == list_key:
                    lst["appears_in_endpoint"] = in_list
                    lst["rank_in_endpoint"] = (
                        symbols_in_order.index(sym) + 1 if in_list else None
                    )
                    lst["total_in_endpoint"] = len(symbols_in_order)
                    break
        except Exception as e:
            _log.warning(f"diagnostic: rank for {sym} in {list_key} failed: {e}")

    async def _fetch_actionable_symbols():
        from app.api.v1.endpoints.transitions import get_actionable_setups
        resp = await get_actionable_setups(limit=12, db=db)
        return [s["symbol"] for s in resp.get("setups", [])]

    async def _fetch_live_symbols():
        from app.api.v1.endpoints.transitions import get_live_transitions
        resp = await get_live_transitions(limit=20, background_tasks=None, db=db)
        return [s["symbol"] for s in resp] if isinstance(resp, list) else []

    async def _fetch_uar_symbols():
        from app.services.setup_queue_service import SetupQueueService
        resp = await SetupQueueService(db).list_u_and_r()
        return [r["symbol"] for r in resp]

    async def _fetch_emerging_symbols():
        from app.services.setup_queue_service import SetupQueueService
        resp = await SetupQueueService(db).list_emerging_leaders()
        return [r["symbol"] for r in resp]

    async def _fetch_bases_symbols():
        from app.services.setup_queue_service import SetupQueueService
        resp = await SetupQueueService(db).list_building_bases()
        return [r["symbol"] for r in resp]

    await _augment_with_rank("actionable", _fetch_actionable_symbols)
    await _augment_with_rank("live", _fetch_live_symbols)
    await _augment_with_rank("u_and_r", _fetch_uar_symbols)
    await _augment_with_rank("emerging_leaders", _fetch_emerging_symbols)
    await _augment_with_rank("building_bases", _fetch_bases_symbols)

    # Per-symbol priority_score breakdown for /actionable — works even when the symbol
    # is below the top-12 cutoff. This is what answers "what's holding me back?".
    try:
        from app.api.v1.endpoints.transitions import _calculate_priority_score_with_breakdown
        from app.services.transition_engine import TransitionEngine
        from app.services.market_regime_engine import MarketRegimeEngine

        # Find the /actionable list check to attach breakdown to it.
        # Compute regardless of pass/fail — the breakdown shows where the score
        # components sit even when the symbol doesn't qualify (educational).
        actionable_check = next((l for l in lists if l["key"] == "actionable"), None)
        if actionable_check:
            t_engine = TransitionEngine(db)
            r_engine = MarketRegimeEngine(db)
            regime = await r_engine.detect_regime()
            # days_in_state: best-effort from setup_state_log
            from app.api.v1.endpoints.transitions import _get_days_in_state
            dis_map = await _get_days_in_state(db, [sym])
            days_in_state = dis_map.get(sym, 1)
            base_score, breakdown = await _calculate_priority_score_with_breakdown(
                metrics, regime, t_engine, db, days_in_state
            )
            ctx_v = ctx_mult.score_multiplier
            grp_v = group_mult.score_multiplier
            final_unclamped = base_score * ctx_v * grp_v
            final = min(1.0, final_unclamped)
            breakdown_full = dict(breakdown)
            breakdown_full["ctx_multiplier"] = {
                "value": ctx_v,
                "max_value": 1.10,
                "kind": "market_wide",
            }
            breakdown_full["group_multiplier"] = {
                "value": grp_v,
                "max_value": 1.15,
                "kind": "group_rotation",
                "badge": group_mult.badge,
                "group": stock.market_group,
            }
            breakdown_full["final_priority_unclamped"] = round(final_unclamped, 4)
            breakdown_full["final_priority"] = round(final, 4)
            breakdown_full["clamped"] = final_unclamped > 1.0
            actionable_check["score_breakdown"] = breakdown_full
    except Exception as e:
        import logging as _log_mod
        _log_mod.getLogger(__name__).warning(f"diagnostic: score_breakdown for {sym} failed: {e}")

    # Quality Assessment — top-of-page plain-language narrative answering
    # "why is this symbol where it is, and what would push it to top?"
    assessment = _build_quality_assessment(stock, metrics, lists, ctx_mult, group_mult)

    # Minervini per-criterion breakdown (helpful when quality_leader fails)
    minervini_status = evaluate_minervini_criteria(metrics)

    return {
        "header": header,
        "lists": lists,
        "transition_history": transition_history,
        "market_context_applied": market_context_applied,
        "group_strength": group_strength_payload,
        "minervini_status": minervini_status,
        "assessment": assessment,
    }


def _build_quality_assessment(stock, m, lists, ctx_mult, group_mult) -> dict:
    """Generate plain-language assessment of where the symbol stands and what's
    blocking it from being top-tier.

    Returns:
      {
        verdict: "elite" | "strong" | "mid" | "weak" | "disqualified",
        headline: str,
        strengths: [str],
        gaps: [{name, severity, what_to_do}],
      }
    """
    strengths: list[str] = []
    gaps: list[dict] = []

    actionable_check = next((l for l in lists if l["key"] == "actionable"), None)
    bd = actionable_check.get("score_breakdown") if actionable_check else None

    # Disqualified: fails the institutional liquidity prereq
    if not actionable_check or not bd:
        return {
            "verdict": "disqualified",
            "headline": "Sin datos suficientes para evaluar.",
            "strengths": [],
            "gaps": [],
        }

    # Detect why criteria fails (if it does)
    failing = [c for c in actionable_check.get("criteria", []) if not c["passes"]]
    if failing:
        # Group failures
        liquidity_fail = any("volume" in c["name"].lower() or "adr" in c["name"].lower() for c in failing)
        ema_fail = any("ema" in c["name"].lower() or "EMA" in c["name"] for c in failing)
        structure_fail = any(s in c["name"] for c in failing for s in ("SMA", "ema50", "EMA50", "ema200", "EMA200", "perf_1y"))

        if liquidity_fail:
            return {
                "verdict": "disqualified",
                "headline": "Descalificado — no pasa el filtro institucional de liquidez (volumen ≥ 800k, ADR ≥ 4%).",
                "strengths": [],
                "gaps": [{
                    "name": "Liquidez insuficiente",
                    "severity": "blocker",
                    "what_to_do": "Este símbolo no es tradeable a tamaño institucional. Esperar volumen sostenido o descartar.",
                }],
            }
        if structure_fail:
            return {
                "verdict": "weak",
                "headline": "Setup roto — fallan criterios estructurales (Stage 2 / Minervini SEPA).",
                "strengths": [],
                "gaps": [{
                    "name": "Estructura no es de tendencia alcista",
                    "severity": "blocker",
                    "what_to_do": "Esperar a que precio/medias se realineen. Fuera de scope de setup institucional hasta entonces.",
                }],
            }
        if ema_fail:
            d9 = m.distance_to_ema9_atr
            d21 = m.distance_to_ema21_atr
            return {
                "verdict": "mid",
                "headline": "Fuera de zona de pullback — precio extendido respecto a EMAs cortas.",
                "strengths": [],
                "gaps": [{
                    "name": "Distancia EMA fuera de rango",
                    "severity": "blocker",
                    "what_to_do": f"Esperar pullback: precio debe estar en [-1.0, +0.5] ATR de EMA9 ({d9:+.2f} actual) o EMA21 ({d21:+.2f} actual).",
                }],
            }

    # Criteria passed — analyze the score breakdown to find gaps
    components = bd["components"]
    pq_comp = next((c for c in components if c["name"] == "pullback_quality"), None)
    fresh_comp = next((c for c in components if c["name"] == "freshness"), None)
    regime_comp = next((c for c in components if c["name"] == "regime_alignment"), None)

    final = bd["final_priority"]

    # Pullback quality analysis
    if pq_comp:
        pq_pct = pq_comp["value"]
        if pq_pct >= 85:
            strengths.append(f"Pullback de alta calidad ({pq_pct:.0f}/100) — estructura técnica sólida")
        elif pq_pct >= 70:
            sub = pq_comp.get("sub_components", [])
            weakest = sorted(sub, key=lambda s: s["points"] / s["max_points"] if s["max_points"] else 1)[:2]
            issues = "; ".join(s["verdict"] for s in weakest)
            gaps.append({
                "name": "Pullback quality mid-tier",
                "severity": "medium",
                "what_to_do": f"Score {pq_pct:.0f}/100 (top suele ser 85+). Sub-issues: {issues}",
            })
        else:
            sub = pq_comp.get("sub_components", [])
            weakest = sorted(sub, key=lambda s: s["points"] / s["max_points"] if s["max_points"] else 1)[:3]
            issues = "; ".join(s["verdict"] for s in weakest)
            gaps.append({
                "name": "Pullback quality bajo",
                "severity": "high",
                "what_to_do": f"Score {pq_pct:.0f}/100 lejos del top. Principales gaps: {issues}",
            })

    # Freshness analysis
    if fresh_comp:
        fr_pct = fresh_comp["value"]
        if fr_pct >= 100:
            strengths.append("Freshness en peak (1-3 días en estado)")
        elif fr_pct >= 75:
            strengths.append(f"Freshness buena ({fresh_comp['note']})")
        else:
            gaps.append({
                "name": "Setup envejecido",
                "severity": "medium" if fr_pct >= 40 else "high",
                "what_to_do": f"{fresh_comp['note']}. Solo una nueva transición resetea esto — esperar o descartar.",
            })

    # Regime analysis
    if regime_comp:
        if regime_comp["value"] >= 0.20:
            strengths.append("Régimen de mercado favorable (risk_on)")
        elif regime_comp["value"] <= 0.10:
            gaps.append({
                "name": "Régimen de mercado adverso",
                "severity": "medium",
                "what_to_do": "Risk-off general. Reducir tamaño o esperar mejora del contexto macro.",
            })

    # Multipliers
    ctx_v = bd["ctx_multiplier"]["value"]
    grp_v = bd["group_multiplier"]["value"]
    if ctx_v >= 1.10:
        strengths.append("Contexto multidimensional fuerte (× 1.10)")
    elif ctx_v < 1.00:
        gaps.append({
            "name": "Contexto suprime el score",
            "severity": "high" if ctx_v <= 0.7 else "medium",
            "what_to_do": f"Multiplier × {ctx_v:.2f}. Participation/leadership en deterioro — esperar mejora del contexto macro.",
        })

    if grp_v >= 1.15:
        strengths.append(f"Grupo líder rotacionalmente — {bd['group_multiplier'].get('group','')} (top 20%)")
    elif grp_v <= 0.85:
        gaps.append({
            "name": "Grupo rotacionalmente débil",
            "severity": "medium",
            "what_to_do": f"Grupo {bd['group_multiplier'].get('group','')} en bottom 20%. Penalty × 0.85. Esperar rotación al grupo o buscar setups en grupos fuertes.",
        })

    # Final verdict
    if final >= 0.95:
        verdict = "elite"
        headline = "Setup de élite. Cerca del top en cada dimensión medida."
    elif final >= 0.85:
        verdict = "strong"
        headline = "Setup fuerte. Pocas áreas por mejorar."
    elif final >= 0.70:
        verdict = "mid"
        headline = "Setup mid-tier. Pasa criterios pero hay gaps específicos para subir."
    elif final >= 0.50:
        verdict = "weak"
        headline = "Setup débil. Pasa el filtro pero el score compuesto es bajo."
    else:
        verdict = "weak"
        headline = "Score muy bajo. Probablemente mejor mirar otros setups."

    return {
        "verdict": verdict,
        "headline": headline,
        "strengths": strengths,
        "gaps": gaps,
    }
