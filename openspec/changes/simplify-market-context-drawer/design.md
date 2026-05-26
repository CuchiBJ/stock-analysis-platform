## Context

`MarketContextDrawer` se abre con click en `MarketContextBar`. Hoy renderiza:

- 2 section headers (descriptor + delta 5d)
- 9 métricas participation crudas
- 10 métricas leadership crudas
- 5 cards "pending" (engines de Phase 2-4)
- 2 líneas de footer (as_of/universe + 20d sample size)

Total: ~28 elementos informacionales visibles sin interacción adicional.

El audit identifica que un trader institucional decide con **3-4 métricas** del bloque participación + leadership; el resto es debug que ocupa espacio cognitivo cada vez que el drawer se abre. La hipótesis del rediseño: las 7 que sobreviven (3 participation + 4 leadership) son las que **mueven decisión**; las otras 13 son **trazabilidad** que el operador consulta una vez al mes (cuando algo se ve raro y quiere verificar).

`MarketContextData` (definido en `MarketContextBar`) llega ya completo del backend — todas las 19 métricas vienen en un solo fetch. Por eso el toggle "Raw metrics" no requiere segundo request: muestra/oculta lo que ya está en memoria.

## Goals / Non-Goals

**Goals:**
- 19 métricas visibles → 7 visibles + 12 detrás de toggle (más una métrica primaria reclasificada: `highs_lows_ratio` que no era visible separadamente — bueno, sí lo era).
- Toggle "Raw metrics" colapsa por defecto. Estado local (`useState`) — no persiste.
- Sección "Coming in Phase 2-4": 5 cards → 1 línea de texto.
- Footer: 2 líneas → 1 línea (drop "20d sample size").
- Total elementos por defecto: ~28 → ~10. ~64% reducción.

**Non-Goals:**
- No cambiar el backend ni el shape de datos.
- No introducir librerías nuevas (`@radix-ui/react-collapsible` etc.) — toggle con `useState` y render condicional.
- No tocar `MarketContextBar`.
- No agregar copy explicativo per-métrica.
- No animar el expand/collapse (snap transitions; aceptable para drawer modal).
- No persistir preferencia del usuario (re-colapsa al reabrir).

## Decisions

### D1: Selección de las 7 métricas primarias

Cita textual del audit: *"Las que cambian decisión: breadth%, momentum 5d, leader_count, leader_count_delta_20d, leader_pullback_quality_avg, leader_climactic_count"* (6 nombradas).

**Selección final (7)**:

| Bloque | Métrica | Por qué primaria |
|---|---|---|
| Participation | `breadth_above_ema21` | El "breadth%" del audit (EMA21 es el horizonte swing) |
| Participation | `breadth_momentum_5d` | El "momentum 5d" del audit — vector de cambio |
| Participation | `highs_lows_ratio` | Salud de extremos; complementa breadth absoluto |
| Leadership | `leader_count` | Cuántos leaders activos hoy |
| Leadership | `leader_count_delta_20d` | Expansión/contracción del liderazgo (horizonte swing) |
| Leadership | `leader_pullback_quality_avg` | Salud de pullbacks actuales (operativo) |
| Leadership | `leader_climactic_count` | Riesgo de agotamiento — primer trigger de cautela |

**Rechazadas del set primario**:
- `breadth_above_ema50/ema200` → covered conceptually por EMA21 + momentum; nivel exacto es debug
- `breadth_momentum_20d` → redundante con _5d salvo en contextos de transición lenta
- `near_highs_count`/`near_lows_count` → input para `highs_lows_ratio`; la ratio comprime la info
- `participation_persistence` → debug
- `leader_count_delta_5d` → ruido de día a día; 20d es el window operativo
- `leader_tightness_avg`/`leader_vol_contraction_avg` → cualidad técnica fina; debug
- `leader_rs_persistence_10d` → comportamiento, no decisión inmediata
- `leader_extension_count` → cerca de climactic pero menos crítico
- `leadership_turnover_5d` → diagnóstico de rotación; consultado cuando algo se ve raro

### D2: Toggle "Raw metrics" — UX

**Decisión**: un botón al final de la lista visible que dice `▸ Raw metrics (13)` o `▾ Raw metrics (13)`, con click toggle. Cuando expandido, renderiza las 13 restantes con el mismo `MetricRow` debajo. Sin animación.

**Por qué**: minimalismo. No introducir un componente custom expandible; basta con `useState<boolean>` + ternary render. El número entre paréntesis le dice al operador que hay más sin abrirlo.

### D3: Toggle es global, no por sección

**Decisión**: un único toggle al final del drawer (después de Leadership), no uno por sección. Cuando expandido, muestra las 13 raw metrics en dos sub-bloques (Participation raw, Leadership raw) bajo un mismo header "Raw metrics".

**Por qué**: simplicidad. Un solo botón. El operador casi nunca expande; cuando lo hace, quiere ver todo (debug = "¿qué está pasando?", no "quiero ver solo participation"). Dos toggles serían más UX overhead que UX gain.

### D4: Sección "Phase 2-4 pending" — colapsar a una línea

**Decisión**: reemplazar el bloque `{ctx.engines_pending.map(...)}` por una sola línea en el footer area:

```
Phase 2–4 pending · persistence · forgiveness · rotation · volatility · follow-through
```

Estilo: `text-[10px] text-white/30`. Pre-existente: 5 cards × ~50px de alto = ~250px de espacio vertical. Post: ~20px.

**Por qué**: la información ("estos engines vienen") sigue presente; el peso visual baja 90%. Defiende contra "anticipation theater" (mostrar peso por features no entregadas).

**Alternativa rechazada**: eliminar la sección. Rechazada porque scaffolding honesto sobre roadmap es valioso para el operador que viene de la audit (sabe qué viene); colapsado es honesto + barato.

### D5: Footer — eliminar "20d sample size"

**Decisión**: eliminar la línea `20d sample size: {p.delta_sample_size_20d} stocks`.

**Por qué**: el sample size no se consulta operacionalmente — solo importa si alguien duda de los deltas, en cuyo caso revisa logs o specs. `as_of` + `universe_size` ya cubren el contexto temporal y de cobertura.

### D6: Estado del toggle no persiste

**Decisión**: `useState(false)` reset cada vez que el drawer monta.

**Por qué**: el drawer es modal efímero (se cierra al click backdrop, se desmonta). Persistir requeriría localStorage + reading on mount; overhead innecesario para un caso de uso ocasional. Operador que recurrentemente necesita raw metrics → señal de que hay un problema más profundo (engines wrong, métricas no confiables) y no se resuelve con UI memory.

## Risks / Trade-offs

1. **Operador acostumbrado a las 19 métricas no las encuentra**: mitigado porque están a 1 click ("Raw metrics" toggle). Audit explícita la queja "instrumentar todo" como problema, no como necesidad.
2. **Si se descubre que una métrica raw es decisional, hay que re-promoverla**: trivial — mover del bloque raw al primario. Cero migración de datos.
3. **Mostrar `highs_lows_ratio` sin mostrar sus inputs (`near_highs_count`, `near_lows_count`) puede confundir**: aceptable; la ratio comprime. Si el operador quiere descomponerla, abre raw.
4. **Toggle sin animación puede sentirse abrupto**: aceptable para drawer modal de uso ocasional. No vale la complejidad de transitions.
5. **Phase 2-4 reducido a una línea reduce su presencia como compromiso visible**: tradeoff intencional. Compromisos sin fecha son ruido visual; el roadmap real vive en specs/PRODUCT_BRAIN.
6. **El bloque raw metrics expandido aumenta el alto del drawer**: aceptable porque el drawer tiene `overflow-y-auto` y solo el operador que lo expandió pidió ese contenido.
