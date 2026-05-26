## ADDED Requirements

### Requirement: Compact setup card MUST keep visible element count under fifteen per instance

El componente `CompactSetupCard` SHALL renderizar como máximo 15 elementos visuales por instancia, donde "elemento visual" se cuenta como cualquier badge, ícono, label, valor numérico, párrafo de texto, o token de métrica visible sin interacción del usuario. Esta restricción defiende Principio 3 (context compression mandatory) y Principio 6 (operational clarity > feature richness): el panel principal del dashboard renderiza 6 instancias en paralelo, y un card de >15 elementos × 6 = >90 elementos solo en su lista primaria, lo cual contradice la meta de "sub-20-second market assessment" declarada en PRODUCT_BRAIN.

#### Scenario: Default render under nominal data

- **WHEN** `CompactSetupCard` recibe props completos típicos de un actionable setup (símbolo, freshness, continuation %, narrative, métricas Dist/RS/Vol, priceLabel)
- **THEN** el DOM renderiza ≤15 elementos visuales contables (header chips + cont%, state label, price label, narrative, 3 métricas labeled, optional badges como `watch` o `exhausted` cuando aplican)

#### Scenario: Information availability under hover

- **WHEN** el operador hace hover sobre el `continuation %`
- **THEN** se expone via `title` (tooltip nativo) la procedencia de la probabilidad: `empirical · N=<sampleSize>` o `rule-based · sin sample histórico suficiente`, sin agregar elementos visibles al render base

### Requirement: Compact setup card MUST NOT render constant or hardcoded chrome

El componente SHALL omitir cualquier elemento cuyo valor sea constante en su contexto de uso o que duplique información ya presente en otro elemento del mismo card. Esto incluye:

- El transition icon/label del footer, dado que `TopActionableSetups` siempre pasa `transition="stable"`. Si en el futuro otro caller renderiza transitions dinámicas, el requisito se revisa.
- El contador `Nd in state`, dado que el `freshness` badge ya codifica la misma información en bandas operativas (fresh, aging, late-stage, stale, extended).
- La métrica "Base" en el grid, dado que `TopActionableSetups` la hardcodea como `'fast'`/`'8w'` según `setup_type`, duplicando textualmente el `state` label.

#### Scenario: Hardcoded transition is not rendered

- **WHEN** el caller pasa `transition="stable"` (caso único actual en `TopActionableSetups`)
- **THEN** el card NO renderiza el footer con transition icon ni transition label

#### Scenario: Days-in-state is not rendered when freshness is present

- **WHEN** el card recibe ambos `freshness` y `daysInState`
- **THEN** solo se renderiza el `freshness` badge; el valor numérico `daysInState` no aparece como elemento visible

#### Scenario: Hardcoded "Base" metric is not rendered

- **WHEN** el caller pasa `keyMetrics.base` con un valor hardcoded
- **THEN** el grid de métricas omite la cell "Base" y renderiza solo Dist / RS / Vol
