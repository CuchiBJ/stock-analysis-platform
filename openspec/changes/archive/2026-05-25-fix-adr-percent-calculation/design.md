## Context

`calculate_adr_percent()` en `momentum.py` recibe solo close prices y mide cambio porcentual close-to-close:

```python
def calculate_adr_percent(prices: pd.Series, days: int = 20) -> float:
    recent_prices = prices.tail(days + 1)
    daily_changes = recent_prices.pct_change().abs()
    return daily_changes.mean() * 100
```

Esto NO es ADR. Es el promedio del cambio close-to-close absoluto. ADR es el rango intradiario (high - low) normalizado por el close.

**Diferencia ilustrada con MCHP (datos reales):**

```
Día ejemplo MCHP
  Open:  $89.00
  High:  $92.50
  Low:   $88.00
  Close: $91.11
  Close anterior: $88.50

Cálculo actual:  |91.11 - 88.50| / 88.50 * 100 = 2.95%
Cálculo correcto: (92.50 - 88.00) / 91.11 * 100 = 4.94%
```

El cálculo actual subestima sistemáticamente la volatilidad porque ignora todo el movimiento intradiario. Un stock puede oscilar 5% durante el día y cerrar plano — el cálculo actual reporta ~0% mientras que el ADR real es 5%.

**Impacto observado:**

| Stock | adr_percent actual | ADR real estimado | Pasa filtro 4%? |
|---|---|---|---|
| MCHP | 2.26% | ~4-5% | ❌ ahora, ✅ después |
| ON | 3.18% | ~5-6% | ❌ ahora, ✅ después |
| AXTI (small-cap volátil) | 7.28% | ~9-12% | ✅ ahora, ✅ después |

## Goals / Non-Goals

**Goals:**
- `adr_percent` mide rango high-low promedio de los últimos 20 días
- Large-caps institucionales con rango diario real >= 4% pasan los filtros
- La métrica es interpretable: si dice 5%, el stock se mueve ~5% punto a punto cada día

**Non-Goals:**
- No cambiar el período (sigue siendo 20 días)
- No cambiar el rango de la métrica (0-100%, mismo significado conceptual)
- No tocar otros cálculos en momentum.py

## Decisions

### Decisión 1: Firma de la función — DataFrame con columnas `high`, `low`, `close`

La función debe acceder a high y low. Tres alternativas:

**Opción A (elegida): aceptar DataFrame con columnas `high`, `low`, `close`**
```python
def calculate_adr_percent(df: pd.DataFrame, days: int = 20) -> float:
    recent = df.tail(days)
    daily_range_pct = (recent['high'] - recent['low']) / recent['close'] * 100
    return float(daily_range_pct.mean())
```
- Pro: una sola firma para todos los callers, datos completos disponibles
- Pro: el caller en `metrics_calculator.py` ya tiene un DataFrame con todas las columnas

**Opción B descartada: aceptar tres Series separadas (high, low, close)**
- Más verboso en el caller, no aporta beneficio

**Opción C descartada: mantener firma actual y calcular ADR como abs(pct_change) ajustado**
- No hay forma de obtener el rango high-low desde solo close prices

### Decisión 2: Manejo de NaN y casos borde

La división `(high - low) / close` puede producir NaN si:
- `close == 0` (stock dejó de cotizar — no debería pasar pero defensivo)
- `high` o `low` son NaN en algún día

```python
recent = df.tail(days).dropna(subset=['high', 'low', 'close'])
if len(recent) < 5:           # mínimo 5 días válidos para que tenga significado
    return 0.0
valid = recent[recent['close'] > 0]
if len(valid) == 0:
    return 0.0
daily_range_pct = (valid['high'] - valid['low']) / valid['close'] * 100
return float(daily_range_pct.mean())
```

### Decisión 3: Threshold de `_INSTITUTIONAL_SETUP` se evalúa post-recalculación

No tocamos el threshold de 4% en este change. Después de recalcular:
- Si MCHP y ON pasan con la fórmula corregida → mantener 4%
- Si todavía fallan (improbable basado en estimación) → considerar bajar a 3%

Esto es una decisión basada en datos, no en suposiciones.

### Decisión 4: Recalcular usa el script existente

`scripts/recalculate_metrics_with_atr.py` ya existe y procesa todos los símbolos. Lo reutilizamos con la URL de localhost (`postgresql+asyncpg://postgres:postgres@localhost:5432/stock_analysis`) como hicimos para `weekly_tightness`.

## Risks / Trade-offs

**[Riesgo 1: Stocks que pasaban el filtro 4% con fórmula incorrecta podrían tener ADR real más bajo y dejar de pasar]**
→ Aceptado y deseado. Si un stock pasaba con close-to-close artificialmente alto (e.g., movimientos direccionales sin rango intradiario), no debería pasar — no es un stock que tradeable para swing.

**[Riesgo 2: La recalculación cambia 33k+ rows. Servicios downstream verán diferentes valores]**
→ Mitigación: el cambio es una corrección de bug, no un cambio de definición. Los thresholds existentes (>= 4%, >= 3%, etc.) estaban calibrados sobre datos sesgados. Algunos pueden necesitar ajuste, pero eso se evalúa post-recalc con datos reales.

**[Riesgo 3: La función se llama desde otros lugares además de metrics_calculator.py]**
→ Mitigación: verificar todos los callers con grep antes de cambiar la firma. Si hay otros callers usando close prices, actualizarlos también.

## Migration Plan

1. Aplicar fix a `calculate_adr_percent()` en momentum.py
2. Actualizar caller en `metrics_calculator.py`
3. Verificar que no haya otros callers de la función (grep)
4. Verificar con un test sintético: stock con range conocido debe producir el ADR esperado
5. Correr recalculación con script existente
6. Validar MCHP y ON post-recalc
7. Decisión sobre threshold de `_INSTITUTIONAL_SETUP` basada en valores reales

Rollback: revertir los dos archivos y re-correr el script de recalc.

## Open Questions

*(ninguna — la fórmula es estándar en la industria)*
