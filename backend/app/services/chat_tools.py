"""Read-only tool layer for the in-app chat.

Each tool is a thin async wrapper around an existing endpoint function or
service method, called with an explicit ``AsyncSession``. Nothing here mutates
the database — every handler is a SELECT path that already powers a UI panel.

``TOOLS`` is the JSON schema list handed to Claude; ``HANDLERS`` maps each tool
name to its coroutine. ``test_chat_tools.py`` asserts the two stay in sync.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints import transitions as tx
from app.api.v1.endpoints.calibration import calibration_by_transition_type
from app.services.setup_queue_service import SetupQueueService

# Valid enum values surfaced to the model so it passes correct arguments.
_TRANSITION_TYPES = (
    "entering_pullback, volume_dry_up, compressing, flush_and_recover, "
    "support_holding, breakout, reclaiming, continuation_holding, weakening, "
    "distribution, failing, stabilizing"
)
_REGIMES = "risk_on, choppy, transition, risk_off"
_QUEUE_TYPES = "u_and_r, rs_leaders, emerging_leaders, building_bases"


# ─── Handlers ────────────────────────────────────────────────────────────────
# The endpoint functions declare ``db = Depends(get_db)``; Depends only resolves
# when FastAPI invokes them, so calling directly with an explicit db is correct.


async def get_actionable_setups(db: AsyncSession, limit: int = 6) -> dict:
    return await tx.get_actionable_setups(limit=limit, db=db)


async def get_live_transitions(db: AsyncSession, limit: int = 10) -> list:
    return await tx.get_live_transitions(limit=limit, background_tasks=None, db=db)


async def get_symbol_transition(db: AsyncSession, symbol: str) -> dict:
    return await tx.get_symbol_operational_transition(symbol=symbol, db=db)


async def get_symbol_observations(db: AsyncSession, symbol: str) -> list:
    return await tx.observations_for_symbol(symbol=symbol, db=db)


async def get_symbol_history(db: AsyncSession, symbol: str, days: int = 30) -> dict:
    return await SetupQueueService(db).get_symbol_history(symbol.upper(), days)


async def get_calibration(db: AsyncSession) -> dict:
    return await calibration_by_transition_type(db=db)


async def get_track_record(
    db: AsyncSession,
    transition_type: str,
    regime: Optional[str] = None,
    days: int = 90,
) -> dict:
    return await tx.track_record(
        transition_type=transition_type, regime=regime, days=days, db=db
    )


async def get_setup_queue(db: AsyncSession, queue_type: str) -> list:
    svc = SetupQueueService(db)
    if queue_type == "u_and_r":
        return await svc.list_u_and_r()
    if queue_type == "rs_leaders":
        return await svc.list_rs_leaders()
    if queue_type == "emerging_leaders":
        return await svc.list_emerging_leaders()
    if queue_type == "building_bases":
        return await svc.list_building_bases()
    raise ValueError(f"Unknown queue_type '{queue_type}'. Valid: {_QUEUE_TYPES}")


HANDLERS = {
    "get_actionable_setups": get_actionable_setups,
    "get_live_transitions": get_live_transitions,
    "get_symbol_transition": get_symbol_transition,
    "get_symbol_observations": get_symbol_observations,
    "get_symbol_history": get_symbol_history,
    "get_calibration": get_calibration,
    "get_track_record": get_track_record,
    "get_setup_queue": get_setup_queue,
}


# ─── Tool schemas (handed to Claude) ─────────────────────────────────────────

TOOLS = [
    {
        "name": "get_actionable_setups",
        "description": (
            "Top setups accionables de hoy, rankeados por priority_score (calidad "
            "del setup, 0-1). Úsala cuando el usuario pregunte qué comprar/observar "
            "hoy, los mejores setups, o el ranking actual. Incluye continuation_prob, "
            "tipo de setup, distancia a EMAs, RS y group_strength por símbolo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Cuántos setups devolver (1-12).",
                    "minimum": 1,
                    "maximum": 12,
                }
            },
        },
    },
    {
        "name": "get_live_transitions",
        "description": (
            "Feed de las transiciones de estado más recientes del universo "
            "institucional (pullbacks en zona EMA y breakouts). Úsala para "
            "'qué está pasando ahora', cambios de estado recientes en general."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Cuántas transiciones devolver (1-20).",
                    "minimum": 1,
                    "maximum": 20,
                }
            },
        },
    },
    {
        "name": "get_symbol_transition",
        "description": (
            "Transición operacional ACTUAL de un símbolo concreto (su estado más "
            f"reciente vs el día previo). Tipos posibles: {_TRANSITION_TYPES}. "
            "Úsala cuando pregunten 'en qué estado está <símbolo>'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker, ej. ELAN."}
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_symbol_observations",
        "description": (
            "Historial de cambios de estado (observaciones) de un símbolo, con su "
            "outcome posterior (SUCCESS/FAILURE/NEUTRAL/PENDING/INSUFFICIENT_DATA) y "
            "métricas a 1/5/20 días. Úsala para 'qué cambios de estado tuvo <símbolo>' "
            "o 'cómo le fue después de cada señal'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker, ej. ELAN."}
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_symbol_history",
        "description": (
            "Resumen de los últimos N días de un símbolo: régimen actual, "
            "observaciones recientes y track record por (tipo de transición × "
            "régimen). Úsala para una vista compacta del recorrido reciente de un "
            "símbolo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker, ej. ELAN."},
                "days": {
                    "type": "integer",
                    "description": "Ventana en días (default 30).",
                },
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_calibration",
        "description": (
            "Tasa de éxito empírica observada por tipo de transición (qué % de los "
            "setups de cada tipo entregaron buen rendimiento posterior), con tamaños "
            "de muestra. Úsala para preguntas de calibración / qué tan confiable es "
            "cada tipo de señal."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_track_record",
        "description": (
            "Estadísticas históricas de un tipo de transición (opcionalmente filtrado "
            f"por régimen) en una ventana de días: success/failure/neutral rate, "
            f"avg pct_5d, gain/drawdown en ATR. Tipos: {_TRANSITION_TYPES}. "
            f"Regímenes: {_REGIMES}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "transition_type": {
                    "type": "string",
                    "description": f"Uno de: {_TRANSITION_TYPES}.",
                },
                "regime": {
                    "type": "string",
                    "description": f"Opcional. Uno de: {_REGIMES}.",
                },
                "days": {
                    "type": "integer",
                    "description": "Ventana en días (1-365, default 90).",
                },
            },
            "required": ["transition_type"],
        },
    },
    {
        "name": "get_setup_queue",
        "description": (
            "Devuelve una de las colas de setups: 'u_and_r' (unconfirmed & recently "
            "triggered), 'rs_leaders' (líderes por fuerza relativa), "
            "'emerging_leaders' (fuertes aún no calificados), 'building_bases' "
            "(líderes consolidando bases VCP). Úsala para listar candidatos por "
            "categoría."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "queue_type": {
                    "type": "string",
                    "description": f"Una de: {_QUEUE_TYPES}.",
                    "enum": [
                        "u_and_r",
                        "rs_leaders",
                        "emerging_leaders",
                        "building_bases",
                    ],
                }
            },
            "required": ["queue_type"],
        },
    },
]


async def dispatch(name: str, args: dict, db: AsyncSession):
    """Run the handler for ``name`` with the model-supplied ``args``."""
    handler = HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"Unknown tool '{name}'")
    return await handler(db=db, **args)
