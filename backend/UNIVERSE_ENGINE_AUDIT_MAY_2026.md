# AUDITORÍA PROFUNDA DEL UNIVERSE ENGINE - Mayo 2026

## EXECUTIVE SUMMARY

**Estado General:** 15% Alineación con Adaptive Market Discovery Philosophy

**Diagnóstico:** El sistema tiene arquitectura institucional bien diseñada (AutoDiscoveryEngine, DiscoveryScanner, TierManager, HealthMonitor, LifecycleTracker) pero **NO ESTÁ INTEGRADA** en el flujo operativo. El sistema funciona como un **SCREENER CON LISTAS ESTÁTICAS**.

**Problema Crítico:** El scheduler actualiza métricas cada 30 minutos para símbolos existentes, pero **NO ejecuta discovery scans, NO detecta nuevos líderes, NO reevalúa tiers, NO monitorea salud del universo**.

**Riesgo:** 85% - El sistema perderá líderes emergentes, cambios sectoriales, IPOs relevantes y oportunidades de momentum porque depende de listas estáticas (Wikipedia S&P 500, Polygon listings) que se actualizan manualmente.

---

# DISCOVERY PIPELINE ANALYSIS

**Estado:** INFRAESTRUCTURA EXISTENTE PERO DESINTEGRADA

**Componentes Existentes:**
- AutoDiscoveryEngine: Detecta volume explosion (3x avg), RS acceleration (RS > 2.0 por 5 días), abnormal RS (RS > 3.0), breakout (10% price change), sector leadership (top 3 sector)
- DiscoveryScanner: Ejecuta nightly scans para RS leaders, emerging structure, volume anomalies, tightness, sector leadership
- UniverseEngine: Orquesta refresh_universe() y run_nightly_scans()

**INTEGRACIÓN ACTUAL:**
- Scheduler (scheduler.py) **NO LLAMA** discovery functions
- Scheduler solo ejecuta: trigger_metrics_update() y _update_prices()
- run_nightly_scans() existe pero **NO es llamado por scheduler**
- refresh_universe() existe pero solo vía API endpoint manual

**FLUJO DE ONBOARDING ACTUAL:**
1. Manual: POST /api/v1/data/ingest-stock-list → ingresa desde Polygon
2. Manual: POST /api/v1/data/ingest-tickers-external → ingresa desde Wikipedia (S&P 500, NASDAQ-100)
3. NO hay auto-onboarding de discovery candidates
4. NO hay integración entre discovery e ingestion

**CONCLUSIÓN:** Discovery pipeline existe en código pero está completamente desconectado del sistema operativo.

---

# UNIVERSE HEALTH

**Estado:** MONITORING EXISTENTE PERO INACTIVO

**Componentes Existentes:**
- HealthMonitor: Detecta missing sectors, stale tickers (>7 días), dead listings (no price data), symbol inconsistencies, coverage gaps (<10 tickers por sector), universe freshness (score 0-100)
- UniverseHealthReport: Genera reportes con alerts, freshness score, tier distribution

**INTEGRACIÓN ACTUAL:**
- HealthMonitor **NO es llamado por scheduler**
- generate_health_report() existe pero **NO se ejecuta automáticamente**
- Alerts no se emiten automáticamente
- No hay dashboard de salud activo

**DATOS ACTUALES:**
- 3922 símbolos en Stock table
- 7422 registros en instrument_identities
- 229 T1, 758 T2, 1142 T3, 1371 T4
- NO se conoce freshness score actual
- NO se conoce cantidad de stale tickers
- NO se conocen coverage gaps

**CONCLUSIÓN:** Health monitoring existe pero está completamente inactivo.

---

# STALENESS ANALYSIS

**Estado:** DETECCIÓN DE STALENESS EXISTE PERO INACTIVA

**Componentes Existentes:**
- check_stale_tickers(): Detecta símbolos no actualizados en >7 días
- check_dead_listings(): Detecta símbolos sin datos de precio
- check_coverage_gaps(): Detecta sectores con <10 tickers
- calculate_universe_freshness(): Calcula score 0-100 basado en antigüedad de datos

**INTEGRACIÓN ACTUAL:**
- Scheduler **NO ejecuta** staleness checks
- NO hay auto-removal de stale symbols
- NO hay auto-refresh de coverage gaps
- NO hay auto-detection de delistings

**PROBLEMAS IDENTIFICADOS:**
- Símbolos delistados pueden permanecer en DB indefinidamente
- Símbolos stale pueden seguir siendo procesados
- Sectores con coverage gaps no se llenan automáticamente
- Universe freshness no se monitorea

**CONCLUSIÓN:** Staleness detection existe pero está completamente inactiva.

---

# MARKET COVERAGE GAPS

**Estado:** DEPENDENCIA DE LISTAS ESTÁTICAS

**Fuentes Actuales:**
- Wikipedia: S&P 500 (listado estático de ~500 símbolos)
- NASDAQ-100 (listado estático de ~100 símbolos)
- Polygon: All stock listings (listado estático de miles de símbolos)

**PROBLEMAS:**
- NO hay detección de IPOs relevantes
- NO hay detección de nuevos high RS names
- NO hay detección de cambios sectoriales
- NO hay detección de low-float momentum emergente
- NO hay detección de continuation names
- NO hay detección de sector rotation

**GAPS DE COBERTURA:**
- IPOs: Solo se agregan manualmente
- Small caps: No se detectan automáticamente
- Emerging momentum: No se detecta
- Sector rotation: No se monitorea
- New leaders: No se detectan

**CONCLUSIÓN:** Market coverage depende completamente de listas estáticas, no de discovery adaptativo.

---

# WHY IMPORTANT TICKERS ARE MISSING

**CAUSA RAÍZ:** Discovery system existe pero está desintegrado del flujo operativo.

**CASO TTMI:**
- TTMI está en DB (migrado desde legacy Stock table)
- TTMI tiene métricas calculadas
- TTMI cumple con criterios de LiveTransitions
- PERO: TTMI tiene solo 1 registro que cumple con TODOS los criterios en últimos 7 días
- PERO: LiveTransitions necesita 2+ registros para calcular transición operacional

**CASO GENERAL:**
- Tickers relevantes que NO están en DB: Nunca se detectan
- Tickers con momentum emergente: No se descubren automáticamente
- Tickers con RS acelerado: No se descubren automáticamente
- Tickers con volume explosion: No se descubren automáticamente

**CONCLUSIÓN:** Tickers importantes faltan porque el sistema depende de listas estáticas y no ejecuta discovery automático.

---

# AUTO-DISCOVERY FAILURES

**FALLO 1: Scheduler Integration**
- Scheduler NO llama discovery functions
- Discovery scans no se ejecutan automáticamente
- NO hay nightly scans automatizados

**FALLO 2: Candidate Processing**
- AutoDiscoveryEngine genera DiscoveryCandidates
- PERO: process_discovery_candidate() existe pero NO se llama
- PERO: Candidates no se onboarding automáticamente
- PERO: Candidates no se enriquecen automáticamente

**FALLO 3: Tier Re-evaluation**
- TierManager tiene reevaluate_tier()
- PERO: NO se llama por scheduler
- PERO: Tiers no se actualizan dinámicamente
- PERO: Líderes emergentes no se promocionan a T1/T2

**FALLO 4: Lifecycle Tracking**
- LifecycleTracker tiene track_emerging_leader()
- PERO: NO se llama automáticamente
- PERO: Emergent leaders no se detectan
- PERO: Lifecycle states no se actualizan

**CONCLUSIÓN:** Auto-discovery failures son 100% debido a falta de integración, no a falta de código.

---

# TIER SYSTEM EVALUATION

**Estado:** SISTEMA DE TIERS ESTÁTICO, NO DINÁMICO

**Criterios Actuales:**
- TIER 1: Market cap > $10B, volume > 5M/day, RS > 1.5
- TIER 2: Market cap > $2B, volume > 1M/day, RS > 1.2
- TIER 3: Market cap > $500M, volume > 500K/day
- TIER 4: Market cap < $500M o volume < 500K/day

**PROBLEMAS:**
- Tiers se asignaron durante migración inicial
- NO hay repriorización dinámica
- NO hay promoción automática de líderes emergentes
- NO hay democión automática de líderes deteriorados
- NO hay re-evaluación periódica

**DISTRIBUCIÓN ACTUAL:**
- 229 T1 (5.8%)
- 758 T2 (19.3%)
- 1142 T3 (29.1%)
- 1371 T4 (34.9%)
- NO se sabe si esta distribución refleja market relevance actual

**CONCLUSIÓN:** Tier system es estático, no refleja market relevance dinámica.

---

# METRICS UPDATE ANALYSIS

**Estado:** ACTUALIZACIÓN DE MÉTRICAS ES LENTA Y NO DIFERENCIADA

**Actual:**
- MetricsCalculator corre cada 30 minutos durante horario de mercado
- Calcula todas las métricas para todos los símbolos
- NO hay separación entre SLOW METRICS y FAST OPERATIONAL METRICS

**PROBLEMAS:**
- 30 minutos es demasiado lento para:
  - Reclaim detection (necesita intraday)
  - Deterioration tracking (necesita intraday)
  - Transition tracking (necesita intraday)
  - Leadership shifts (necesita intraday)
- NO hay métricas operacionales en tiempo real
- NO hay métricas de alta frecuencia para TIER 1

**SEPARACIÓN CONCEPTUAL FALTANTE:**
- SLOW METRICS (diario): EMA50, EMA200, RSI, RS baseline, ADR
- FAST OPERATIONAL METRICS (intraday): Distance to EMA21, Volume patterns, Reclaim status, Deterioration score

**CONCLUSIÓN:** Metrics update no está diferenciado por tipo de métrica ni por tier priority.

---

# WHAT FEELS STATIC

**1. Discovery Pipeline**
- Depende de listas estáticas (Wikipedia, Polygon)
- NO hay auto-discovery automatizado
- NO hay detección de anomalías en tiempo real
- NO hay detección de líderes emergentes

**2. Universe Management**
- Universe se actualiza manualmente via API
- NO hay auto-removal de stale symbols
- NO hay auto-detection de delistings
- NO hay auto-fill de coverage gaps

**3. Tier System**
- Tiers estáticos, no dinámicos
- NO hay repriorización automática
- NO hay promoción/democión basada en market changes

**4. Lifecycle Tracking**
- Lifecycle states no se actualizan automáticamente
- NO hay detección de IPOs
- NO hay detección de symbol changes
- NO hay detección de sector migrations

**5. Market Coverage**
- Depende de listas estáticas
- NO hay detección de sector rotation
- NO hay detección de emerging momentum
- NO hay detección de continuation names

---

# WHAT FEELS ADAPTIVE

**1. Metrics Update**
- Scheduler actualiza métricas automáticamente cada 30 minutos
- NO requiere intervención manual
- Funciona durante horario de mercado

**2. Price Update**
- Scheduler actualiza precios automáticamente cada 15 minutos
- NO requiere intervención manual
- Funciona durante horario de mercado

**3. DatabasePollingDataSource (frontend)**
- Polling diferenciado por tier (TIER 1: 15s, TIER 2: 60s, TIER 3: 5m, TIER 4: daily)
- Respeta prioridad institucional
- Es adaptive en el frontend

**CONCLUSIÓN:** Lo único adaptive es la actualización de datos existentes, NO el discovery de nuevos datos.

---

# WHAT FEELS RETAIL

**1. Dependencia de Listas Estáticas**
- Wikipedia S&P 500 (retail thinking)
- NASDAQ-100 (retail thinking)
- Polygon all listings (retail thinking)

**2. No Institutional Discovery**
- NO hay detección de block trades
- NO hay detección de institutional activity
- NO hay detección de leadership emergence

**3. No Market Evolution Awareness**
- NO hay detección de sector rotation
- NO hay detección de emerging sectors
- NO hay detección de declining sectors

**4. Manual Onboarding**
- Ingestion manual via API
- NO hay auto-onboarding
- NO hay auto-validation

---

# WHAT FEELS INSTITUTIONAL

**1. Arquitectura del Universe Engine**
- Diseño institucional correcto
- Componentes bien separados
- Layers bien definidos (Source, Normalization, Validation, Enrichment, Lifecycle, Tiers)

**2. Tier System Design**
- Criterios institucionales correctos (market cap, volume, RS)
- Prioritization por tier
- Processing diferenciado por tier

**3. Discovery Triggers**
- Triggers institucionales correctos (volume explosion, RS acceleration, sector leadership)
- Thresholds institucionales correctos
- Confidence scoring

**4. Health Monitoring**
- Health checks institucionales correctos (stale tickers, dead listings, coverage gaps)
- Freshness scoring
- Alert system

**CONCLUSIÓN:** La arquitectura es institucional, pero la implementación es estática.

---

# PRIORITY FIXES

## PRIORITY 1 (CRÍTICAS - Discovery Integration)

1. **Integrar Discovery Scans en Scheduler**
   - Agregar run_nightly_scans() al scheduler loop
   - Ejecutar discovery scans después de market close
   - Procesar discovery candidates automáticamente

2. **Implementar Auto-Onboarding**
   - Integrar process_discovery_candidate() en scheduler
   - Onboard automáticamente discovery candidates con confidence > 80
   - Enrich automáticamente nuevos símbolos

3. **Implementar Tier Re-evaluation**
   - Agregar reevaluate_tier() al scheduler loop
   - Ejecutar re-evaluation diaria para TIER 2-4
   - Ejecutar re-evaluation semanal para TIER 1

4. **Implementar Health Monitoring**
   - Agregar generate_health_report() al scheduler loop
   - Ejecutar health checks diarios
   - Emitir alerts automáticamente

## PRIORITY 2 (HIGH - Market Coverage)

5. **Implementar IPO Detection**
   - Integrar IPO detection en discovery scans
   - Onboard automáticamente IPOs relevantes
   - Track IPO lifecycle

6. **Implementar Sector Rotation Detection**
   - Detectar cambios en sector leadership
   - Detectar sectores emergentes
   - Detectar sectores en declive

7. **Implementar Coverage Gap Auto-Fill**
   - Detectar sectores con <10 tickers
   - Llenar gaps automáticamente desde Polygon
   - Priorizar sectores con high RS

## PRIORITY 3 (MEDIUM - Metrics Differentiation)

8. **Separar SLOW vs FAST Metrics**
   - SLOW metrics: EMA50, EMA200, RSI, RS baseline (diario)
   - FAST metrics: Distance to EMA21, Reclaim status, Deterioration (intraday)
   - Actualizar FAST metrics cada 5 minutos para TIER 1

9. **Implementar Realtime Discovery**
   - Detectar volume explosion en tiempo real
   - Detectar RS acceleration en tiempo real
   - Emitir alerts inmediatos

10. **Implementar Lifecycle Auto-Tracking**
    - Detectar lifecycle changes automáticamente
    - Actualizar lifecycle states automáticamente
    - Emitir lifecycle events

---

# RECOMMENDED ARCHITECTURAL CHANGES

## CAMBIO 1: Scheduler Integration

**Estado Actual:**
```python
async def _scheduler_loop(self):
    while self._running:
        # Price update every 15 minutes
        if (now - last_price_update).total_seconds() >= 900:
            asyncio.create_task(self._update_prices())
        
        # Metrics update every 30 minutes
        if (now - last_metrics_update).total_seconds() >= 1800:
            await self.trigger_metrics_update(limit=3125)
```

**Propuesto:**
```python
async def _scheduler_loop(self):
    while self._running:
        # Price update every 15 minutes
        if (now - last_price_update).total_seconds() >= 900:
            asyncio.create_task(self._update_prices())
        
        # Fast metrics every 5 minutes (TIER 1)
        if (now - last_fast_metrics_update).total_seconds() >= 300:
            await self.trigger_fast_metrics_update(tier=UniverseTier.TIER_1)
        
        # Slow metrics every 30 minutes (all tiers)
        if (now - last_metrics_update).total_seconds() >= 1800:
            await self.trigger_metrics_update(limit=3125)
        
        # Discovery scans after market close
        if current_time >= market_close and (now - last_discovery_scan).total_seconds() >= 86400:
            await self.run_nightly_scans()
        
        # Tier re-evaluation daily
        if current_time >= market_close and (now - last_tier_reevaluation).total_seconds() >= 86400:
            await self.reevaluate_tiers()
        
        # Health monitoring daily
        if current_time >= market_close and (now - last_health_check).total_seconds() >= 86400:
            await self.generate_health_report()
```

## CAMBIO 2: Discovery Pipeline Integration

**Estado Actual:**
- Discovery candidates se generan pero NO se procesan
- process_discovery_candidate() existe pero NO se llama

**Propuesto:**
```python
async def process_discovery_candidates(self, candidates: List[DiscoveryCandidate]):
    """Process discovery candidates automatically"""
    for candidate in candidates:
        if candidate.confidence >= 80:
            # Auto-onboard high-confidence candidates
            await self.auto_onboard_candidate(candidate)
        elif candidate.confidence >= 50:
            # Queue for manual review
            await self.queue_for_review(candidate)
```

## CAMBIO 3: Tier System Dynamic Re-evaluation

**Estado Actual:**
- Tiers estáticos, asignados durante migración
- NO hay re-evaluation automática

**Propuesto:**
```python
async def reevaluate_tiers_daily(self):
    """Reevaluate tiers daily based on current market data"""
    # Get all active symbols with current metrics
    symbols = await self.get_active_symbols()
    
    for symbol in symbols:
        metrics = await self.get_current_metrics(symbol)
        enriched = await self.enrich_ticker(symbol, metrics)
        
        current_tier = self.tier_manager.get_tier(symbol)
        new_tier = self.tier_manager.determine_tier(enriched)
        
        if current_tier != new_tier:
            # Emit tier change event
            await self.emit_tier_change_event(symbol, current_tier, new_tier)
```

## CAMBIO 4: Health Monitoring Integration

**Estado Actual:**
- HealthMonitor existe pero NO se usa

**Propuesto:**
```python
async def generate_health_report_daily(self):
    """Generate health report and take corrective actions"""
    report = await self.health_monitor.generate_health_report(...)
    
    # Auto-removal of dead listings
    for dead_symbol in report.dead_listings:
        await self.remove_symbol(dead_symbol)
    
    # Auto-refresh of coverage gaps
    for sector, count in report.coverage_gaps.items():
        if count < 10:
            await self.fill_coverage_gap(sector)
    
    # Auto-prioritize stale symbols for update
    for stale_symbol in report.stale_tickers:
        await self.prioritize_for_update(stale_symbol)
```

---

# FINAL VERDICT

**DIAGNÓSTICO:** El sistema tiene arquitectura institucional excelente pero implementación estática.

**ESTADO ACTUAL:** 15% Adaptive Market Discovery Engine, 85% Static Screener with Static Lists.

**PROBLEMA CRÍTICO:** Discovery infrastructure existe pero está completamente desintegrado del scheduler.

**RIESGO:** 85% - El sistema perderá líderes emergentes, cambios sectoriales, IPOs relevantes y oportunidades de momentum.

**URGENCIA:** ALTA - El sistema necesita integración inmediata de discovery pipeline para dejar de ser un screener estático y convertirse en un adaptive market discovery engine.

**RECOMENDACIÓN:** Implementar PRIORITY 1 fixes inmediatamente (Scheduler integration, auto-onboarding, tier re-evaluation, health monitoring). Esto transformará el sistema de estático a adaptive en 2-3 semanas.
