## Why

Patrón repetido hoy mismo: Fernando ve un símbolo y pregunta "¿por qué FN no aparece?" / "¿por qué AAOI no está en U&R?". Cada vez termino corriendo queries SQL ad-hoc para explicar qué filtro falla. La info ya existe en la DB pero **no es inspeccionable desde la UI**: tenés que confiar en que el sistema decidió bien.

Sin un deep-dive por símbolo, la plataforma es una caja negra para casos individuales. Con uno, cualquier símbolo (incluyendo los que NO aparecen en ninguna lista) puede ser auditado: qué filtros pasa, cuáles falla, con qué valor vs qué threshold. Cierra Principio 7 (interpretability) a nivel símbolo.

## What Changes

- **NEW endpoint** `GET /api/v1/stocks/{symbol}/diagnostic` que retorna, para CUALQUIER símbolo activo:
  - `header`: symbol, name, sector, industry, market_group, group_strength {group, badge, multiplier}, current_price
  - `lists`: array de checks por cada lista del sistema (`/actionable`, `/live`, `/queue/u-and-r`, `/queue/emerging-leaders`, `/queue/building-bases`). Cada check tiene:
    - `name`: nombre legible (e.g., "U&R Queue")
    - `passes`: bool
    - `criteria`: array de `{name, threshold, actual, passes, kind}` donde `kind` ∈ {numeric, boolean, range}
  - `transition_history`: últimas 30d de `transition_observations` para el símbolo
  - `market_context_applied`: `{participation, leadership, score_multiplier}` que aplicarían si entrara a /actionable
- **NEW page** `/stock/[symbol]` (Next.js App Router) que renderiza:
  - Header con grupo y multipliers
  - Tabla de "Estado en cada lista" con checkmark o cruz por lista, expandible para ver criterios fallidos
  - Cuadrícula de transitions recientes (icono + tipo + age + outcome status)
  - Card de market context aplicado
- **NEW component** `SymbolSearch` en `DashboardLayout` (nav): input simple, Enter → navega a `/stock/{TICKER}`. Phase 1 sin autocomplete (texto + uppercase).
- **NEW endpoint** `GET /api/v1/stocks/search?q=XX` (opcional, para autocomplete futuro) — retorna up to 10 symbols matching prefix. **Skip en Phase 1**: solo input texto + navigate.

## Capabilities

### New Capabilities
- `symbol-diagnostic` — endpoint + page que explican por qué un símbolo entra o no en cada lista, con todos los criterios y valores

### Modified Capabilities
- (none) — los endpoints existentes (/actionable, /queue/*, etc.) no cambian. El diagnostic LEE las mismas reglas pero las expone como pass/fail explícitos.

## Impact

- NEW: `backend/app/services/symbol_diagnostic.py` — lógica de evaluación por lista (replicar los filtros de cada endpoint como expresiones Python inspectables)
- NEW: `backend/app/api/v1/endpoints/stocks_diagnostic.py` o agregar al `stocks.py` existente — endpoint
- NEW: `backend/tests/test_symbol_diagnostic.py` — unit tests por lista
- NEW: `frontend/app/stock/[symbol]/page.tsx`
- NEW: `frontend/components/layout/SymbolSearch.tsx`
- MODIFIED: `frontend/components/layout/DashboardLayout.tsx` — mount SymbolSearch en el nav
- MODIFIED: cards de `/queue/*` y `/actionable` — link "ver detalle" al `/stock/{symbol}` (mejora secundaria)

## Non-goals

- **No autocomplete del search** — texto + Enter es suficiente Phase 1. Si el operador escribe mal, ve "símbolo no encontrado" y reintenta. Autocomplete agrega complejidad (debounce, lista ordenada, hit ranking) que no necesita Phase 1.
- **No edit/save de "símbolos favoritos"** — esto es deep-dive read-only. Si quiere watchlist personal, es otro change (rechazado anteriormente por Fernando).
- **No recomendación cuando el símbolo no califica** — el page muestra qué criterios fallan, no "compra cuando esto cambie". Operador interpreta.
- **No replica TODAS las decisiones del sistema** — Phase 1 cubre las 5 listas principales (actionable, live, 3 queues). El priority_score interno (composición de muchos sub-scores) no se desglosa Phase 1.
- **No diff vs ayer/semana pasada** — "qué cambió" requiere histórico de filter results que no guardamos. Defer.
- **No exporta a CSV/clipboard** — operador puede screenshot.
- **No bulk-diagnose** — un símbolo a la vez. Multi-symbol comparison es un patrón distinto.
