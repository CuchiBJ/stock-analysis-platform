# QQQ scheduled refresh verification

## Scope and ownership
The primary agent authored the proposal, design, spec and acceptance criteria; GPT-6-luna investigated and implemented the backend correction. The primary agent reviewed the integrated diff and owns final verification.

Reference composition is shared by the scheduled download and Polygon EOD filter. SPY and QQQ are included regardless of stocks membership; sector ETF references remain included. No new stock candidates, dependencies, migrations, API fields or frontend changes.

## Checks
- Pre-change baseline: pipeline health, overview and sector ETF tests:33 passed (34 warnings).
- Final primary-agent regression run: `cd backend && venv/bin/python -m pytest tests/test_market_context_benchmark_refresh.py tests/test_market_context_overview.py tests/test_pipeline_health.py tests/test_sector_etf_momentum.py tests/test_market_context_breadth.py tests/test_market_context_sector_evolution.py -q --disable-warnings` — 48 passed, 34 existing warnings.
- `openspec validate fix-market-context-benchmark-refresh --strict` passed.
- `git diff --check` passed.
- Ruff unavailable (`No module named ruff`, reported by implementation agent); no dependency installed.
- Frontend checks and production browser QA not repeated because no frontend or API contract changed and this correction is not deployed.
- Baseline checksum comparison confirms Dashboard bar/drawer, market posture policy, previous-session breadth semantics, sector evolution and page integration remain unchanged.

## Operational follow-up
The initial correction was verified locally. Following explicit user authorization, it was deployed with historical recovery on2026-10-26; see deployment.md. The existing five-day download window resumes current quotes but does not fill the existing QQQ history gap. MetricsCalculator uses the last260 stored observations without checking continuity, so a new metrics date alone does not prove a repaired history.

The authorized operation recovered the complete adjusted260-bar calculation window, verified exact SPY reference coverage, recalculated latest QQQ metrics and checked the authenticated page. Source, images, frozen candidate and original QQQ rows were retained for recovery. No unrelated symbols or posture history were backfilled.

## Changed files
- `backend/app/services/benchmarks.py`: Market context reference tuple and shared composition helper.
- `backend/app/data/scheduler.py`: scheduled price selection uses shared composition.
- `backend/app/data/ingestors/polygon_eod_ingestor.py`: EOD filtering includes those references.
- `backend/tests/test_market_context_benchmark_refresh.py`: real entry-point regressions with mocked providers and synthetic persistence.
- `backend/tests/test_market_context_overview.py`: dated QQQ evidence regression.
- `openspec/changes/fix-market-context-benchmark-refresh/`: proposal, design, spec, tasks and this verification record.

## Authorized recovery implementation —2026-10-26
- User explicitly authorized production QQQ historical recovery, metrics recalculation and automatic refresh activation.
- Added scripts/recover_qqq.py and tests/test_qqq_recovery.py. GPT-6-luna implemented the tool and another GPT-6-luna agent independently reviewed it; primary agent fixed/reconciled review findings and verified integration.
- Final primary-agent offline checks: `cd backend && venv/bin/python -m pytest tests/test_qqq_recovery.py tests/test_market_context_benchmark_refresh.py tests/test_market_context_overview.py -q --disable-warnings` —36 passed,34 existing warnings.
- Recovery tests include real SQLite success with another symbol preserved, actual MetricsCalculator, a single commit, and fault injection after calculator flush proving original prices and metrics are restored on rollback.
- Frozen production prepare (no DB writes) validated260 exact SPY sessions from2025-10-14 to2026-10-26. Candidate and tool hashes saved under /opt/stock-analysis/backups/qqq-recovery-20261026T181538Z.
- Production pre-execution snapshot contains276 QQQ prices and0 metrics; copied durably outside the running container before execution.

## Production result
- Recovery completed in one transaction:260 prices upserted and1 latest QQQ metric written for2026-10-26.
- Read-only verification found0 missing QQQ dates against the latest260 SPY references.
- QQQ quote and metrics both dated2026-10-26; verified quote713.6799926757812 (UI713.68), EMA50 724.6125147075339, EMA200687.1614512458775, SMA150699.3525284830729 and SMA200676.574928894043.
- API and scheduler rebuilt/recreated successfully, and the configured automatic reference set includes QQQ. Frontend remained running.
- Authenticated browser confirmed QQQ713.68, +1.32%, price and indicators current for2026-10-26, and4/4 divergence comparisons evaluable.
- Evidence screenshot: /tmp/qqq-recovered-production-20261026.jpg.
