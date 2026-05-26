AUDITORÍA: estado actual vs. estado declarado
Mapeé el estado actual (post-context-decision-wiring) y lo comparé contra PRODUCT_BRAIN.md, DECISION_FILTER.md, WHAT_THIS_PRODUCT_IS_NOT.md. Lo que sigue es honesto, no diplomático.

VEREDICTO GENERAL
Backend: 6/10. Las primitivas core (TransitionEngine, SetupLifecycle, OutcomeTracker, MarketContextEngine) son genuinamente institucionales. Pero la superficie creció: 30 servicios, 18 endpoint files, ~60 rutas — el 73% sin consumidor frontend (44/60). Estás shippeando más rápido de lo que estás consolidando.
Frontend: 5/10. Más limpio que en la auditoría de mayo (no hay sparklines falsos, polling sano, sin MarketStatusBar zombie en dashboard) — pero la pantalla principal ahora tiene TRES listas paralelas de "acá hay acciones para mirar": TopActionableSetups (6 cards) + LiveTransitionFeed (20 eventos) + VcpCandidatesPanel (10 VCP). Y CompactSetupCard tiene 25 elementos visuales por card.
Coherencia filosófica: 4/10. DECISION_FILTER.md existe pero no se aplica visiblemente. La auditoría de mayo ya lo señaló y la situación empeoró: hay 19 OpenSpec changes activos, lo cual es un pipeline de fábrica de features, no un backlog priorizado.
PRINCIPALES RIESGOS
Tres listas paralelas en el mismo screen. Decision fatigue garantizada. PRODUCT_BRAIN habla de "scarcity + clarity" — la realidad es saturación + paralelismo.
44 endpoints zombi (73% de la superficie). No es teoría: es código desplegado, carga de mantenimiento real, y un mapa engañoso de "qué hace este producto".
OpenSpec es la nueva fábrica. 19 changes en vuelo. Sin un sweep de DECISION_FILTER, el propio backlog es drift.
El cambio que acabo de shippear (context-decision-wiring) introdujo context_snapshot en 4 lugares distintos (MarketContextBar, header de TopActionableSetups, header de cada queue page, SuppressionCard). Drift causado por el change diseñado para combatir drift. Yo lo metí.
Dos engines de régimen siguen vivos. market_regime_engine (viejo, RISK_ON/RISK_OFF) + market_context_engine (nuevo, participation × leadership). El nuevo multiplicador compone con _REGIME_CONT_MULT del viejo. Decisión 4 del design lo justifica como "interim", pero el interim ya es estructural si no hay deadline para retiro.
DRIFT DETECTADO
Screener thinking todavía vivo:

/scanner page — corre scans ad-hoc por tipo. Contradicción directa con WHAT_THIS_PRODUCT_IS_NOT.md. Si un usuario quiere screener genérico, tiene Finviz.
/watchlists page — CRUD para "acciones que miro". El producto entero ES una watchlist curada. Una watchlist dentro de una watchlist es theater.
quality_swing_scanner_service.py — meterle "quality" al nombre no lo redime; sigue siendo screener.
VcpCandidatesPanel en /dashboard — VCP es patrón estructural, no transition. Listar "10 candidatos rankeados por score" es flavor de breakout-screener.
Analytics theater:

MarketContextDrawer muestra 9 métricas de participation + 10 de leadership = 19 números. Un trader decidiendo usa 3-4. Está honesto porque está detrás de un click, pero su existencia muestra mentalidad "instrumentar todo".
/leader-health/{history,analysis}, /market-regime/{history,analysis} — endpoints históricos sin consumidor. Ghosts analíticos.
10 endpoints en /universe/* — todos sin consumidor.
Ruido visual:

CompactSetupCard tiene 23-25 elementos por card. El badge exhausted amber que acabo de agregar es el 26.
Cada card muestra: freshness badge, watch badge (a veces), exhausted badge (a veces), continuation %, empirical/rule-based sub-label, sample size, dist_to_setup_pct, dist_ema_label, transition icon, days_in_state, RS, vol, base, narrative. Dossier completo por card.
Seis cards en grid de 6 = 138-150 elementos visuales en un solo panel. Las afirmaciones de "sub-20-second market assessment" de PRODUCT_BRAIN no son verificables contra esto.
FEATURES QUE DEBERÍAN ELIMINARSE (kill list)
/scanner + /scanners/* endpoints — contradicción directa con la identidad del producto.
/watchlists + endpoints relacionados — utility CRUD dentro de un producto que ya es lista curada.
/universe/* (10 endpoints) — si los necesitás para ops, son un CLI, no una API surface.
/themes endpoint — sin consumidor.
MarketStatusBar.tsx — no renderizado en /dashboard, superseded por MarketContextBar. Borrar.
/setup-lifecycle/* (4 endpoints) — todos sin consumidor. El engine se consume internamente.
/leader-health/history,analysis y /market-regime/history,analysis — observabilidad sin observador.
VcpCandidatesPanel en /dashboard — moverlo a /queue/building-bases (que ya hace VCP) y quitarlo del screen principal.
FEATURES QUE DEBERÍAN SIMPLIFICARSE
CompactSetupCard de 25 a ~12-14 elementos:
empirical (N=X) / rule-based → tooltip on hover, no inline
dist_ema_label redundante con la métrica EMA → eliminar
Transition icon footer → siempre es "stable" en actionable, eliminar
"Base" hardcoded a fast/8w → calcular real o eliminar
MarketContextDrawer de 19 a 6 métricas. Las que cambian decisión: breadth%, momentum 5d, leader_count, leader_count_delta_20d, leader_pullback_quality_avg, leader_climactic_count. El resto detrás de toggle "raw metrics".
Repetición de context_snapshot — mostralo UNA vez (en MarketContextBar). Sacalo del header de actionable, del header de cada queue page, y del SuppressionCard. Esto es drift que yo causé hoy.
Retirar _REGIME_CONT_MULT. Componer dos multiplicadores de régimen es la peor forma de drift. A/B de una semana de outcomes, matar al perdedor.
FEATURES CORE QUE DEBERÍAN EXPANDIRSE
OutcomeTracker → EmpiricalProbabilityCalculator. Lo más genuinamente institucional. Expandir cohort key para incluir regime cuando haya N suficiente. Es el camino al Principio 5 completamente realizado.
SetupLifecycle state machine como columna vertebral del dashboard. Hoy es UN panel entre varios. Debería ser el organizador del screen — todo lo demás cuelga de él.
Pre-reclaim como primera clase. is_pre_reclaim_candidate existe en código pero no como surface dedicada. Esa es la condición institucional de "estoy a punto de operar". Merece su propio lens, listado por readiness, no por priority_score.
Phase 2 de MarketContextEngine (persistence, forgiveness, rotation, volatility, follow_through). Conceptos reales. Pero consolidados, no estirados — cada uno debe pasar DECISION_FILTER antes de empezar.
PRIORIDADES REALES (próximas 2-4 semanas)
Kill the zombie endpoints. 44 endpoints sin consumidor. Un PR. Reduce superficie, reduce confusión sobre "qué hace este producto". La métrica a bajar es el endpoint count.
Consolidar dashboard a una sola lista. Hoy son 3. Elegí la que mueve decisiones (TopActionableSetups). VCP → Building Bases. LiveTransitionFeed → sidebar event log, no panel peer.
Pasar el backlog de OpenSpec por DECISION_FILTER. 19 changes. Esperá que 6-8 fallen. Cerrarlos.
Retirar _REGIME_CONT_MULT. Una semana de A/B, archivar perdedor.
Simplificar CompactSetupCard. PR único, concreto. Bajar a 12-14 elementos.
"NO IMPLEMENTAR" LIST
Charts / mini-charts / OHLC overlays — TradingView ya existe
Sistema de notificaciones / alertas — el dashboard ES la alerta
Accounts / preferences / themes (UI themes, no market themes) — producto de un solo operador
AI commentary / GPT narratives — el narrative generator alcanza
Backtesting UI — el outcome tracker ya da los datos; UI de backtest es screener thinking
Earnings calendar / news feed — el contexto es régimen, no noticias
Mobile app / responsive optimization — producto de escritorio
Multi-user / sharing / collaboration
UI para configurar pesos de scoring — los pesos son constantes operator-tunable en código
"Strategy builder" / rule editor — cada "builder" es una confesión de que el sistema no decide
QUICK WINS (esta semana)
Borrar MarketStatusBar.tsx (zombie)
Borrar endpoint /themes + service relacionado
Sacar dist_ema_label del footer de CompactSetupCard
Sacar context_snapshot del header de TopActionableSetups (MarketContextBar ya lo muestra)
Sacar context_snapshot de cada /queue page (idem). Mantenerlo SOLO dentro del SuppressionCard donde es informativo en bloqueo.
Borrar /universe/* (10 endpoints), /setup-lifecycle/* (4 endpoints), /leader-health/history,analysis, /market-regime/history,analysis.
DEUDA TÉCNICA CRÍTICA
30 services, 18 endpoint files, 46 columnas en StockMetrics — todo creció, nada se borró. En 4 días, cero servicios eliminados, varios agregados.
transition_engine.py (817 LOC) y scheduler.py (937 LOC) — ambos sobre el umbral. Targets concretos: extraer clasificación de OperationalTransition a su módulo; extraer jobs del scheduler a un package scheduler/jobs/.
No hay framework de A/B / experiment. Cada multiplicador nuevo se compone con los existentes. No hay forma segura de retirar lógica vieja. _REGIME_CONT_MULT × ctx_multiplier es el caso canónico.
OpenSpec backlog como nueva forma de deuda técnica. 19 changes sin prioridad visible.
except Exception en todos lados — la auditoría de mayo lo dijo, sigue vigente. Lo vi en context_decision_filter.fetch_current_context (lo escribí yo ayer). En boundaries del sistema está bien; dentro de lifecycle oculta bugs.
COMPONENTES MÁS IMPORTANTES (genuinamente institucional)
TransitionEngine — transiciones operativas con narrativa. La columna vertebral.
SetupLifecycleEngine — state machine formal. Lo más alineado con PRODUCT_BRAIN.
EmpiricalProbabilityCalculator — outcomes reales, no fórmulas. Lo único que puede corregirse a sí mismo.
OutcomeTracker — el feedback loop. Sin esto todo lo demás es opinión.
MarketContextEngine (participation + leadership) — read multi-dimensional de régimen. El nuevo decision filter lo cablea correctamente — el problema es solo la repetición visual.
ATR-normalization en todo (distance_to_ema*_atr) — institucional puro.
COMPONENTES "RETAIL DASHBOARD THEATER"
VcpCandidatesPanel en el dashboard — listar patrones por score es flavor screener
/scanner page — el ideal platónico del screener
/watchlists page — CRUD adentro de un producto que ya ES una watchlist
MarketContextDrawer con 19 métricas — instrumentar-todo theater
Endpoints /history y /analysis — existen para verse profesionales, sin consumidor
/universe/* 10 endpoints — admin que debería ser CLI
El sub-label empirical/rule-based en cada card — info útil pero saturando. Tooltip.
OBSERVACIÓN INCÓMODA FINAL
El change que acabo de shippear (market-context-decision-wiring) está bien diseñado a nivel de spec — cierra el loop del Principio 5. Pero a nivel de UI agregué context_snapshot en 4 lugares y un badge más por card, sin quitar nada. Es exactamente el patrón de drift que esta auditoría describe: shippear lo correcto + sumar superficie + nunca restar.

El próximo change que entre debería ser un delete-change: una sola PR que borre los 44 endpoints zombi, el MarketStatusBar, las 4 repeticiones de context_snapshot, y dist_ema_label del footer. Si DECISION_FILTER.md es real, "agregar nada, restar mucho" tiene que poder pasar como change válido en OpenSpec.