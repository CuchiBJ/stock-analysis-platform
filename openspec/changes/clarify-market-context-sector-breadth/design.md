## Context

Breadth usa universo QUALITY_FILTERS y elegibilidad estricta de OHLC actual más252 sesiones SPY previas válidas. Sectores actuales solo incluyen eventos; metadata se consulta para sus símbolos. Para tasas se requiere el conjunto elegible completo, no los eventos ni todo el universo.

## Goals / Non-Goals

**Goals:** Separar concentración de eventos de incidencia por sector; preservar cobertura, detalle y reglas actuales.
**Non-Goals:** Política, recomendaciones, datos nuevos de proveedor, normalización con universo actual para fechas históricas, cambios al Dashboard o despliegue.

## Decisions

1. En rama include_constituents, recoger símbolos elegibles durante el mismo loop anual, consultar Stock metadata para universe_symbols en una sola consulta. Inicializar sectores para todos esos símbolos; eligible_symbols cuenta elegibles únicos, excluded_symbols el resto. Metadata ausente/vacía => Sin sector. Conservar highs/lows y orden alfabético de símbolos y sectores backend. Un símbolo dual suma una vez al denominador pero una vez en cada lado. No modificar respuesta ni consultas metadata cuando include_constituents=False.
2. Cada sector ahora expone {sector,highs,lows,eligible_symbols,excluded_symbols}. Sumas de denominadores y eventos deben reconciliar con globales. Sectores con cobertura pero cero eventos permanecen; sectores totalmente excluidos también. No ratios redundantes backend: frontend deriva tasas. Propagación por overview existente conserva campos.
3. Tipo sector frontend extiende campos opcionales (compatibilidad API anterior). Extraer bloque Extremes y StockList de MarketContextPage a SectorBreadth.tsx; helper puro market-context-sectors.ts. Mantener enlaces /stock/{encoded symbol}, nombres y disclosure nativo keyboard. No cambiar otras secciones.
4. Cabecera: N máximos de E elegibles (N/E%) y M mínimos de E elegibles (M/E%), fecha y excluidas. E=0 => Sin cobertura suficiente, no 0%; E>0 y N=M=0 => Sin eventos en esta sesión. El ratio up_ratio pasa a disclosure de metodología como porcentaje entre eventos, nunca porcentaje de universo. Nota símbolo dual y metadata sectorial actual visible en metodología.
5. Concentración factual separada para máximos y mínimos: tomar hasta2 sectores con eventos del lado, ordenar conteo desc y nombre para desempate, mostrar nombres y sumatoria/total con %. Si total0 no hay concentración; si suma de sectores difiere del total global no calcular y decir detalle incompleto. No etiquetar concentración como fuerza sectorial. Sin sector participa como grupo explícito.
6. Filas sectoriales compactas: nombre, elegibles/excluidas, conteos altos/bajos y % de elegibles propios. Barras enfrentadas: mínimos izquierda rojo, máximos derecha verde; cada mitad escala fija0..100%, no escala relativa al sector más grande ni al total de eventos. Mostrar escala textual y valores, no depender de color. Tasas ausentes => Sin cobertura suficiente si E=0, Cobertura no disponible si campo falta/invalid; sin barra para ese lado. Validar conteos enteros finitos0<=N<=E; ratios inconsistentes no se claman/clamp como válidos. Nunca dividir por highs.length+lows.length para tasas.
7. Selector nativo Ordenar sectores: Eventos (default suma highs+lows desc), % máximos, % mínimos. Desconocidos al final en modos tasa; empates por nombre. Ordenar copia, no mutar props. Summary por sector sigue visible; lista de acciones cerrada por defecto. Grupo general sin desplegable extra, permite escaneo de sectores en una pasada.
8. Helpers y render estático con datos sintéticos prueban universos desiguales (6/100 vs3/10), concentraciones12/15=80%, dual, ausencia de cobertura, cero eventos, contrato legacy. Backend pruebas SQLite incluyen sector sin eventos, otro excluido e integridad de sumas y default original. Browser QA local de sort y disclosure. Sin dependencias nuevas; clases Tailwind en componente.

## Risks / Trade-offs

- Listar todos los sectores agrega filas → son pocos grupos, detalle cerrado y orden por eventos.
- Metadata sectorial no versionada → texto explícito; no prometer composición histórica.
- Campo faltante en deploy mixto → counts disponibles pero tasas y barras ausentes.
- Mismo símbolo dual → incidencia de máximos y mínimos no es partición exclusiva; evitar barras100% apiladas y totales de acciones únicas inferidos.

## Migration Plan

Sin migraciones. Backend opt-in aditivo y frontend tolerante a respuesta anterior. Validar localmente; no desplegar en este incremento.

## Open Questions

Ninguna.
