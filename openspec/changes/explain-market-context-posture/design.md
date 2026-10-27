## Context

ContextEvidence contiene una tarjeta de postura cuya evidencia queda oculta. market_posture.py decide FUERA cuando health=DAMAGED y base=DEFENSIVO; eso no prueba daño nuevo hoy. La respuesta expone policy, health y follow_through suficientes para una explicación local. Se conserva todo el Dashboard y la respuesta API original.

## Goals / Non-Goals

**Goals:** Explicar nivel, dirección y persistencia sin recalcular la postura. Mostrar condiciones con estado textual cumplida/pendiente/sin datos y evidencia numérica.

**Non-Goals:** Cambios backend, reglas, umbrales, recomendaciones nuevas, probabilidad de recuperación, nueva ingesta, despliegue.

## Decisions

1. Crear helper puro frontend/lib/market-context-explanation.ts y componente PostureExplanation.tsx. ContextEvidence delega solamente su rama posture. No ampliar el componente existente ni tocar el resto de secciones.
2. El estado autoritativo es ctx.posture.state. Borde rojo FUERA, ámbar DEFENSIVO/SELECTIVO, neutro NORMAL/AGRESIVO/desconocido; no usar verde para estados estáticos. Mantener instruction salvo FUERA: presentar «Sin compras nuevas — postura restrictiva del sistema». No afirmar deterioro activo hoy por inferirlo del estado.
3. Síntesis visible breve, máximo tres frases. Caso DAMAGED + base DEFENSIVO: «Los niveles siguen defensivos y la memoria de daño mantiene la postura en FUERA», únicamente si state también FUERA. Si ambos descriptores EXPANDING, mencionar mejora reciente que no equivale a reparación. Otros casos: base reportada, techo de salud reportado, estado final, sin inventar causalidad; si faltan policy/health, declarar evidencia incompleta.
4. Tres filas compactas siempre visibles: Nivel (amplitud y densidad, usando policy.inputs cuando hay policy, sin sustituir null por otra métrica), Dirección (descriptores traducidos y delta participación en pp / liderazgo en % relativos), Memoria (estado de salud y damaged_days/window_days). Follow-through NOT_PAYING: «Continuidad insuficiente: limita la postura como máximo a SELECTIVO», con delivery/base si finitos; nunca decir que por sí solo causa FUERA. Other follow-through may be shown factually without inferred ceiling.
5. Severidad de hoy solo desde health.series.find(date===as_of).severity: clean «Rueda actual sin daño clasificado», mild «Retroceso leve en la rueda actual», severe «Daño severo en la rueda actual», falta «Daño de la rueda actual: sin datos». No usar último elemento si fecha no coincide.
6. Con salud DAMAGED/FRAGILE mostrar dos grupos visibles. Reparación de salud: (a) ventana completa 7 ruedas, usando repair_window_days (el backend expone longitud observada, no longitud requerida), (b) repair_clean_days >= repair_required_clean_days, (c) recent_severe_days===0 con severe_lookback_days al menos 3. Mostrar valores reales, sin defaults inventados para ausentes. Constantes de ventana 7/3 corresponden a market_health.py actual; documentarlas y cubrirlas por tests. No prometer NORMAL: «La reparación de salud no garantiza una mejora de postura; siguen vigentes los niveles y la continuidad».
7. Solo DAMAGED: grupo «Acceso anticipado a SELECTIVO» con puertas necesarias: base_state conocida y distinta de DEFENSIVO/FUERA; cero severos recientes; y una alternativa: streak >= required O exceptional_recovery_session===true O policy.exceptional_retained===true. Presentar cada puerta y la disyunción claramente. Streak usa campos health, sin defaults. Desconocido nunca cumplido; una rama OR comprobada true puede cumplir aun si otra falta. No afirmar aprobación final del acceso ni recalcular state. Explicar que excepción/confirmaciones no anulan protecciones ni conceden NORMAL/AGRESIVO. Para FRAGILE no mostrar anticipación; para otras saludes no mostrar checklists no aplicables.
8. Niveles defensivos muestran pisos recibidos en policy.thresholds cuando existen; defensive_active informa también bandas de salida recibidas. No codificar pisos de amplitud/densidad. Falta de umbral => Sin datos, no un cero.
9. Conservar motivos/instruction/unlock/policy originales en disclosure «Respuesta original del sistema», explícitamente auditoría del servicio; no reproducir el unlock heredado como explicación principal. No modificar strings mediante reemplazos frágiles. Fallback sin policy muestra estado/instrucción y limitación; no genera causas definitivas.
10. Pruebas de helper y render estático (patrón existente frontend/lib/market-context-breadth.test.mjs) prueban contenido visible fuera de details, gates, ausencia de datos y no mutación. No dependencias. QA visual local con fixture si disponible; jamás usar producción para tests.

## Risks / Trade-offs

- Texto original de servicio inexacto sigue en auditoría y Dashboard → explicitar discrepancia y aislar nueva síntesis en página; su corrección compartida sería otro cambio.
- Duplicación de presentación de condiciones → usar datos/flags del contrato, sin producir nuevo veredicto ni score. Ventanas fijas quedan explícitas, cubiertas por pruebas.
- Payload parcial → Sin datos, no confirmación positiva ni valores por defecto.

## Migration Plan

Sin migraciones ni cambio API. Implementar y verificar localmente. Mantener mejora anterior intacta. No despliegue en esta iteración.

## Open Questions

Ninguna para esta iteración.
