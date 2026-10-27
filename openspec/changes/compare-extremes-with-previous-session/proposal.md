## Why
El usuario solicita reemplazar nuevos extremos de 52 semanas por extremos respecto de la sesión anterior.

## What Changes
- Comparar high/low de la sesión analizada con high/low de la sesión SPY anterior disponible.
- Actualizar conteos globales, sectores, evolución, Dashboard y metodología.
- Renombrar el campo API a new_session_highs_vs_lows para no atribuir semántica diaria a un campo anual.

## Capabilities
### New Capabilities
- `market-context-session-extremes`: Extremos respecto de la sesión anterior.

## Impact
Servicios breadth, overview y sector evolution, consumidores frontend y pruebas. Esta petición sustituye explícitamente las reglas de 252 sesiones en add-market-context-breadth-comparisons, clarify-market-context-sector-breadth y show-market-context-sector-evolution. No cambia referencias anuales de índices, ratio de proximidad ni política de mercado. Sin migraciones o dependencias nuevas.
