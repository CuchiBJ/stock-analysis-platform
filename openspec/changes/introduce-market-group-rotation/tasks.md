## 1. Define market group mapping module

- [ ] 1.1 Create `backend/app/services/market_group_mapping.py`
- [ ] 1.2 Define top-level constant `MARKET_GROUPS: list[str]` with the 25 canonical names: `Electronic Technology, Technology Services, Health Technology, Health Services, Finance, Banks, Insurance, Defense, Industrials, Commercial Services, Transportation, Retail, Consumer Cyclical, Auto, Consumer Staples, Consumer Products, Energy, Renewables, Mining & Metals, Chemicals, Building, Real Estate, Utilities, Media & Telecom`
- [ ] 1.3 Define `YAHOO_INDUSTRY_TO_MARKET_GROUP: dict[str, str]` with all 155 industries from the audit query. Group by target market group; comment each entry. Note explicit cross-sector mappings (`Internet Content & Information` → Technology Services; `Solar` → Renewables). Map `Shell Companies` → omit (not in dict)
- [ ] 1.4 Define `MARKET_GROUP_TO_FAMILY: dict[str, str]` mapping each of the 25 groups to one of 8 families: tech, healthcare, financial, industrial, consumer, energy, materials, yield
- [ ] 1.5 Define `FAMILY_BORDER_COLOR: dict[str, str]` with tailwind classes (e.g. `'tech': 'border-l-cyan-500'`); this is exported for the frontend type contract but actual usage is in TS — duplicate the table there or fetch from a generated constant. Decision: keep the source in Python and duplicate in TS (small dict, low drift risk)
- [ ] 1.6 Implement `def map_industry_to_market_group(industry: str | None, sector: str | None) -> str | None`. Logic: if `industry in YAHOO_INDUSTRY_TO_MARKET_GROUP`, return it; else `None`. (`sector` arg reserved for future fallback heuristics; unused in Phase 1.)
- [ ] 1.7 Add unit tests `backend/tests/test_market_group_mapping.py` covering: known mappings, unknowns return None, None input returns None, Shell Companies returns None, cross-sector (Solar → Renewables) correctness

## 2. Database migration

- [ ] 2.1 Create Alembic migration: `alembic revision -m "add_market_group_to_stocks"`
- [ ] 2.2 Migration body: `op.add_column('stocks', sa.Column('market_group', sa.String(50), nullable=True))` + `op.create_index('ix_stocks_market_group', 'stocks', ['market_group'])`
- [ ] 2.3 Downgrade: drop index + drop column
- [ ] 2.4 Update `backend/app/models/stock.py` — add `market_group: Mapped[str] = mapped_column(String(50), nullable=True)` field and `Index('ix_stocks_market_group', 'market_group')` to `__table_args__`
- [ ] 2.5 Run migration locally: `alembic upgrade head` (verify column exists, no data loss on other columns)

## 3. Populate script (one-time backfill)

- [ ] 3.1 Create `backend/scripts/populate_market_group.py`
- [ ] 3.2 Use the same `DATABASE_URL` env pattern as `recalculate_metrics_with_atr.py` (with fallback to localhost)
- [ ] 3.3 Logic: `SELECT symbol, industry, sector FROM stocks WHERE industry IS NOT NULL`. For each row, call `map_industry_to_market_group(industry, sector)`. Collect `(symbol, market_group)` pairs. Bulk update via single `UPDATE` per group: `UPDATE stocks SET market_group = :group WHERE symbol = ANY(:syms)`. Print summary: total scanned, total mapped, unmapped count and sample of unmapped industries
- [ ] 3.4 Make idempotent: re-running gives same result (no append, no duplicates)
- [ ] 3.5 Run script against local DB. Expect ~2.480 mapped, ~73 unmapped (Shell Companies), 0 errors. Capture stdout summary in PR description

## 4. Auto-populate on ingest

- [ ] 4.1 In `backend/app/data/ingestors/stock_ingestor.py`, locate the 3 places that write to `stock.industry` or `stock.sector` (lines ~54, 100, 138-142, 224-226)
- [ ] 4.2 After each write, add: `stock.market_group = map_industry_to_market_group(stock.industry, stock.sector)`. Same transaction
- [ ] 4.3 Import `from app.services.market_group_mapping import map_industry_to_market_group` at the top of the file

## 5. Refactor sector_service to group by market_group

- [ ] 5.1 In `backend/app/services/sector_service.py::calculate_sector_performance`, change the SQL: replace `SELECT s.sector` with `SELECT s.market_group`, replace `AND s.sector IS NOT NULL` with `AND s.market_group IS NOT NULL`
- [ ] 5.2 In the Python loop, change `sectors[row.sector].append(row)` → `groups[row.market_group].append(row)`
- [ ] 5.3 Change `"name": sector_name` → `"name": group_name` (variable rename for clarity); response field name stays `"name"` for compat
- [ ] 5.4 Keep `sector_performance.sort(...)` unchanged — still sorting by monthly performance
- [ ] 5.5 Add a comment at the top of the method explaining: "Groups by market_group (~25 momentum-trading groups) — see market_group_mapping.py. The endpoint path /sectors/performance is preserved for compat but the unit of grouping changed from GICS L1 to market_group in 2026-05"

## 6. Frontend — SectorHeatmap update

- [ ] 6.1 In `frontend/components/charts/SectorHeatmap.tsx`, create a constant table `MARKET_GROUP_TO_FAMILY` (mirror of the Python dict; ~25 entries) and `FAMILY_BORDER_COLOR` (8 entries: `{tech: 'border-l-cyan-500', healthcare: 'border-l-pink-500', financial: 'border-l-blue-500', industrial: 'border-l-amber-500', consumer: 'border-l-orange-500', energy: 'border-l-red-500', materials: 'border-l-stone-500', yield: 'border-l-purple-500'}`)
- [ ] 6.2 Helper `function familyBorder(name: string): string` — looks up family then border color, with a default `'border-l-white/10'` for unknowns
- [ ] 6.3 Change the grid from `grid-cols-4` to `grid-cols-5` for the data section (line ~147) and the loading state (line ~95)
- [ ] 6.4 On each tile, add the class: `border-l-2 ${familyBorder(sector.name)}` to the outer div (line ~154)
- [ ] 6.5 Fix the hardcoded `http://localhost:8000` (line ~21) → use `API_URL` from `@/lib/utils` like other components. (Drift cleanup detected during this work — flag in PR.)

## 7. Verification

- [ ] 7.1 Run backend tests: `cd backend && pytest tests/test_market_group_mapping.py -v`
- [ ] 7.2 Run frontend `npx tsc --noEmit` — expect zero errors
- [ ] 7.3 Restart backend; curl `GET /api/v1/sectors/performance` — expect array of ~25 objects, each with new market group names (verify: presence of "Electronic Technology", "Health Technology", absence of "Technology", "Healthcare")
- [ ] 7.4 Restart frontend; load `/dashboard`; visually verify:
  - Heatmap shows ~25 tiles in 5 cols × 5 rows
  - Each tile has left accent border colored by family (tech tiles share cyan, healthcare tiles share pink, etc.)
  - Tile labels show market group names (not GICS L1)
  - Tooltip on hover still works and shows the new name
- [ ] 7.5 Confirm a tile that should exist (e.g. "Electronic Technology") shows reasonable stock_count (~140-160)
- [ ] 7.6 Confirm absence of "Shell Companies" tile

## 8. Cleanup and OpenSpec close

- [ ] 8.1 Run `openspec validate introduce-market-group-rotation --strict` — expect clean
- [ ] 8.2 Sanity check: confirm `stocks.sector` column is unchanged and still queryable (for future use cases); only the heatmap consumer was migrated
