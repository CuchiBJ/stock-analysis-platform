## Why

`CompactSetupCard` renderiza ~18 elementos visuales por card. Con 6 cards en `TopActionableSetups`, el panel principal del dashboard muestra ~108 elementos solo en su lista primaria. La afirmación de PRODUCT_BRAIN de "sub-20-second market assessment" no es verificable contra esa densidad.

La auditoría institucional (mayo 2026) identifica este componente como el de mayor leverage para reducir carga cognitiva: pura UI, sin riesgo arquitectónico, 6× efecto por aparecer 6 veces. Defiende **Principio 3 (Context compression mandatory)** y **Principio 6 (Operational clarity > feature richness)**.

## What Changes

- **Eliminar el footer completo** (Clock + "Nd in state" + transition icon + transition label). El campo `transition` en `actionable` setups es siempre `"stable"` — el icono y label nunca cambian; son ruido. El `daysInState` ya está implícito en el `freshness` badge (fresh = 0-3d, aging = 4-7d, late-stage = 8-14d, etc.).
- **Eliminar el metric "Base"** (`fast` / `8w` hardcoded en `TopActionableSetups` según `setup_type`). No es información — es un duplicado del `state` label ("EMA9 Pullback" / "EMA21 Pullback"). Reduce el grid de métricas de 4 a 3.
- **Mover la sub-etiqueta `empirical (N=X)` / `rule-based`** del header a tooltip on-hover sobre el `continuation %`. El operador casual ve el número; quien quiera trazabilidad la encuentra con un hover. Elimina 1 línea visible por card.
- **Eliminar import y constante `TRANSITION_ICON`** del componente, junto con el ícono `Clock`. Reduce dependencies de `lucide-react` para este archivo.
- **BREAKING (interno)**: el prop `transition` y `daysInState` siguen existiendo pero solo se usan internamente para badge `freshness` (vía caller); el `transition` icon ya no se renderiza. Caller (`TopActionableSetups`) no requiere cambios — los props mantienen tipo.

Resultado: 18 → 12 elementos por card. 6 cards × 12 = 72 elementos en el panel principal (33% reducción).

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- (none) — Esto es una simplificación de presentación dentro de un componente React. No cambia ningún requisito de las capabilities backend existentes (`transition-engine`, `priority-engine`, `setup-lifecycle`, etc.).

## Impact

- **Modificado**: `frontend/components/dashboard/CompactSetupCard.tsx` — remover footer, remover "Base" del grid, agregar tooltip de probabilidad source/N.
- **Modificado**: `frontend/components/dashboard/TopActionableSetups.tsx` — quitar `base` del objeto `keyMetrics` que se pasa al card. El prop sigue siendo opcional; otros callers (si los hubiera) no se rompen.
- **Sin cambios**: backend, otras superficies, lógica de scoring, lógica de probabilidad empirical.
- **Visualmente no afecta**: continuation %, empirical badge color, accent border, narrative, freshness, watch badge, exhausted warning, price label, RS/Vol/Dist metrics, hover behavior.

## Non-goals

- No tocar `MarketContextDrawer` (19 → 6 métricas) — change separada.
- No introducir tooltip library nueva — usar `<span title="...">` nativo o un componente simple inline.
- No re-arquitectar la grid responsive (`xl:grid-cols-6`).
- No tocar el `Card` base o el sistema de tokens de color.
- No remover props del interface (`transition`, `daysInState`, `keyMetrics.base`) — solo dejar de renderizarlos / pasarlos. Limpieza más profunda queda fuera de scope (tendría que verificar todos los callers; este cambio se mantiene quirúrgico).
