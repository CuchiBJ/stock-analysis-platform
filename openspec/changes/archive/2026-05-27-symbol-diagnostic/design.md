## Context

Los filtros de cada lista viven en distintos archivos:
- `transitions.py`: `_INSTITUTIONAL_SETUP`, `_EMA9_TRIGGER`, `_EMA21_TRIGGER`, `_ACTIONABLE_FILTER`
- `universe_filters.py`: `QUALITY_FILTERS`
- `quality_leader_gate.py`: `is_quality_leader`, `evaluate_minervini_criteria`
- `setup_queue_service.py`: U&R "from above" rule, Building bases VCP, Emerging Leaders criteria (inline en métodos)

Para que el diagnostic sea inspeccionable, **no podemos reusar las SQL queries directamente** — devuelven sí/no booleano por toda la condición. Necesitamos descomponer cada filtro en checks individuales con (name, threshold, actual, passes).

## Goals / Non-Goals

**Goals:**
- Para cualquier símbolo activo: explicar pass/fail por lista con detalle de cada criterio
- Cero refactor del production code — diagnostic es un módulo PARALELO que replica las reglas como expresiones Python inspectables
- Test coverage por cada lista que verifique pass + fail caminos con metrics sintéticos

**Non-Goals:**
- DRY perfecto entre diagnostic y filters de producción (sería refactor mayor)
- Diagnostic en tiempo real ultra-eficiente (cada call hace ~5-10 queries, aceptable para per-symbol lookup)
- Historical diff ("ayer pasaba, hoy no")
- Multi-symbol diagnostic

## Decisions

### D1: Diagnostic module replica filtros como Python (no SQL)

**Decisión**: `symbol_diagnostic.py` define funciones puras `diagnose_<list>(metrics, history, observations) -> ListCheck` que toman los datos ya cargados y devuelven el dict con criterios.

```python
def diagnose_actionable(m: StockMetrics) -> ListCheck:
    return ListCheck(
        name="Top Actionable Setups",
        criteria=[
            criterion("pullback_quality ≥ 55", m.pullback_quality_score, 55.0, "ge"),
            criterion("avg_volume_10d ≥ 800k", m.avg_volume_10d, 800_000, "ge"),
            criterion("EMA9 distance in [-1.0, +0.5] ATR", m.distance_to_ema9_atr, (-1.0, 0.5), "range"),
            ...
        ]
    )
```

**Por qué**: el diagnostic NUNCA debería decir "no califica" mientras el filter real lo deja entrar (o viceversa). Hay riesgo de drift. Mitigación:
1. Tests con metrics conocidos que pasan/fallan filters reales y verifican que diagnostic concuerda
2. Cada filter constant (_INSTITUTIONAL_SETUP, etc.) tiene su contraparte de diagnostic en el mismo módulo, con comentario `# mirrors X in transitions.py`

**Alternativa rechazada**: introspectar `_INSTITUTIONAL_SETUP` (un `and_(...)` de SQLAlchemy) para extraer criterios programáticamente. Frágil — depende de internals de SQLAlchemy.

### D2: Para listas con state histórico (U&R "from above"), cargar ventana mínima

**Decisión**: U&R requiere d21_atr en los últimos 10 días + observations recientes. El diagnostic carga ventana 25 días de metrics + observations para tener TODO lo que el filter real consulta.

**Performance**: por símbolo individual, ~3 queries: latest metrics, 25d history, recent observations. <100ms total. Aceptable.

### D3: Símbolos no encontrados → 404 con detalle

**Decisión**: si el ticker no existe en `stocks` table → HTTP 404 `{"detail": "Symbol XYZ not found"}`.

Si existe pero no tiene metrics (ej. delistado, sin coverage) → HTTP 200 pero `header.has_metrics=false`, `lists=[]`, mensaje explícito en respuesta.

**Por qué**: 404 cubre tipos ("FOOBAR"), 200-con-flag cubre símbolos válidos sin datos suficientes. Distinción útil para el frontend.

### D4: Search es input-y-navega, no autocomplete

**Decisión**: `<input>` que en Enter hace `router.push("/stock/" + input.toUpperCase())`. Cero llamadas a la API para autocomplete.

**Por qué**: 90% del tiempo Fernando sabe qué ticker quiere. El autocomplete agrega 4-5 layers (debounce, dropdown, keyboard nav, click) por solo ahorrar typo recovery.

**Para evitar ruido**: si la página /stock/{symbol} recibe un símbolo no existente, muestra error state con sugerencia (ej. "did you mean NXT?" — fuzzy match contra Stock.symbol). Phase 2.

### D5: Lista "Estado en cada lista" siempre muestra las 5 listas — incluso las que pasa

**Decisión**: el detalle de pass/fail se muestra para TODAS las listas, no solo las que falla. Para listas que pasan, default colapsado mostrando solo ✓; expandible para ver criterios verdes (educativo).

**Por qué**: a veces querés saber CÓMO está pasando una lista para entender el margen de seguridad (ej. "passes con 802k vs 800k umbral — se podría caer mañana"). Es información operacional.

### D6: Transition history visualización compacta

**Decisión**: lista vertical de las últimas ~10 obs (timestamp + type + outcome_status como badge), no gráfica de líneas.

**Por qué**: con N≤30 obs por símbolo en 30 días, un gráfico no agrega valor. Una lista es legible inmediata.

## Risks / Trade-offs

1. **Drift diagnostic vs filter real**: si alguien cambia `_INSTITUTIONAL_SETUP` y olvida actualizar `diagnose_institutional`, el diagnostic miente. Mitigación: tests que comparen pass/fail entre filter SQL y diagnostic Python con metrics sintéticos. Si el test falla, alguien refactoreó sin sincronizar.

2. **Filtros que dependen de joins (e.g., quality_leader_gate consulta otros datos)**: el diagnostic los necesita explícitos. Algunas funciones existentes (`is_quality_leader`) pueden reutilizarse directamente.

3. **Performance per-symbol**: ~5-10 queries por call. Para uso humano (1 lookup ≈ 1 request) aceptable. Si en el futuro alguien lo ejecuta en bulk (no es el caso Phase 1), revisar.

4. **Mantenimiento futuro**: cada nueva lista o filter que se agregue al sistema requiere una contraparte en diagnostic. Sin esto, la lista nueva queda sin explicación. Documentar en code comments.

5. **Fernando podría usar el deep-dive para racionalizar entries malas**: "el sistema dice que NO pero está por X%, voy igual". El page solo informa, no recomienda. Tradeoff aceptado — más data > menos data, aunque puede confirmar bias.

6. **Símbolos delistados o sin coverage**: tienen `Stock` row pero no metrics recientes. El page debe manejarlo elegante (no crash). Manejado con `has_metrics=false`.
