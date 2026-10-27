# QQQ recovery and activation —2026-10-26

User explicitly authorized recovering QQQ history, recalculating its indicators and activating scheduled updates in production.

## Scope
Four scoped code files: backend/app/services/benchmarks.py, backend/app/data/scheduler.py, backend/app/data/ingestors/polygon_eod_ingestor.py and backend/scripts/recover_qqq.py. No migrations or frontend release required.

## Recovery assets
Directory: /opt/stock-analysis/backups/qqq-recovery-20261026T181538Z.
- candidate.json + SHA256: frozen adjusted yfinance data,260 sessions2025-10-14 through2026-10-26.
- qqq-before.json + SHA256: all mapped fields of276 original QQQ prices and0 QQQ metrics, copied durably before execution.
- source-before.tar.gz, tool/source hashes and images-before.txt.
- Rollback tags stock-analysis-api:rollback-qqq-20261026 and stock-analysis-scheduler:rollback-qqq-20261026.
- prepare.log, backup-summary.json, execution.log and build.log retain operational results.

## Execution and checks
- Production sources matched the pre-fix baseline.
- Candidate preparation made no DB writes and validated exact coverage and coherent finite OHLCV.
- Offline test run:36 passed,34 existing warnings, including SQLite success and injected rollback after calculator flush. Independent read-only review resolved candidate/backup integrity and exact-window findings.
- Scheduler paused during backup and atomic application; trap retained recovery of the service on failure.
- Tool verified frozen candidate SHA256, backup equal to current QQQ snapshot and unchanged SPY reference dates before committing.
- Upserted260 QQQ prices and calculated one latest metric atomically. No other symbols or historical posture records changed.
- Recreated API and scheduler with corrected reference inclusion; API healthy, scheduler running, frontend healthy.
- Operational read-only check:0 missing dates among260 reference sessions; latest price and critical moving averages valid for2026-10-26.
- Authenticated UI shows QQQ713.68 (+1.32%) with current price/indicator dates and4/4 divergence pairs evaluable. Screenshot /tmp/qqq-recovered-production-20261026.jpg.

## Boundaries
Captured price is the provider observation at recovery time during the session, not a guaranteed real-time stream or final closing value. Continued quotes depend on the existing scheduled downloader/provider cadence. No broad historical metric recalculation, global database restore, schema change or frontend deployment was performed.
