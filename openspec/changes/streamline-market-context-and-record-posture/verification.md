# Compact context and recorded posture — verification

## Delivered scope
- Compact posture header retains authoritative state, instruction, synthesis, same-session damage and continuity; detailed evidence and recovery gates remain in a native disclosure, with audit nested inside.
- Sector evolution presents twelve compact summary rows with dated rates, deltas and coverage. One selected sector exposes its fixed-scale graphs and complete dated observations.
- Actual current/overview emissions store the latest observed posture per session. Overview exposes additive exact-date posture_history; legacy current body remains unchanged. Historical reconstruction is not used.

## Files
Frontend: components/market-context/PostureExplanation.tsx, SectorEvolution.tsx, SessionChanges.tsx; lib/market-context.ts, market-context-changes.ts and associated explanation, changes and sector-evolution tests.
Backend: models/market_posture_record.py; repositories/market_posture_record_repository.py; services/market_posture_record_service.py; api/v1/endpoints/market_context.py; tests/test_market_posture_records.py and test_market_context_overview.py.
Migration: alembic/versions/f6a7b8c9d0e1_add_market_posture_records.py and model registration in alembic/env.py.

## Delegation and review
The primary agent specified the shared contract and reviewed integration. GPT-6-luna agents implemented frontend and backend independently; a separate GPT-6-luna read-only reviewer checked persistence, UTC, concurrency, migration and comparison validation. Review fixes covered previous-session date bounds, avoiding payload logs, out-of-order writes, UTC format compatibility, selection removal and compact table headings.

## Verification
- Primary-agent backend run: `cd backend && venv/bin/python -m pytest tests/test_market_posture_records.py tests/test_market_context_overview.py tests/test_market_posture.py tests/test_market_context_evolution.py tests/test_pipeline_health.py tests/test_market_context_benchmark_refresh.py tests/test_market_context_breadth.py tests/test_market_context_sector_evolution.py -q --disable-warnings` — 90 passed, 34 existing warnings.
- Frontend primary-agent run: `cd frontend && npm test` — 71 passed; implementation agent also passed lint, production build and typecheck in sequence. After the final dated-caption adjustment, tests (71), lint, build and typecheck passed again in the implementation agent; the primary agent verified the final caption/headings in browser.
- Primary-agent disposable SQLite migration upgrade/downgrade passed and preserved an unrelated sentinel table. PostgreSQL offline DDL generation verified timezone-aware timestamps, session primary key and bounded downgrade. No production migration applied.
- Browser QA used actual components in an isolated Next fixture with synthetic data. Verified default closed evidence, opening all recovery gates, a single sector detail via keyboard/pointer, selection retained on refresh, closing when removed and staying closed on reappearance. Observed NORMAL→FUERA as More restrictive with exact dates/timestamps.
- At desktop widths 1272 and960, collapsed posture fixture measured246.5px; twelve-row sector table was638px at default width. No graphs appear before selection.
- Baseline checksums preserved Dashboard bar/drawer, posture engine, QQQ ingestion correction and previous-session extremes/sector calculation.

## Limitations and release requirements
- Ruff unavailable; no dependency installed to work around it.
- PostgreSQL concurrency stress testing was not performed. Local SQLite covers write ordering/conflict guards. Production migration, actual posture capture and authenticated browser checks subsequently passed on2026-10-26; see deployment.md.
- Deployed2026-10-26 with additive migration f6a7b8c9d0e1 applied. Durable capture is active. Missing-table degradation remains covered by offline tests.
- History begins with actual emissions after deployment and capture; sessions never observed have no records. Each row represents the latest recorded observation, not an official closing posture. No historical backfill was run.
- Follow-up: the separate QQQ recovery was explicitly authorized and completed on2026-10-26; see ../fix-market-context-benchmark-refresh/deployment.md.
