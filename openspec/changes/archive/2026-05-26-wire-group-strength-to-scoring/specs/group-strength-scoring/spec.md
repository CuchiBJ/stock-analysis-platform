## ADDED Requirements

### Requirement: Group strength MUST be derived from monthly performance percentile

El sistema SHALL computar la fuerza relativa de cada `market_group` rankeando los ~24 grupos activos por el campo `performance_monthly` retornado por `SectorService.calculate_sector_performance`. El sistema SHALL asignar buckets discretos:
- Top 20% de grupos (5 grupos cuando hay 25) → `badge="leader"`, `multiplier=1.15`
- Bottom 20% de grupos → `badge="weak"`, `multiplier=0.85`
- Restantes ~15 grupos → `badge="neutral"`, `multiplier=1.00`

La función `compute_group_multiplier(market_group, group_perfs)` SHALL ser pura: dada la misma entrada, retorna la misma salida. El cálculo del percentil se hace sobre el snapshot recibido como argumento; no debe leer DB.

#### Scenario: Top-5 group receives leader boost

- **WHEN** se invoca `compute_group_multiplier("Electronic Technology", group_perfs)` y "Electronic Technology" está en el top 20% del ranking por `performance_monthly`
- **THEN** retorna `GroupMultiplier(score_multiplier=1.15, badge="leader")`

#### Scenario: Bottom-5 group receives weak penalty

- **WHEN** se invoca `compute_group_multiplier("Consumer Staples", group_perfs)` y "Consumer Staples" está en el bottom 20% del ranking
- **THEN** retorna `GroupMultiplier(score_multiplier=0.85, badge="weak")`

#### Scenario: Middle groups are neutral

- **WHEN** se invoca `compute_group_multiplier("Industrials", group_perfs)` y "Industrials" está fuera del top y bottom 20%
- **THEN** retorna `GroupMultiplier(score_multiplier=1.00, badge="neutral")`

### Requirement: Missing or unknown group MUST default to neutral

El sistema SHALL retornar `GroupMultiplier(score_multiplier=1.00, badge="neutral")` para cualquier entrada donde:
- `market_group` es `None` (stock sin `market_group` poblado, ej. Shell Companies o industry no mapeada)
- `market_group` no está en `group_perfs` (el grupo existe en taxonomía pero no en el snapshot — caso de cold-start o grupo sin stocks que pasen quality filter)
- `group_perfs` está vacío (cold-start, fetch falló)

Esto SHALL garantizar que datos faltantes nunca penalicen un setup. Espejo del comportamiento `UNKNOWN → NEUTRAL` en `context_decision_filter`.

#### Scenario: NULL market_group returns neutral

- **WHEN** se invoca `compute_group_multiplier(None, {"Electronic Technology": 3.5, ...})`
- **THEN** retorna `GroupMultiplier(score_multiplier=1.00, badge="neutral")`

#### Scenario: Empty group_perfs returns neutral for any group

- **WHEN** se invoca `compute_group_multiplier("Electronic Technology", {})`
- **THEN** retorna `GroupMultiplier(score_multiplier=1.00, badge="neutral")`

#### Scenario: Group not present in snapshot returns neutral

- **WHEN** se invoca `compute_group_multiplier("Renewables", group_perfs)` y "Renewables" no está como key en `group_perfs` (no pasó quality filter ese día)
- **THEN** retorna `GroupMultiplier(score_multiplier=1.00, badge="neutral")`

### Requirement: Actionable endpoint MUST apply group multiplier composed with context

El endpoint `GET /api/v1/transitions/actionable` SHALL aplicar `group_multiplier` al `priority_score` de cada setup, compuesto multiplicativamente con el `ctx_multiplier` ya existente. La composición SHALL ser:

```
final_priority = clamp_0_100(priority_score * ctx_multiplier.score_multiplier * group_multiplier.score_multiplier)
```

El endpoint SHALL incluir en cada item del response un campo `group_strength` con la forma:

```json
{
  "group": "Electronic Technology",
  "badge": "leader",
  "multiplier": 1.15
}
```

El campo `priority_score` del response SHALL contener el valor final ya ajustado (con ambos multipliers aplicados), idéntico al comportamiento actual con `ctx_multiplier`.

#### Scenario: Setup in leader group is boosted

- **WHEN** un setup tiene `priority_score=80`, contexto macro neutral (`ctx_multiplier=1.0`), y `market_group="Electronic Technology"` (leader)
- **THEN** el response trae `priority_score=92` (80 × 1.0 × 1.15) y `group_strength={"group": "Electronic Technology", "badge": "leader", "multiplier": 1.15}`

#### Scenario: Setup in weak group is penalized

- **WHEN** un setup tiene `priority_score=80`, contexto macro neutral (`ctx_multiplier=1.0`), y `market_group="Consumer Staples"` (weak)
- **THEN** el response trae `priority_score=68` (80 × 1.0 × 0.85) y `group_strength={"group": "Consumer Staples", "badge": "weak", "multiplier": 0.85}`

#### Scenario: Macro context dominates over group strength

- **WHEN** un setup tiene `priority_score=80`, contexto macro COLLAPSING (`ctx_multiplier=0.5`), y `market_group="Electronic Technology"` (leader)
- **THEN** el response trae `priority_score=46` (80 × 0.5 × 1.15), mostrando que el contexto adverso domina el boost del grupo

#### Scenario: Final score capped at 100

- **WHEN** la composición arroja un valor mayor a 100 (ej. priority_score=95, ctx_multiplier=1.1, group_multiplier=1.15 → 120.2)
- **THEN** el response trae `priority_score=100` (clamp aplicado)

### Requirement: Queue endpoints MUST surface group strength as badge only

Los endpoints `GET /api/v1/queue/u-and-r`, `/queue/emerging-leaders`, `/queue/building-bases` SHALL incluir en cada item del response un campo `group_strength` con la forma:

```json
{
  "group": "Electronic Technology",
  "badge": "leader"
}
```

(Sin campo `multiplier` — no aplica porque el sort key de la lens no se altera.)

Los endpoints de queue SHALL preservar el sort key original de cada lens:
- `/u-and-r`: ordenado por `(event_age_days asc, |distance_to_ema21_atr| asc, -rs_spy desc)`
- `/emerging-leaders`: ordenado por `-perf_13w desc`
- `/building-bases`: ordenado por `(atr_range_last_20d asc, -vcp_score desc)`

El campo `group_strength.badge` es informativo: el frontend lo renderiza como chip visual pero NO debe usarse para reordenar localmente.

#### Scenario: U&R item includes group badge without changing order

- **WHEN** un consumer llama `GET /api/v1/queue/u-and-r` y recibe N candidatos
- **THEN** cada item trae `group_strength: {group: str, badge: str}` y el orden de los items es idéntico al que tenía antes de este change (sort por event_age_days asc)

#### Scenario: Building-bases item also surfaces group badge

- **WHEN** un consumer llama `GET /api/v1/queue/building-bases`
- **THEN** cada item trae `group_strength: {group: str, badge: str}` aunque building-bases tradicionalmente no se filtra por contexto (badge es solo informativo)

#### Scenario: Stock without market_group shows neutral badge

- **WHEN** un item en cualquier queue tiene `stocks.market_group IS NULL` en DB
- **THEN** el item trae `group_strength: {group: null, badge: "neutral"}` (group puede ser null para señalar ausencia)

### Requirement: Small groups MUST default to neutral to avoid sample noise

Cuando el `performance_monthly` de un grupo proviene de menos de 5 stocks (post-quality-filter), el sistema SHALL forzar `badge="neutral"` y `multiplier=1.00` para ese grupo, independiente de dónde caiga en el ranking.

Razón: la varianza de la media muestral con n<5 es alta, lo cual hace que el ranking de ese grupo sea inestable día a día. Asignar un boost o penalty basado en muestra chica genera regret operativo.

#### Scenario: Group with 4 stocks defaults to neutral despite top performance

- **WHEN** un grupo "FooGroup" tiene `stock_count=4` y su `performance_monthly` está en top 20%
- **THEN** `compute_group_multiplier("FooGroup", group_perfs)` retorna `GroupMultiplier(score_multiplier=1.00, badge="neutral")`

### Requirement: Frontend MUST render group strength badge in setup cards and queue rows

El componente `<GroupStrengthBadge>` (compartido) SHALL renderizar:
- Chip cyan-400 con texto "🔥 Group leader" cuando `badge === "leader"`
- Chip amber-400 con texto "⚠️ Weak group" cuando `badge === "weak"`
- `null` (no renderiza nada) cuando `badge === "neutral"` o `group_strength` es ausente

El badge SHALL incluir tooltip on-hover mostrando el nombre del grupo y su rank (ej. "Electronic Technology · #2 of 25"). El componente debe ser usado consistentemente en:
- `CompactSetupCard` (usado por TopActionableSetups)
- Filas de `/queue/u-and-r`, `/queue/emerging-leaders`, `/queue/building-bases`

#### Scenario: Leader badge renders cyan chip

- **WHEN** un setup card recibe prop `groupStrength={group: "Electronic Technology", badge: "leader"}`
- **THEN** se renderiza un chip cyan-400 con texto "🔥 Group leader" y tooltip mostrando el group name

#### Scenario: Weak badge renders amber chip

- **WHEN** un setup card recibe prop `groupStrength={group: "Consumer Staples", badge: "weak"}`
- **THEN** se renderiza un chip amber-400 con texto "⚠️ Weak group" y tooltip mostrando el group name

#### Scenario: Neutral renders nothing

- **WHEN** un setup card recibe prop `groupStrength={group: "Industrials", badge: "neutral"}` o `groupStrength=null`
- **THEN** no se renderiza ningún badge (no ocupa espacio en el layout)
