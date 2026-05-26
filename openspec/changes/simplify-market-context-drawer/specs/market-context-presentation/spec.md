## ADDED Requirements

### Requirement: Market context drawer MUST surface at most eight elements by default

El componente `MarketContextDrawer` SHALL renderizar como máximo 8 elementos informacionales visibles sin interacción adicional del usuario (excluyendo chrome estructural como section headers descriptor/delta, header del panel, botón close, y backdrop). Esta restricción defiende Principio 3 (context compression mandatory) y Principio 6 (operational clarity > feature richness): el drawer existe para responder "¿qué contexto evalúa el sistema ahora?" en segundos, no para listar todas las métricas internas del engine.

El conjunto primario (7 métricas) DEBE ser: `breadth_above_ema21`, `breadth_momentum_5d`, `highs_lows_ratio` (participation); `leader_count`, `leader_count_delta_20d`, `leader_pullback_quality_avg`, `leader_climactic_count` (leadership). El octavo elemento permitido es el footer compacto con `as_of` y `universe_size`.

Las restantes métricas (las 13 raw) SHALL exponerse mediante un toggle "Raw metrics" colapsado por defecto, sin requerir un nuevo fetch al backend.

#### Scenario: Default render shows only primary metrics

- **WHEN** el operador abre el drawer con datos completos del backend
- **THEN** el DOM muestra exactamente las 7 métricas primarias listadas + footer compacto + dos section headers (Participation, Leadership Quality) con sus descriptores y delta_5d + sección "Phase 2-4 pending" colapsada en una línea; ninguna de las 13 raw metrics aparece sin click

#### Scenario: Raw metrics toggle exposes the rest

- **WHEN** el operador hace click en el botón "Raw metrics (13)"
- **THEN** las 13 métricas restantes se renderizan inline debajo del toggle, sin disparar un fetch adicional al backend, y el caret del botón cambia de ▸ a ▾

#### Scenario: Drawer remount resets toggle

- **WHEN** el operador cierra el drawer y lo reabre
- **THEN** el toggle "Raw metrics" vuelve a estado colapsado (no persiste preferencia)

### Requirement: Phase 2-4 pending engines MUST render as a single line

El componente SHALL representar la lista `ctx.engines_pending` (típicamente: persistence, forgiveness, rotation, volatility, follow-through) como una sola línea de texto compacta de baja prominencia visual (text-[10px] text-white/30 o equivalente), no como cards individuales por engine. Esto reduce "anticipation theater": el roadmap se reconoce sin ocupar peso visual proporcional al trabajo aún no entregado.

#### Scenario: Pending engines line render

- **WHEN** `ctx.engines_pending` contiene N nombres de engines pendientes
- **THEN** se renderiza una sola línea con formato `Phase 2-4 pending: name1 · name2 · ... · nameN` (o variante en español), sin cards, badges, ni containers individuales por engine
