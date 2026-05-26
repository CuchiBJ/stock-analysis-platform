## Context

`EmpiricalProbabilityCalculator.lookup()` ya implementa la lógica que necesitamos espejar en el endpoint: queries a `transition_observations` filtrando por `outcome_status IN ('SUCCESS', 'FAILURE')` y agrupando por cohort. La diferencia clave: el calculator hace lookup por (transition_type, rs_bucket) y elige el primer cohort con N≥5; el endpoint de calibration debe mostrar **todas** las filas por transition_type, incluyendo las que no cruzan el umbral.

Estado actual de la DB (medido 2026-05-26):
- `total_observations = 1`
- `status_breakdown: PENDING=1`
- `success_rate_by_type: {}` (ninguno resuelto)

Por eso el empty-state es crítico: si construimos el panel y muestra una tabla vacía sin contexto, el operador concluye "el sistema no sirve". Si muestra "System has just started — first calibration in ~N weeks" + el conteo actual, mantiene confianza honesta.

## Goals / Non-Goals

**Goals:**
- Operador puede entrar a `/calibration` y entender en <30 segundos: cuántas observations existen, qué transition types tienen track record empírico, y qué success rate observan.
- Honestidad explícita: cero números fabricados. Si no hay data, lo decimos.
- Read-only desde `transition_observations`; cero side effects.
- Defender Principio 7 (interpretability) y Principio 8 (honest about uncertainty).

**Non-Goals:**
- No predicted vs actual (requiere `predicted_at_detection` que hoy no se guarda).
- No reliability diagram (requiere N≥30 por bucket).
- No alerting / no detección automática de mis-calibration.
- No persistencia adicional ni cambios al lifecycle de outcomes.

## Decisions

### D1: Granularidad — por transition_type solamente

**Decisión**: una fila por cada `OperationalTransition` value (no-STABLE). Sin desagregar por rs_bucket en Phase 1.

**Por qué**: con N=1 obs hoy, agregar buckets significa 50+ celdas todas vacías. Por transition_type tenemos ~10 filas — manejable visualmente, y cuando llegue data, cada fila cruza el threshold con 5 obs en lugar de 25.

**Alternativa rechazada**: bucketear por (transition_type, rs_bucket) para alinear con el cohort key del calculator. Visualmente saturado; defer a Phase 2.

### D2: `success_rate` se computa con la misma lógica que el calculator

**Decisión**: `SUCCESS / (SUCCESS + FAILURE)`, excluyendo NEUTRAL/PENDING/INSUFFICIENT_DATA del denominador. Idéntico a `EmpiricalProbabilityCalculator._query_cohort`.

**Por qué**: coherencia. El número que muestra `/calibration` para `entering_pullback` debe ser el mismo que el card del setup muestra cuando hace lookup para ese cohort. Esto es "calibración in-sample" (predigo desde el mismo set que mido) — limitación reconocida en non-goals.

### D3: Threshold `min_samples_required = 5` expuesto en el response

**Decisión**: el endpoint retorna `min_samples_required: 5` en cada fila. El frontend lo usa para mostrar "Need X more observations" cuando n_resolved < 5.

**Por qué**: evita hardcodear el threshold en el frontend. Si en el futuro se cambia a 10 (más estricto), basta cambiar la constante en backend.

### D4: Status enum — `empirical | insufficient | no_data`

**Decisión**: tres estados explícitos por fila:
- `empirical`: n_resolved ≥ 5 → success_rate confiable
- `insufficient`: 0 < n_resolved < 5 → tenemos datos pero no suficientes
- `no_data`: n_resolved = 0 → ninguna resuelta (puede haber PENDING)

**Por qué**: el operador necesita distinguir "no hemos observado nunca" de "hemos observado poco". El frontend renderiza badges diferenciados (gris vs amber vs verde).

### D5: Listar TODOS los transition types del enum, no solo los que tienen obs

**Decisión**: el endpoint devuelve una fila por cada `OperationalTransition.value` excepto STABLE, aunque n_resolved=0. Las filas sin data salen con `status='no_data'` y `success_rate=null`.

**Por qué**: el operador ve qué transitions existen como concepto, no solo las que casualmente se detectaron. Si `flush_and_recover` nunca se detectó, eso es información — quizás el threshold es muy estricto.

**Alternativa rechazada**: ocultar filas sin data. Crea la ilusión de que el universo de transitions es solo lo observado.

### D6: Orden de filas

**Decisión**: ordenar por (1) status descendente (empirical > insufficient > no_data) y (2) dentro de cada status, n_resolved desc.

**Por qué**: el operador escanea de arriba abajo y encuentra primero las filas con info útil. Las "no_data" quedan abajo como referencia.

### D7: Empty-state global

**Decisión**: cuando `total_resolved = 0` (todo es PENDING o no_data), el frontend muestra un card de cabecera explícito:

> "Sistema observando — 1 observation registrada, ninguna resuelta aún. Los outcomes se evalúan 10 días post-detección. Primera data de calibración esperada para ~2026-06-05."

Cuando hay al menos 1 resolved, el card se reemplaza por stats compactas: "X total observations · Y resolved · Z transition types with empirical data".

**Por qué**: empty-state silencioso es peor que la ausencia de panel. El mensaje explícito enseña qué espera el sistema y cuándo.

### D8: Computar la fecha "Primera data esperada" como heurística

**Decisión**: si `total_pending > 0`, mostrar `min(date_detected) + 10d` como ETA aproximado. Si total = 0, no mostrar ETA (no hay nada en flight).

**Por qué**: información honesta sobre cuándo esperar el primer dato. Heurística simple, no requiere lógica de scheduler.

### D9: Endpoint cache

**Decisión**: sin cache. La query es liviana (GROUP BY sobre tabla pequeña).

**Por qué**: con el volumen actual (1 obs) y proyectado (cientos en meses), no vale la complejidad. Si en el futuro la tabla crece >10k obs, agregar cache de 60s.

### D10: Página `/calibration` vs sección en `/guide`

**Decisión**: nueva página dedicada `/calibration`.

**Por qué**: paralelo a `/queue` y `/guide` — operacional, no documental. El `/guide` debería tener una mención + link, no embeber la tabla.

## Risks / Trade-offs

1. **In-sample calibration es trivialmente perfecta** — si computo success_rate desde el mismo set que el calculator usa para predecir, los números coinciden por construcción. Mitigación: el panel se enmarca como "qué success rate hemos observado", no "qué tan calibrado está el sistema". Calibración real (out-of-sample) requiere `predicted_at_detection` — defer.

2. **Empty panel mata confianza** — operador entra y ve "no data" en casi todo. Mitigación: empty-state explícito con ETA + contexto de cuántas obs estamos esperando. Honestidad > apariencia.

3. **El data starvation es el problema real** — este panel hace visible que el sistema casi no observa. Eso es bueno (forza priorizar accumulation) pero puede generar frustración. Mitigación: copy del empty-state debe ser claro sobre por qué (on-demand vs batch) y qué viene después.

4. **Sample size 5 puede ser muy bajo** — con N=5, success_rate tiene rango ±30 pp por azar puro. El badge "empirical" puede dar falsa confianza. Mitigación: documentar en `/guide` que N≥5 es threshold mínimo, no garantía de precisión. Considerar threshold más alto (N≥10) post-Phase 1 si los números resultan ruidosos.

5. **No hay versionado del modelo** — si el calculator cambia su threshold o cohort key, las obs viejas siguen contando. Sin un campo `model_version` no podemos detectar drift por cambios de definición. Mitigación: out of scope Phase 1; agregar `model_version_at_detection` si en el futuro se hace recalibración formal.
