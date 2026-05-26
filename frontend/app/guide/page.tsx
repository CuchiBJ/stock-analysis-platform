import DashboardLayout from '@/components/layout/DashboardLayout'

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-8">
      <h2 className="text-base font-bold text-foreground uppercase tracking-widest mb-4 pb-2 border-b border-white/10">
        {title}
      </h2>
      <div className="space-y-4">{children}</div>
    </section>
  )
}

function Block({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-white/8 bg-white/3 px-4 py-3 space-y-1.5">
      {title && <p className="text-xs font-semibold text-white/60 uppercase tracking-wide">{title}</p>}
      {children}
    </div>
  )
}

function Row({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="flex gap-3 py-1.5 border-b border-white/5 last:border-0">
      <span className="text-xs text-white/50 w-52 shrink-0">{label}</span>
      <div>
        <span className="text-xs text-white/90">{value}</span>
        {note && <span className="text-xs text-white/30 ml-2">— {note}</span>}
      </div>
    </div>
  )
}

function Descriptor({ name, color, meaning }: { name: string; color: string; meaning: string }) {
  return (
    <div className="flex items-start gap-3 py-1.5 border-b border-white/5 last:border-0">
      <span className={`text-xs font-bold w-28 shrink-0 ${color}`}>{name}</span>
      <span className="text-xs text-white/60">{meaning}</span>
    </div>
  )
}

function Toc({ items }: { items: { id: string; label: string }[] }) {
  return (
    <div className="flex flex-wrap gap-2 mb-8">
      {items.map(item => (
        <a
          key={item.id}
          href={`#${item.id}`}
          className="text-[11px] px-3 py-1 rounded-full border border-white/10 text-white/50 hover:text-white/80 hover:border-white/20 transition-colors"
        >
          {item.label}
        </a>
      ))}
    </div>
  )
}

export default function GuidePage() {
  return (
    <DashboardLayout>
      <div className="max-w-3xl mx-auto space-y-10">

        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-foreground">Guía de interpretación</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Cómo leer los datos de la plataforma — qué mide cada número y qué significa en la práctica.
          </p>
        </div>

        <Toc items={[
          { id: 'universo',      label: 'Universo de análisis' },
          { id: 'context',       label: 'Market Context' },
          { id: 'participation', label: 'Participation' },
          { id: 'leadership',    label: 'Leadership' },
          { id: 'queue',         label: 'Setup Queue' },
          { id: 'transitions',   label: 'Transitions' },
          { id: 'prob-source',   label: 'Probabilidad de continuación' },
          { id: 'context-filter', label: 'Cómo el contexto filtra los setups' },
        ]} />

        {/* ── UNIVERSO ──────────────────────────────────────────────── */}
        <Section id="universo" title="Universo de análisis">
          <p className="text-sm text-white/60">
            No todos los stocks del mercado entran en los cálculos. La plataforma aplica
            tres filtros mínimos para excluir penny stocks, acciones ilíquidas y nombres
            sin volatilidad operativa. A este conjunto filtrado se le llama el
            <strong className="text-white/80"> universo de calidad</strong>.
          </p>
          <Block title="Filtros aplicados">
            <Row label="Volumen promedio 10 días"   value="> 500,000 acciones diarias"  note="liquidez mínima para operar sin deslizamiento" />
            <Row label="Precio actual"              value="> $5.00"                      note="excluye penny stocks" />
            <Row label="ADR — Average Daily Range"  value="> 2%"                         note="mínima volatilidad para que el movimiento sea aprovechable" />
          </Block>
          <p className="text-xs text-white/40">
            El universo actual es de ~1,978 stocks. Todos los porcentajes de breadth,
            liderazgo y participación se calculan sobre este conjunto, no sobre el mercado completo.
          </p>
        </Section>

        {/* ── MARKET CONTEXT ────────────────────────────────────────── */}
        <Section id="context" title="Market Context — la barra de contexto">
          <p className="text-sm text-white/60">
            La barra superior del dashboard muestra el estado actual del mercado en dos
            dimensiones independientes: <strong className="text-white/80">participation</strong> (amplitud)
            y <strong className="text-white/80">leadership</strong> (calidad del liderazgo institucional).
            Cada dimensión tiene su propio descriptor y sus propias métricas. No se colapsan en
            un solo número — intencionalmente.
          </p>
          <Block>
            <p className="text-xs text-white/60">
              Un mercado puede tener participation <span className="text-green-400 font-semibold">EXPANDING</span> y
              leadership <span className="text-amber-400 font-semibold">THINNING</span> al mismo tiempo.
              Eso significa que más stocks suben, pero los institucionales se están retirando.
              Es una señal de advertencia que una etiqueta única ("risk on") ocultaría.
            </p>
          </Block>
        </Section>

        {/* ── PARTICIPATION ─────────────────────────────────────────── */}
        <Section id="participation" title="Participation — amplitud del mercado">
          <p className="text-sm text-white/60">
            Mide cuántos stocks del universo de calidad están participando del movimiento.
            El indicador central es la <strong className="text-white/80">breadth</strong>:
            el porcentaje de stocks que cotizan por encima de su EMA21.
          </p>

          <Block title="Cómo se calcula la breadth">
            <p className="text-xs text-white/60">
              Se cuenta cuántos stocks tienen el precio por encima de su media exponencial de
              21 días, y se divide por el total del universo. Cada stock cuenta igual: 1 si
              está arriba, 0 si está abajo. No hay ponderación por capitalización.
            </p>
            <p className="text-xs text-white/40 mt-1">
              Ejemplo: 1,085 stocks sobre EMA21 ÷ 1,978 en el universo = 54.95% de breadth.
            </p>
          </Block>

          <Block title="Descriptor — qué está haciendo la breadth">
            <p className="text-xs text-white/50 mb-2">
              El descriptor refleja el cambio de breadth en los últimos ~5 días de trading
              (medido en puntos porcentuales, pp).
            </p>
            <Descriptor name="EXPANDING"  color="text-green-400"  meaning="La breadth subió más de +5pp. Más stocks se suman al movimiento. Mercado con amplitud creciente." />
            <Descriptor name="STABLE"     color="text-white/70"   meaning="La breadth se mantiene entre −5pp y +5pp. Mercado lateral sin deterioro ni expansión." />
            <Descriptor name="NARROWING"  color="text-amber-400"  meaning="La breadth cayó entre −5pp y −15pp. Menos stocks participan. El rally se está achicando." />
            <Descriptor name="COLLAPSING" color="text-red-400"    meaning="La breadth cayó más de −15pp. Colapso de amplitud. El movimiento lo sostienen muy pocos stocks." />
          </Block>

          <Block title="Métricas de referencia">
            <Row label="breadth_above_ema21"        value="% del universo sobre su EMA21"         note="indicador principal de amplitud de corto plazo" />
            <Row label="breadth_above_ema50"        value="% del universo sobre su EMA50"         note="amplitud de mediano plazo" />
            <Row label="breadth_above_ema200"       value="% del universo sobre su EMA200"        note="amplitud estructural de largo plazo" />
            <Row label="breadth_momentum_5d"        value="diferencia de breadth vs ~5 días atrás" note="insumo del descriptor" />
            <Row label="breadth_momentum_20d"       value="diferencia de breadth vs ~20 días atrás" note="tendencia de más largo plazo" />
            <Row label="near_highs_count"           value="stocks a menos de 1 ATR de su máximo anual" note="stocks en zona de fuerza real" />
            <Row label="near_lows_count"            value="stocks a más de 6 ATR de su máximo anual"   note="proxy de stocks cerca de mínimos anuales" />
            <Row label="highs_lows_ratio"           value="near_highs ÷ near_lows"               note="ratio > 1 es sano; < 0.5 indica distribución" />
            <Row label="participation_persistence"  value="dispersión de la breadth en 20 días"  note="alta dispersión = mercado volátil e inestable" />
          </Block>

          <Block title="Cómo leerlo en práctica">
            <p className="text-xs text-white/60">
              El descriptor EXPANDING con un momentum_20d negativo indica un <strong className="text-white/80">rebote
              técnico desde un piso</strong>, no una expansión desde base. Siempre cruzar el descriptor
              con el momentum_20d y el highs/lows ratio para entender si la fuerza es nueva o es recuperación.
            </p>
          </Block>
        </Section>

        {/* ── LEADERSHIP ────────────────────────────────────────────── */}
        <Section id="leadership" title="Leadership — calidad del liderazgo institucional">
          <p className="text-sm text-white/60">
            Mide cuántos stocks califican como líderes institucionales y qué tan saludable
            es ese grupo. La definición de "líder" es estricta: tiene que cumplir los
            8 criterios Minervini SEPA simultáneamente.
          </p>

          <Block title="Qué es un líder institucional (8 criterios Minervini SEPA)">
            <Row label="Performance anual"        value="> 30%"                     note="el stock está en tendencia alcista real, no rebote" />
            <Row label="Precio sobre EMA200"      value="precio > media 200 días"   note="tendencia de largo plazo intacta" />
            <Row label="Precio sobre EMA50"       value="precio > media 50 días"    note="tendencia de mediano plazo intacta" />
            <Row label="SMA50 sobre SMA150"       value="media 50d > media 150d"    note="alineación alcista de mediano plazo" />
            <Row label="SMA150 sobre SMA200 ×1.05" value="media 150d > media 200d +5%" note="tendencia de largo plazo con pendiente positiva" />
            <Row label="Rango anual"              value="> 60% del máximo al mínimo" note="el stock tuvo movimiento real, no lateralización" />
            <Row label="Precio sobre mínimo anual" value="> 70% sobre el mínimo del año" note="lejos del piso — el mercado no lo abandonó" />
            <Row label="ADR"                      value="> 3%"                      note="volatilidad operativa suficiente para el setup" />
          </Block>

          <Block title="Descriptor — qué le está pasando al pool de líderes">
            <p className="text-xs text-white/50 mb-2">
              El descriptor refleja el cambio porcentual en la cantidad de líderes vs ~5 días atrás,
              con un override de agotamiento que toma prioridad sobre cualquier crecimiento de count.
            </p>
            <Descriptor name="EXPANDING"  color="text-green-400"  meaning="Más del +5% de líderes nuevos vs 5 días atrás. El mercado genera liderazgo fresco." />
            <Descriptor name="HEALTHY"    color="text-green-400"  meaning="El pool de líderes se mantiene estable (±5%). Mercado sostenible para setups institucionales." />
            <Descriptor name="THINNING"   color="text-amber-400"  meaning="El pool cayó entre −5% y −15%. El liderazgo se contrae. Selectividad mayor." />
            <Descriptor name="COLLAPSING" color="text-red-400"    meaning="El pool cayó más del −15%. Pocos líderes quedan. Ambiente hostil para nuevas entradas." />
            <Descriptor name="EXHAUSTED"  color="text-red-400"    meaning="Override: más del 25% de líderes están climácticos o más del 40% extended. Señal de techo independientemente de si el count crece." />
          </Block>

          <Block title="Métricas de referencia">
            <Row label="leader_count"                value="cantidad de líderes Minervini hoy" />
            <Row label="leader_count_delta_5d"       value="cambio vs ~5 días atrás (en cantidad)" />
            <Row label="leader_count_delta_20d"      value="cambio vs ~20 días atrás (en cantidad)" />
            <Row label="leader_pullback_quality_avg" value="calidad promedio de los pullbacks de los líderes"  note="0–100; >60 es structure ordenada" />
            <Row label="leader_tightness_avg"        value="contracción semanal promedio de los líderes"       note="valores bajos = bases más apretadas" />
            <Row label="leader_vol_contraction_avg"  value="contracción de volatilidad semanal promedio"       note="negativo = volatilidad expandiéndose" />
            <Row label="leader_rs_persistence_10d"   value="% de líderes RS-strong hoy que también lo eran hace 10 días" note="alta persistencia = liderazgo con continuidad real" />
            <Row label="leader_extension_count"      value="líderes con precio > 3 ATR sobre su EMA21"         note="sobreextendidos — riesgo de entrada" />
            <Row label="leader_climactic_count"      value="líderes con ADR del día > 2× su promedio 20 días"  note="movimiento climáctico — posible techo de corto plazo" />
            <Row label="leadership_turnover_5d"      value="stocks que entraron o salieron del pool en 5 días"  note="alto turnover = pool inestable" />
          </Block>

          <Block title="La señal más importante: EXHAUSTED">
            <p className="text-xs text-white/60">
              Un mercado donde el count de líderes crece pero más del 25% están haciendo
              movimientos climácticos es un mercado a punto de rotar. El override EXHAUSTED
              existe para capturar exactamente eso: expansión aparente con deterioro interno.
              Es la señal más contraintuitiva y la más valiosa del engine.
            </p>
          </Block>
        </Section>

        {/* ── SETUP QUEUE ───────────────────────────────────────────── */}
        <Section id="queue" title="Setup Queue — lentes de búsqueda">
          <p className="text-sm text-white/60">
            La cola de setups organiza los líderes institucionales en tres lentes según
            el tipo de oportunidad. Cada lente tiene criterios propios de calidad y ordena
            los resultados por score de relevancia.
          </p>

          <Block title="U&R Queue — Undercut & Rally">
            <p className="text-xs text-white/60">
              Líderes que bajaron bajo un soporte clave (mínimo de base, EMA21) y están
              recuperando activamente. Es el setup de mayor confianza estadística en mercados
              con liderazgo institucional: el mercado probó el nivel, rechazó la debilidad
              y volvió a cerrar sobre estructura.
            </p>
            <p className="text-xs text-white/40 mt-1">
              Busca: líderes Minervini + señal de U&R activa + price_above_low_pct alto +
              volumen en la recuperación.
            </p>
          </Block>

          <Block title="Emerging Leaders">
            <p className="text-xs text-white/60">
              Stocks que están a punto de calificar como líderes Minervini pero todavía
              no pasan todos los criterios. Muestra cuántos criterios cumplen y cuáles
              les faltan. Permite monitorear candidatos antes de que entren al pool principal.
            </p>
            <p className="text-xs text-white/40 mt-1">
              Busca: stocks que cumplen 5, 6 o 7 de los 8 criterios Minervini.
            </p>
          </Block>

          <Block title="Building Bases">
            <p className="text-xs text-white/60">
              Líderes Minervini activos que están construyendo una base —
              semanas de lateralización ordenada con contracción de volumen.
              Son los candidatos a la próxima ruptura.
            </p>
            <p className="text-xs text-white/40 mt-1">
              Busca: líderes Minervini + semanas_en_base + tightness + contracción de
              volatilidad semanal + sin sobreextensión.
            </p>
          </Block>
        </Section>

        {/* ── TRANSITIONS ───────────────────────────────────────────── */}
        <Section id="transitions" title="Transitions — cambios de estado">
          <p className="text-sm text-white/60">
            El feed de transitions muestra stocks que cambiaron de estado de setup en las
            últimas horas. No es un screener — es detección de movimientos específicos
            en stocks que ya cumplen criterios de calidad.
          </p>

          <Block title="Tipos de transición">
            <Row label="ENTERING_PULLBACK"    value="El stock empieza a retraerse desde zona de fuerza"    note="primer día de pullback desde zona extendida o breakout" />
            <Row label="PULLBACK_DEEPENING"   value="El pullback continúa y se profundiza"                 note="segunda o tercera jornada de retroceso" />
            <Row label="HOLDING_SUPPORT"      value="El stock llegó a una zona de soporte y está aguantando" note="precio tocó EMA21 o zona de base y no cedió" />
            <Row label="TRIGGER_READY"        value="Setup maduro listo para entrada"                      note="pullback ordenado + compresión + soporte aguantando" />
            <Row label="BREAKING_OUT"         value="Ruptura sobre la zona de resistencia o base"         note="cierre sobre el pivot con expansión de rango" />
            <Row label="FAILED_BREAKOUT"      value="La ruptura no se sostuvo"                             note="precio volvió bajo el pivot dentro de los 3 días" />
            <Row label="RECOVERY_ATTEMPT"     value="El stock intenta recuperar soporte perdido"           note="bounce desde mínimos pero sin confirmación aún" />
          </Block>

          <Block title="Qué NO es el feed de transitions">
            <p className="text-xs text-white/60">
              No es una señal de compra automática. Es detección de comportamiento: el sistema
              observa que algo cambió en la estructura de precio del stock y lo registra.
              La decisión de entrada siempre requiere confirmar contexto de mercado
              (participation + leadership) y estructura propia del setup.
            </p>
          </Block>
        </Section>

        {/* ── PROBABILIDAD DE CONTINUACIÓN ─────────────────────────── */}
        <Section id="prob-source" title="Probabilidad de continuación — empirical vs rule-based">
          <p className="text-sm text-white/60">
            Cada setup card muestra un porcentaje que estima la probabilidad de que el setup
            continúe favorablemente. Debajo del porcentaje aparece una etiqueta que indica
            de dónde viene ese número. Hay dos orígenes posibles.
          </p>

          <Block title="empirical (N=…) — calculado sobre observaciones reales">
            <p className="text-xs text-white/60">
              El número viene de observaciones históricas reales almacenadas en la base de datos.
              El sistema busca todos los setups del mismo tipo y rango de RS que ya se resolvieron,
              y calcula la tasa de éxito real:
            </p>
            <p className="text-xs font-mono text-white/50 bg-white/5 rounded px-3 py-2 mt-2">
              éxitos / (éxitos + fracasos)
            </p>
            <p className="text-xs text-white/40 mt-2">
              Los resultados NEUTRAL (ni claro éxito ni claro fracaso dentro de la ventana de evaluación)
              se excluyen del denominador. No inflan ni deflactan la tasa — representan ambigüedad genuina.
            </p>
            <p className="text-xs text-white/40 mt-1">
              El número entre paréntesis es el tamaño de la muestra: N=18 significa que la tasa
              se calculó sobre 18 observaciones resueltas. Un N=5 es el mínimo válido — técnicamente
              correcto pero estadísticamente escaso. Un N=50+ ya es robusto.
            </p>
          </Block>

          <Block title="rule-based — fórmula compuesta">
            <p className="text-xs text-white/60">
              No hay suficientes observaciones históricas para este tipo de setup y rango de RS.
              El sistema usa una fórmula de pesos fijos: calidad semanal (40%),
              pullback quality (30%), RS vs SPY (20%), contracción de volumen (10%).
            </p>
            <p className="text-xs text-white/40 mt-1">
              Esta fórmula no fue calibrada contra outcomes reales — es heurística.
              La etiqueta amber sirve para distinguirla visualmente del número empírico.
              Con el tiempo, a medida que se acumulen observaciones, más setups migrarán
              a fuente empírica.
            </p>
          </Block>

          <Block title="Por qué N importa — cómo leer el tamaño de muestra">
            <Row label="N &lt; 5"  value="no se reporta — demasiado escaso" note="el sistema usa rule-based automáticamente" />
            <Row label="N = 5–10"  value="empírico pero mínimo"            note="leer con cautela; un outcome diferente cambia mucho la tasa" />
            <Row label="N = 10–30" value="empírico moderado"               note="señal útil, pero puede reflejar un solo régimen de mercado" />
            <Row label="N &gt; 30" value="empírico robusto"                note="la tasa ya refleja múltiples condiciones de mercado" />
          </Block>

          <Block title="Por qué algunos setups siempre muestran rule-based">
            <p className="text-xs text-white/60">
              Tipos de transición raros o rangos de RS poco frecuentes tienen muy pocas
              observaciones históricas. El sistema requiere al menos 5 observaciones resueltas
              para reportar un número empírico. La proporción de setups con fuente empírica
              crecerá semana a semana a medida que la base de datos acumule más datos.
            </p>
          </Block>
        </Section>

        {/* ── CONTEXT FILTER ───────────────────────────────────────── */}
        <Section id="context-filter" title="Cómo el contexto filtra los setups">
          <p className="text-sm text-white/60">
            Los descriptores de Participation y Leadership no son solo informativos — se traducen
            en decisiones concretas sobre cada lens y cada setup. El sistema aplica un
            multiplicador al <code className="text-white/50">priority_score</code> y puede suprimir
            lenses completas cuando las condiciones de mercado lo justifican.
          </p>

          <Block title="Multiplicadores de score — tres niveles">
            <Row label="EXPANDING × EXPANDING/HEALTHY" value="× 1.1 (boost moderado)"  note="amplitud creciente + liderazgo sano → señal de alta calidad" />
            <Row label="STABLE / UNKNOWN"               value="× 1.0 (neutro)"         note="sin penalización ni boost — condición base" />
            <Row label="NARROWING + liderazgo adverso"  value="× 0.7 (reducción)"      note="liderazgo THINNING, COLLAPSING o EXHAUSTED" />
            <Row label="EXHAUSTED leadership (override)" value="× 0.6 + aviso"         note="el multiplicador refleja agotamiento del liderazgo" />
            <Row label="COLLAPSING participation"        value="× 0.5 (reducción fuerte)" note="colapso de amplitud — prioridades bajadas significativamente" />
          </Block>

          <Block title="Supresión de lenses — cuándo y cuáles">
            <p className="text-xs text-white/60">
              Dos lenses pueden ser suprimidas por contexto. Building Bases nunca se suprime
              (formación estructural de semanas — independiente del régimen de corto plazo).
            </p>
            <Row label="COLLAPSING participation"              value="suprime U&amp;R + Emerging Leaders" note="sin amplitud no hay candidatos de corto horizonte confiables" />
            <Row label="NARROWING + leadership adverso"        value="suprime Emerging Leaders"           note="U&R permanece disponible — líderes establecidos aún pueden configurarse" />
            <Row label="Building Bases"                        value="nunca suprimida"                    note="la construcción multi-semana es independiente del régimen" />
          </Block>

          <Block title="Supresión no oculta — respuesta estructurada">
            <p className="text-xs text-white/60">
              Cuando una lens está suprimida, la respuesta del sistema incluye{' '}
              <code className="text-white/50">suppressed: true</code> con una razón en español
              y el <code className="text-white/50">context_snapshot</code> que produjo la decisión.
              La lista de candidatos se calcula igual — el botón "ver de todas formas" la muestra
              sin un nuevo llamado al servidor.
            </p>
            <p className="text-xs text-white/40 mt-1">
              El sistema siempre dice la verdad. El override es UI-only: el operador puede decidir
              ignorar la supresión, pero el backend no cambia su evaluación.
            </p>
          </Block>

          <Block title="EXHAUSTED leadership — la advertencia amber">
            <p className="text-xs text-white/60">
              Cuando <code className="text-white/50">leadership = EXHAUSTED</code> (y la combinación
              no está cubierta por una regla más fuerte), cada setup card muestra un badge amber{' '}
              <span className="text-amber-400">exhausted</span> junto al porcentaje de continuación.
              Los setups sobreviven la supresión pero el sistema avisa que el liderazgo está
              en fase de agotamiento.
            </p>
          </Block>

          <Block title="UNKNOWN — nunca suprime">
            <p className="text-xs text-white/60">
              Si el motor de contexto devuelve UNKNOWN en cualquier dimensión (arranque en frío,
              base de datos vacía, cache vencido sin datos), el multiplicador es 1.0 y no se
              suprime ninguna lens. El sistema nunca restringe la vista del operador por datos
              ausentes — solo por datos adversos observados.
            </p>
          </Block>

          <Block title="Barra de contexto — indicador de supresión">
            <p className="text-xs text-white/60">
              La barra superior muestra <span className="text-amber-400/80">· suprime N lenses</span>{' '}
              cuando el contexto actual activa alguna regla. Hacer click sobre ese texto muestra
              cuáles lenses están afectadas. Esto permite correlacionar el estado de la barra
              con el comportamiento de las colas sin abrir cada una.
            </p>
          </Block>
        </Section>

        {/* ── CONCEPTOS CLAVE ───────────────────────────────────────── */}
        <Section id="conceptos" title="Conceptos clave">
          <Block title="ATR — Average True Range">
            <p className="text-xs text-white/60">
              El rango promedio diario de movimiento del stock, medido en precio absoluto.
              Se usa para normalizar distancias: en lugar de decir "el precio está $2 bajo
              la EMA21", se dice "está −0.8 ATR bajo la EMA21". Esto hace que las distancias
              sean comparables entre stocks de distintos precios y volatilidades.
            </p>
          </Block>

          <Block title="RS — Relative Strength vs SPY">
            <p className="text-xs text-white/60">
              Compara la performance del stock contra el ETF del S&P 500. Un RS de 115
              significa que el stock superó al SPY en un 15% en el período medido.
              RS &gt; 100 indica outperformance. Los líderes Minervini suelen tener RS
              entre 110 y 150+ en el momento de sus mejores setups.
            </p>
          </Block>

          <Block title="Distancias normalizadas por ATR">
            <p className="text-xs text-white/60">
              Muchas métricas de la plataforma expresan distancias en unidades de ATR
              en lugar de porcentajes. Por ejemplo, <code className="text-white/50">distance_to_ema21_atr</code> de
              +2.5 significa que el precio está a 2.5 rangos diarios sobre su EMA21.
              Encima de +3 ATR se considera sobreextendido.
            </p>
          </Block>

          <Block title="Por qué no hay un score único de mercado">
            <p className="text-xs text-white/60">
              Un número único como "mercado al 72%" o una etiqueta como "risk on" colapsa
              información en una dimensión y oculta contradicciones internas. Un mercado
              puede tener breadth expanding mientras el liderazgo se agota — eso es
              información crítica que un score único borra. La plataforma reporta
              dimensiones separadas para que el operador pueda ver esas contradicciones.
            </p>
          </Block>
        </Section>

      </div>
    </DashboardLayout>
  )
}
