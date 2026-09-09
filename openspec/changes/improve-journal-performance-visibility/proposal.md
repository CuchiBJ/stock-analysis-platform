## Why

El Journal muestra resultados a nivel decisión, pero Ganados/Pérdidas/Break even no conducen a las operaciones que explican cada contador. El gráfico de evolución identifica puntos por número de secuencia y no por el trade real, y el P&L neto oculta cuánto aportaron los ganadores y cuánto drenaron los perdedores.

Esto defiende **#6 Operational clarity > feature richness** y **#7 Interpretability**: cada cifra debe conducir a las operaciones reales que la produjeron.

## What Changes

- Los contadores pasan a ser filtros inmediatos, con `Todos` como limpieza explícita.
- La API expone una clasificación canónica por decisión para evitar drift entre lista y contadores.
- Cada punto de evolución expone activo, dirección, fechas disponibles, P&L, resultado e ids, y abre el detalle existente.
- Se agregan ganancia/pérdida promedio y acumulada sobre decisiones totalmente resueltas.

## Non-goals

- No se cambia la banda break even vigente (±0,1R; fallback ±0,1% del nominal).
- No se agrega soporte short ni precisión horaria: las fuentes actuales son long-only y guardan `Date`.
- No se modifica la base de datos ni se reemplaza el gráfico de win rate existente.

## Impact

- Backend: `backend/app/api/v1/endpoints/journal.py` y tests de clasificación.
- Frontend: Journal, tipo `Trade` y `WinRateEvolutionChart`.
- API: campos aditivos en `decision_overall`, trades y puntos de evolución.
