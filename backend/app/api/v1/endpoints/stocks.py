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
    # ALSO captures the sort-key signature so we can explain WHY this symbol is at its rank.
    import logging as _logging
    _log = _logging.getLogger(__name__)

    async def _augment_with_rank(list_key: str, fetch_rows, key_fields: list[dict]):
        """fetch_rows() returns list[dict] with at least 'symbol' + the sort-key fields.
        key_fields is [{field, direction, label}] in sort precedence order.
        """
        try:
            rows = await fetch_rows()
            symbols_in_order = [r["symbol"] for r in rows]
            in_list = sym in symbols_in_order
            rank = symbols_in_order.index(sym) + 1 if in_list else None
            for lst in lists:
                if lst["key"] == list_key:
                    lst["appears_in_endpoint"] = in_list
                    lst["rank_in_endpoint"] = rank
                    lst["total_in_endpoint"] = len(rows)
                    if in_list and len(rows) > 0:
                        lst["rank_explanation"] = _build_rank_explanation(
                            list_key, rows, sym, rank, key_fields
                        )
                    break
        except Exception as e:
            _log.warning(f"diagnostic: rank for {sym} in {list_key} failed: {e}")

    async def _fetch_actionable_rows():
        from app.api.v1.endpoints.transitions import get_actionable_setups
        resp = await get_actionable_setups(limit=12, db=db)
        return resp.get("setups", [])

    async def _fetch_live_rows():
        from app.api.v1.endpoints.transitions import get_live_transitions
        resp = await get_live_transitions(limit=20, background_tasks=None, db=db)
        return resp if isinstance(resp, list) else []

    async def _fetch_uar_rows():
        from app.services.setup_queue_service import SetupQueueService
        return await SetupQueueService(db).list_u_and_r()

    async def _fetch_emerging_rows():
        from app.services.setup_queue_service import SetupQueueService
        return await SetupQueueService(db).list_emerging_leaders()

    async def _fetch_bases_rows():
        from app.services.setup_queue_service import SetupQueueService
        return await SetupQueueService(db).list_building_bases()

    await _augment_with_rank("actionable", _fetch_actionable_rows, [
        {"field": "priority_score", "direction": "desc", "label": "priority_score"},
    ])
    await _augment_with_rank("live", _fetch_live_rows, [
        {"field": "transition", "direction": "category", "label": "transition type (entering_pullback primero)"},
        {"field": "is_pre_reclaim", "direction": "desc_bool", "label": "is_pre_reclaim flag"},
        {"field": "observation_priority", "direction": "desc", "label": "observation_priority"},
        {"field": "strength", "direction": "desc", "label": "strength"},
    ])
    await _augment_with_rank("u_and_r", _fetch_uar_rows, [
        {"field": "event_age_days", "direction": "asc", "label": "event_age (más nuevo primero)"},
        {"field": "distance_to_ema21_atr", "direction": "abs_asc", "label": "|distancia EMA21| (más cerca primero)"},
        {"field": "rs_spy", "direction": "desc", "label": "RS vs SPY"},
    ])
    await _augment_with_rank("emerging_leaders", _fetch_emerging_rows, [
        {"field": "perf_13w", "direction": "desc", "label": "perf_13w"},
    ])
    await _augment_with_rank("building_bases", _fetch_bases_rows, [
        {"field": "atr_range_last_20d", "direction": "asc", "label": "ATR range 20d (más apretado primero)"},
        {"field": "vcp_score", "direction": "desc", "label": "VCP score"},
    ])

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


def _build_rank_explanation(
    list_key: str,
    rows: list[dict],
    sym: str,
    rank: int,
    key_fields: list[dict],
) -> dict:
    """Explain WHY this symbol is at its rank in this list.

    Compares against:
    - the top symbol (rank 1)
    - the immediately-above symbol (rank-1) if not at top
    - the immediately-below symbol (rank+1) if not at bottom

    Returns dict with sort_key_label, this_symbol values, comparisons,
    and a plain-language narrative.
    """
    def get_val(row: dict, field: str):
        return row.get(field)

    def fmt(v):
        if v is None:
            return "n/a"
        if isinstance(v, float):
            return f"{v:.2f}"
        return str(v)

    this_row = rows[rank - 1]
    top_row = rows[0]
    above_row = rows[rank - 2] if rank > 1 else None
    below_row = rows[rank] if rank < len(rows) else None

    # Extract values per sort key
    this_values = {kf["field"]: get_val(this_row, kf["field"]) for kf in key_fields}
    top_values = {kf["field"]: get_val(top_row, kf["field"]) for kf in key_fields}

    # Determine the deciding factor — first key where this differs from top
    def is_better(this_v, top_v, direction):
        if this_v is None or top_v is None:
            return False
        if direction == "desc":
            return this_v > top_v
        if direction == "asc":
            return this_v < top_v
        if direction == "abs_asc":
            return abs(this_v) < abs(top_v)
        if direction == "category":
            return this_v == top_v  # categorical equality
        return False

    deciding_factor = None
    for kf in key_fields:
        if this_values[kf["field"]] != top_values[kf["field"]]:
            deciding_factor = kf
            break

    sort_label = " → ".join(kf["label"] for kf in key_fields)

    # Build narrative
    parts = []
    if rank == 1:
        parts.append(f"Top de la lista — gana por {key_fields[0]['label']}.")
    else:
        if deciding_factor:
            this_v = fmt(this_values[deciding_factor["field"]])
            top_v = fmt(top_values[deciding_factor["field"]])
            top_sym = top_row.get("symbol", "?")
            parts.append(
                f"Rank #{rank} vs top ({top_sym}): {deciding_factor['label']} "
                f"= {this_v} (this) vs {top_v} (top)."
            )
        else:
            parts.append(f"Empate en sort keys con top — orden de inserción.")

        if above_row is not None and deciding_factor:
            ab_sym = above_row.get("symbol", "?")
            ab_v = fmt(get_val(above_row, deciding_factor["field"]))
            parts.append(
                f"Inmediato encima ({ab_sym}): {deciding_factor['label']} = {ab_v}."
            )

    return {
        "list_key": list_key,
        "sort_key_label": sort_label,
        "key_fields": [{"field": kf["field"], "label": kf["label"], "direction": kf["direction"]} for kf in key_fields],
        "this_symbol": {"symbol": sym, "values": this_values},
        "top_symbol": {"symbol": top_row.get("symbol"), "values": top_values},
        "above_symbol": (
            {"symbol": above_row.get("symbol"),
             "values": {kf["field"]: get_val(above_row, kf["field"]) for kf in key_fields}}
            if above_row else None
        ),
        "below_symbol": (
            {"symbol": below_row.get("symbol"),
             "values": {kf["field"]: get_val(below_row, kf["field"]) for kf in key_fields}}
            if below_row else None
        ),
        "deciding_factor": deciding_factor["label"] if deciding_factor else None,
        "narrative": " ".join(parts),
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

    # Detect why criteria fails (if it does). Classify each fail into a category
    # and surface the actual failing criteria in the gaps. Headline reflects the
    # PRIMARY blocker but the operator always sees the full list.
    failing = [c for c in actionable_check.get("criteria", []) if not c["passes"]]
    if failing:
        def has_kw(c, *kws):
            n = c["name"].lower()
            return any(k.lower() in n for k in kws)

        liquidity_fails = [c for c in failing if has_kw(c, "avg_volume", "≥ 800k", "≥ 700k", "≥ 500k", "≥ $5", "current_price ≥")]
        volatility_fails = [c for c in failing if has_kw(c, "adr_percent", "adr ≥")]
        structure_fails  = [c for c in failing if has_kw(c, "sma150", "sma200", "perf_1y", "52w low", "52W low", "52w high", "52W high", "price > ema50", "price > sma")]
        ema_fails        = [c for c in failing if has_kw(c, "ema9 distance", "ema21 distance", "ema9 or ema21")]
        pq_fails         = [c for c in failing if has_kw(c, "pullback_quality")]

        # Build a gap entry per failing criterion (REAL granular info)
        gap_list = [{
            "name": c["name"],
            "severity": "blocker",
            "what_to_do": f"Valor actual: {c['actual']} — umbral: {c['threshold']}.",
        } for c in failing]

        # Pick the most specific headline based on which category has fails
        if liquidity_fails:
            headline = "Descalificado por liquidez — volumen/precio mínimo no se cumple."
            verdict = "disqualified"
        elif volatility_fails and not structure_fails and not ema_fails:
            headline = f"ADR insuficiente — la acción no se mueve lo suficiente diario para el setup ({m.adr_percent:.2f}% vs ≥4% requerido)."
            verdict = "weak"
        elif structure_fails:
            # Build a specific reason describing which structural criteria fail
            reasons = []
            if any("perf_1y" in c["name"] for c in structure_fails):
                reasons.append(f"perf_1y={m.perf_1y:.0f}% (Stage 2 requiere >30%)")
            if any("52w low" in c["name"].lower() for c in structure_fails):
                if m.low_52w and m.low_52w > 0 and m.current_price:
                    pct = (m.current_price - m.low_52w) / m.low_52w * 100
                    reasons.append(
                        f"recuperación desde mín 52w insuficiente ({pct:.0f}% sobre low, requiere ≥50%)"
                    )
                else:
                    reasons.append("recuperación desde mín 52w insuficiente")
            if any("52w high" in c["name"].lower() for c in structure_fails):
                reasons.append("muy lejos del máximo 52w (>3 ATR)")
            if any("sma" in c["name"].lower() for c in structure_fails):
                reasons.append("SMAs no alineadas (medias largas no en orden alcista)")
            if any("ema50" in c["name"].lower() for c in structure_fails):
                reasons.append("precio bajo EMA50")
            headline = f"Setup roto — estructura no es de tendencia alcista ({'; '.join(reasons) if reasons else 'criterios Minervini fallan'})."
            verdict = "weak"
        elif ema_fails:
            d9 = m.distance_to_ema9_atr
            d21 = m.distance_to_ema21_atr
            headline = f"Fuera de zona de pullback — precio extendido (EMA9 {d9:+.2f} ATR, EMA21 {d21:+.2f} ATR; rango requerido [-1.0, +0.5])."
            verdict = "mid"
        elif pq_fails:
            headline = f"Pullback quality bajo ({m.pullback_quality_score:.0f}/100 < 55 requerido)."
            verdict = "weak"
        else:
            headline = f"Falla 1+ criterio del setup institucional."
            verdict = "weak"

        return {"verdict": verdict, "headline": headline, "strengths": [], "gaps": gap_list}

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
