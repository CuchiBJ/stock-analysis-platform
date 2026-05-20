# Plan Post Migración - Universe Engine

## Estado Actual
- ✅ Arquitectura de fallback implementada
- ✅ Servidor backend corriendo en http://localhost:8000
- ✅ DataSourceStrategy abstraction creada
- ✅ WebSocketDataSource implementada
- ✅ SmartPollingDataSource implementada
- ✅ DataSourceManager con auto fallback implementado
- ✅ NormalizedEventBus implementado
- ✅ Integración con Universe Engine (tiers)
- ✅ Integración con Transition Engine
- ✅ Redis caching layer implementado
- ✅ Request deduplication implementado
- ✅ Stale-while-revalidate implementado
- ✅ RealtimePriceService actualizado
- ✅ main.py startup actualizado
- ✅ Documentación de arquitectura creada
- ✅ Errores de importación arreglados
- ❌ Universe Engine vacío (0 símbolos)
- ⏳ Migración pendiente

## Plan Post Migración

### 1. Ejecutar migración al Universe Engine
**Script:** `backend/scripts/migrate_to_universe_engine.py`

**Errores conocidos:**
- Columna `universe_tiers.created_at` no existe
- Columna `metadata` renombrada a `alert_metadata` en `universe.py`

**Arreglos aplicados:**
- `LifecycleState.ACTIVE` → `LifecycleState.ACTIVE.value`
- `LifecycleState.DELISTED` → `LifecycleState.DELISTED.value`
- Validación de `float_shares` para evitar overflow

**Comando:**
```bash
cd /home/fernando/repositorios/stock-analysis-platform/backend
source venv/bin/activate
python scripts/migrate_to_universe_engine.py
```

### 2. Verificar Universe Engine poblado
**Objetivo:** Confirmar que hay símbolos en el Universe Engine con tiers asignados

**Comando:**
```bash
cd /home/fernando/repositorios/stock-analysis-platform/backend
source venv/bin/activate
python -c "
from app.universe.universe_engine import get_universe_engine
from app.universe.tiers.tier_manager import UniverseTier

universe = get_universe_engine()
tier_manager = universe.tier_manager

print('Total símbolos:', len(universe.get_all_tickers()))
for tier in [UniverseTier.TIER_1, UniverseTier.TIER_2, UniverseTier.TIER_3, UniverseTier.TIER_4]:
    symbols = tier_manager.get_tickers_by_tier(tier)
    print(f'{tier.value}: {len(symbols)} símbolos')
"
```

### 3. Reiniciar servidor backend
**Objetivo:** El servidor está corriendo pero con 0 símbolos. Necesita reiniciarse para cargar símbolos del Universe Engine.

**Comando:**
```bash
# Detener servidor actual
pkill -f "uvicorn app.main:app"

# Reiniciar servidor
cd /home/fernando/repositorios/stock-analysis-platform/backend
source venv/bin/activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**O usar el script:**
```bash
cd /home/fernando/repositorios/stock-analysis-platform
./start.sh
```

### 4. Verificar servicio de precios con símbolos
**Objetivo:** Confirmar que el servicio de precios en tiempo real tiene símbolos suscritos y funciona en modo polling.

**Endpoint:** `GET http://localhost:8000/api/v1/realtime/status`

**Comando:**
```bash
curl http://localhost:8000/api/v1/realtime/status
```

**Esperado:**
```json
{
  "running": true,
  "mode": "polling",
  "active_source": "SmartPollingDataSource",
  "symbols_count": > 0,
  "messages_received": > 0,
  "messages_broadcast": > 0,
  "last_update": "timestamp",
  "mode_change_count": 1,
  "data_source_health": { ... },
  "connected_clients": 0
}
```

### 5. Verificar frontend conectado
**Objetivo:** Confirmar que el frontend puede conectarse al backend y mostrar datos correctamente.

**Frontend:** http://localhost:3000

**Verificar:**
- Frontend carga sin errores
- No hay errores de conexión en la consola del navegador
- Los paneles muestran datos
- El WebSocket está conectado

## Notas Importantes

### Redis (Opcional)
Redis no está disponible actualmente. El sistema funciona sin Redis pero sin caching. Para habilitar Redis:

```bash
# Iniciar Redis
sudo systemctl start redis

# Verificar Redis
redis-cli ping
```

### Polygon API Key
No hay API key válida de Polygon con permisos WebSocket. El sistema funciona en modo polling sin API key.

### Intervalos de Polling
- Tier 1: 15 segundos
- Tier 2: 1 minuto
- Tier 3: 5 minutos
- Tier 4: 5 minutos

## Archivos Modificados

### Backend
- `app/market_data/strategies/data_source_strategy.py` - DataSourceStrategy abstraction
- `app/market_data/strategies/data_source_manager.py` - DataSourceManager
- `app/market_data/events/normalized_event_bus.py` - NormalizedEventBus
- `app/services/realtime_price_service.py` - Actualizado para usar nueva arquitectura
- `app/main.py` - Actualizado para no requerir POLYGON_API_KEY
- `app/universe/universe_engine.py` - Actualizado para funcionar sin API key
- `app/models/universe.py` - Renombrado `metadata` a `alert_metadata`
- `scripts/migrate_to_universe_engine.py` - Arreglos para migración

### Documentación
- `backend/REALTIME_FALLBACK_ARCHITECTURE.md` - Documentación completa de arquitectura

## Resumen de Arquitectura

### Componentes
- **DataSourceStrategy** - Abstract interface para data sources
- **WebSocketDataSource** - Polygon WebSocket implementation
- **SmartPollingDataSource** - REST API polling con tier-based intervals
- **DataSourceManager** - Manager con auto fallback
- **NormalizedEventBus** - Event bus para eventos internos
- **RealtimePriceService** - Orquestador de precios en tiempo real

### Características
- ✅ Provider-agnostic (WebSocket o Polling)
- ✅ Automatic fallback on WebSocket failure
- ✅ Graceful degradation
- ✅ Tier-based polling intervals
- ✅ Redis caching (opcional)
- ✅ Request deduplication
- ✅ Stale-while-revalidate
- ✅ Mismo flujo de eventos internos
- ✅ Frontend no sabe el origen de datos

### Modos de Operación
- **WEBSOCKET** - Primary mode (low latency, real-time)
- **POLLING** - Fallback mode (tier-based intervals)
- **DEGRADED** - Extended polling on repeated failures
