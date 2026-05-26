## 1. Auditar callers de calculate_adr_percent() [universe-management]

- [ ] 1.1 Ejecutar `grep -rn "calculate_adr_percent" backend/` para identificar todos los callers
- [ ] 1.2 Confirmar que el único caller real es `metrics_calculator.py:151` (el import en línea 12 es solo la referencia)
- [ ] 1.3 Si hay otros callers no esperados, documentarlos antes de cambiar la firma

## 2. Reescribir calculate_adr_percent() con la fórmula correcta [universe-management]

- [ ] 2.1 En `backend/app/data/processors/momentum.py`, reemplazar completamente el método `calculate_adr_percent()`:
  ```python
  def calculate_adr_percent(df: pd.DataFrame, days: int = 20) -> float:
      """Average Daily Range as percentage of close price.
      
      Standard formula: mean((high - low) / close * 100) over last N days.
      Stocks with insufficient valid data return 0.0.
      """
      if not isinstance(df, pd.DataFrame):
          raise TypeError("calculate_adr_percent expects DataFrame with high/low/close columns")
      required = {'high', 'low', 'close'}
      if not required.issubset(df.columns):
          raise TypeError(f"DataFrame must contain columns: {required}")
      
      recent = df.tail(days).dropna(subset=['high', 'low', 'close'])
      valid = recent[recent['close'] > 0]
      if len(valid) < 5:
          return 0.0
      
      daily_range_pct = (valid['high'] - valid['low']) / valid['close'] * 100
      return float(daily_range_pct.mean())
  ```
- [ ] 2.2 Actualizar el docstring para que sea explícito sobre la fórmula y el rango esperado

## 3. Actualizar el caller en metrics_calculator.py [universe-management]

- [ ] 3.1 En `backend/app/data/ingestors/metrics_calculator.py` línea 151, identificar el DataFrame fuente (probablemente `df` o similar) que contiene high/low/close
- [ ] 3.2 Reemplazar `calculate_adr_percent(close_prices, 20)` por `calculate_adr_percent(df, 20)` (o la variable correspondiente que contenga las columnas high/low/close)
- [ ] 3.3 Verificar visualmente que la longitud del DataFrame es >= 20 antes del cálculo (probablemente ya está cubierto por la guard `len(close_prices) >= 20`)

## 4. Test sintético de la fórmula [universe-management]

- [ ] 4.1 Crear un test inline en Python:
  - Caso A: DataFrame con high/low/close donde range = 5% del close → debe retornar ~5.0
  - Caso B: DataFrame con solo 3 días válidos → debe retornar 0.0
  - Caso C: DataFrame con close=0 en algunos días → debe excluir esos días
  - Caso D: pasar una Series en vez de DataFrame → debe lanzar TypeError
- [ ] 4.2 Confirmar que los 4 casos pasan antes de continuar

## 5. Recalcular métricas [universe-management]

- [ ] 5.1 Correr el script de recalculación (mismo patrón que `fix-weekly-tightness-calculation`):
  ```bash
  cd backend && DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/stock_analysis" venv/bin/python3 -c "
  import asyncio, sys
  sys.path.insert(0, '.')
  from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
  from sqlalchemy.orm import sessionmaker
  from sqlalchemy import select
  from app.models.stock import StockMetrics
  from app.data.ingestors.metrics_calculator import MetricsCalculator
  
  async def main():
      engine = create_async_engine('postgresql+asyncpg://postgres:postgres@localhost:5432/stock_analysis')
      async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
      async with async_session() as db:
          result = await db.execute(select(StockMetrics.symbol).distinct())
          symbols = [r[0] for r in result.all()]
          calc = MetricsCalculator(db)
          for i, s in enumerate(symbols):
              try: await calc.calculate_metrics_for_symbol(s)
              except: pass
              if (i+1) % 200 == 0:
                  await db.commit()
                  print(f'{i+1}/{len(symbols)}')
          await db.commit()
          print('Done')
  asyncio.run(main())
  "
  ```
- [ ] 5.2 Confirmar que el script termina sin errores

## 6. Validación post-recalculación [universe-management]

- [ ] 6.1 Query: `SELECT symbol, ROUND(adr_percent::numeric, 2) FROM stock_metrics WHERE symbol IN ('MCHP', 'ON', 'AXTI', 'LITE', 'TLT') ORDER BY symbol, date DESC LIMIT 10`
- [ ] 6.2 Validar que MCHP esté en rango 3-5%
- [ ] 6.3 Validar que ON esté en rango 4-6%
- [ ] 6.4 Validar que AXTI (small-cap volátil) siga en rango 7%+
- [ ] 6.5 Validar que un ETF de bonos o utility tenga ADR < 1.5%

## 7. Decisión sobre threshold de _INSTITUTIONAL_SETUP [universe-management]

- [ ] 7.1 Ejecutar `curl http://localhost:8000/api/v1/transitions/live?limit=20` y confirmar si MCHP y ON ahora pasan el filtro `adr_percent >= 4.0%` post-recalc
- [ ] 7.2 Si SÍ pasan: no tocar el threshold de 4%, el bug era la fórmula
- [ ] 7.3 Si NO pasan (improbable): considerar bajar el threshold a 3% en `_INSTITUTIONAL_SETUP` con justificación documentada
- [ ] 7.4 Documentar la decisión en el commit message
