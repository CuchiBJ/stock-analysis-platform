## Context

`CompactSetupCard` es el componente de mayor exposición visual del dashboard: aparece 6 veces en `TopActionableSetups` (panel principal de `/dashboard`). Hoy renderiza ~18 elementos por instancia (símbolo, priority flame, watch badge, freshness badge, exhausted warning, continuation %, empirical sub-line, state label, price label, narrative, 4 métricas, footer con clock + daysInState + transition icon + transition label).

Tres elementos identificados por la auditoría institucional de mayo 2026 como puro ruido:

1. **Footer transition icon/label**: en `TopActionableSetups`, `transition` se pasa hardcoded como `"stable"` (línea 148). El icono y label nunca cambian — son chrome muerto.
2. **Footer `Nd in state`**: redundante con el `freshness` badge, que ya codifica la misma información en bandas (fresh ≤3d, aging ≤7d, late-stage ≤14d, stale ≤20d, extended >20d).
3. **Metric "Base"**: en `TopActionableSetups` se pasa hardcoded como `'fast'` (EMA9) u `'8w'` (EMA21) según `setup_type`. No es una métrica calculada — es un duplicado textual del `state` label ("EMA9 Pullback" / "EMA21 Pullback").

La sub-línea `empirical (N=X)` / `rule-based` es información honesta pero de baja frecuencia de consulta: el operador toma decisiones con el `continuation %`, no con la procedencia del número. Mover a tooltip mantiene la honestidad (Principio 7: interpretability) sin saturar.

## Goals / Non-Goals

**Goals:**
- Reducir elementos visibles por card de ~18 a ~12 (33% menos).
- Mantener cero pérdida de información accionable: cada elemento eliminado es o constante (transition footer), o redundante (daysInState vs freshness, Base vs state), o consultable on-demand (probability source).
- Cambio quirúrgico: cero impacto en lógica de scoring, backend, otras superficies.
- Defender Principio 3 (context compression) y Principio 6 (operational clarity > feature richness).

**Non-Goals:**
- No tocar `MarketContextDrawer` ni ningún otro componente.
- No introducir tooltip library (Radix, Floating UI, etc.). Usar `<span title="...">` o tooltip mínimo inline con CSS group-hover.
- No modificar el shape de los datos del backend.
- No remover props del interface — el shape se mantiene para evitar romper otros callers (aunque hoy solo hay uno). Limpieza profunda de props es out-of-scope.

## Decisions

### D1: Tooltip nativo vs componente

**Decisión**: usar `<span title="...">` nativo del browser para el continuation %.

**Por qué**: zero dependencies, zero JavaScript, accessibility por defecto. La información (source + N) es texto plano, no requiere formato rico. El tradeoff de estética (tooltip browser-default vs custom) es aceptable porque el caso de uso es ocasional.

Alternativa rechazada: componente `Tooltip` custom con CSS group-hover. Más bonito visualmente, pero suma ~10 líneas de JSX y conflicts con z-index del grid. No vale para Phase 1.

### D2: Eliminar `daysInState` del footer pero mantenerlo en props

**Decisión**: el prop `daysInState` sigue existiendo en `CompactSetupCardProps` (no se quita del interface), simplemente no se renderiza dentro del componente.

**Por qué**: el freshness ya codifica la banda. El número exacto sirve a debug pero el card no es un panel de debug — `/queue` lo muestra explícitamente cuando hace falta. Mantener el prop evita auditar todos los callers.

### D3: Eliminar metric "Base" del grid

**Decisión**: el grid de métricas pasa de 4 (Dist | RS | Vol | Base) a 3 (Dist | RS | Vol). Grid sigue siendo 2-cols, con tercer cell vacío.

**Alternativa considerada**: grid 1×3 horizontal. Rechazada porque cambia altura del card y rompe alineación con cards hermanos en `grid-cols-6`. Mantener 2×2 con un cell vacío es trivial y preserva ritmo vertical.

**Por qué eliminar Base**: el caller lo hardcodea como `'fast'`/`'8w'`. No hay nada que calcular. Si en el futuro existe una métrica de base real (semanas, profundidad, contracciones), se reintroduce con un valor real — no este placeholder.

### D4: Probability tooltip — copy

```
empirical: "Probabilidad empírica · N=42 observaciones"
rule_based: "Probabilidad rule-based · sin sample histórico suficiente"
sin source: tooltip vacío (no se setea title)
```

Spanish consistente con el resto del UI.

### D5: Eliminar imports muertos

Con el footer fuera, `Clock`, `TrendingUp`, `TrendingDown`, `Activity` no se usan. Eliminar imports y la constante `TRANSITION_ICON`. Mantener `Flame` (usado por `isPriority`).

## Risks / Trade-offs

1. **Tooltip nativo no se ve en mobile/touch**: aceptable porque el producto es desktop-only (declarado en `WHAT_THIS_PRODUCT_IS_NOT.md`, item "Mobile app / responsive").
2. **Pérdida del transition icon como señal de cambio**: Es un riesgo aparente, no real — `transition` siempre llega como `"stable"` desde `actionable`. Si en el futuro se quisiera mostrar transitions dinámicas en `actionable`, requeriría primero que el backend las calcule (hoy no lo hace) — se reintroducirá entonces.
3. **El cell vacío en el grid 2×2 puede verse asimétrico**: tradeoff a verificar visualmente; si molesta, el grid se puede cambiar a `grid-cols-3` con 3 métricas horizontales (sin cambiar altura). Decisión defer a inspección visual post-implementación.
4. **Sub-línea empirical/rule-based oculta**: operador que confía en `continuation %` sin saber su origen puede tomar decisiones con falsa confianza. Mitigación: el accent border ya codifica cont% threshold; el operador que quiere trazabilidad la encuentra con hover. Si en producción se observa que el operador siempre revisa la sub-línea, se reintroduce — fácil rollback.
5. **No-op para otros callers**: hoy `CompactSetupCard` solo se usa en `TopActionableSetups`. Si en el futuro otro caller espera el footer, hay que reconsiderar — pero hoy no hay drift que defender.
