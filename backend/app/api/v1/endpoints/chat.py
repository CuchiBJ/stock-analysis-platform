"""In-app chat — natural-language Q&A over the DB via Claude tool use.

Read-only by construction: the model can only call the curated tools in
``chat_tools`` (all SELECT paths), never raw SQL or writes. Stateless per
request — the frontend resends the plain-text history; this endpoint runs a
fresh tool-use loop each call.
"""
from __future__ import annotations

import json
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db
from app.services import chat_tools

logger = logging.getLogger(__name__)

router = APIRouter()

MODEL = "claude-opus-4-8"
MAX_TOKENS = 16000
MAX_TOOL_ITERATIONS = 8  # safety cap on the agentic loop


def _system_prompt() -> str:
    return (
        "Sos un asistente analítico embebido en una plataforma de análisis de "
        "acciones (estilo Minervini/SEPA). Respondés preguntas sobre el estado "
        f"de la base de datos. La fecha de hoy es {date.today().isoformat()}.\n\n"
        "Conceptos del dominio:\n"
        "- 'Transiciones' son cambios de estado operacional de un setup "
        "(entering_pullback, breakout, reclaiming, weakening, etc.).\n"
        "- 'Calibración' / 'track record' = tasa de éxito empírica observada de "
        "cada tipo de transición según outcomes históricos.\n"
        "- 'Setups accionables' se rankean por priority_score (calidad del setup); "
        "'continuation_prob' es una probabilidad aparte (heurística/empírica).\n"
        "- Regímenes de mercado: risk_on, choppy, transition, risk_off.\n\n"
        "Reglas:\n"
        "- SIEMPRE anclá tus respuestas en los datos que devuelven las "
        "herramientas. No inventes símbolos, números ni tasas: si no llamaste a "
        "una herramienta para ese dato, no lo afirmes.\n"
        "- Si los datos no alcanzan, decilo explícitamente.\n"
        "- Respondé en español, conciso y al grano. Usá los números reales "
        "(scores, %, tamaños de muestra) que devuelven las herramientas."
    )


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


def _client():
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY no está configurada en el backend.",
        )
    # Imported lazily so the app boots even if the package isn't installed yet.
    from anthropic import AsyncAnthropic

    return AsyncAnthropic(api_key=settings.anthropic_api_key)


@router.post("/")
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages no puede estar vacío.")

    client = _client()

    messages: list[dict] = [
        {"role": m.role, "content": m.content} for m in req.messages
    ]
    tools_used: list[str] = []

    try:
        for _ in range(MAX_TOOL_ITERATIONS):
            response = await client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=_system_prompt(),
                thinking={"type": "adaptive"},
                tools=chat_tools.TOOLS,
                messages=messages,
            )

            # Preserve the full assistant turn (incl. thinking + tool_use blocks).
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                break

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                tools_used.append(block.name)
                try:
                    result = await chat_tools.dispatch(block.name, dict(block.input), db)
                    content = json.dumps(result, default=str, ensure_ascii=False)
                    is_error = False
                except Exception as e:  # surface tool errors back to the model
                    logger.warning("chat tool '%s' failed: %s", block.name, e)
                    content = f"Error ejecutando {block.name}: {e}"
                    is_error = True
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": content,
                        "is_error": is_error,
                    }
                )

            messages.append({"role": "user", "content": tool_results})
        else:
            logger.warning("chat hit MAX_TOOL_ITERATIONS without finishing")

        answer = "".join(
            b.text for b in response.content if getattr(b, "type", None) == "text"
        ).strip()

        return {
            "answer": answer or "(sin respuesta)",
            "tools_used": tools_used,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("chat endpoint error: %s", e)
        raise HTTPException(status_code=500, detail=f"Error en el chat: {e}")
