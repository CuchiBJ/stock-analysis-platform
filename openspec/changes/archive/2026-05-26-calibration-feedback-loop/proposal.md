## Why

El sistema muestra "continuation probability" en cada setup card pero no expone si esa probabilidad se cumple en la práctica. `EmpiricalProbabilityCalculator` ya retorna `source='empirical' | 'rule_based'` y `sample_size`, pero el operador no tiene forma de validar si el número es predictivo o teatro.

Sin un loop de calibración visible, todas las decisiones cuelgan de fe: multiplicadores (0.85/1.00/1.15), score_multiplier de contexto, threshold de cohort (N≥5), etc. Mostrar la calibración cierra **Principio 7 (interpretability)** y **Principio 8 (honest about uncertainty)**: el sistema admite cuándo no sabe.

Hallazgo crítico paralelo: hoy hay **1 observación total** en `transition_observations` (3 días sin acumular). El loop de recording es on-demand desde `/actionable`, no batch. Este change asume esa limitación — el panel arranca casi vacío y se llena con honestidad ("insufficient data, N<5") en lugar de mostrar números falsos. La infrastructura de batch detection es scope aparte (próximo change post-calibration).

## What Changes

- **Backend**: nuevo endpoint `GET /api/v1/calibration/by-transition-type` que retorna un array de filas, una por cada `transition_type` no-STABLE definido en el enum. Cada fila incluye:
  - `transition_type: str`
  - `n_resolved: int` (count de SUCCESS + FAILURE)
  - `n_pending: int` (PENDING + INSUFFICIENT_DATA)
  - `success_rate: float | null` (null si n_resolved < 5)
  - `success_count: int`
  - `failure_count: int`
  - `status: 'empirical' | 'insufficient' | 'no_data'`
  - `min_samples_required: int` (constante = 5, expuesta para que el frontend diga "faltan X obs")
- **Frontend**: nueva página `/calibration` con tabla simple:
  - Una fila por transition type ordenadas por status (empirical → insufficient → no_data) y luego por n_resolved desc
  - Empty-state honesto cuando el global N=0 ("System has just started observing — first calibration data expected in N weeks")
  - Badge `empirical` (verde) / `insufficient` (amber) / `no_data` (gris) por fila
  - Footer con `total_observations`, `total_resolved`, `total_pending`
- **Navegación**: link a `/calibration` desde `DashboardLayout` (siguiendo el patrón de `/queue` y `/guide`)
- **Sin cambios** a `EmpiricalProbabilityCalculator`, `OutcomeTracker`, ni `transition_engine`. La data se lee de `transition_observations` directamente con la misma lógica de clasificación que el calculator usa.

Resultado: el operador puede entrar a `/calibration` y ver, para cada transition_type, cuántas observations se han recolectado, cuántas resolvieron en SUCCESS/FAILURE, y qué tasa empírica real entregaron. Si todas dicen "insufficient" o "no_data", es información valiosa — el sistema admite que aún no tiene track record.

## Capabilities

### New Capabilities
- `calibration-reporting` — endpoint + UI para mostrar success rate empírica observada por transition_type

### Modified Capabilities
- (none) — La nueva capability lee `transition_observations` sin tocar el resto del stack.

## Impact

- **NEW**: `backend/app/api/v1/endpoints/calibration.py`
- **NEW**: `backend/tests/test_calibration_endpoint.py`
- **MODIFIED**: `backend/app/api/v1/api.py` — registrar el router
- **NEW**: `frontend/app/calibration/page.tsx`
- **MODIFIED**: `frontend/components/layout/DashboardLayout.tsx` — agregar nav link "Calibration"
- **Sin cambios**: `EmpiricalProbabilityCalculator`, `OutcomeTracker`, `transition_engine`, scheduler.

## Non-goals

- **No fix de data starvation**: el problema de que solo hay 1 observación es scope aparte. Este change asume el estado actual y muestra honestidad sobre la limitación. Si Fernando decide después agregar batch detection, este panel se llena solo sin cambios.
- **No reliability diagram** (predicted bucket vs actual): es la siguiente capa de calibración, requiere ≥30 obs por bucket. Defer hasta que haya volumen.
- **No calibración por (transition_type, rs_bucket)**: el cohort key del empirical calculator. Visualmente saturado y la mayoría de celdas serían "insufficient" durante meses. Phase 2.
- **No alerting si el sistema está mal calibrado**: solo mostramos números crudos. La interpretación queda al operador.
- **No persistencia del "predicted_probability_at_detection"**: hoy el sistema no guarda la predicción que hizo cuando detectó la transición; eso permitiría calibración out-of-sample real. Defer — la versión in-sample (cohort-based) es suficiente Phase 1.
- **No tocar el shape de `transition_observations`**: no se agregan columnas.
- **No telemetría de uso del panel**.
