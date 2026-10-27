## Decisions
Usar una sola sesión SPY estrictamente anterior a as_of, no un día calendario ni la última fila disponible de cada símbolo. Requerir high/low finitos, positivos y coherentes en ambas sesiones. High actual > high previo cuenta máximo; low actual < low previo cuenta mínimo. Empates no cuentan; una acción puede contar en ambos lados. Ausencia o invalidez excluye al símbolo sin buscar otra fecha.

Compartir evaluador entre amplitud y evolución. La evolución consulta hasta seis sesiones SPY para reconstruir cinco comparaciones; conserva denominadores, universo por fecha y metadata actual. Actualizar el nombre del campo en productores y consumidores conjuntamente. Overview mantiene extremes como contenedor neutral. La etiqueta sesión anterior describe la referencia: fecha visible sigue siendo la sesión analizada. Backend y frontend deben actualizarse juntos; no ofrecer alias anual con datos diarios.

## Verification
SQLite sintético para calendario, gaps, empates, duales, OHLC inválido, universo y reconciliación; tests frontend y controles estáticos. No servicios ni datos de producción.
